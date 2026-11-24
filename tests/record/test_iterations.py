"""REC-18, REC-01: `ailsa lsd run` registers iterations in a run (fake LSD only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.cli.lsd import lsd
from ailsa.record.log import read_events
from ailsa.record.lsdrec import find_iteration_by_sha, index_map, latest_main_iteration
from ailsa.record.models import SolverRun

from ._fake_lsd import install_fake_lsd

LSD_TEXT = """; tiny generic input
MULT 1 C 3 3
MULT 2 C 3 2
MULT 3 O 3 1
"""


def _events(run_dir: Path) -> list[dict]:
    return read_events(run_dir)["events"]


def _types(run_dir: Path) -> list[str]:
    return [e["type"] for e in _events(run_dir)]


@pytest.fixture
def run_env(new_run, tmp_path, monkeypatch):
    _, run_dir = new_run
    bin_dir = install_fake_lsd(tmp_path / "bin", "solutions", count=3)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    it = run_dir / "agent" / "iteration_01"
    it.mkdir(parents=True)
    (it / "compound.lsd").write_text(LSD_TEXT)
    return run_dir, it


def _invoke(*args: str):
    return CliRunner().invoke(lsd, ["run", *args])


def test_index_map() -> None:
    assert index_map(LSD_TEXT)["3"] == {"element": "O", "hybridisation": 3, "h": 1}


def test_run_registers_iteration(run_env, monkeypatch) -> None:
    run_dir, it = run_env
    monkeypatch.chdir(it)
    res = _invoke("compound.lsd", "--format", "json")
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    for key in ("success", "solution_count", "return_code", "output_files", "stderr"):
        assert key in data
    assert data["outcome"] == "solutions" and data["iteration"] == "it01"
    assert data["partial_count"] is None and data["elapsed_s"] >= 0
    assert "Recorded as it01 (main)" in res.stderr

    events = _events(run_dir)
    types = [e["type"] for e in events]
    assert types.index("lsd.input.registered") < types.index("solver.started")
    assert types.index("solver.started") < types.index("solver.finished")
    reg = next(e for e in events if e["type"] == "lsd.input.registered")["payload"]
    assert reg["iteration"] == "it01" and reg["parent"] is None and reg["purpose"] == "main"
    assert reg["path"] == "agent/iteration_01/compound.lsd"
    assert reg["diff"] is None and reg["index_map"]["1"]["element"] == "C"
    fin = next(e for e in events if e["type"] == "solver.finished")["payload"]
    assert fin["outcome"] == "solutions" and fin["count"] == 3
    assert fin["provenance"] == "run" and fin["lsd"]["version"] == "3.4.9"
    assert fin["lsd"]["sha256"]
    assert "solutions.converted" in types

    folder = run_dir / "iterations" / "it01"
    for name in (
        "compound.lsd",
        "ring3",
        "ring4",
        "compound.sol",
        "solutions.smi",
        "solncounter",
        "lsd.out",
        "lsd.err",
        "solver.json",
    ):
        assert (folder / name).is_file(), name
    SolverRun.model_validate(json.loads((folder / "solver.json").read_text()))
    # outputs stay next to the input
    assert (it / "compound.sol").is_file() and (it / "solutions.smi").is_file()


def test_second_iteration_has_parent_and_diff(run_env, monkeypatch) -> None:
    run_dir, it = run_env
    monkeypatch.chdir(it)
    assert _invoke("compound.lsd", "--format", "json").exit_code == 0
    it2 = run_dir / "agent" / "iteration_02"
    it2.mkdir()
    (it2 / "compound.lsd").write_text(LSD_TEXT + "MULT 4 C 3 0\n")
    res = _invoke(str(it2 / "compound.lsd"), "--format", "json")
    assert json.loads(res.stdout)["iteration"] == "it02"
    events = _events(run_dir)
    reg = [e for e in events if e["type"] == "lsd.input.registered"][1]["payload"]
    assert reg["parent"] == "it01" and "+MULT 4 C 3 0" in reg["diff"]
    assert latest_main_iteration(events) == "it02"
    sha = reg["lsd_sha256"]
    assert find_iteration_by_sha(events, sha) == "it02"


def test_purpose_and_unknown_parent(run_env, monkeypatch) -> None:
    run_dir, it = run_env
    monkeypatch.chdir(it)
    assert _invoke("compound.lsd").exit_code == 0
    it2 = run_dir / "agent" / "iteration_02"
    it2.mkdir()
    (it2 / "compound.lsd").write_text(LSD_TEXT)
    ok = _invoke(str(it2 / "compound.lsd"), "--purpose", "family", "--parent", "it01")
    assert ok.exit_code == 0
    reg = [e for e in _events(run_dir) if e["type"] == "lsd.input.registered"][1]["payload"]
    assert reg["purpose"] == "family" and reg["parent"] == "it01"
    before = len(_events(run_dir))
    bad = _invoke(str(it2 / "compound.lsd"), "--parent", "it09")
    assert bad.exit_code == 1
    assert len(_events(run_dir)) == before


def test_timeout_message_and_partial_count(run_env, tmp_path, monkeypatch) -> None:
    run_dir, it = run_env
    install_fake_lsd(tmp_path / "bin", "sleep", seconds=10, partial=12)
    monkeypatch.chdir(it)
    res = _invoke("compound.lsd", "--timeout", "2")
    assert "LSD stopped at the time limit: 12 structures found so far" in res.stdout
    assert "LSD failed" not in res.stdout
    fin = next(e for e in _events(run_dir) if e["type"] == "solver.finished")["payload"]
    assert fin["outcome"] == "timeout" and fin["partial_count"] == 12


def test_outside_a_run_nothing_is_recorded(new_run, tmp_path, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.delenv("AILSA_RUN_DIR", raising=False)
    bin_dir = install_fake_lsd(tmp_path / "bin", "solutions", count=2)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    work = tmp_path / "work"
    work.mkdir()
    (work / "compound.lsd").write_text(LSD_TEXT)
    monkeypatch.chdir(work)
    res = _invoke("compound.lsd", "--format", "json")
    data = json.loads(res.stdout)
    assert "iteration" not in data and data["outcome"] == "solutions"
    assert not (run_dir / "iterations").exists() or not any((run_dir / "iterations").iterdir())
    text = _invoke("compound.lsd")
    assert "Outcome" not in text.stdout and "Solutions found: 2" in text.stdout
