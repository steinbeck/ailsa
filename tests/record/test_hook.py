"""Hook entry point: payload mapping, no-op outside runs, silence, start cost."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ailsa.record.events import COMMAND_CAP, HEARTBEAT, HOOK_ERRORS, TEXT_CAP
from ailsa.record.hook import map_hook_event
from ailsa.record.hooksettings import handler
from ailsa.record.log import append_event, read_events
from ailsa.record.resolve import bind_session

FIX = Path(__file__).parent / "fixtures" / "hooks"


def load(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def run_hook(
    payload: str | dict,
    run_dir: Path | None,
    tmp_path: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AILSA_", "CLAUDE_CODE"))}
    env["AILSA_WORKSPACE"] = str(tmp_path / "ws")
    env["AILSA_CONFIG"] = str(tmp_path / "config.json")
    env["HOME"] = str(tmp_path / "home")
    if run_dir is not None:
        env["AILSA_RUN_DIR"] = str(run_dir)
    env.update(extra_env or {})
    text = payload if isinstance(payload, str) else json.dumps(payload)
    hook = handler(sys.executable)  # the exact command the settings install
    return subprocess.run(
        [hook["command"], *hook["args"], *args],
        input=text,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd or tmp_path,
        timeout=30,
    )


def events_of(run_dir: Path, type: str | None = None) -> list[dict]:
    evs = read_events(run_dir)["events"]
    return [e for e in evs if type is None or e["type"] == type]


def test_session_start_startup(new_run, tmp_path):
    _, run = new_run
    r = run_hook(load("session_start"), run, tmp_path)
    assert r.returncode == 0 and r.stdout == ""
    (ev,) = events_of(run, "session.started")
    assert ev["payload"]["source"] == "startup"
    assert ev["actor"]["kind"] == "hook" and ev["actor"]["name"] == "SessionStart"
    assert ev["after_finish"] is False  # true only after run.finished (CR-05)
    assert (run / HEARTBEAT).is_file()
    assert not events_of(run, "agent.model_reported")


def test_session_start_compact_reports_model(new_run, tmp_path):
    _, run = new_run
    data = {**load("session_start"), "source": "compact", "model": "claude-haiku-5-5"}
    run_hook(data, run, tmp_path)
    (rep,) = events_of(run, "agent.model_reported")
    assert rep["payload"] == {
        "agent": "main",
        "requested": None,
        "actual": "claude-haiku-5-5",
        "source": "harness",
    }


def test_prompt_submitted_capped_and_auto(new_run, tmp_path):
    _, run = new_run
    data = {**load("user_prompt_submit"), "prompt": "<task-notification>" + "x" * 6000}
    run_hook(data, run, tmp_path)
    (ev,) = events_of(run, "prompt.submitted")
    assert len(ev["payload"]["text"]) == TEXT_CAP
    assert ev["payload"]["chars"] == 6000 + len("<task-notification>")
    assert ev["payload"]["auto"] is True
    run_hook(load("user_prompt_submit"), run, tmp_path)
    assert events_of(run, "prompt.submitted")[-1]["payload"]["auto"] is False


def test_notification_and_permission_request(new_run, tmp_path):
    _, run = new_run
    base = {"session_id": "11111111-1111-4111-8111-111111111111", "cwd": "/RUN"}
    note = {**base, "hook_event_name": "Notification", "notification_type": "permission_prompt"}
    run_hook({**note, "message": "needs ok"}, run, tmp_path)
    run_hook({**note, "notification_type": "auth_success"}, run, tmp_path)
    perm = {**base, "hook_event_name": "PermissionRequest", "tool_name": "Bash"}
    run_hook(perm, run, tmp_path)
    waits = events_of(run, "human.waiting")
    assert [w["payload"]["notification_type"] for w in waits] == [
        "permission_prompt",
        "permission_request",
    ]
    assert "Bash" in waits[1]["payload"]["message"]


def test_subagent_start_stop(new_run, tmp_path):
    _, run = new_run
    run_hook(load("subagent_start"), run, tmp_path)
    run_hook(load("subagent_stop"), run, tmp_path)
    (sp,) = events_of(run, "agent.spawned")
    (st,) = events_of(run, "agent.stopped")
    assert sp["payload"] == {"agent_id": "agent-sub-0001", "agent_type": "general-purpose"}
    assert sp["actor"]["agent_id"] == "agent-sub-0001"
    assert st["payload"]["transcript"] == "agent-sub-0001.jsonl"
    assert "/" not in json.dumps(st["payload"]["transcript"])


def test_bash_tool_shell(new_run, tmp_path):
    _, run = new_run
    data = load("post_tool_use_bash")
    data["tool_input"]["command"] = "echo " + "y" * 5000
    run_hook(data, run, tmp_path)
    (ev,) = events_of(run, "tool.shell")
    assert len(ev["payload"]["command"]) == COMMAND_CAP
    assert ev["payload"]["response_bytes"] > 0
    assert len(ev["payload"]["response_sha256"]) == 64
    assert "stdout" not in json.dumps(ev["payload"])


def test_agent_tool_message_and_model(new_run, tmp_path):
    _, run = new_run
    run_hook(load("post_tool_use_agent"), run, tmp_path)
    (msg,) = events_of(run, "agent.message")
    assert msg["payload"]["kind"] == "task"
    assert msg["payload"]["from"] == "main"
    assert msg["payload"]["to"] == "general-purpose"
    (rep,) = events_of(run, "agent.model_reported")
    assert rep["payload"]["requested"] == "haiku"
    assert rep["payload"]["actual"] == "claude-haiku-5-5"
    assert rep["payload"]["source"] == "harness"


def test_send_message(new_run, tmp_path):
    _, run = new_run
    run_hook(load("send_message"), run, tmp_path)
    (ev,) = events_of(run, "agent.message")
    assert ev["payload"]["kind"] == "message"
    assert ev["payload"]["to"] == "agent-sub-0001"
    assert ev["payload"]["text"] == "thanks"


def test_handback_and_models_used():
    data = {
        "hook_event_name": "PostToolUse",
        "tool_name": "SubagentHandback",
        "agent_id": "agent-x",
        "tool_input": {"message": "report"},
    }
    ((t, p, _),) = map_hook_event(data)
    assert t == "agent.message" and p["kind"] == "handback" and p["from"] == "agent-x"
    agent = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "s", "prompt": "p"},
        "tool_response": {"modelsUsed": ["m1", "m2"]},
    }
    out = map_hook_event(agent)
    assert out[1][1]["actual"] == "m1"


def test_compact_stop_end(new_run, tmp_path):
    _, run = new_run
    for name in ("pre_compact", "post_compact", "stop", "session_end"):
        run_hook(load(name), run, tmp_path, extra_env={"AILSA_NO_TRANSCRIPT": "1"})
    stages = [e["payload"]["stage"] for e in events_of(run, "context.compacted")]
    assert stages == ["pre", "post"]
    assert events_of(run, "agent.turn_ended")[0]["payload"]["agent_id"] == "main"
    assert events_of(run, "session.ended")[0]["payload"]["reason"] == "other"
    assert not events_of(run, "transcript.copied")


def test_stop_failure_and_model_switch():
    ((t, p, _),) = map_hook_event({"hook_event_name": "StopFailure", "error": "rate_limit"})
    assert t == "run.paused" and p["cause"] == "rate_limit"
    ((t, p, _),) = map_hook_event(
        {"hook_event_name": "PostModelSwitch", "from_model": "a", "to_model": "b"}
    )
    assert t == "model.switched" and p["to_model"] == "b"


def test_unknown_keys_become_raw_keys():
    data = {**load("session_start"), "brand_new": {"secret": 1}}
    ((_, payload, _),) = map_hook_event(data)
    assert payload["raw_keys"] == ["brand_new"]
    assert "secret" not in json.dumps(payload)


def test_session_end_copies_transcripts(new_run, tmp_path):
    _, run = new_run
    sid = "11111111-1111-4111-8111-111111111111"
    proj = tmp_path / "proj"
    shutil_copy(FIX.parent / "transcripts" / "main.jsonl", proj / f"{sid}.jsonl")
    shutil_copy(
        FIX.parent / "transcripts" / "subagent.jsonl", proj / sid / "subagents" / "agent-1.jsonl"
    )
    data = {**load("session_end"), "transcript_path": str(proj / f"{sid}.jsonl")}
    run_hook(data, run, tmp_path)
    (ev,) = events_of(run, "transcript.copied")
    assert ev["payload"]["via"] == "session_end"
    assert (run / "transcript" / f"{sid}.jsonl").is_file()
    assert (run / "transcript" / "subagents" / "agent-1.jsonl").is_file()


def shutil_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def test_config_transcript_false(new_run, tmp_path):
    _, run = new_run
    (tmp_path / "config.json").write_text('{"transcript": false}')
    sid = "11111111-1111-4111-8111-111111111111"
    shutil_copy(FIX.parent / "transcripts" / "main.jsonl", tmp_path / f"{sid}.jsonl")
    data = {**load("session_end"), "transcript_path": str(tmp_path / f"{sid}.jsonl")}
    run_hook(data, run, tmp_path)
    assert events_of(run, "session.ended") and not events_of(run, "transcript.copied")


def test_noop_outside_run(tmp_path):
    r = run_hook(load("session_start"), None, tmp_path)
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert not (tmp_path / "ws").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_garbage_input(new_run, tmp_path):
    _, run = new_run
    for text in ("{not json", "", "[1,2]", json.dumps({"x": 1})):
        r = run_hook(text, run, tmp_path)
        assert r.returncode == 0 and r.stdout == ""
    lines = (run / HOOK_ERRORS).read_text().splitlines()
    assert len(lines) == 4
    assert not events_of(run)


def test_rebind_on_resume(new_run, tmp_path):
    _, run = new_run
    data = {**load("session_start"), "source": "resume"}
    run_hook(data, run, tmp_path)
    (ev,) = events_of(run, "run.bound")
    assert ev["payload"]["via"] == "session_start"
    pointer = tmp_path / "ws" / ".sessions" / data["session_id"]
    assert pointer.is_file() or any((tmp_path / "ws").rglob(data["session_id"]))


def test_frontmatter_arg_skipped_in_launcher_runs(new_run, tmp_path):
    _, run = new_run
    r = run_hook(
        load("stop"), run, tmp_path, "frontmatter", extra_env={"AILSA_HOOKS_VIA_SETTINGS": "1"}
    )
    assert r.returncode == 0 and not events_of(run, "agent.turn_ended")
    run_hook(load("stop"), run, tmp_path, "frontmatter")
    assert len(events_of(run, "agent.turn_ended")) == 1


def test_start_time_and_imports(tmp_path):
    code = (
        "import sys, json\n"
        "import ailsa.record.hook\n"
        "bad = [m for m in ('pydantic','numpy','rdkit','click') if m in sys.modules]\n"
        "print(json.dumps(bad))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert json.loads(r.stdout) == []
    run_hook(load("stop"), None, tmp_path)  # warm file caches
    t0 = time.monotonic()
    run_hook(load("stop"), None, tmp_path)
    assert time.monotonic() - t0 < 0.5


@pytest.mark.parametrize("name", ["stop", "subagent_start"])
def test_never_stdout(new_run, tmp_path, name):
    _, run = new_run
    assert run_hook(load(name), run, tmp_path).stdout == ""


def test_planted_module_in_working_folder_is_not_imported(new_run, tmp_path):
    """CR-01: the hook command never puts the session's folder on sys.path."""
    _, run = new_run
    project = tmp_path / "project"
    project.mkdir()
    marker = tmp_path / "planted-module-ran"
    (project / "json.py").write_text(f"open({str(marker)!r}, 'w').close()\n", encoding="utf-8")
    r = run_hook(load("stop"), run, tmp_path, cwd=project)
    assert r.returncode == 0
    assert not marker.exists()
    assert len(events_of(run, "agent.turn_ended")) == 1


