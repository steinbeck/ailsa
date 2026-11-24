"""Spectra view products for the run record (REC-29).

A viewer draws spectra from these files instead of re-reading vendor data. The products use
the same reader path, referencing and noise sigma as the peak pickers:

- processed experiments go through ``BrukerReader``; raw-only ones through ``case.rawproc``;
- 1D: ``data.f32`` (little-endian float32, full resolution);
- 2D: ``level0.i16`` (full resolution) and coarser levels, noise-normalised and log-quantised to
  int16, pooled by signed max-abs so that a one-pixel cross-peak survives every level;
  plus ``proj_f1.f32`` / ``proj_f2.f32`` (max-abs skyline projections in noise units).

Nothing is written into the dataset: all output goes under ``out_root``. Experiments that cannot
be shown come back with a reason; an export failure is reported, never raised.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import numpy as np

from ailsa._version import __version__
from ailsa.record.events import view_id as _view_id
from ailsa.record.fsutil import atomic_write_json, sha256_file

INT16_SCALE = 32767
LEVEL_CAP = 1024
MIN_DIM = 256
CONTOUR_LEVELS_SIGMA = [3.0, 5.0, 8.0, 13.0, 21.0]
_VALID_2D = {"HSQC", "HMBC", "COSY", "TOCSY", "NOESY", "ROESY"}
_MSG_CAP = 300


# ----------------------------------------------------------------------------- numerics


def quantise(
    data: np.ndarray[Any, Any], sigma: float, zmax: float | None = None
) -> tuple[np.ndarray[Any, Any], float]:
    """Noise-normalise and log-quantise to int16; returns ``(q, zmax)``.

    ``q = round(sign(z) * 32767 * log1p(|z|) / log1p(zmax))`` with ``z = data / sigma``. Pass the
    ``zmax`` of the full-resolution array to quantise a pooled level on the same scale.
    """
    z = np.asarray(data, dtype=np.float64) / float(sigma)
    peak = float(np.max(np.abs(z))) if z.size else 0.0
    top = peak if zmax is None else float(zmax)
    return _quantise_z(z, top), top


def _quantise_z(z: np.ndarray[Any, Any], zmax: float) -> np.ndarray[Any, Any]:
    denom = np.log1p(zmax) if zmax > 0 else 0.0
    if denom <= 0:
        return np.zeros(z.shape, dtype=np.int16)
    q = np.sign(z) * INT16_SCALE * np.log1p(np.abs(z)) / denom
    out: np.ndarray[Any, Any] = np.clip(np.rint(q), -INT16_SCALE, INT16_SCALE).astype(np.int16)
    return out


def dequantise(q: np.ndarray[Any, Any], zmax: float) -> np.ndarray[Any, Any]:
    """Inverse of :func:`quantise`; returns values in noise units (z)."""
    qf = np.asarray(q, dtype=np.float64)
    if zmax <= 0:
        return np.zeros(qf.shape, dtype=np.float64)
    back: np.ndarray[Any, Any] = np.sign(qf) * np.expm1(np.abs(qf) * np.log1p(zmax) / INT16_SCALE)
    return back


def pool_max_abs(a: np.ndarray[Any, Any], f: int) -> np.ndarray[Any, Any]:
    """Downsample by ``f`` per axis keeping the element of largest magnitude, with its sign."""
    if f < 1:
        raise ValueError("pooling factor must be at least 1")
    a = np.asarray(a)
    if f == 1:
        return np.asarray(a.copy())
    h, w = a.shape
    ph, pw = (-h) % f, (-w) % f
    if ph or pw:
        a = np.pad(a, ((0, ph), (0, pw)))
    hh, ww = a.shape[0] // f, a.shape[1] // f
    blocks = a.reshape(hh, f, ww, f).transpose(0, 2, 1, 3).reshape(hh, ww, f * f)
    idx = np.argmax(np.abs(blocks), axis=2)
    return np.take_along_axis(blocks, idx[..., None], axis=2)[..., 0]


def projections(z: np.ndarray[Any, Any]) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    """Max-abs skyline projections ``(f1, f2)`` of a 2D array in z space (sign kept)."""
    rows = np.take_along_axis(z, np.argmax(np.abs(z), axis=1)[:, None], axis=1)[:, 0]
    cols = np.take_along_axis(z, np.argmax(np.abs(z), axis=0)[None, :], axis=0)[0, :]
    return rows, cols


def level_factors(shape: tuple[int, int]) -> list[int]:
    """Pooling factors of the derived levels (level0 is the full-resolution array)."""
    big = max(shape)
    factors: list[int] = []
    if big > LEVEL_CAP:
        factor = -(-big // LEVEL_CAP)
    else:
        factor = 2
    while True:
        if max(shape) <= MIN_DIM:
            break
        factors.append(factor)
        pooled = (-(-shape[0] // factor), -(-shape[1] // factor))
        if max(pooled) <= MIN_DIM:
            break
        factor *= 2
    return factors


# ----------------------------------------------------------------------------- helpers


def _par(path: Path, key: str) -> float | None:
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return None
    match = re.search(rf"^##\${key}=\s*(\S+)", text, re.MULTILINE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _hash_sources(exp_dir: Path, names: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in names:
        path = exp_dir / name
        if path.is_symlink() or not path.is_file():
            continue
        out[name] = sha256_file(path)
    return out


def _referencing_vendor(exp_dir: Path, two_d: bool) -> dict[str, Any]:
    pdata = exp_dir / "pdata" / "1"
    ref: dict[str, Any] = {"source": "vendor procs"}
    f2 = {"SF": _par(pdata / "procs", "SF"), "OFFSET": _par(pdata / "procs", "OFFSET")}
    if two_d:
        ref["f2"] = f2
        ref["f1"] = {"SF": _par(pdata / "proc2s", "SF"), "OFFSET": _par(pdata / "proc2s", "OFFSET")}
    else:
        ref.update(f2)
    return ref


def _referencing_raw(exp_dir: Path, two_d: bool) -> dict[str, Any]:
    ref: dict[str, Any] = {"source": "rawproc acqus"}
    f2 = {"SFO1": _par(exp_dir / "acqus", "SFO1"), "O1": _par(exp_dir / "acqus", "O1")}
    if two_d:
        ref["f2"] = f2
        ref["f1"] = {"SFO1": _par(exp_dir / "acqu2s", "SFO1"), "O1": _par(exp_dir / "acqu2s", "O1")}
    else:
        ref.update(f2)
    return ref


def _write(path: Path, arr: np.ndarray[Any, Any], dtype: str) -> None:
    np.ascontiguousarray(arr).astype(dtype).tofile(path)


def _result(
    status: str,
    exp: str,
    *,
    state: str | None = None,
    view: str | None = None,
    files: list[str] | None = None,
    reason: str | None = None,
    started: float,
) -> dict[str, Any]:
    return {
        "status": status,
        "experiment": exp,
        "state": state,
        "view_id": view,
        "files": files or [],
        "reason": reason,
        "seconds": round(time.perf_counter() - started, 3),
    }


# ----------------------------------------------------------------------------- export


def export_experiment(
    exp_dir: Path,
    out_dir: Path,
    *,
    exp_id: str,
    state_hint: str | None = None,
    qc_verdict: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write the view product of one experiment under ``out_dir/<exp_id>/<state>/``.

    ``exp_id`` is the experiment label (expno or alias, as in the inventory). Never raises:
    the returned dict has ``status`` ``ok``, ``skipped`` or ``failed``.
    """
    started = time.perf_counter()
    try:
        return _export(
            Path(exp_dir), Path(out_dir), exp_id, state_hint, qc_verdict, overwrite, started
        )
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"[:_MSG_CAP]
        return _result("failed", exp_id, reason=msg, started=started)


