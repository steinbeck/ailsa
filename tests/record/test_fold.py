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


def test_transcript_model_reports_are_not_hook_evidence(tmp_path: Path) -> None:
    """WR-09: a hook-less run whose transcript models were read still shows hooks absent."""
    from ailsa.record.transcript import record_transcript_models

    run = build_fixture_record(tmp_path / "rh", hooks=False)
    transcript = tmp_path / "t.jsonl"
    line = {"type": "assistant", "message": {"model": "m-actual"}, "requestedModel": "m"}
    transcript.write_text(json.dumps(line) + "\n")
    assert record_transcript_models(run, [transcript]) == 1
    # Records written before the fix stamped the transcript's report with actor kind "hook".
    append_event(
        run,
        "agent.model_reported",
        {"agent": "sub", "requested": None, "actual": "m", "source": "transcript"},
        actor={"kind": "hook", "name": "transcript"},
        allow_after_finish=True,
    )
    m = _fold(run)
    assert m["harness"]["hooks_recorded"] is False


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


def test_events_after_finish_change_no_classification(tmp_path: Path) -> None:
    """CR-05: post-finish hook events never count as human messages, hook counts or the end."""
    run = build_fixture_record(tmp_path / "pf", base_utc="2026-01-01T10:00:00.000Z")
    append_event(
        run,
        "run.finished",
        {"state": "result_declared", "reason": "closed"},
        actor={"kind": "tool", "name": "t"},
        utc="2026-01-01T10:30:00.000Z",
    )
    before = _fold(run)
    hook = {"kind": "hook", "name": "UserPromptSubmit"}
    for text in ("first look", "second look"):
        ev = append_event(
            run,
            "prompt.submitted",
            {"text": text, "chars": len(text), "auto": False},
            actor=hook,
            allow_after_finish=True,
            utc="2026-01-01T11:00:00.000Z",
        )
        assert ev["after_finish"] is True
    append_event(
        run,
        "session.ended",
        {"reason": "other"},
        actor={"kind": "hook", "name": "SessionEnd"},
        allow_after_finish=True,
        utc="2026-01-01T11:05:00.000Z",
    )
    after = _fold(run)
    assert after["human_messages"] == before["human_messages"] == 0
    assert after["assisted"] is before["assisted"] is False
    assert after["harness"]["hook_counts"] == before["harness"]["hook_counts"]
    assert after["status"]["ended_utc"] == before["status"]["ended_utc"]
    assert after["status"]["state"] == before["status"]["state"]
    # WR-10: the manifest ends at run.finished (only the log's length and head move).
    for m in (before, after):
        m["integrity"].pop("events")
        m["integrity"].pop("head")
    assert after == before


def test_session_end_mid_run_is_not_the_end(tmp_path: Path) -> None:
    """WR-10: /clear ends a session, the run goes on in a new one: not 'stopped'."""
    run = _open_run(tmp_path)
    hook = {"kind": "hook", "name": "SessionEnd"}
    append_event(run, "session.ended", {"reason": "clear"}, actor=hook,
                 utc="2026-01-01T11:58:00.000Z")
    late = {"kind": "hook", "name": "PostToolUse"}
    append_event(run, "tool.shell", {"command": "ls", "response_bytes": 0,
                                     "response_sha256": ""}, actor=late,
                 utc="2026-01-01T11:58:01.000Z")
    assert _fold(run)["status"]["state"] == "stopped_before_result"
    append_event(run, "session.started", {"source": "clear", "model": None},
                 actor={"kind": "hook", "name": "SessionStart"}, utc="2026-01-01T11:59:00.000Z")
    m = _fold(run)
    assert m["status"]["state"] == "running" and m["status"]["ended_utc"] is None


def test_unexpected_payload_types_are_anomalies_not_crashes(tmp_path: Path) -> None:
    """CR-07: fold skips an event of unexpected shape with a warning; readers keep working."""
    from click.testing import CliRunner

    from ailsa.cli.run import run as run_cli
    from ailsa.record.render import render_run

    run = build_fixture_record(tmp_path / "odd")
    tool = {"kind": "tool", "name": "t"}
    append_event(run, "spectra.scanned", {"experiments": 3, "unreadable": 0}, actor=tool)
    append_event(run, "note.added", {"text": "x", "sender": "t"}, actor=tool, utc=12345)  # type: ignore[arg-type]
    m = _fold(run, heartbeat={"utc": 7})
    anomalies = [w for w in m["warnings"] if w.startswith("record_anomaly:")]
    assert len(anomalies) == 1 and "spectra.scanned" in anomalies[0]
    assert "experiments is a int, not a list" in anomalies[0]
    assert m["experiments"]["exp:1"]["kind"] == "13C"  # the well-formed scan still counts
    assert m["status"]["state"] == "result_declared"
    rebuild_manifest(run, now=NOW)
    render_run(run)
    res = CliRunner().invoke(run_cli, ["status", "--run", str(run)])
    assert res.exit_code == 0, res.output


