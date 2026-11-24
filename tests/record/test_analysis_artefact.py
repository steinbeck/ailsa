"""REC-20: per-solution correlation analysis saved in a run, with the ELIM window."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.cli.lsd import lsd
from ailsa.record.log import read_events
from ailsa.record.models import SolutionAnalysis
from ailsa.record.rankrec import (
    ANALYSIS_CAP,
    allowed_max_bonds,
    elim_window,
    parse_correlations,
    parse_elim,
)

# Propanal-like chain C1-C2-C3=O4: HMBC 1 3 spans two bonds (3J, inside the window),
# HMBC 4 1 spans three bonds (4J, outside it).
BASE = """; tiny generic input
MULT 1 C 3 3
MULT 2 C 3 2
MULT 3 C 2 1
MULT 4 O 2 0
HMBC 1 3
HMBC 4 1
COSY 1 2
"""
SOL_ONE = """4 {n}
1 C 4 3 0 0 0 2 1 0 0
1 C 4 2 0 0 0 1 1 3 1 0 0
1 C 4 1 0 0 0 2 1 4 2 0 0
1 O 2 0 0 0 0 3 2 0 0
"""


def _sol(count: int) -> str:
    blocks = "".join(SOL_ONE.format(n=i) for i in range(1, count + 1))
    return "OUTLSD\n" + blocks + "0\n"


def _folder(tmp_path: Path, lsd_text: str, count: int = 2) -> Path:
    d = tmp_path / "elsewhere"
    d.mkdir()
    (d / "compound.lsd").write_text(lsd_text)
    (d / "compound.sol").write_text(_sol(count))
    (d / "solncounter").write_text(f"{count}\n")
    return d


@pytest.fixture
def run_env(new_run, tmp_path, monkeypatch):
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    monkeypatch.chdir(tmp_path)
    return run_dir


def _import(folder: Path) -> None:
    res = CliRunner().invoke(lsd, ["import", str(folder)])
    assert res.exit_code == 0, res.output


def _analyze(folder: Path, *extra: str):
    return CliRunner().invoke(
        lsd, ["analyze", str(folder / "compound.sol"), str(folder / "compound.lsd"), *extra]
    )


def _model(run_dir: Path, name: str) -> SolutionAnalysis:
    path = run_dir / "iterations" / "it01" / name
    return SolutionAnalysis.model_validate(json.loads(path.read_text()))


def test_parse_elim_and_windows() -> None:
    assert parse_elim("ELIM 3 5\n") == {"max_eliminated": 3, "max_bonds": 5}
    assert parse_elim("ELIM 2 0\n") == {"max_eliminated": 2, "max_bonds": None}
    assert parse_elim("; ELIM 3 5\n") is None
    elim = parse_elim("ELIM 3 5\n")
    assert elim_window("HMBC", elim) == 5 and elim_window("COSY", elim) == 6
    lines = parse_correlations("HMBC (4 5) 8 2 3\nCOSY 5 9\nHMBC 6 8 4\n")
    assert [(ln["kind"], ln["a"], ln["b"]) for ln in lines] == [
        ("HMBC", 4, 8),
        ("HMBC", 5, 8),
        ("COSY", 5, 9),
        ("HMBC", 6, 8),
    ]
    assert allowed_max_bonds(lines[0]) == 3
    assert allowed_max_bonds(lines[2]) == 3
    assert allowed_max_bonds(lines[3]) == 4
    assert allowed_max_bonds({"kind": "HMBC", "lower": 3, "upper": 0}) is None


def test_analysis_with_elim_lists_the_dropped_correlations(run_env, tmp_path) -> None:
    folder = _folder(tmp_path, BASE + "ELIM 1 4\n")
    _import(folder)
    plain = _analyze(folder)
    assert plain.exit_code == 0, plain.output
    assert "Recorded analysis" not in plain.stdout

    model = _model(run_env, "analysis.1.json")
    assert model.cap == ANALYSIS_CAP == 500 and model.analysed == 2 and model.total == 2
    assert model.truncated is False and model.elim_active is True
    assert model.elim is not None and model.elim.max_eliminated == 1 and model.elim.max_bonds == 4
    first = model.solutions[0]
    assert first.solution_id == "sol:it01:1"
    by_line = {(c.kind, c.carbon, c.proton): c for c in first.correlations}
    assert by_line[("HMBC", 1, 3)].j_coupling == 3 and not by_line[("HMBC", 1, 3)].exceeds_window
    far = by_line[("HMBC", 4, 1)]
    assert far.path_length == 3 and far.j_coupling == 4 and far.allowed_max == 3
    assert far.exceeds_window is True
    assert by_line[("COSY", 1, 2)].j_coupling == 3
    assert first.dropped_by_elim == [1]

    events = read_events(run_env)["events"]
    ev = next(e for e in events if e["type"] == "solutions.analysed")
    assert ev["payload"] == {"iteration": "it01", "analysed": 2, "cap": 500, "truncated": False}


def test_without_elim_nothing_is_dropped(run_env, tmp_path) -> None:
    folder = _folder(tmp_path, BASE)
    _import(folder)
    assert _analyze(folder).exit_code == 0
    model = _model(run_env, "analysis.1.json")
    assert model.elim_active is False and model.elim is None
    assert all(s.dropped_by_elim == [] for s in model.solutions)
    assert any(c.exceeds_window for c in model.solutions[0].correlations)


def test_single_solution(run_env, tmp_path) -> None:
    folder = _folder(tmp_path, BASE)
    _import(folder)
    assert _analyze(folder, "--solution", "2").exit_code == 0
    model = _model(run_env, "analysis.1.json")
    assert [s.solution for s in model.solutions] == [2]
    assert model.analysed == 1 and model.total == 2 and model.truncated is False


def test_cap_is_stated(run_env, tmp_path) -> None:
    folder = _folder(tmp_path, BASE, count=ANALYSIS_CAP + 5)
    _import(folder)
    assert _analyze(folder).exit_code == 0
    model = _model(run_env, "analysis.1.json")
    assert model.total == ANALYSIS_CAP + 5 and model.analysed == ANALYSIS_CAP
    assert model.truncated is True and len(model.solutions) == ANALYSIS_CAP


def test_stdout_is_unchanged_by_recording(run_env, tmp_path, monkeypatch) -> None:
    folder = _folder(tmp_path, BASE)
    _import(folder)
    recorded = _analyze(folder, "--format", "json")
    monkeypatch.delenv("AILSA_RUN_DIR")
    plain = _analyze(folder, "--format", "json")
    assert recorded.stdout == plain.stdout


def test_unregistered_input_is_not_recorded(run_env, tmp_path) -> None:
    folder = _folder(tmp_path, BASE)
    res = _analyze(folder)
    assert res.exit_code == 0, res.output
    assert "not recorded" in res.stderr
    assert not (run_env / "iterations").exists()