# --- CR-05: only the session bound to a run records into it -----------------------------------

FIXTURE_SID = "11111111-1111-4111-8111-111111111111"
OTHER_SID = "22222222-2222-4222-8222-222222222222"
TOOL = {"kind": "tool", "name": "test"}


def _finish(run: Path) -> None:
    append_event(run, "run.finished", {"state": "stopped_before_result", "reason": "t"}, actor=TOOL)


def _bind_in_record(run: Path, sid: str) -> None:
    append_event(run, "run.bound", {"session_id": sid, "harness": "x", "via": "init"}, actor=TOOL)


@pytest.mark.parametrize("finished", [False, True])
def test_cwd_marker_alone_never_records(new_run, tmp_path, finished):
    """A session opened inside a run folder (e.g. to inspect it) writes nothing into the run."""
    _, run = new_run
    if finished:
        _finish(run)
    before = (run / "events.jsonl").read_bytes() if finished else b""
    agent = run / "agent"
    for name in ("session_start", "user_prompt_submit", "stop", "session_end"):
        data = {**load(name), "cwd": str(agent)}
        assert run_hook(data, None, tmp_path, cwd=agent).returncode == 0
    if finished:
        assert (run / "events.jsonl").read_bytes() == before
    else:
        assert events_of(run) == []
    assert not (run / HEARTBEAT).exists()
    assert not (run / "transcript").exists()


