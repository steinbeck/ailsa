"""D-07 warning gate: silent by default, one stderr line when a record was expected."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from ailsa.record import resolve
from ailsa.record.events import FINISHED
from ailsa.record.resolve import bind_session, current_run_for_tool

SID = "abcd1234-ef56-7890"


@pytest.fixture(autouse=True)
def _reset_warned() -> None:
    resolve._warned = False


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    path = tmp_path / "outside"
    path.mkdir()
    return path


def test_silent_by_default(workspace: Path, outside: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    buf = io.StringIO()
    assert current_run_for_tool("pick", cwd=outside, stream=buf) is None
    assert buf.getvalue() == ""


def test_one_line_when_required(workspace: Path, outside: Path, monkeypatch) -> None:
    monkeypatch.setenv("AILSA_REQUIRE_RUN", "1")
    buf = io.StringIO()
    assert current_run_for_tool("pick", cwd=outside, stream=buf) is None
    assert buf.getvalue().startswith("ailsa: not recorded: no active run")
    assert buf.getvalue().count("\n") == 1
    current_run_for_tool("pick", cwd=outside, stream=buf)
    assert buf.getvalue().count("\n") == 1


def test_missing_run_dir(workspace: Path, outside: Path, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AILSA_RUN_DIR", str(tmp_path / "nope"))
    buf = io.StringIO()
    assert current_run_for_tool("pick", cwd=outside, stream=buf) is None
    assert "AILSA_RUN_DIR not found" in buf.getvalue()


def test_unresolvable_session_pointer(workspace: Path, outside: Path, monkeypatch) -> None:
    bind_session(workspace, SID, workspace / "gone")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    buf = io.StringIO()
    assert current_run_for_tool("pick", cwd=outside, stream=buf) is None
    assert "not recorded: no active run" in buf.getvalue()


def test_finished_run(workspace: Path, new_run, monkeypatch) -> None:
    _, run_dir = new_run
    (run_dir / FINISHED).write_text("{}")
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    buf = io.StringIO()
    assert current_run_for_tool("pick", stream=buf) is None
    assert buf.getvalue() == "ailsa: not recorded: run finished\n"


def test_active_run_found(workspace: Path, new_run, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    buf = io.StringIO()
    ref = current_run_for_tool("pick", stream=buf)
    assert ref is not None and ref.run_dir == run_dir
    assert buf.getvalue() == ""
