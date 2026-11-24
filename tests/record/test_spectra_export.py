"""Spectra view products (REC-29): quantisation, pooling, per-experiment export, command."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from ailsa.record.models import SpectrumView
from ailsa.spectra.export import (
    dequantise,
    export_dataset,
    export_experiment,
    level_factors,
    pool_max_abs,
    quantise,
)

# ----------------------------------------------------------------------------- numerics


def test_quantise_roundtrip_within_one_percent() -> None:
    rng = np.random.default_rng(1)
    z = rng.uniform(1.0, 5000.0, 4000) * rng.choice([-1.0, 1.0], 4000)
    q, zmax = quantise(z, 1.0)
    assert q.dtype == np.int16
    back = dequantise(q, zmax)
    assert np.all(np.abs(back - z) / np.abs(z) < 0.01)


def test_quantise_zero_array() -> None:
    q, zmax = quantise(np.zeros((4, 4)), 1.0)
    assert zmax == 0.0 and not q.any()


@pytest.mark.parametrize("factor", [2, 4, 8])
def test_pool_keeps_single_negative_pixel(factor: int) -> None:
    a = np.zeros((1024, 1024))
    a[513, 7] = -50.0
    pooled = pool_max_abs(a, factor)
    assert pooled.shape == (1024 // factor, 1024 // factor)
    assert pooled[513 // factor, 7 // factor] == -50.0
    assert np.count_nonzero(pooled) == 1


def test_pool_pads_odd_shapes() -> None:
    a = np.zeros((10, 7))
    a[9, 6] = 3.0
    pooled = pool_max_abs(a, 4)
    assert pooled.shape == (3, 2)
    assert pooled[2, 1] == 3.0


def test_level_factors() -> None:
    assert level_factors((512, 1024)) == [2, 4]
    assert level_factors((200, 200)) == []
    assert level_factors((4096, 2048)) == [4, 8, 16]


# ----------------------------------------------------------------------------- synthetic data


def _procs(path: Path, si: int, sf: float, offset: float, sw: float) -> None:
    path.write_text(
        f"##$SI= {si}\n##$XDIM= {si}\n##$SF= {sf}\n##$OFFSET= {offset}\n##$SW_p= {sw}\n"
        "##$FTSIZE= {0}\n##$BYTORDP= 0\n##$DTYPP= 0\n##$NC_proc= 0\n##$AXNUC= <1H>\n".format(si)
    )


def _acq(
    path: Path, pulprog: str, nuc: str, sfo1: float, sw: float, td: int, extra: str = ""
) -> None:
    path.write_text(
        f"##$PULPROG= <{pulprog}>\n##$NUC1= <{nuc}>\n##$NS= 8\n##$SFO1= {sfo1}\n"
        f"##$BF1= {sfo1}\n##$O1= {sfo1 * 5}\n##$SW_h= {sw}\n##$SW= {sw / sfo1}\n"
        f"##$TD= {td}\n##$SOLVENT= <CDCl3>\n##$TE= 298\n##$AQ_mod= 3\n##$FnMODE= 0\n"
        f"##$DECIM= 20\n##$DSPFVS= 20\n##$GRPDLY= 67.98\n{extra}"
    )


def make_1d(root: Path, expno: str = "1", processed: bool = True) -> Path:
    exp = root / expno
    pd = exp / "pdata" / "1"
    pd.mkdir(parents=True)
    _acq(exp / "acqus", "zgpg30", "13C", 100.6, 20000.0, 4096)
    if processed:
        _procs(pd / "procs", 4096, 100.6, 220.0, 20000.0)
        rng = np.random.default_rng(2)
        data = rng.normal(0, 10, 4096)
        data[1000] = 5000.0
        data.astype("<i4").tofile(pd / "1r")
        np.zeros(4096, dtype="<i4").tofile(exp / "fid")  # acqus is read through the raw file
    else:
        np.zeros(4096, dtype="<i4").tofile(exp / "fid")
    return exp


def make_2d(
    root: Path, expno: str = "2", pulprog: str = "hsqcetgpsisp2.2", processed: bool = True
) -> Path:
    exp = root / expno
    pd = exp / "pdata" / "1"
    pd.mkdir(parents=True)
    _acq(exp / "acqus", pulprog, "1H", 400.1, 4800.0, 1024)
    _acq(exp / "acqu2s", pulprog, "13C", 100.6, 20000.0, 512)
    if processed:
        _procs(pd / "procs", 1024, 400.1, 10.0, 4800.0)
        _procs(pd / "proc2s", 512, 100.6, 200.0, 20000.0)
        rng = np.random.default_rng(3)
        data = rng.normal(0, 10, (512, 1024))
        data[301, 77] = -4000.0
        data.astype("<i4").tofile(pd / "2rr")
        np.zeros(512 * 1024, dtype="<i4").tofile(exp / "ser")
    else:
        np.zeros((16, 64), dtype="<i4").tofile(exp / "ser")
    return exp


# ----------------------------------------------------------------------------- per experiment


def test_export_2d_files_and_view(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    exp = make_2d(ds)
    out = tmp_path / "out"
    res = export_experiment(exp, out, exp_id="2")
    assert res["status"] == "ok", res
    assert res["state"] == "vendor" and res["view_id"] == "view:2:vendor"
    d = out / "2" / "vendor"
    view = json.loads((d / "view.json").read_text())
    model = SpectrumView.model_validate(view)
    assert model.kind == "2d" and model.points == [512, 1024]
    assert [lv.file for lv in model.levels] == ["level0.i16", "level1.i16", "level2.i16"]
    for lv in model.levels:
        assert (d / lv.file).stat().st_size == 2 * lv.shape[0] * lv.shape[1]
    assert (d / "proj_f1.f32").stat().st_size == 4 * 512
    assert (d / "proj_f2.f32").stat().st_size == 4 * 1024
    assert model.levels[-1].shape == [128, 256]
    assert model.contour_levels_sigma == [3, 5, 8, 13, 21]
    assert model.reader == "ailsa.readers.bruker" and model.reader_version
    assert "pdata/1/2rr" in model.source_sha256
    assert model.referencing["f2"]["SF"] == 400.1
    assert model.noise_sigma and model.noise_sigma > 0
    assert "title" not in json.dumps(view).lower()


def test_cross_peak_survives_levels_and_dequantises(tmp_path: Path) -> None:
    exp = make_2d(tmp_path / "ds")
    out = tmp_path / "out"
    export_experiment(exp, out, exp_id="2")
    d = out / "2" / "vendor"
    view = SpectrumView.model_validate(json.loads((d / "view.json").read_text()))
    zmax = view.quantisation.zmax  # type: ignore[union-attr]
    sigma = view.noise_sigma
    assert sigma
    for lv in view.levels:
        q = np.fromfile(d / lv.file, dtype="<i2").reshape(lv.shape)
        assert q.min() < -30000
        i = np.unravel_index(np.argmin(q), q.shape)
        z = dequantise(q[i], zmax)
        assert abs(float(z) * sigma - (-4000.0)) / 4000.0 < 0.02
        factor = int(lv.factor or 1)
        assert i == (301 // factor, 77 // factor)


def test_export_1d(tmp_path: Path) -> None:
    exp = make_1d(tmp_path / "ds")
    out = tmp_path / "out"
    res = export_experiment(exp, out, exp_id="1")
    assert res["status"] == "ok", res
    d = out / "1" / "vendor"
    raw = np.fromfile(d / "data.f32", dtype="<f4")
    assert raw.size == 4096 and raw.max() == 5000.0
    view = json.loads((d / "view.json").read_text())
    assert view["quantisation"] is None and view["kind"] == "1d"
    SpectrumView.model_validate(view)


def test_raw_only_uses_rawproc(tmp_path: Path) -> None:
    exp = make_1d(tmp_path / "ds", processed=False)
    res = export_experiment(exp, tmp_path / "out", exp_id="1")
    assert res["status"] == "ok", res
    assert res["state"] == "rawproc"
    view = json.loads((tmp_path / "out" / "1" / "rawproc" / "view.json").read_text())
    assert view["reader"] == "ailsa.case.rawproc"


def test_nus_without_reconstruction_skipped(tmp_path: Path) -> None:
    exp = make_2d(tmp_path / "ds", processed=False)
    (exp / "acqus").write_text((exp / "acqus").read_text() + "##$NusAMOUNT= 25\n")
    res = export_experiment(exp, tmp_path / "out", exp_id="2")
    assert res == {**res, "status": "skipped", "reason": "NUS data not reconstructed"}


def test_unsupported_2d_type_skipped(tmp_path: Path) -> None:
    exp = make_2d(tmp_path / "ds", pulprog="h2bcetgpl3")
    res = export_experiment(exp, tmp_path / "out", exp_id="2")
    assert res["status"] == "skipped" and res["reason"]
    assert not (tmp_path / "out").exists()


def test_reader_exception_is_reported_not_raised(tmp_path: Path) -> None:
    exp = make_2d(tmp_path / "ds")
    (exp / "pdata" / "1" / "2rr").write_bytes(b"\x00\x01")
    res = export_experiment(exp, tmp_path / "out", exp_id="2")
    assert res["status"] == "failed"
    assert ":" in res["reason"]


def test_second_export_is_skipped_unless_overwrite(tmp_path: Path) -> None:
    exp = make_1d(tmp_path / "ds")
    out = tmp_path / "out"
    assert export_experiment(exp, out, exp_id="1")["status"] == "ok"
    assert export_experiment(exp, out, exp_id="1")["reason"] == "already exported"
    assert export_experiment(exp, out, exp_id="1", overwrite=True)["status"] == "ok"


def test_export_dataset_lists_unreadable(tmp_path: Path) -> None:
    from ailsa.record.inventory import build_inventory

    ds = tmp_path / "ds"
    make_1d(ds, "1")
    make_2d(ds, "2")
    (ds / "3").mkdir()
    inv = build_inventory(ds, blind=False, fingerprint="sha256:x")
    results = export_dataset(ds, inv, tmp_path / "out")
    assert [r["experiment"] for r in results] == ["1", "2", "3"]
    assert [r["status"] for r in results] == ["ok", "ok", "skipped"]
    assert results[2]["reason"]
    only = export_dataset(ds, inv, tmp_path / "out2", only={"2"})
    assert [r["experiment"] for r in only] == ["2"]


# ----------------------------------------------------------------------------- command


def _dataset(tmp_path: Path) -> Path:
    ds = tmp_path / "ds"
    make_1d(ds, "1")
    make_2d(ds, "2")
    (ds / "3").mkdir()
    return ds


def _events(run: Path) -> list[dict]:
    from ailsa.record.log import read_events

    return read_events(run)["events"]


def test_command_in_run_registers_views(
    tmp_path: Path, new_run: tuple[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    from ailsa.cli.spectra import spectra
    from ailsa.record.fingerprint import dataset_fingerprint

    run = new_run[1]
    monkeypatch.setenv("AILSA_RUN_DIR", str(run))
    ds = _dataset(tmp_path)
    before = dataset_fingerprint(ds)
    res = CliRunner().invoke(spectra, ["export", str(ds), "--format", "json"])
    assert res.exit_code == 0, res.output
    out = json.loads(res.output)
    assert [v["experiment"] for v in out["views"]] == ["1", "2"]
    assert [s["experiment"] for s in out["skipped"]] == ["3"]
    assert out["failed"] == [] and out["seconds"] >= 0
    assert (run / "spectra" / "2" / "vendor" / "view.json").is_file()
    assert dataset_fingerprint(ds) == before
    events = [e for e in _events(run) if e["type"] == "spectrum.processed"]
    assert [e["payload"]["status"] for e in events] == ["ok", "ok", "skipped"]
    assert events[2]["payload"]["reason"]
    kinds = [a["kind"] for a in events[1]["artefacts"]]
    assert kinds.count("spectrum-view") == 1 and kinds.count("spectrum-data") == 5
    assert any(e["type"] == "spectra.scanned" for e in _events(run))
    assert not (ds / "spectra").exists()


def test_command_experiment_filter_and_text(
    tmp_path: Path, new_run: tuple[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    from ailsa.cli.spectra import spectra

    monkeypatch.setenv("AILSA_RUN_DIR", str(new_run[1]))
    ds = _dataset(tmp_path)
    res = CliRunner().invoke(spectra, ["export", str(ds), "--experiment", "1"])
    assert res.exit_code == 0, res.output
    assert res.output.split()[:3] == ["1", "vendor", "ok"]
    assert len(res.output.strip().splitlines()) == 1


def test_command_run_option(
    tmp_path: Path, new_run: tuple[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    from ailsa.cli.spectra import spectra

    ds = _dataset(tmp_path)
    res = CliRunner().invoke(
        spectra, ["export", str(ds), "--run", str(new_run[1]), "--experiment", "1"]
    )
    assert res.exit_code == 0, res.output
    assert (new_run[1] / "spectra" / "1" / "vendor" / "view.json").is_file()


def test_command_needs_run_or_out(tmp_path: Path, workspace: Path) -> None:
    from click.testing import CliRunner

    from ailsa.cli.spectra import spectra

    res = CliRunner().invoke(spectra, ["export", str(_dataset(tmp_path))])
    assert res.exit_code == 1
    assert "spectra export needs an active run or --out DIR" in res.output


def test_command_out_writes_no_event(
    tmp_path: Path, new_run: tuple[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    from ailsa.cli.spectra import spectra
    from ailsa.record.fingerprint import dataset_fingerprint

    monkeypatch.setenv("AILSA_RUN_DIR", str(new_run[1]))
    ds = _dataset(tmp_path)
    before = dataset_fingerprint(ds)
    out = tmp_path / "view-out"
    res = CliRunner().invoke(spectra, ["export", str(ds), "--out", str(out), "--format", "json"])
    assert res.exit_code == 0, res.output
    assert (out / "1" / "vendor" / "data.f32").is_file()
    assert _events(new_run[1]) == []
    assert dataset_fingerprint(ds) == before


# ----------------------------------------------------------------------------- real data


def test_example_dataset_optional() -> None:
    folder = os.environ.get("AILSA_EXAMPLE_TERPINEOL")
    if not folder or not Path(folder).is_dir():
        pytest.skip("AILSA_EXAMPLE_TERPINEOL not set")
    import tempfile
    import time

    from ailsa.record.inventory import build_inventory

    ds = Path(folder)
    inv = build_inventory(ds, blind=False, fingerprint="sha256:x")
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.perf_counter()
        results = export_dataset(ds, inv, Path(tmp))
        total = time.perf_counter() - t0
        size = sum(p.stat().st_size for p in Path(tmp).rglob("*") if p.is_file())
        print(f"EXPORT total_seconds={total:.1f} total_bytes={size}")
        for r in results:
            print(f"EXPORT {r['experiment']} {r['status']} {r['seconds']}s {r['reason']}")
    assert len(results) == 7
    assert all(r["status"] == "ok" for r in results), results
