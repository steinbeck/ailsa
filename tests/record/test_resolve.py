"""Active-run resolution order."""

from __future__ import annotations

from pathlib import Path

import pytest

from ailsa.record import resolve
from ailsa.record.resolve import (
    bind_session,
    find_active_run,
    session_pointer_path,
    unbind_session,
)
from ailsa.record.workspace import create_run_dir

SID = "abcd1234-ef56-7890"


@pytest.fixture(autouse=True)
def _reset_warned() -> None:
    resolve._warned = False


def test_explicit_wins(workspace: Path, new_run: tuple[str, Path], monkeypatch) -> None:
    run_id, run_dir = new_run
    _, other = create_run_dir(workspace, "other")
    monkeypatch.setenv("AILSA_RUN_DIR", str(other))
    ref = find_active_run(str(run_dir))
    assert ref is not None and ref.run_dir == run_dir and ref.via == "flag"
    ref = find_active_run(run_id)
    assert ref is not None and ref.run_dir == run_dir


def test_env_beats_session_and_cwd(workspace: Path, new_run, monkeypatch, tmp_path) -> None:
    _, run_dir = new_run
    _, other = create_run_dir(workspace, "other")
    bind_session(workspace, SID, other)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    ref = find_active_run(session_id=SID, cwd=other)
    assert ref is not None and ref.via == "env" and ref.run_dir == run_dir


def test_session_beats_cwd(workspace: Path, new_run, tmp_path: Path) -> None:
    _, run_dir = new_run
    _, other = create_run_dir(workspace, "other")
    bind_session(workspace, SID, run_dir)
    ref = find_active_run(session_id=SID, cwd=other)
    assert ref is not None and ref.via == "session" and ref.run_dir == run_dir.resolve()


def test_cwd_walk_up(workspace: Path, new_run) -> None:
    _, run_dir = new_run
    deep = run_dir / "agent" / "iteration_01"
    deep.mkdir(parents=True)
    ref = find_active_run(cwd=deep)
    assert ref is not None and ref.via == "cwd" and ref.run_dir == run_dir.resolve()


def test_invalid_session_id_ignored(workspace: Path, new_run) -> None:
    _, run_dir = new_run
    assert session_pointer_path(workspace, "../../etc") is None
    assert bind_session(workspace, "../../etc", run_dir) is False
    assert not (workspace / ".sessions").exists()
    assert find_active_run(session_id="../../etc", cwd=workspace) is None


def test_bind_unbind(workspace: Path, new_run) -> None:
    _, run_dir = new_run
    assert bind_session(workspace, SID, run_dir)
    pointer = workspace / ".sessions" / SID
    assert pointer.read_text().strip() == str(run_dir.resolve())
    unbind_session(workspace, SID)
    assert not pointer.exists()


def test_nothing_found(workspace: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert find_active_run(cwd=outside) is None
