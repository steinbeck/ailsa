"""REC-14: every solver run ends with a typed outcome (fake LSD only)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from ailsa.lsd.runner import LSDRunner, classify_outcome, maxs_limit, read_solncounter

from ._fake_lsd import install_fake_lsd

LSD_TEXT = """; tiny generic input
MULT 1 C 3 3
MULT 2 C 3 2
MULT 3 O 3 1
"""


def _classify(**over: object) -> tuple[str, str | None]:
    base: dict[str, object] = {
        "started": True,
        "blocked": False,
        "error_line": None,
        "timed_out": False,
        "count": 3,
        "limit": None,
        "no_solution_text": False,
        "sol_exists": True,
        "smiles_ok": True,
        "conversion_skipped": False,
    }
    base.update(over)
    return classify_outcome(**base)  # type: ignore[arg-type]


def test_classify_table() -> None:
    assert _classify(started=False) == ("not_run", "not_run")
    assert _classify(blocked=True) == ("blocked", "blocked")
    assert _classify(error_line="LSD error 420: x") == ("error", "error")
    assert _classify(timed_out=True, count=12) == ("timeout", "timeout")
    assert _classify(count=0, no_solution_text=True) == ("no_solution", "no_solution")
    assert _classify(count=5, limit=5) == ("limit_reached", None)
    assert _classify() == ("solutions", None)
    assert _classify(smiles_ok=False) == ("solutions", "conversion_failed")
    assert _classify(conversion_skipped=True) == ("solutions", "conversion_skipped_large")


def test_maxs_limit_ignores_comments() -> None:
    assert maxs_limit("; MAXS 9\nMULT 1 C 3 3\nMAXS 25\n") == 25
    assert maxs_limit("MULT 1 C 3 3\n") is None


@pytest.fixture
def work(tmp_path: Path) -> Path:
    d = tmp_path / "it"
    d.mkdir()
    (d / "compound.lsd").write_text(LSD_TEXT)
    return d


def _runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, **params: object) -> LSDRunner:
    bin_dir = install_fake_lsd(tmp_path / "bin", mode, **params)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    return LSDRunner()


def test_solutions(tmp_path, monkeypatch, work) -> None:
    result = _runner(tmp_path, monkeypatch, "solutions", count=3).run_file(
        work / "compound.lsd", work, timeout=20
    )
    assert result.outcome == "solutions"
    assert result.solution_count == 3
    assert result.elapsed_s > 0
    assert result.smiles_absent_reason is None
    assert result.success is True


def test_no_solution(tmp_path, monkeypatch, work) -> None:
    result = _runner(tmp_path, monkeypatch, "nosolution").run_file(
        work / "compound.lsd", work, timeout=20
    )
    assert result.outcome == "no_solution"
    assert result.smiles_absent_reason == "no_solution"
    assert result.partial_count is None


def test_error_line(tmp_path, monkeypatch, work) -> None:
    result = _runner(tmp_path, monkeypatch, "error", code=420).run_file(
        work / "compound.lsd", work, timeout=20
    )
    assert result.outcome == "error"
    assert result.error_line is not None and "420" in result.error_line
    assert result.smiles_absent_reason == "error"


def test_limit_reached(tmp_path, monkeypatch, work) -> None:
    (work / "compound.lsd").write_text(LSD_TEXT + "MAXS 4\n")
    result = _runner(tmp_path, monkeypatch, "maxs").run_file(work / "compound.lsd", work, timeout=20)
    assert result.outcome == "limit_reached"
    assert result.limit == 4
    assert result.solution_count == 4


def test_conversion_failed_keeps_count_for_the_record(tmp_path, monkeypatch, work) -> None:
    result = _runner(tmp_path, monkeypatch, "solutions", count=2, outlsd="fail").run_file(
        work / "compound.lsd", work, timeout=20
    )
    assert result.outcome == "solutions"
    assert result.smiles_absent_reason == "conversion_failed"
    assert result.found_count == 2
    assert result.success is False


def test_timeout_reports_partial_count_and_leaves_no_process(tmp_path, monkeypatch, work) -> None:
    runner = _runner(tmp_path, monkeypatch, "sleep", seconds=10, partial=12)
    start = time.monotonic()
    result = runner.run_file(work / "compound.lsd", work, timeout=2)
    assert time.monotonic() - start < 7
    assert result.outcome == "timeout"
    assert result.timed_out is True
    assert result.partial_count == 12
    assert result.smiles_absent_reason == "timeout"
    assert "timed out" in result.stderr
    probe = subprocess.run(["pgrep", "-f", str(tmp_path / "bin")], capture_output=True, text=True)
    assert probe.stdout.strip() == ""


def test_read_solncounter(tmp_path: Path) -> None:
    assert read_solncounter(tmp_path) is None
    (tmp_path / "solncounter").write_text("7\n")
    assert read_solncounter(tmp_path) == 7


def test_banner_version_despite_nonzero_exit(tmp_path, monkeypatch) -> None:
    _runner(tmp_path, monkeypatch, "solutions")
    assert LSDRunner.get_version() == "3.4.9"
