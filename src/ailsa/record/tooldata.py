"""Record helpers for the pick, identify, NUS and JCAMP tools (REC-05, REC-07, REC-17, REC-19).

Standard library at module level; the artefact models are imported inside the functions that
need them, so importing this module stays cheap.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from ailsa.record.events import artefact_id, exp_id, peak_id, pick_id
from ailsa.record.fsutil import sha256_bytes, sha256_file
from ailsa.record.log import first_event, log_session
from ailsa.record.resolve import RunRef

_SOURCE_FILES = (
    "acqus",
    "acqu2s",
    "pdata/1/procs",
    "pdata/1/proc2s",
    "pdata/1/1r",
    "pdata/1/2rr",
)
_OUTPUT_KINDS = {"nus", "jcamp", "peaks"}


def experiment_of(path: str | os.PathLike[str]) -> tuple[str, Path]:
    """Return (expno, experiment folder) for an experiment or processed-data folder."""
    here = Path(path).resolve()
    for folder in (here, *here.parents):
        if folder.parent.name == "pdata":
            return folder.parent.parent.name, folder.parent.parent
        if (folder / "acqus").is_file() or (folder / "pdata").is_dir():
            return folder.name, folder
    return here.name, here


def source_hashes(exp_dir: str | os.PathLike[str]) -> dict[str, str]:
    """sha256 of the acquisition, processing and spectrum files that exist."""
    base = Path(exp_dir)
    out: dict[str, str] = {}
    for name in _SOURCE_FILES:
        p = base / name
        if p.is_symlink() or not p.is_file():
            continue
        out[name] = sha256_file(p)
    return out


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


def referencing_of(exp_dir: str | os.PathLike[str], two_d: bool) -> dict[str, Any]:
    """Referencing parameters as the pickers see them (vendor procs files)."""
    pdata = Path(exp_dir) / "pdata" / "1"

    def one(name: str) -> dict[str, Any]:
        return {"SF": _par(pdata / name, "SF"), "OFFSET": _par(pdata / name, "OFFSET")}

    if two_d:
        return {"f2": one("procs"), "f1": one("proc2s")}
    return one("procs")


def _write_new(target: Path, data: bytes) -> None:
    from ailsa.record.artefacts import _write_new as write

    write(target, data, False)


def _run_target(run_dir: str | os.PathLike[str], rel: str) -> Path:
    from ailsa.record.artefacts import run_target

    return run_target(run_dir, rel)


def _dump(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode("utf-8")


def record_pick(
    run: RunRef,
    *,
    path: str | os.PathLike[str],
    picker: str,
    parameters: dict[str, Any],
    referencing: dict[str, Any] | None,
    noise_sigma: float | None,
    peaks: list[dict[str, Any]],
    two_d: bool,
    command: str = "pick",
) -> str:
    """Write a peak-pick artefact and its peaks.picked event; return the pick id."""
    from ailsa.record.models import PeakPick

    expno, exp_dir = experiment_of(path)
    hashes = source_hashes(exp_dir)
    ref = referencing if referencing is not None else referencing_of(exp_dir, two_d)
    with log_session(run.run_dir) as lg:
        n = lg.next_counter("pick:" + expno)
        pid = pick_id(expno, n)
        entries: list[Any] = []
        for i, p in enumerate(peaks, start=1):
            entry: dict[str, Any] = {"id": peak_id(expno, n, i)}
            for key in ("ppm", "ppm_f2", "ppm_f1", "intensity", "snr"):
                if p.get(key) is not None:
                    entry[key] = p[key]
            entries.append(entry)
        model = PeakPick(
            pick_id=pid,
            experiment=exp_id(expno),
            source_sha256=hashes,
            picker=picker,
            parameters=parameters,
            referencing=ref,
            noise_sigma=noise_sigma,
            peaks=entries,
            rejected=[],
            rejected_available=False,
        )
        blob = _dump(model.model_dump(mode="json", by_alias=True))
        rel = f"peaks/{expno}.{n}.json"
        target = _run_target(run.run_dir, rel)
        if os.path.lexists(target):
            raise FileExistsError(f"artefact path already exists: {rel}")
        art = {
            "id": artefact_id("peak-pick", lg.next_counter("art:peak-pick")),
            "kind": "peak-pick",
            "path": rel,
            "sha256": sha256_bytes(blob),
            "bytes": len(blob),
            "supersedes": None,
        }
        _write_new(target, blob)
        lg.append(
            "peaks.picked",
            {
                "pick_id": pid,
                "experiment": exp_id(expno),
                "picker": picker,
                "parameters": parameters,
                "count": len(entries),
                "noise_sigma": noise_sigma,
            },
            actor={"kind": "tool", "name": f"ailsa {command}"},
            refs=[exp_id(expno), pid],
            artefacts=[art],
        )
    return pid


def _is_blind(run_dir: Path) -> bool:
    first = first_event(run_dir) or {}
    payload = first.get("payload") or {}
    dataset = payload.get("dataset") or {}
    return bool(dataset.get("blind")) if isinstance(dataset, dict) else False


def record_identity(
    run: RunRef,
    result: dict[str, Any],
    *,
    smiles: str,
    reported_name: str | None,
) -> str:
    """Save an identity verdict as an artefact with an identity.derived event."""
    from ailsa.record.models import IdentityVerdict

    derived = result.get("derived")
    derived = derived if isinstance(derived, dict) else {}
    blind = _is_blind(run.run_dir)
    inchikey = derived.get("inchi_key")
    verdict = str(result.get("verdict"))
    with log_session(run.run_dir) as lg:
        n = lg.next_counter("identity")
        model = IdentityVerdict(
            smiles=smiles,
            canonical_smiles=derived.get("canonical_smiles"),
            inchikey=inchikey,
            verdict=verdict,
            derived_name=derived.get("name"),
            reported_name=reported_name,
            name_match=None if result.get("name_match") is None else str(result["name_match"]),
            hidden_in_blind=blind,
        )
        blob = _dump(model.model_dump(mode="json", by_alias=True))
        rel = f"identity/{n}.json"
        target = _run_target(run.run_dir, rel)
        if os.path.lexists(target):
            raise FileExistsError(f"artefact path already exists: {rel}")
        art = {
            "id": artefact_id("identity", lg.next_counter("art:identity")),
            "kind": "identity",
            "path": rel,
            "sha256": sha256_bytes(blob),
            "bytes": len(blob),
            "supersedes": None,
        }
        _write_new(target, blob)
        lg.append(
            "identity.derived",
            {
                "smiles": smiles,
                "inchikey": inchikey,
                "verdict": verdict,
                "hidden_in_blind": blind,
            },
            actor={"kind": "tool", "name": "ailsa identify"},
            artefacts=[art],
        )
    return rel


def run_output_dir(
    run: RunRef, kind: str, name: str, *sub: str, children: tuple[str, ...] = ()
) -> Path:
    """Create and return ``<run>/<kind>/<name>[/<sub>...]`` (mode 0700) for tool output in a run.

    Every component, and each of ``children`` below it (checked, not created), must not be a
    symlink: tool output never goes through a link into the dataset or elsewhere (REC-05).
    Raises ValueError otherwise.
    """
    if kind not in _OUTPUT_KINDS:
        raise ValueError(f"unknown run output kind: {kind}")
    for part in (name, *sub, *children):
        if not part or part in {".", ".."} or "/" in part or "\\" in part or "\x00" in part:
            raise ValueError(f"invalid run output name: {part!r}")
    rel = "/".join((kind, name, *sub))
    for child in children:
        _run_target(run.run_dir, f"{rel}/{child}")
    target = _run_target(run.run_dir, rel)
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    return target
