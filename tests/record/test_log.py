"""Append-only event log: genesis, chaining, concurrency, counters, heartbeat."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ailsa.record.fsutil import sha256_bytes
from ailsa.record.log import (
    append_event,
    chain_head,
    first_event,
    log_session,
    read_events,
    verify_chain,
    write_heartbeat,
)

ACTOR = {"kind": "tool", "name": "test"}

WORKER = """\
import sys
from ailsa.record.log import append_event

run_dir, count = sys.argv[1], int(sys.argv[2])
for i in range(count):
    append_event(run_dir, "note.added", {"text": str(i), "sender": "w"},
                 actor={"kind": "tool", "name": "worker"})
"""


def test_genesis_and_chaining(new_run: tuple[str, Path]) -> None:
    run_id, run_dir = new_run
    first = append_event(run_dir, "note.added", {"text": "a", "sender": "t"}, actor=ACTOR)
    assert first["seq"] == 1
    assert first["prev"] == sha256_bytes(run_id.encode())
    second = append_event(run_dir, "note.added", {"text": "b", "sender": "t"}, actor=ACTOR)
    raw_first = (run_dir / "events.jsonl").read_bytes().split(b"\n")[0]
    assert second["seq"] == 2
    assert second["prev"] == sha256_bytes(raw_first)
    assert verify_chain(run_dir)["clean"] is True
    assert chain_head(run_dir) == verify_chain(run_dir)["head"]


def test_missing_log_is_clean_and_empty(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    result = read_events(run_dir)
    assert result["events"] == []
    assert result["integrity"]["clean"] is True


def test_concurrent_writers_gapless(new_run: tuple[str, Path], tmp_path: Path) -> None:
    _, run_dir = new_run
    worker = tmp_path / "append_worker.py"
    worker.write_text(WORKER)
    procs = [subprocess.Popen([sys.executable, str(worker), str(run_dir), "50"]) for _ in range(8)]
    try:
        for proc in procs:
            assert proc.wait(timeout=60) == 0
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    result = read_events(run_dir)
    assert [e["seq"] for e in result["events"]] == list(range(1, 401))
    assert result["integrity"]["clean"] is True


def test_counters_increment(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    with log_session(run_dir) as session:
        assert session.next_counter("iteration") == 1
        assert session.next_counter("iteration") == 2
        assert session.next_counter("ranking") == 1


def _art(kind: str, n: int, path: str) -> dict[str, object]:
    return {"id": f"art:{kind}:{n}", "kind": kind, "path": path, "sha256": "0" * 64,
            "bytes": 1, "supersedes": None}


def _seed_ids(run_dir: Path) -> None:
    append_event(
        run_dir,
        "lsd.input.registered",
        {"iteration": "it02", "parent": None, "purpose": "main", "lsd_sha256": "x", "path": "p"},
        actor=ACTOR,
        artefacts=[_art("lsd-input", 2, "iterations/it02/compound.lsd")],
    )
    append_event(
        run_dir,
        "ranking.computed",
        {"ranking_id": "rk03", "method": "m", "inputs": [], "candidate_count": 0},
        actor=ACTOR,
        artefacts=[_art("ranking", 3, "rankings/rk03.json")],
    )
    append_event(
        run_dir,
        "identity.derived",
        {"smiles": "C", "inchikey": None, "verdict": "v"},
        actor=ACTOR,
        artefacts=[_art("identity", 1, "identity/4.json")],
    )


def test_corrupt_counters_are_rebuilt_from_the_log(new_run: tuple[str, Path]) -> None:
    """WR-12: an invalid .counters.json never restarts ids; the rebuild is recorded."""
    _, run_dir = new_run
    _seed_ids(run_dir)
    (run_dir / ".counters.json").write_text("{not json")
    with log_session(run_dir) as session:
        assert session.next_counter("iteration") == 3
        assert session.next_counter("ranking") == 4
        assert session.next_counter("art:ranking") == 4
        assert session.next_counter("identity") == 5
        assert session.next_counter("art:peak-pick") == 1
    warnings = [e for e in read_events(run_dir)["events"] if e["type"] == "warning.raised"]
    assert len(warnings) == 1 and warnings[0]["payload"]["code"] == "counters_rebuilt"
    assert read_events(run_dir)["integrity"]["clean"] is True


def test_missing_counters_are_rebuilt_quietly_only_for_a_new_run(
    new_run: tuple[str, Path]
) -> None:
    """WR-12: a missing file in a fresh run is normal; in a run with ids it is a warning."""
    _, run_dir = new_run
    with log_session(run_dir) as session:
        assert session.next_counter("iteration") == 1
    assert read_events(run_dir)["events"] == []
    _seed_ids(run_dir)
    (run_dir / ".counters.json").unlink()
    with log_session(run_dir) as session:
        assert session.next_counter("iteration") == 3
    types = [e["type"] for e in read_events(run_dir)["events"]]
    assert types.count("warning.raised") == 1


def test_overrides_are_deterministic(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    ev = append_event(
        run_dir,
        "note.added",
        {"text": "a", "sender": "t"},
        actor=ACTOR,
        utc="2026-11-24T14:17:00.000Z",
        host="box",
    )
    assert ev["utc"] == "2026-11-24T14:17:00.000Z"
    assert ev["host"] == "box"
    line = (run_dir / "events.jsonl").read_bytes().rstrip(b"\n")
    assert json.loads(line) == ev


def test_first_event(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    assert first_event(run_dir) is None
    ev = append_event(run_dir, "note.added", {"text": "a", "sender": "t"}, actor=ACTOR)
    append_event(run_dir, "note.added", {"text": "b", "sender": "t"}, actor=ACTOR)
    assert first_event(run_dir) == ev


def test_heartbeat_does_not_touch_log(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    append_event(run_dir, "note.added", {"text": "a", "sender": "t"}, actor=ACTOR)
    before = (run_dir / "events.jsonl").read_bytes()
    write_heartbeat(run_dir, "hook")
    beat = json.loads((run_dir / "heartbeat.json").read_text())
    assert beat["source"] == "hook" and beat["utc"].endswith("Z")
    assert (run_dir / "events.jsonl").read_bytes() == before


def test_short_writes_are_completed(new_run: tuple[str, Path], monkeypatch) -> None:
    """WR-02: os.write may write fewer bytes; the writer loops until the line is on disk."""
    import os

    _, run_dir = new_run
    real_write = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: real_write(fd, bytes(data[:7])))
    append_event(run_dir, "note.added", {"text": "a" * 50, "sender": "t"}, actor=ACTOR)
    fin = append_event(run_dir, "run.finished", {"state": "x", "reason": "y"}, actor=ACTOR)
    monkeypatch.setattr(os, "write", real_write)
    result = read_events(run_dir)
    assert result["integrity"]["clean"] is True
    assert [e["seq"] for e in result["events"]] == [1, 2]
    assert json.loads((run_dir / "finished.json").read_text())["seq"] == fin["seq"]


def test_write_without_progress_raises_and_writes_no_finished(
    new_run: tuple[str, Path], monkeypatch
) -> None:
    """WR-02: a write that makes no progress raises; finished.json is not written."""
    import os

    import pytest

    _, run_dir = new_run
    monkeypatch.setattr(os, "write", lambda fd, data: 0)
    with pytest.raises(OSError):
        append_event(run_dir, "run.finished", {"state": "x", "reason": "y"}, actor=ACTOR)
    assert not (run_dir / "finished.json").exists()
