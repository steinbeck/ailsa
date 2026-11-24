"""REC-23: the log is closed after run.finished except for flagged hook events."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ailsa.record.fsutil import sha256_bytes
from ailsa.record.log import RecordWriteRefused, append_event, verify_chain

TOOL = {"kind": "tool", "name": "test"}
HOOK = {"kind": "hook", "name": "hook"}


def _finish(run_dir: Path) -> dict:
    return append_event(
        run_dir, "run.finished", {"state": "result_declared", "reason": "test"}, actor=TOOL
    )


def test_finished_sentinel_written(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    ev = _finish(run_dir)
    fin = json.loads((run_dir / "finished.json").read_text())
    line = (run_dir / "events.jsonl").read_bytes().rstrip(b"\n")
    assert fin["seq"] == ev["seq"]
    assert fin["head"] == sha256_bytes(line)


def test_non_hook_refused_after_finish(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    _finish(run_dir)
    with pytest.raises(RecordWriteRefused):
        append_event(run_dir, "note.added", {"text": "x", "sender": "t"}, actor=TOOL)
    with pytest.raises(RecordWriteRefused):
        append_event(run_dir, "run.finished", {"state": "x", "reason": "y"}, actor=TOOL)


def test_hook_needs_after_finish_flag(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    _finish(run_dir)
    with pytest.raises(RecordWriteRefused):
        append_event(run_dir, "session.ended", {"reason": "other"}, actor=HOOK)
    ev = append_event(
        run_dir, "session.ended", {"reason": "other"}, actor=HOOK, allow_after_finish=True
    )
    assert ev["after_finish"] is True
    assert verify_chain(run_dir)["clean"] is True


def test_hook_flag_does_not_admit_non_hook_type(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    _finish(run_dir)
    with pytest.raises(RecordWriteRefused):
        append_event(
            run_dir,
            "note.added",
            {"text": "x", "sender": "t"},
            actor=HOOK,
            allow_after_finish=True,
        )


def test_flag_is_stamped_from_run_state_not_caller(new_run: tuple[str, Path]) -> None:
    """CR-05: a hook event during the run is not after_finish, whatever the caller allows."""
    _, run_dir = new_run
    ev = append_event(
        run_dir, "session.started", {"source": "startup"}, actor=HOOK, allow_after_finish=True
    )
    assert ev["after_finish"] is False
