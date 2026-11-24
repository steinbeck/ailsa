"""Reducer tests: manifest state is derived from declarations only."""

from __future__ import annotations

import json
from pathlib import Path

from ailsa.record.events import MANIFEST
from ailsa.record.fold import fold, rebuild_manifest
from ailsa.record.log import append_event, read_events, write_heartbeat

from ._fixture_record import HOST, build_fixture_record

NOW = "2026-01-01T12:00:00.000Z"


def _fold(run: Path, **kw: object) -> dict:
    r = read_events(run)
    return fold(r["events"], r["integrity"], now=NOW, **kw)  # type: ignore[arg-type]


def test_declared(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "r1")
    m = _fold(run)
    assert m["status"]["state"] == "result_declared"
    assert m["status"]["inferred"] is False
    assert m["status"]["label"] == "result declared: proposal"
    assert m["status"]["counts_as_clean"] is True
    assert m["dataset"]["label"] == "example"


def test_stale(tmp_path: Path) -> None:
    m = _fold(build_fixture_record(tmp_path / "r2", stale=True))
    assert m["status"]["state"] == "declaration_stale"
    assert m["final"]["stale"] is True


def test_hand_ranking_is_not_a_result(tmp_path: Path) -> None:
    m = _fold(build_fixture_record(tmp_path / "r3", hand_ranking=True))
    assert m["status"]["state"] == "stopped_before_result"
    assert m["status"]["inferred"] is True
    assert m["status"]["label"] == "stopped before a result (inferred)"
    assert m["status"]["counts_as_clean"] is False


def test_withdrawn(tmp_path: Path) -> None:
    m = _fold(build_fixture_record(tmp_path / "r4", withdraw=True))
    assert m["status"]["state"] == "stopped_before_result"
    assert m["final"]["withdrawn"] is True


def _open_run(tmp_path: Path) -> Path:
    run = build_fixture_record(tmp_path / "r5")
    lines = (run / "events.jsonl").read_bytes().splitlines(keepends=True)
    (run / "events.jsonl").write_bytes(b"".join(lines[:5]))  # run.created .. first events
    return run


def test_no_heartbeat_and_running(tmp_path: Path) -> None:
    run = _open_run(tmp_path)
    last = read_events(run)["events"][-1]["utc"]
    assert last < NOW
    assert _fold(run)["status"]["state"] == "no_heartbeat"
    r = read_events(run)
    soon = fold(r["events"], r["integrity"], now="2026-01-01T10:09:00.000Z")
    assert soon["status"]["state"] == "running"


def test_heartbeat_counts_as_activity(tmp_path: Path) -> None:
    run = _open_run(tmp_path)
    r = read_events(run)
    hb = {"utc": "2026-01-01T11:55:00.000Z", "source": "test"}
    assert fold(r["events"], r["integrity"], heartbeat=hb, now=NOW)["status"]["state"] == "running"


def test_hook_counts(tmp_path: Path) -> None:
    m = _fold(build_fixture_record(tmp_path / "h1"))
    assert m["harness"]["hooks_recorded"] is True
    assert set(m["harness"]["hook_counts"]) == {
        "prompts",
        "permission_waits",
        "subagents",
        "messages",
        "compactions",
        "turns",
        "session_stops",
    }
    assert m["harness"]["hook_counts"]["prompts"] == 1
    m2 = _fold(build_fixture_record(tmp_path / "h2", hooks=False))
    assert m2["harness"]["hooks_recorded"] is False


def test_unclean_never_counts_as_clean(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "u1")
    path = run / "events.jsonl"
    lines = path.read_bytes().splitlines(keepends=True)
    lines[6] = lines[6].replace(b"three", b"fours")
    path.write_bytes(b"".join(lines))
    m = _fold(run)
    assert m["integrity"]["clean"] is False
    assert m["status"]["state"] == "result_declared"
    assert m["status"]["counts_as_clean"] is False


def test_indexes(tmp_path: Path) -> None:
    m = _fold(build_fixture_record(tmp_path / "i1"))
    assert m["experiments"]["exp:1"]["used_by"] == ["pick:1:1"]
    assert m["experiments"]["exp:5"]["used_by"] == []
    it = m["iterations"]["it01"]
    assert it["purpose"] == "main" and it["outcome"] == "solutions" and it["count"] == 2
    assert m["artefacts"]["art:ranking:1"]["superseded_by"] is None
    assert m["rankings"]["rk01"]["artefact"] == "art:ranking:1"
    assert m["notes"] == 1


def test_supersession_marked() -> None:
    ev = {"seq": 1, "type": "x", "artefacts": [{"id": "art:a:1", "kind": "a", "path": "p"}]}
    ev2 = {
        "seq": 2,
        "type": "x",
        "artefacts": [{"id": "art:a:2", "kind": "a", "path": "q", "supersedes": "art:a:1"}],
    }
    m = fold([ev, ev2], {"clean": True})
    assert m["artefacts"]["art:a:1"]["superseded_by"] == "art:a:2"


def test_foreign_host_and_human_messages(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "f1")
    append_event(
        run,
        "prompt.submitted",
        {"text": "hello", "chars": 5, "auto": False},
        actor={"kind": "hook"},
        host="elsewhere",
        utc="2026-01-01T11:00:00.000Z",
    )
    m = _fold(run)
    assert m["foreign_host_events"] == 1
    assert m["writer_host"] == HOST
    assert m["human_messages"] == 1
    assert m["assisted"] is None
    assert _fold(build_fixture_record(tmp_path / "f2"))["assisted"] is False


def test_unknown_types_ignored() -> None:
    m = fold([{"seq": 1, "type": "future.thing", "payload": {}}], {"clean": True}, now=NOW)
    assert m["status"]["state"] in ("running", "no_heartbeat")


def test_rebuild_is_byte_stable(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "b1")
    write_heartbeat(run, "test")
    rebuild_manifest(run, now=NOW)
    first = (run / MANIFEST).read_bytes()
    rebuild_manifest(run, now=NOW)
    assert (run / MANIFEST).read_bytes() == first
    assert json.loads(first)["schema"] == "ailsa.run-manifest"
