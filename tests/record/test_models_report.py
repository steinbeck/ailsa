"""Requested vs actual model per agent, with source (REC-25)."""

from __future__ import annotations

import json
from pathlib import Path

from ailsa.record.fold import fold
from ailsa.record.hook import map_hook_event
from ailsa.record.log import append_event, read_events
from ailsa.record.transcript import models_from_transcript, record_transcript_models

FIX = Path(__file__).parent / "fixtures"


def reports(run: Path) -> list[dict]:
    return [
        e["payload"] for e in read_events(run)["events"] if e["type"] == "agent.model_reported"
    ]


def test_models_from_fixtures():
    (main,) = models_from_transcript(FIX / "transcripts" / "main.jsonl")
    assert main == {"agent": "main", "requested": "claude-haiku-5-5", "actual": "claude-haiku-5-5"}
    (sub,) = models_from_transcript(FIX / "transcripts" / "subagent.jsonl")
    assert sub["agent"] == "agent-sub-0001" and sub["actual"] == "claude-haiku-5-5"


def test_models_from_missing_or_garbage(tmp_path):
    assert models_from_transcript(tmp_path / "none.jsonl") == []
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n[1]\n{}\n")
    assert models_from_transcript(bad) == []


def test_record_transcript_models_once_per_agent(new_run):
    _, run = new_run
    files = [FIX / "transcripts" / "main.jsonl", FIX / "transcripts" / "subagent.jsonl"]
    assert record_transcript_models(run, files) == 2
    assert record_transcript_models(run, files) == 0
    got = reports(run)
    assert {r["agent"] for r in got} == {"main", "agent-sub-0001"}
    assert all(r["source"] == "transcript" for r in got)


def test_hook_report_from_agent_tool():
    data = json.loads((FIX / "hooks" / "post_tool_use_agent.json").read_text())
    reps = [p for t, p, _ in map_hook_event(data) if t == "agent.model_reported"]
    assert reps == [
        {
            "agent": "agent-sub-0001",
            "requested": "haiku",
            "actual": "claude-haiku-5-5",
            "source": "harness",
        }
    ]


def test_all_sources_kept_per_agent(new_run):
    _, run = new_run
    actor = {"kind": "agent", "name": "x"}
    for source, actual in (("harness", "m-h"), ("self-report", "m-s")):
        append_event(
            run,
            "agent.model_reported",
            {"agent": "main", "requested": "alias", "actual": actual, "source": source},
            actor=actor,
        )
    record_transcript_models(run, [FIX / "transcripts" / "main.jsonl"])
    read = read_events(run)
    manifest = fold(read["events"], read["integrity"])
    agent = manifest["agents"]["main"]
    assert [r["source"] for r in agent["reports"]] == ["harness", "self-report", "transcript"]
