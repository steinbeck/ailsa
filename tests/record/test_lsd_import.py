"""`ailsa lsd import`: solver output produced elsewhere is registered as imported."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from ailsa.cli.lsd import lsd
from ailsa.record.log import read_events
from ailsa.record.models import SolverRun

LSD_TEXT = "MULT 1 C 3 3\nMULT 2 O 3 1\n"


def _folder(tmp_path: Path, *, sol: bool = True, counter: str | None = "2") -> Path:
    d = tmp_path / "elsewhere"
    d.mkdir()
    (d / "compound.lsd").write_text(LSD_TEXT)
    if sol:
        (d / "compound.sol").write_text(LSD_TEXT + "SOLUTION 1\nSOLUTION 2\n")
        (d / "solutions.smi").write_text("CCO\nCCO\n")
    if counter is not None:
        (d / "solncounter").write_text(counter + "\n")
    return d


def _invoke(*args: str):
    return CliRunner().invoke(lsd, ["import", *args])


def test_import_registers_iteration_as_imported(new_run, tmp_path, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    folder = _folder(tmp_path)
    res = _invoke(str(folder), "--format", "json")
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout) == {
        "iteration": "it01",
        "outcome": "solutions",
        "count": 2,
        "provenance": "imported",
    }
    events = read_events(run_dir)["events"]
    fin = next(e for e in events if e["type"] == "solver.finished")["payload"]
    assert fin["provenance"] == "imported" and fin["elapsed_s"] is None
    kept = run_dir / "iterations" / "it01"
    for name in ("compound.lsd", "compound.sol", "solutions.smi", "solncounter", "solver.json"):
        assert (kept / name).is_file(), name
    model = SolverRun.model_validate(json.loads((kept / "solver.json").read_text()))
    assert model.provenance == "imported" and model.elapsed_s is None


def test_only_solncounter_is_a_partial_result(new_run, tmp_path, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    folder = _folder(tmp_path, sol=False, counter="12")
    res = _invoke(str(folder), "--format", "json")
    data = json.loads(res.stdout)
    assert data["outcome"] == "timeout" and data["count"] == 12
    fin = next(e for e in read_events(run_dir)["events"] if e["type"] == "solver.finished")
    assert fin["payload"]["partial_count"] == 12


def test_several_lsd_files_need_input_option(new_run, tmp_path, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    folder = _folder(tmp_path)
    (folder / "other.lsd").write_text(LSD_TEXT)
    assert _invoke(str(folder)).exit_code == 1
    assert _invoke(str(folder), "--input", str(folder / "compound.lsd")).exit_code == 0


def test_no_lsd_file_is_refused(new_run, tmp_path, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _invoke(str(empty)).exit_code == 1


def test_without_a_run_it_fails(tmp_path, workspace, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    folder = _folder(tmp_path)
    res = _invoke(str(folder))
    assert res.exit_code == 1
    assert "lsd import needs an active run" in res.output
