"""Tamper evidence and crash recovery of the event log."""

from __future__ import annotations

from pathlib import Path

from ailsa.record.log import append_event, read_events, verify_chain

ACTOR = {"kind": "tool", "name": "test"}


def _fill(run_dir: Path, count: int = 10) -> None:
    for i in range(count):
        append_event(run_dir, "note.added", {"text": f"note{i}", "sender": "t"}, actor=ACTOR)


def test_flipped_byte_detected(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    _fill(run_dir)
    path = run_dir / "events.jsonl"
    lines = path.read_bytes().split(b"\n")
    lines[4] = lines[4].replace(b"note4", b"note9")
    path.write_bytes(b"\n".join(lines))
    result = read_events(run_dir)
    integrity = result["integrity"]
    assert integrity["clean"] is False
    assert integrity["first_bad_seq"] == 5
    assert integrity["reason"] == "chain_break"
    assert len(result["events"]) == 10
    suspects = [e["seq"] for e in result["events"] if e.get("_suspect")]
    assert suspects == list(range(5, 11))


def test_unparseable_line_detected(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    _fill(run_dir)
    path = run_dir / "events.jsonl"
    lines = path.read_bytes().split(b"\n")
    lines[4] = b"X" + lines[4][1:]
    path.write_bytes(b"\n".join(lines))
    integrity = verify_chain(run_dir)
    assert integrity["clean"] is False
    assert integrity["first_bad_seq"] == 5
    assert integrity["reason"] == "unparseable"
    assert integrity["bad_lines"][0]["line"] == 5


def test_deleted_line_detected(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    _fill(run_dir)
    path = run_dir / "events.jsonl"
    lines = path.read_bytes().split(b"\n")
    del lines[6]
    path.write_bytes(b"\n".join(lines))
    integrity = verify_chain(run_dir)
    assert integrity["clean"] is False
    assert integrity["first_bad_seq"] == 7
    assert integrity["reason"] in ("seq_gap", "chain_break")


def test_truncated_tail_then_recovery(new_run: tuple[str, Path]) -> None:
    _, run_dir = new_run
    _fill(run_dir, 5)
    path = run_dir / "events.jsonl"
    data = path.read_bytes()
    cut = data[: len(data) - 20]
    path.write_bytes(cut)
    result = read_events(run_dir)
    assert len(result["events"]) == 4
    assert result["integrity"]["reason"] == "truncated"
    assert result["integrity"]["clean"] is False

    append_event(run_dir, "note.added", {"text": "after", "sender": "t"}, actor=ACTOR)
    after = read_events(run_dir)
    types = [e["type"] for e in after["events"]]
    assert types[-2:] == ["log.recovered", "note.added"]
    recovered = after["events"][-2]
    assert recovered["payload"]["discarded_bytes"] > 0
    assert recovered["seq"] == 5
    integrity = verify_chain(run_dir)
    assert integrity["reason"] == "truncated_recovered"
    assert integrity["first_bad_seq"] == recovered["seq"]
    assert integrity["clean"] is False
    # the damaged bytes are kept as evidence
    assert path.read_bytes().startswith(cut)
