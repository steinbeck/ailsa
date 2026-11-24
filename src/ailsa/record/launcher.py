"""The launcher: ``ailsa run start`` (D-05, REC-24, REC-25, REC-27, REC-33).

Creates the run, writes per-run hook settings, installs the lean skill into the run's work
folder and starts the harness there. The launcher waits for it, enforces the time limit, copies
the transcripts and always ends the run: the record is closed and rendered whatever the
harness did. Standard library only (plus the record modules).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ailsa.record.events import AGENT_DIR, ARGV_ITEM_CAP, HOOKS_SETTINGS
from ailsa.record.fsutil import atomic_write_json
from ailsa.record.log import append_event

SKILL_NAME = "ailsa-lite"
# Plan 02 spike answer A8: a slash prompt invokes a project skill in `claude -p`.
SLASH_PROMPT_WORKS = True
KILL_GRACE_S = 10
HARNESSES = ("claude", "opencode")
_HARNESS_NAME = {"claude": "claude-code", "opencode": "opencode"}
_SKILL_DIRS = {"claude": (".claude", "skills"), "opencode": (".opencode", "skills")}
_DROPPED_ENV = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDECODE")
_ACTOR = {"kind": "launcher", "name": "ailsa run start"}


class LauncherError(Exception):
    """The run cannot be prepared or started."""


def default_prompt(dataset: str | os.PathLike[str], slash_ok: bool = SLASH_PROMPT_WORKS) -> str:
    if slash_ok:
        return f"/{SKILL_NAME} {dataset}"
    return f"Use the {SKILL_NAME} skill to determine the structure of the compound in {dataset}."


def build_argv(
    *,
    harness: str = "claude",
    model: str,
    prompt: str,
    headless: bool,
    run_dir: str | os.PathLike[str],
    dataset: str | os.PathLike[str],
    session_id: str | None = None,
    confidential: bool = False,
    extra: Sequence[str] = (),
) -> list[str]:
    if harness == "opencode":
        return ["opencode", "run", "--model", model, prompt, *extra]
    if harness != "claude":
        raise LauncherError(f"unknown harness {harness!r}")
    argv = ["claude"]
    # The prompt comes first in an interactive start: --add-dir is variadic.
    argv += ["-p", prompt] if headless else [prompt]
    argv += ["--model", model]
    if session_id:
        argv += ["--session-id", session_id]
    argv += [
        "--settings",
        str(Path(run_dir) / HOOKS_SETTINGS),
        "--add-dir",
        str(dataset),
        "--dangerously-skip-permissions",
    ]
    if confidential:
        argv += ["--disallowedTools", "WebFetch", "WebSearch"]
    return [*argv, *extra]


def _context_entries(files: Sequence[str | os.PathLike[str]]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for item in files:
        path = Path(item).expanduser()
        if not path.is_file():
            raise LauncherError(f"context file not found: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"name": path.name, "sha256": digest})
    return entries


def child_environment(
    run_dir: Path, *, harness: str, transcript: bool, base: Mapping[str, str] | None = None
) -> dict[str, str]:
    env = {k: v for k, v in (os.environ if base is None else base).items() if k not in _DROPPED_ENV}
    exe_dir = str(Path(sys.executable).parent)
    env["PATH"] = exe_dir + os.pathsep + env.get("PATH", "")
    env["AILSA_RUN_DIR"] = str(run_dir)
    env["AILSA_REQUIRE_RUN"] = "1"
    env["AILSA_HOOKS_VIA_SETTINGS"] = "1"
    env["AILSA_HARNESS"] = _HARNESS_NAME[harness]
    env["CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS"] = "15000"
    if not transcript:
        env["AILSA_NO_TRANSCRIPT"] = "1"
    return env


def prepare_run(
    dataset: str | os.PathLike[str],
    *,
    harness: str = "claude",
    model: str,
    headless: bool = True,
    time_limit_s: int = 3600,
    run_class: str = "internal",
    label: str | None = None,
    formula: str | None = None,
    source: str | None = None,
    licence: str | None = None,
    blind: bool = False,
    allow_prior_runs: bool = False,
    prompt: str | None = None,
    context_files: Sequence[str | os.PathLike[str]] = (),
    views: bool = True,
    transcript: bool = True,
    extra_args: Sequence[str] = (),
) -> dict[str, Any]:
    from ailsa.record.hooksettings import build_settings
    from ailsa.record.resolve import REQUIRE_ENV, RUN_DIR_ENV, SESSION_ENV
    from ailsa.record.runinit import _packaged_skill, init_run

    if harness not in HARNESSES:
        raise LauncherError(f"unknown harness {harness!r}; choose claude or opencode")
    skill_src = _packaged_skill(SKILL_NAME)
    if skill_src is None:
        raise LauncherError(f"the packaged skill {SKILL_NAME} was not found")
    ds = Path(dataset).expanduser()
    shown = str(ds.resolve()) if ds.is_dir() else str(ds)
    request_prompt = prompt if prompt else default_prompt(shown)
    contexts = _context_entries(context_files)
    harness_name = _HARNESS_NAME[harness]
    confidential = run_class == "confidential"
    if harness == "claude":
        web_tools = "disabled" if confidential else "enabled"
    else:
        web_tools = "unknown"

    # The launcher process itself is never bound to a session or run.
    clean = {
        k: v
        for k, v in os.environ.items()
        if k not in (SESSION_ENV, RUN_DIR_ENV, REQUIRE_ENV, "CLAUDECODE")
    }
    from ailsa.record.runinit import InitRefused

    try:
        result = init_run(
            ds,
            blind=blind,
            allow_prior_runs=allow_prior_runs,
            run_class=run_class,
            label=label,
            formula=formula,
            source=source,
            licence=licence,
            skill=SKILL_NAME,
            mode="headless" if headless else "interactive",
            harness=harness_name,
            prompt=request_prompt,
            args=[a[:ARGV_ITEM_CAP] for a in sys.argv[1:40]],
            context_files=contexts,
            time_limit_s=time_limit_s,
            web_tools=web_tools,
            web_tools_enforced=harness == "claude",
            views=views,
            env=clean,
        )
    except InitRefused as exc:
        raise LauncherError(str(exc)) from None

    run_dir = Path(result["run_dir"])
    agent_dir = run_dir / AGENT_DIR
    session_id: str | None = None
    if harness == "claude":
        session_id = str(uuid.uuid4())
        settings = build_settings(sys.executable, auto_memory=False)
        atomic_write_json(run_dir / HOOKS_SETTINGS, settings)
    parts = _SKILL_DIRS[harness]
    shutil.copytree(skill_src, agent_dir.joinpath(*parts, SKILL_NAME), symlinks=False)
    if context_files:
        target = agent_dir / "context"
        target.mkdir(mode=0o700, exist_ok=True)
        for item in context_files:
            shutil.copy2(Path(item).expanduser(), target / Path(item).name)
    argv = build_argv(
        harness=harness,
        model=model,
        prompt=request_prompt,
        headless=headless,
        run_dir=run_dir,
        dataset=shown,
        session_id=session_id,
        confidential=confidential,
        extra=extra_args,
    )
    return {
        "run_id": result["run_id"],
        "run_dir": str(run_dir),
        "agent_dir": str(agent_dir),
        "argv": argv,
        "env": child_environment(run_dir, harness=harness, transcript=transcript),
        "harness": harness_name,
        "model": model,
        "headless": headless,
        "time_limit_s": time_limit_s,
        "session_id": session_id,
        "transcript": transcript,
        "warnings": result["warnings"],
    }


def _signal_tree(proc: subprocess.Popen[Any], sig: int, group: bool) -> None:
    try:
        if group:
            os.killpg(proc.pid, sig)
        else:
            proc.send_signal(sig)
    except (ProcessLookupError, PermissionError):
        pass


def _wait_with_limit(proc: subprocess.Popen[Any], limit: int | None, group: bool) -> bool:
    """Wait for the child; True when the time limit ended it. The child is always reaped."""
    timed_out = False
    try:
        try:
            proc.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            timed_out = True
            _signal_tree(proc, signal.SIGTERM, group)
            try:
                proc.wait(timeout=KILL_GRACE_S)
            except subprocess.TimeoutExpired:
                _signal_tree(proc, signal.SIGKILL, group)
    finally:
        if proc.poll() is None:
            _signal_tree(proc, signal.SIGKILL, group)
        proc.wait()
        if group:
            _signal_tree(proc, signal.SIGKILL, group)  # grandchildren left behind
    return timed_out


def _copy_transcripts(run_dir: Path, session_id: str | None) -> None:
    from ailsa.record.transcript import (
        TRANSCRIPT_DIR,
        copy_transcripts,
        find_session_transcript,
        record_transcript_models,
    )

    main = find_session_transcript(session_id)
    if main is None:
        return
    copied = copy_transcripts(run_dir, main, session_id, via="launcher")
    files = [run_dir / TRANSCRIPT_DIR / str(c["name"]) for c in copied]
    if not files:
        files = [run_dir / TRANSCRIPT_DIR / main.name]
    record_transcript_models(run_dir, [f for f in files if f.is_file()])


def launch(prepared: dict[str, Any], *, extra_args: Sequence[str] = ()) -> dict[str, Any]:
    """Start the harness, wait, copy transcripts and close the run. Never leaves an open run."""
    from ailsa.record.closing import close_run
    from ailsa.record.render import render_run

    run_dir = Path(prepared["run_dir"])
    argv = list(prepared["argv"]) + list(extra_args)
    headless = bool(prepared["headless"])
    limit = prepared.get("time_limit_s")
    append_event(
        run_dir,
        "run.attempt.started",
        {
            "attempt": 1,
            "harness": prepared["harness"],
            "time_limit_s": limit,
            "argv": [a[:ARGV_ITEM_CAP] for a in argv],
        },
        actor=_ACTOR,
        fsync=True,
    )
    append_event(
        run_dir,
        "agent.model_reported",
        {"agent": "main", "requested": prepared["model"], "actual": None, "source": "launcher"},
        actor=_ACTOR,
    )
    started = time.monotonic()
    exit_code: int | None
    reason = "exited"
    out_path = run_dir / "transcript" / "harness-output.log"
    try:
        out_path.parent.mkdir(mode=0o700, exist_ok=True)
        if headless:
            with open(out_path, "ab") as out:
                proc = subprocess.Popen(
                    argv,
                    cwd=prepared["agent_dir"],
                    env=prepared["env"],
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        else:
            proc = subprocess.Popen(argv, cwd=prepared["agent_dir"], env=prepared["env"])
    except OSError as exc:
        exit_code = None
        reason = f"spawn_failed: {type(exc).__name__}: {exc}"[:200]
    else:
        timed_out = _wait_with_limit(proc, limit, headless)
        exit_code = proc.returncode
        if timed_out:
            reason = "time_limit"
    append_event(
        run_dir,
        "run.attempt.ended",
        {
            "attempt": 1,
            "exit_code": exit_code,
            "reason": reason,
            "elapsed_s": round(time.monotonic() - started, 3),
        },
        actor=_ACTOR,
        fsync=True,
    )
    if prepared.get("transcript") and prepared.get("session_id"):
        try:
            _copy_transcripts(run_dir, prepared["session_id"])
        except Exception as exc:  # noqa: BLE001 - a transcript problem never blocks closing
            append_event(
                run_dir,
                "warning.raised",
                {"code": "transcript_copy_failed", "message": f"{type(exc).__name__}: {exc}"},
                actor=_ACTOR,
            )
    closed = close_run(
        run_dir, "time limit" if reason == "time_limit" else "harness exited", actor=_ACTOR
    )
    try:
        render_run(run_dir)
    except Exception as exc:  # noqa: BLE001 - renderings are derived files
        sys.stderr.write(f"ailsa: renderings not written: {exc}\n")
    return {
        "run_id": prepared["run_id"],
        "run_dir": str(run_dir),
        "exit_code": exit_code,
        "reason": reason,
        "state": closed.get("state"),
    }
