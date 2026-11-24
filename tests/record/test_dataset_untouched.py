"""REC-05: tools that run inside a run never write into the dataset."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
from click.testing import CliRunner

from ailsa.cli.identify import identify
from ailsa.cli.jcamp import jcamp
from ailsa.cli.pick import pick
from ailsa.record.fingerprint import dataset_fingerprint

from ..nus.test_reconstruct_orchestration import _RecordingBackend
from .test_spectra_export import make_1d, make_2d

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _no_analysis(dataset: Path) -> bool:
    return not any(p.name == "analysis" for p in dataset.rglob("*"))


def _peaky_2d(root: Path, expno: str) -> Path:
    exp = make_2d(root, expno)
    data = np.zeros((512, 1024))
    for r, c in ((100, 200), (250, 600), (400, 900)):
        data[r - 1 : r + 2, c - 1 : c + 2] = 5000.0
    data.astype("<i4").tofile(exp / "pdata" / "1" / "2rr")
    return exp


def test_pick_and_identify_leave_dataset_alone(new_run, monkeypatch, tmp_path: Path) -> None:
    _, run_dir = new_run
    ds = tmp_path / "ds"
    make_1d(ds, "1")
    _peaky_2d(ds, "2")
    before = dataset_fingerprint(ds)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    monkeypatch.setattr(
        "ailsa.cli.identify.check_identity_result",
        lambda *a, **k: {"verdict": "novel", "derived": {}, "name_match": None},
    )
    assert CliRunner().invoke(pick, ["1d", str(ds / "1")]).exit_code == 0
    assert CliRunner().invoke(pick, ["hsqc", str(ds / "2")]).exit_code == 0
    assert CliRunner().invoke(identify, ["--smiles", "CCO"]).exit_code == 0
    assert dataset_fingerprint(ds) == before
    assert _no_analysis(ds)
    assert (run_dir / "peaks" / "1.1.json").is_file()


def test_nus_staging_goes_to_run(new_run, monkeypatch, tmp_path: Path) -> None:
    import ailsa.nus.runner as runner_module
    from ailsa.nus.runner import NusRunner

    _, run_dir = new_run
    ds = tmp_path / "ds"
    shutil.copytree(FIXTURES / "nus" / "exp3_hsqc", ds / "3")
    before = dataset_fingerprint(ds)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))

    def fake_direct(converted_fid, stage_dir, params=None, **kwargs):
        return Path(stage_dir) / "f2_processed.fid"

    def fake_indirect(reconstructed_fid, stage_dir, params=None, **kwargs):
        out = Path(stage_dir) / "processed.ft2"
        out.write_bytes(b"\x01\x02\x03\x04")
        return out

    monkeypatch.setattr(runner_module, "process_direct", fake_direct)
    monkeypatch.setattr(runner_module, "process_indirect", fake_indirect)
    result = NusRunner(backend=_RecordingBackend([], {})).reconstruct(ds / "3")
    assert result.success is True
    assert Path(result.stage_dir) == (run_dir / "nus" / "3").resolve()
    assert dataset_fingerprint(ds) == before
    assert _no_analysis(ds)


def test_nus_outside_run_default_unchanged(workspace, tmp_path: Path) -> None:
    from ailsa.nus.runner import NusRunner

    exp = tmp_path / "7"
    exp.mkdir()
    stage = NusRunner(backend=_RecordingBackend([], {}))._stage_dir(exp)
    assert stage == exp.resolve() / "analysis" / "nus_recon" / "7"


def test_jcamp_goes_to_run(new_run, monkeypatch, tmp_path: Path) -> None:
    _, run_dir = new_run
    ds = tmp_path / "jds"
    ds.mkdir()
    shutil.copy(FIXTURES / "jcamp" / "C20H32O2_13C.dx", ds)
    before = dataset_fingerprint(ds)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    res = CliRunner().invoke(jcamp, [str(ds)])
    assert res.exit_code in (0, 1), res.output
    assert dataset_fingerprint(ds) == before
    assert _no_analysis(ds)
    assert (run_dir / "jcamp" / "jds").is_dir()
    assert not (ds / "analysis").exists()


def test_jcamp_outside_run_default_unchanged(workspace, tmp_path: Path) -> None:
    ds = tmp_path / "jds"
    ds.mkdir()
    shutil.copy(FIXTURES / "jcamp" / "C20H32O2_13C.dx", ds)
    CliRunner().invoke(jcamp, [str(ds)])
    assert (ds / "analysis").exists()