def _export(
    exp_dir: Path,
    out_dir: Path,
    exp: str,
    state_hint: str | None,
    qc_verdict: str | None,
    overwrite: bool,
    started: float,
) -> dict[str, Any]:
    from ailsa.case.scan import read_experiment

    info = read_experiment(exp_dir)
    if info is None:
        return _result("skipped", exp, reason="parameters unreadable", started=started)
    kind = info.kind
    two_d = (exp_dir / "acqu2s").is_file()
    if kind == "2D-other" or kind.startswith("1D-"):
        return _result(
            "skipped", exp, reason=f"unsupported experiment type: {kind}", started=started
        )
    if two_d and kind not in _VALID_2D:
        return _result("skipped", exp, reason=f"unsupported 2D type: {kind}", started=started)
    nus = info.nus_fraction is not None or bool(info.nus_schedule)
    if info.processed:
        state = state_hint or "vendor"
    elif info.raw and nus:
        return _result("skipped", exp, reason="NUS data not reconstructed", started=started)
    elif info.raw:
        state = "rawproc"
    else:
        return _result("skipped", exp, reason="no processed or raw data", started=started)
    vid = _view_id(exp, state)
    target = out_dir / exp / state
    if (target / "view.json").exists() and not overwrite:
        return _result(
            "skipped", exp, state=state, view=vid, reason="already exported", started=started
        )

    from ailsa.processing.peak_picker import _compute_snr_threshold
    from ailsa.processing.peak_picker_2d import _compute_2d_noise_sigma
    from ailsa.readers import BrukerReader

    vendor = state != "rawproc"
    if vendor:
        reader_name = "ailsa.readers.bruker"
        spec: Any = BrukerReader.read_2d(exp_dir) if two_d else BrukerReader.read_1d(exp_dir)
        sources = _hash_sources(
            exp_dir,
            ("pdata/1/2rr", "pdata/1/proc2s", "pdata/1/procs")
            if two_d
            else ("pdata/1/1r", "pdata/1/procs"),
        )
        referencing = _referencing_vendor(exp_dir, two_d)
    else:
        from ailsa.case import rawproc

        reader_name = "ailsa.case.rawproc"
        if two_d:
            spec = rawproc.process_2d(exp_dir, kind)
        else:
            spec = rawproc.process_1d(exp_dir, signed=kind not in ("13C", "1H"))
        sources = _hash_sources(exp_dir, ("ser", "acqus", "acqu2s") if two_d else ("fid", "acqus"))
        referencing = _referencing_raw(exp_dir, two_d)

    target.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    common: dict[str, Any] = {
        "view_id": vid,
        "experiment": exp,
        "state": state,
        "qc_verdict": qc_verdict,
        "source_sha256": sources,
        "reader": reader_name,
        "reader_version": __version__,
        "referencing": referencing,
        "contour_levels_sigma": CONTOUR_LEVELS_SIGMA,
    }
    if two_d:
        view = _export_2d(
            spec, exp_dir, target, files, info.edited and vendor, _compute_2d_noise_sigma
        )
    else:
        view = _export_1d(spec, target, files, _compute_snr_threshold)
    if not vendor:
        view["sign_meaning"] = "magnitude spectrum: no sign information"
    view.update(common)

    from ailsa.record.models import SpectrumView

    model = SpectrumView.model_validate(view)
    atomic_write_json(target / "view.json", model.model_dump(by_alias=True, mode="json"))
    files.append("view.json")
    rel = [f"{exp}/{state}/{name}" for name in files]
    return _result("ok", exp, state=state, view=vid, files=rel, started=started)


