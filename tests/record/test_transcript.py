"""Transcript copy into the run folder (REC-27)."""

from __future__ import annotations

from pathlib import Path

from ailsa.record.log import append_event, read_events
from ailsa.record.transcript import copy_transcripts, find_session_transcript

FIX = Path(__file__).parent / "fixtures" / "transcripts"
SID = "11111111-1111-4111-8111-111111111111"


def build_projects(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    proj = root / "some-project"
    (proj / SID / "subagents").mkdir(parents=True)
    (proj / f"{SID}.jsonl").write_bytes((FIX / "main.jsonl").read_bytes())
    (proj / SID / "subagents" / "agent-a.jsonl").write_bytes((FIX / "subagent.jsonl").read_bytes())
    (proj / SID / "subagents" / "agent-a.meta.json").write_bytes(
        (FIX / "subagent.meta.json").read_bytes()
    )
    (proj / SID / "subagents" / "notes.txt").write_text("ignored")
    return root


def events(run: Path, type: str) -> list[dict]:
    return [e for e in read_events(run)["events"] if e["type"] == type]


def test_find_session_transcript(tmp_path):
    root = build_projects(tmp_path)
    assert find_session_transcript(SID, root) == root / "some-project" / f"{SID}.jsonl"
    assert find_session_transcript("../etc/passwd", root) is None
    assert find_session_transcript(None, root) is None
    assert find_session_transcript("22222222-2222-4222-8222-222222222222", root) is None


def test_find_uses_env_root(tmp_path, monkeypatch):
    root = build_projects(tmp_path)
    monkeypatch.setenv("AILSA_CLAUDE_PROJECTS", str(root))
    assert find_session_transcript(SID) is not None


def test_copy_all_and_idempotent(new_run, tmp_path):
    _, run = new_run
    root = build_projects(tmp_path)
    main = root / "some-project" / f"{SID}.jsonl"
    files = copy_transcripts(run, main, SID, via="session_end")
    assert {f["name"] for f in files} == {
        f"{SID}.jsonl",
        "subagents/agent-a.jsonl",
        "subagents/agent-a.meta.json",
    }
    assert all(len(f["sha256"]) == 64 and f["bytes"] > 0 for f in files)
    assert (run / "transcript" / "subagents" / "agent-a.meta.json").is_file()
    (ev,) = events(run, "transcript.copied")
    assert ev["payload"]["via"] == "session_end" and ev["actor"]["kind"] == "hook"
    assert copy_transcripts(run, main, SID, via="finalize") == []
    assert len(events(run, "transcript.copied")) == 1


def test_changed_file_copied_again(new_run, tmp_path):
    _, run = new_run
    root = build_projects(tmp_path)
    main = root / "some-project" / f"{SID}.jsonl"
    copy_transcripts(run, main, SID, via="session_end")
    with open(main, "ab") as fh:
        fh.write(b'{"type":"assistant"}\n')
    files = copy_transcripts(run, main, SID, via="finalize")
    assert [f["name"] for f in files] == [f"{SID}.jsonl"]
    assert (run / "transcript" / f"{SID}.jsonl").read_bytes() == main.read_bytes()
    assert len(events(run, "transcript.copied")) == 2


def test_path_resolved_from_session_id(new_run, tmp_path, monkeypatch):
    _, run = new_run
    monkeypatch.setenv("AILSA_CLAUDE_PROJECTS", str(build_projects(tmp_path)))
    files = copy_transcripts(run, None, SID, via="launcher")
    assert len(files) == 3
    assert events(run, "transcript.copied")[0]["actor"]["kind"] == "launcher"


def test_missing_source_is_quiet(new_run, tmp_path):
    _, run = new_run
    assert copy_transcripts(run, tmp_path / "nope.jsonl", None, via="session_end") == []
    assert not events(run, "transcript.copied")


def test_symlinks_skipped(new_run, tmp_path):
    _, run = new_run
    root = build_projects(tmp_path)
    sub = root / "some-project" / SID / "subagents"
    secret = tmp_path / "secret.jsonl"
    secret.write_text("secret")
    (sub / "agent-link.jsonl").symlink_to(secret)
    main = root / "some-project" / f"{SID}.jsonl"
    files = copy_transcripts(run, main, SID, via="session_end")
    assert "subagents/agent-link.jsonl" not in {f["name"] for f in files}
    assert not (run / "transcript" / "subagents" / "agent-link.jsonl").exists()
    link_main = tmp_path / "linked.jsonl"
    link_main.symlink_to(main)
    assert copy_transcripts(run, link_main, None, via="x") == []


def test_symlinked_transcript_folder_is_refused(new_run, tmp_path):
    """WR-03: a transcript/ symlink placed in the run never receives the copies."""
    _, run = new_run
    root = build_projects(tmp_path)
    elsewhere = tmp_path / "dataset"
    elsewhere.mkdir()
    (run / "transcript").symlink_to(elsewhere, target_is_directory=True)
    main = root / "some-project" / f"{SID}.jsonl"
    assert copy_transcripts(run, main, SID, via="session_end") == []
    assert list(elsewhere.iterdir()) == []
    warned = events(run, "warning.raised")
    assert warned and warned[0]["payload"]["code"] == "transcript_path_refused"


def test_size_cap_warns(new_run, tmp_path):
    _, run = new_run
    root = build_projects(tmp_path)
    main = root / "some-project" / f"{SID}.jsonl"
    size = main.stat().st_size
    files = copy_transcripts(run, main, SID, via="session_end", max_total=size + 10)
    assert [f["name"] for f in files] == [f"{SID}.jsonl"]
    (w,) = events(run, "warning.raised")
    assert w["payload"]["code"] == "transcript_size_cap"


def test_copy_after_finish_still_recorded(new_run, tmp_path):
    _, run = new_run
    append_event(
        run, "run.finished", {"state": "done", "reason": "t"}, actor={"kind": "tool"}
    )
    root = build_projects(tmp_path)
    main = root / "some-project" / f"{SID}.jsonl"
    copy_transcripts(run, main, SID, via="session_end")
    (ev,) = events(run, "transcript.copied")
    assert ev["after_finish"] is True