def test_non_dict_events_and_artefacts_are_skipped() -> None:
    events = [
        "not an event",
        {"seq": 1, "type": ["odd"], "payload": {}},
        {"seq": 2, "type": "note.added", "payload": {}, "artefacts": 5},
    ]
    m = fold(events, {"clean": False}, now=NOW)  # type: ignore[arg-type]
    assert m["notes"] == 0  # the event with the odd artefacts field was not fully read
    assert any("artefacts is a int" in w for w in m["warnings"])


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


def _rep(seq: int, agent: str, source: str, actual: str = "m-actual", requested=None) -> dict:
    return {
        "seq": seq,
        "type": "agent.model_reported",
        "payload": {"agent": agent, "requested": requested, "actual": actual, "source": source},
    }


def _spawn(seq: int, aid: str, atype: str) -> dict:
    return {"seq": seq, "type": "agent.spawned", "payload": {"agent_id": aid, "agent_type": atype}}


def _fold_events(events: list[dict]) -> dict:
    return fold(events, {"clean": True}, now=NOW)


def test_three_sources_join_one_agent_entry() -> None:
    m = _fold_events(
        [
            _spawn(1, "a1b2c3", "ailsa-nmr-chemist"),
            _rep(2, "a1b2c3", "harness"),
            _rep(3, "ailsa-nmr-chemist", "self-report", actual="m-claimed"),
            _rep(4, "a1b2c3", "transcript"),
        ]
    )
    assert "ailsa-nmr-chemist" not in m["agents"]
    entry = m["agents"]["a1b2c3"]
    assert [r["source"] for r in entry["reports"]] == ["harness", "self-report", "transcript"]
    assert entry["source"] == "transcript" and entry["actual"] == "m-actual"


def test_self_report_joins_by_teammate_name() -> None:
    msg = {
        "seq": 2,
        "type": "agent.message",
        "payload": {
            "from": "main",
            "to": "t",
            "kind": "task",
            "text": "x",
            "name": "nmr-chemist",
            "agent_id": "a1b2c3",
        },
    }
    m = _fold_events([_spawn(1, "a1b2c3", "other"), msg, _rep(3, "nmr-chemist", "self-report")])
    assert list(m["agents"]) == ["a1b2c3"]
    assert m["agents"]["a1b2c3"]["reports"][0]["source"] == "self-report"


def test_self_report_joins_by_type_prefix() -> None:
    m = _fold_events(
        [_spawn(1, "a1b2c3", "ailsa-lsd-engineer"), _rep(2, "lsd-engineer", "self-report")]
    )
    assert list(m["agents"]) == ["a1b2c3"]


def test_coordinator_alias_joins_main() -> None:
    m = _fold_events([_rep(1, "main", "launcher"), _rep(2, "coordinator", "self-report")])
    assert list(m["agents"]) == ["main"]
    assert len(m["agents"]["main"]["reports"]) == 2


def test_repeated_spawn_joins_most_recent() -> None:
    m = _fold_events(
        [
            _spawn(1, "h1", "ailsa-nmr-chemist"),
            _spawn(2, "h2", "ailsa-nmr-chemist"),
            _rep(3, "ailsa-nmr-chemist", "self-report"),
        ]
    )
    assert m["agents"]["h2"]["reports"] and not m["agents"]["h1"]["reports"]


def test_unknown_sender_keeps_own_key() -> None:
    m = _fold_events([_rep(1, "stranger", "self-report")])
    assert list(m["agents"]) == ["stranger"]


def test_self_report_does_not_override_harness_headline() -> None:
    m = _fold_events(
        [
            _spawn(1, "h1", "t"),
            _rep(2, "h1", "harness", actual="m-actual", requested="m-req"),
            _rep(3, "h1", "self-report", actual="m-claimed"),
        ]
    )
    e = m["agents"]["h1"]
    assert (e["actual"], e["source"], e["requested"]) == ("m-actual", "harness", "m-req")