def _export_1d(spec: Any, target: Path, files: list[str], snr: Any) -> dict[str, Any]:
    data = np.asarray(spec.data, dtype=np.float64)
    ppm = np.asarray(spec.ppm_scale, dtype=np.float64)
    _write(target / "data.f32", data, "<f4")
    files.append("data.f32")
    _, sigma = snr(data, ppm, getattr(spec, "solvent", None))
    return {
        "kind": "1d",
        "nuclei": [spec.nucleus],
        "sf_mhz": [float(spec.frequency)],
        "ppm_start": [float(ppm[0])],
        "ppm_end": [float(ppm[-1])],
        "points": [int(data.size)],
        "noise_sigma": float(sigma),
        "quantisation": None,
        "levels": [{"file": "data.f32", "shape": [int(data.size)], "factor": 1.0}],
        "projections": [],
    }


def _export_2d(
    spec: Any,
    exp_dir: Path,
    target: Path,
    files: list[str],
    edited: bool,
    sigma_fn: Any,
) -> dict[str, Any]:
    data = np.asarray(spec.data, dtype=np.float64)
    sigma = float(sigma_fn(data))
    z = data / sigma
    zmax = float(np.max(np.abs(z))) if z.size else 0.0
    levels: list[dict[str, Any]] = []

    def put(name: str, arr: np.ndarray[Any, Any], factor: float) -> None:
        _write(target / name, _quantise_z(arr, zmax), "<i2")
        files.append(name)
        levels.append(
            {"file": name, "shape": [int(arr.shape[0]), int(arr.shape[1])], "factor": factor}
        )

    put("level0.i16", z, 1.0)
    for n, factor in enumerate(level_factors((z.shape[0], z.shape[1])), start=1):
        put(f"level{n}.i16", pool_max_abs(z, factor), float(factor))
    p1, p2 = projections(z)
    _write(target / "proj_f1.f32", p1, "<f4")
    _write(target / "proj_f2.f32", p2, "<f4")
    files.extend(["proj_f1.f32", "proj_f2.f32"])
    f1 = np.asarray(spec.f1_ppm_scale, dtype=np.float64)
    f2 = np.asarray(spec.f2_ppm_scale, dtype=np.float64)
    meta = getattr(spec, "metadata", {}) or {}
    f1_freq = meta.get("f1_frequency") or _par(exp_dir / "acqu2s", "SFO1") or 0.0
    return {
        "kind": "2d",
        "nuclei": [spec.f1_nucleus, spec.f2_nucleus],
        "sf_mhz": [float(f1_freq), float(spec.frequency)],
        "ppm_start": [float(f1[0]), float(f2[0])],
        "ppm_end": [float(f1[-1]), float(f2[-1])],
        "points": [int(z.shape[0]), int(z.shape[1])],
        "noise_sigma": sigma,
        "quantisation": {"method": "log1p-noise", "zmax": zmax, "scale": float(INT16_SCALE)},
        "levels": levels,
        "projections": [
            {"axis": "f1", "file": "proj_f1.f32"},
            {"axis": "f2", "file": "proj_f2.f32"},
        ],
        "sign_meaning": ("signed: sign encodes multiplicity (edited HSQC)" if edited else None),
    }