def test_session_pointer_binding_records(new_run, tmp_path):
    """The open-session path: ailsa run init wrote the pointer for this session id."""
    _, run = new_run
    assert bind_session(tmp_path / "ws", FIXTURE_SID, run)
    run_hook(load("user_prompt_submit"), None, tmp_path)
    (ev,) = events_of(run, "prompt.submitted")
    assert ev["after_finish"] is False
    other = {**load("user_prompt_submit"), "session_id": OTHER_SID}
    run_hook(other, None, tmp_path)
    assert len(events_of(run, "prompt.submitted")) == 1


def test_finished_run_refuses_unbound_session(new_run, tmp_path):
    _, run = new_run
    _bind_in_record(run, FIXTURE_SID)
    _finish(run)
    other = {**load("user_prompt_submit"), "session_id": OTHER_SID}
    run_hook(other, run, tmp_path)
    run_hook({**load("session_end"), "session_id": OTHER_SID}, run, tmp_path)
    assert not events_of(run, "prompt.submitted") and not events_of(run, "session.ended")


def test_finished_run_takes_bound_session_stragglers(new_run, tmp_path):
    _, run = new_run
    _bind_in_record(run, FIXTURE_SID)
    run_hook(load("stop"), run, tmp_path)
    _finish(run)
    run_hook(load("session_end"), run, tmp_path)
    (turn,) = events_of(run, "agent.turn_ended")
    (end,) = events_of(run, "session.ended")
    assert turn["after_finish"] is False and end["after_finish"] is True


def test_finished_run_heartbeat_is_left_alone(new_run, tmp_path):
    """WR-10: a straggler hook after the close does not rewrite heartbeat.json."""
    _, run = new_run
    _bind_in_record(run, FIXTURE_SID)
    run_hook(load("stop"), run, tmp_path)
    before = (run / HEARTBEAT).read_bytes()
    _finish(run)
    run_hook(load("session_end"), run, tmp_path)
    assert events_of(run, "session.ended")
    assert (run / HEARTBEAT).read_bytes() == before
