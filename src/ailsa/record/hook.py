"""Claude Code hook entry point for the run record (standard library only).

Reads one hook payload from stdin and appends typed events to the run bound to this session
(launcher environment or session pointer; never through the cwd marker alone). Outside such a
run it does nothing. It never writes to stdout (stdout would be injected into the context) and
always exits 0 (exit 1 prints a notice, exit 2 blocks).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ailsa.record.events import COMMAND_CAP, FINISHED, HOOK_ERRORS, TEXT_CAP

MAX_STDIN = 1024 * 1024
WAITING_TYPES = ("permission_prompt", "idle_prompt", "agent_needs_input")
_COMMON_KEYS = frozenset(
    {
        "session_id",
        "transcript_path",
        "cwd",
        "permission_mode",
        "hook_event_name",
        "agent_id",
        "agent_type",
        "effort",
        "prompt_id",
        "background_tasks",
        "session_crons",
        "stop_hook_active",
        "tool_use_id",
    }
)
_KNOWN_KEYS: dict[str, frozenset[str]] = {
    "SessionStart": frozenset({"source", "model"}),
    "UserPromptSubmit": frozenset({"prompt"}),
    "Notification": frozenset({"notification_type", "message", "title"}),
    "PermissionRequest": frozenset({"tool_name", "tool_input", "permission_suggestions"}),
    "SubagentStart": frozenset(),
    "SubagentStop": frozenset({"agent_transcript_path", "last_assistant_message"}),
    "PostToolUse": frozenset({"tool_name", "tool_input", "tool_response"}),
    "PreCompact": frozenset({"trigger", "custom_instructions"}),
    "PostCompact": frozenset({"trigger", "compact_summary"}),
    "Stop": frozenset({"last_assistant_message"}),
    "StopFailure": frozenset({"error", "error_details", "last_assistant_message"}),
    "SessionEnd": frozenset({"reason"}),
    "PostModelSwitch": frozenset({"from_model", "to_model"}),
}

Mapped = tuple[str, dict[str, Any], dict[str, Any]]


def _cap(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text[:limit]


def _raw_keys(data: dict[str, Any], name: str) -> list[str]:
    known = _COMMON_KEYS | _KNOWN_KEYS.get(name, frozenset())
    return sorted(str(k) for k in data if k not in known)


def _text_of(tool_input: dict[str, Any]) -> str:
    for key in ("message", "content", "text"):
        value = tool_input.get(key)
        if isinstance(value, str):
            return value
    return ""


def _post_tool_use(data: dict[str, Any]) -> list[Mapped]:
    tool = data.get("tool_name")
    tool_input = data.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    response = data.get("tool_response")
    caller = data.get("agent_id") or "main"
    if tool == "Bash":
        blob = json.dumps(response, sort_keys=True, default=str).encode("utf-8")
        return [
            (
                "tool.shell",
                {
                    "command": _cap(tool_input.get("command", ""), COMMAND_CAP),
                    "response_bytes": len(blob),
                    "response_sha256": hashlib.sha256(blob).hexdigest(),
                },
                {},
            )
        ]
    if tool == "Agent":
        target = tool_input.get("subagent_type")
        resp = response if isinstance(response, dict) else {}
        out: list[Mapped] = [
            (
                "agent.message",
                {
                    "from": caller,
                    "to": target,
                    "kind": "task",
                    "text": _cap(tool_input.get("prompt", ""), TEXT_CAP),
                    "name": tool_input.get("name"),
                    "agent_id": resp.get("agentId"),
                },
                {},
            )
        ]
        actual = resp.get("resolvedModel")
        if not actual:
            used = resp.get("modelsUsed")
            if isinstance(used, list) and used:
                actual = used[0]
        requested = tool_input.get("model")
        if actual or requested:
            out.append(
                (
                    "agent.model_reported",
                    {
                        "agent": resp.get("agentId") or target or "unknown",
                        "requested": requested,
                        "actual": actual,
                        "source": "harness",
                    },
                    {},
                )
            )
        return out
    if tool == "SendMessage":
        return [
            (
                "agent.message",
                {
                    "from": caller,
                    "to": tool_input.get("to"),
                    "kind": "message",
                    "text": _cap(_text_of(tool_input), TEXT_CAP),
                },
                {},
            )
        ]
    if tool == "SubagentHandback":
        return [
            (
                "agent.message",
                {
                    "from": caller,
                    "to": tool_input.get("to") or "main",
                    "kind": "handback",
                    "text": _cap(_text_of(tool_input), TEXT_CAP),
                },
                {},
            )
        ]
    return []


def map_hook_event(data: dict[str, Any]) -> list[Mapped]:
    """Map one payload to (event type, payload, extra envelope fields)."""
    name = data.get("hook_event_name")
    if not isinstance(name, str):
        return []
    raw = _raw_keys(data, name)
    extra: dict[str, Any] = {}
    if data.get("agent_id"):
        extra["agent_id"] = data.get("agent_id")
    out: list[Mapped] = []
    if name == "SessionStart":
        model = data.get("model")
        out.append(("session.started", {"source": data.get("source"), "model": model}, extra))
        if model:
            out.append(
                (
                    "agent.model_reported",
                    {"agent": "main", "requested": None, "actual": model, "source": "harness"},
                    extra,
                )
            )
    elif name == "UserPromptSubmit":
        text = data.get("prompt")
        text = text if isinstance(text, str) else ""
        out.append(
            (
                "prompt.submitted",
                {"text": text[:TEXT_CAP], "chars": len(text), "auto": text.startswith("<")},
                extra,
            )
        )
    elif name == "Notification":
        kind = data.get("notification_type")
        if kind in WAITING_TYPES:
            out.append(
                (
                    "human.waiting",
                    {"notification_type": kind, "message": _cap(data.get("message", ""), TEXT_CAP)},
                    extra,
                )
            )
    elif name == "PermissionRequest":
        out.append(
            (
                "human.waiting",
                {
                    "notification_type": "permission_request",
                    "message": _cap(f"tool: {data.get('tool_name')}", TEXT_CAP),
                },
                extra,
            )
        )
    elif name == "SubagentStart":
        out.append(
            (
                "agent.spawned",
                {"agent_id": data.get("agent_id"), "agent_type": data.get("agent_type")},
                extra,
            )
        )
    elif name == "SubagentStop":
        path = data.get("agent_transcript_path")
        payload = {
            "agent_id": data.get("agent_id"),
            "agent_type": data.get("agent_type"),
            "transcript": os.path.basename(path) if isinstance(path, str) else None,
        }
        out.append(("agent.stopped", payload, extra))
    elif name == "PostToolUse":
        out.extend((t, p, {**extra, **e}) for t, p, e in _post_tool_use(data))
    elif name in ("PreCompact", "PostCompact"):
        stage = "pre" if name == "PreCompact" else "post"
        out.append(("context.compacted", {"trigger": data.get("trigger"), "stage": stage}, extra))
    elif name == "Stop":
        out.append(("agent.turn_ended", {"agent_id": data.get("agent_id") or "main"}, extra))
    elif name == "StopFailure":
        out.append(("run.paused", {"cause": data.get("error"), "detail": "StopFailure"}, extra))
    elif name == "SessionEnd":
        out.append(("session.ended", {"reason": data.get("reason")}, extra))
    elif name == "PostModelSwitch":
        out.append(
            (
                "model.switched",
                {"from_model": data.get("from_model"), "to_model": data.get("to_model")},
                extra,
            )
        )
    if raw and out:
        out[0][1]["raw_keys"] = raw
    return out


def _log_error(run_dir: Path | None, event: str, etype: str, exc: BaseException) -> None:
    if run_dir is None:
        return
    try:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        msg = str(exc).replace("\n", " ")[:300]
        with open(run_dir / HOOK_ERRORS, "a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {event} {etype}: {msg}\n")
    except Exception:
        pass


def _transcript_enabled() -> bool:
    if os.environ.get("AILSA_NO_TRANSCRIPT") == "1":
        return False
    from ailsa.record.workspace import load_config

    return load_config().get("transcript") is not False


def _bound_sessions(run_dir: Path) -> set[str]:
    """Session ids the record binds to the run (launcher, ``run init``, rebinding hooks)."""
    from ailsa.record.log import read_events

    found: set[str] = set()
    for ev in read_events(run_dir)["events"]:
        payload = ev.get("payload")
        if ev.get("type") == "run.bound" and isinstance(payload, dict):
            sid = payload.get("session_id")
            if isinstance(sid, str) and sid:
                found.add(sid)
    return found


def _bound_run(session_id: Any, cwd: Any) -> Path | None:
    """The run this hook may record into, or None.

    Only a session bound to a run records into it: through the launcher's environment or the
    session pointer that ``ailsa run init`` (or a rebinding SessionStart) wrote. A session that
    merely runs inside a run folder (cwd marker) never does. A finished run takes the
    remaining hook events only of a session its record shows as bound.
    """
    from ailsa.record.resolve import find_active_run

    sid = session_id if isinstance(session_id, str) else None
    ref = find_active_run(session_id=sid, cwd=Path(cwd) if isinstance(cwd, str) and cwd else None)
    if ref is None or ref.via not in ("env", "session"):
        return None
    if (ref.run_dir / FINISHED).exists():
        if sid is None or sid not in _bound_sessions(ref.run_dir):
            return None
    return ref.run_dir


def _run(data: dict[str, Any]) -> None:
    from ailsa.record.log import append_event, write_heartbeat
    from ailsa.record.resolve import RUN_DIR_ENV, bind_session
    from ailsa.record.workspace import workspace_root

    name = data.get("hook_event_name")
    if not isinstance(name, str):
        return
    session_id = data.get("session_id")
    found = _bound_run(session_id, data.get("cwd"))
    if found is None:
        return
    run_dir = found
    try:
        if not (run_dir / FINISHED).exists():
            # A finished run's heartbeat stays as it was at the close (manifest unchanged).
            write_heartbeat(run_dir, name)
        actor_base = {"kind": "hook", "name": name}
        if (
            name == "SessionStart"
            and data.get("source") in ("clear", "resume", "fork")
            and os.environ.get(RUN_DIR_ENV)
            and isinstance(session_id, str)
        ):
            if bind_session(workspace_root(create=False), session_id, run_dir):
                try:
                    append_event(
                        run_dir,
                        "run.bound",
                        {
                            "session_id": session_id,
                            "harness": "claude-code",
                            "via": "session_start",
                        },
                        actor=actor_base,
                    )
                except Exception as exc:
                    _log_error(run_dir, name, "run.bound", exc)
        for etype, payload, extra in map_hook_event(data):
            try:
                append_event(
                    run_dir,
                    etype,
                    payload,
                    actor={**actor_base, "agent_id": extra.get("agent_id")},
                    allow_after_finish=True,  # stragglers of the bound session (checked above)
                )
            except Exception as exc:
                _log_error(run_dir, name, etype, exc)
        if name == "SessionEnd" and _transcript_enabled():
            try:
                from ailsa.record.transcript import copy_transcripts

                tp = data.get("transcript_path")
                copy_transcripts(
                    run_dir,
                    tp if isinstance(tp, str) else None,
                    session_id if isinstance(session_id, str) else None,
                    via="session_end",
                )
            except Exception as exc:
                _log_error(run_dir, name, "transcript.copied", exc)
    except Exception as exc:
        _log_error(run_dir, name, "hook", exc)


def _log_bad_input(exc: BaseException) -> None:
    from ailsa.record.resolve import find_active_run

    ref = find_active_run()
    if ref is not None and ref.via in ("env", "session"):
        _log_error(ref.run_dir, "unknown", "input", exc)


def main() -> None:
    try:
        if sys.argv[1:2] == ["frontmatter"] and os.environ.get("AILSA_HOOKS_VIA_SETTINGS") == "1":
            return
        raw = sys.stdin.buffer.read(MAX_STDIN)
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except ValueError as exc:
            _log_bad_input(exc)
            return
        if isinstance(data, dict) and isinstance(data.get("hook_event_name"), str):
            _run(data)
        else:
            _log_bad_input(ValueError("payload without hook_event_name"))
    except BaseException:
        pass
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