def _folder_ids(dataset: Path, inventory: dict[str, Any]) -> dict[str, Path]:
    """Map inventory labels to experiment folders (same order as ``build_inventory``)."""
    from ailsa.case.scan import _expno_key

    folders = sorted(
        (p for p in dataset.iterdir() if p.is_dir() and not p.is_symlink()),
        key=lambda p: _expno_key(p.name),
    )
    entries = inventory.get("experiments", [])
    mapping: dict[str, Path] = {}
    for folder, entry in zip(folders, entries, strict=False):
        mapping[str(entry["id"]).split(":", 1)[-1]] = folder
    return mapping


def export_dataset(
    dataset: Path,
    inventory: dict[str, Any],
    out_root: Path,
    *,
    only: set[str] | None = None,
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    """Export every experiment of the inventory sequentially; unreadable ones appear as skipped."""
    dataset = Path(dataset).resolve()
    mapping = _folder_ids(dataset, inventory)
    results: list[dict[str, Any]] = []
    for entry in inventory.get("experiments", []):
        label = str(entry["id"]).split(":", 1)[-1]
        if only is not None and label not in only and entry.get("folder_alias") not in only:
            continue
        t0 = time.perf_counter()
        if not entry.get("readable", True):
            results.append(
                _result("skipped", label, reason=entry.get("reason") or "unreadable", started=t0)
            )
            continue
        folder = mapping.get(label)
        if folder is None:
            results.append(
                _result("failed", label, reason="experiment folder not found", started=t0)
            )
            continue
        verdict = (entry.get("nus") or {}).get("qc_verdict")
        results.append(
            export_experiment(
                folder, out_root, exp_id=label, qc_verdict=verdict, overwrite=overwrite
            )
        )
    return results


def register_result(
    run_dir: Path, result: dict[str, Any], *, state_guess: str = "vendor"
) -> list[dict[str, Any]]:
    """Record one export result in the run: one ``spectrum.processed`` event per experiment.

    Files of an ``ok`` result (relative to ``run_dir/spectra``) are registered as artefacts,
    ``view.json`` as ``spectrum-view`` and the data files as ``spectrum-data``. Skipped and
    failed results get the event without artefacts.
    """
    from ailsa.record.artefacts import safe_relpath
    from ailsa.record.log import append_event, log_session

    label = result["experiment"]
    state = result.get("state") or state_guess
    vid = result.get("view_id") or _view_id(label, state)
    payload: dict[str, Any] = {
        "experiment": label,
        "view_id": vid,
        "state": state,
        "status": result["status"],
        "seconds": result["seconds"],
    }
    if result.get("reason"):
        payload["reason"] = result["reason"]
    actor = {"kind": "tool", "name": "ailsa spectra export"}
    refs = [f"exp:{label}", vid]
    run = Path(run_dir)
    if result["status"] != "ok":
        append_event(run, "spectrum.processed", payload, actor=actor, refs=refs)
        return []
    staged: list[tuple[str, str, Path]] = []
    for name in result["files"]:
        rel = safe_relpath(run, f"spectra/{name}")
        kind = "spectrum-view" if name.endswith("view.json") else "spectrum-data"
        staged.append((kind, rel, run / rel))
    hashed = [(k, r, sha256_file(path), path.stat().st_size) for k, r, path in staged]
    entries: list[dict[str, Any]] = []
    with log_session(run) as lg:
        for kind, rel, digest, size in hashed:
            n = lg.next_counter("art:" + kind)
            entries.append(
                {
                    "id": f"art:{kind}:{n}",
                    "kind": kind,
                    "path": rel,
                    "sha256": digest,
                    "bytes": size,
                    "supersedes": None,
                }
            )
        lg.append("spectrum.processed", payload, actor=actor, refs=refs, artefacts=entries)
    return entries


__all__ = [
    "dequantise",
    "export_dataset",
    "export_experiment",
    "level_factors",
    "pool_max_abs",
    "projections",
    "quantise",
    "register_result",
]
