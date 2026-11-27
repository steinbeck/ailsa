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
from ailsa.record.fsutil import atomic_write_json, scrub_home
from ailsa.record.log import RecordWriteRefused, append_event

SKILL_NAME = "ailsa-lite"
FRONTIER_SKILL = "ailsa"
SKILLS = (SKILL_NAME, FRONTIER_SKILL)
# Plan 02 spike answer A8: a slash prompt invokes a project skill in `claude -p`.
SLASH_PROMPT_WORKS = True
KILL_GRACE_S = 10
# How long the run waits at its end for the spectra-export child started by init.
VIEWS_WAIT_S = 30.0
HARNESSES = ("claude", "opencode")
_HARNESS_NAME = {"claude": "claude-code", "opencode": "opencode"}
_SKILL_DIRS = {"claude": (".claude", "skills"), "opencode": (".opencode", "skills")}
_DROPPED_ENV = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDECODE")
_ACTOR = {"kind": "launcher", "name": "ailsa run start"}


class LauncherError(Exception):
    """The run cannot be prepared or started."""


def default_prompt(
    dataset: str | os.PathLike[str],
    slash_ok: bool = SLASH_PROMPT_WORKS,
    *,
    skill: str = SKILL_NAME,
    formula: str | None = None,
) -> str:
    if skill == FRONTIER_SKILL:
        if slash_ok:
            return f"/ailsa:case {dataset}" + (f" {formula}" if formula else "")
        return f"Run the AILSA CASE workflow (/ailsa:case) on the compound in {dataset}."
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


RESUME_NUDGE = (
    "Continue the CASE workflow where it stopped. The run has not declared its result yet. "
    "Check `ailsa run status`, finish the remaining steps inline without waiting to be woken, "
    "and end with `ailsa run finalize` (or `ailsa run close` when no result can be declared)."
)


def build_resume_argv(
    *,
    model: str,
    nudge: str,
    session_id: str,
    run_dir: str | os.PathLike[str],
    dataset: str | os.PathLike[str],
    confidential: bool = False,
    extra: Sequence[str] = (),
) -> list[str]:
    """Argv that resumes the launched Claude Code session headless with a nudge."""
    argv = [
        "claude",
        "--resume",
        session_id,
        "-p",
        nudge,
        "--model",
        model,
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
    run_dir: Path,
    *,
    harness: str,
    transcript: bool,
    base: Mapping[str, str] | None = None,
    teams: bool = False,
) -> dict[str, str]:
    env = {k: v for k, v in (os.environ if base is None else base).items() if k not in _DROPPED_ENV}
    exe_dir = str(Path(sys.executable).parent)
    env["PATH"] = exe_dir + os.pathsep + env.get("PATH", "")
    env["AILSA_RUN_DIR"] = str(run_dir)
    env["AILSA_REQUIRE_RUN"] = "1"
    env["AILSA_HOOKS_VIA_SETTINGS"] = "1"
    env["AILSA_HARNESS"] = _HARNESS_NAME[harness]
    env["CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS"] = "15000"
    if teams:
        env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"
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
    skill: str = SKILL_NAME,
    resume_attempts: int = 1,
    deadline_s: int | None = None,
) -> dict[str, Any]:
    from ailsa.record.hooksettings import build_settings
    from ailsa.record.resolve import REQUIRE_ENV, RUN_DIR_ENV, SESSION_ENV
    from ailsa.record.runinit import _packaged_skill, init_run

    if harness not in HARNESSES:
        raise LauncherError(f"unknown harness {harness!r}; choose claude or opencode")
    if resume_attempts < 1:
        raise LauncherError("--resume-attempts must be at least 1")
    if resume_attempts > 1 and not (headless and harness == "claude"):
        raise LauncherError("--resume-attempts above 1 needs a headless Claude Code run")
    if deadline_s is not None and deadline_s < 1:
        raise LauncherError("--deadline must be at least 1 second")
    if skill not in SKILLS:
        raise LauncherError(f"unknown skill {skill!r}; choose one of {', '.join(SKILLS)}")
    frontier = skill == FRONTIER_SKILL
    if frontier:
        # Checked before init_run so a refusal leaves no run folder behind.
        if harness != "claude":
            raise LauncherError("the frontier skill runs only in Claude Code (--harness claude)")
        if not (Path.home() / ".claude" / "commands" / "ailsa" / "case.md").is_file():
            raise LauncherError(
                "the frontier skill is not installed; "
                "run: ailsa skill install ailsa --target claude"
            )
    skill_src = _packaged_skill(skill)
    if skill_src is None:
        raise LauncherError(f"the packaged skill {skill} was not found")
    ds = Path(dataset).expanduser()
    shown = str(ds.resolve()) if ds.is_dir() else str(ds)
    request_prompt = prompt if prompt else default_prompt(shown, skill=skill, formula=formula)
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
            skill=skill,
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
    try:
        if harness == "claude":
            session_id = str(uuid.uuid4())
            settings = build_settings(sys.executable, auto_memory=False)
            atomic_write_json(run_dir / HOOKS_SETTINGS, settings)
        if not frontier:
            # The frontier command skill must be the global install: its commands read
            # ~/.claude/ailsa/references.
            parts = _SKILL_DIRS[harness]
            shutil.copytree(skill_src, agent_dir.joinpath(*parts, skill), symlinks=False)
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
    except Exception as exc:
        # The run exists already: end it instead of leaving it open without an attempt.
        message = f"launcher setup failed: {type(exc).__name__}: {exc}"[:500]
        _settle_views(result.get("views_pid"), VIEWS_WAIT_S)
        _close_quietly(run_dir, message)
        raise LauncherError(f"{message} (run {result['run_id']} closed)") from exc
    return {
        "run_id": result["run_id"],
        "run_dir": str(run_dir),
        "agent_dir": str(agent_dir),
        "argv": argv,
        "env": child_environment(run_dir, harness=harness, transcript=transcript, teams=frontier),
        "harness": harness_name,
        "skill": skill,
        "model": model,
        "headless": headless,
        "time_limit_s": time_limit_s,
        "resume_attempts": resume_attempts,
        "deadline_s": deadline_s,
        "dataset": shown,
        "confidential": confidential,
        "extra_args": list(extra_args),
        "session_id": session_id,
        "transcript": transcript,
        "warnings": result["warnings"],
        "views_pid": result.get("views_pid"),
    }


def _close_quietly(run_dir: Path, reason: str) -> dict[str, Any]:
    """Close the run; an already closed run (e.g. the agent ran ``ailsa run close``) is fine."""
    from ailsa.record.closing import CloseRefused, close_run
    from ailsa.record.fold import rebuild_manifest

    try:
        return close_run(run_dir, reason, actor=_ACTOR)
    except CloseRefused:
        try:
            state = (rebuild_manifest(run_dir).get("status") or {}).get("state")
        except Exception:  # noqa: BLE001 - the state is only reported
            state = None
        return {"state": state, "head": None}
    except Exception as exc:  # noqa: BLE001 - report, never crash after the harness ran
        sys.stderr.write(f"ailsa: run not closed: {type(exc).__name__}: {exc}\n")
        return {"state": None, "head": None}


def _descendants(pid: int) -> list[int]:
    """Every process below ``pid`` (children first), from ``ps``; empty when ps fails."""
    try:
        out = subprocess.run(
            ["ps", "-A", "-o", "pid=", "-o", "ppid="],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    children: dict[int, list[int]] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    found: list[int] = []
    queue = list(children.get(pid, []))
    while queue:
        child = queue.pop(0)
        if child in found or child == os.getpid():
            continue
        found.append(child)
        queue.extend(children.get(child, []))
    return found


def _signal_tree(
    proc: subprocess.Popen[Any], sig: int, group: bool, tree: Sequence[int] = ()
) -> None:
    """Signal the harness: its process group (headless), or it and ``tree`` (interactive)."""
    if group:
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        return
    targets = [proc.pid, *tree] if proc.poll() is None else list(tree)
    for pid in targets:
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def _terminate(proc: subprocess.Popen[Any], group: bool) -> None:
    """SIGTERM the harness and everything it started, SIGKILL whatever is left after the grace.

    A headless harness has its own session, so its process group holds its tool children. An
    interactive one stays in the terminal's foreground group (its TUI needs the terminal), so
    its descendants are collected before signalling: they lose their parent link once it dies.
    """
    tree = [] if group else _descendants(proc.pid)
    _signal_tree(proc, signal.SIGTERM, group, tree)
    try:
        proc.wait(timeout=KILL_GRACE_S)
    except subprocess.TimeoutExpired:
        if not group:
            tree = [*tree, *(p for p in _descendants(proc.pid) if p not in tree)]
    _signal_tree(proc, signal.SIGKILL, group, tree)


class _StopRequested(BaseException):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


class _SignalGate:
    """SIGINT/SIGTERM during a launch: recorded once, raised only while waiting for the harness.

    Outside the wait the signal is only noted, so it never interrupts a log write; the run is
    then ended and closed as interrupted. An interactive harness shares the terminal with the
    launcher and handles Ctrl-C itself, so the launcher ignores SIGINT there.
    """

    def __init__(self, *, sigint: bool) -> None:
        self.signum: int | None = None
        self.armed = False
        self._sigint = sigint
        self._old: dict[int, Any] = {}

    def __enter__(self) -> _SignalGate:
        import threading

        if threading.current_thread() is threading.main_thread():
            self._old[signal.SIGTERM] = signal.signal(signal.SIGTERM, self._handle)
            self._old[signal.SIGINT] = signal.signal(
                signal.SIGINT, self._handle if self._sigint else signal.SIG_IGN
            )
        return self

    def __exit__(self, *exc: object) -> None:
        for sig, old in self._old.items():
            signal.signal(sig, old)

    def _handle(self, signum: int, frame: Any) -> None:
        if self.signum is None:
            self.signum = signum
            if self.armed:
                self.armed = False
                raise _StopRequested(signum)


_STOP_REASONS: dict[int, str] = {
    int(signal.SIGINT): "interrupted",
    int(signal.SIGTERM): "terminated",
}


def _wait_with_limit(
    proc: subprocess.Popen[Any], limit: int | None, group: bool, gate: _SignalGate | None = None
) -> str | None:
    """Wait for the child; return why the launcher ended it (time limit or a signal), or None.

    The child (and, headless, its process group) is always ended and reaped.
    """
    stopped: str | None = None
    try:
        try:
            if gate is not None:
                gate.armed = True
                if gate.signum is not None:
                    raise _StopRequested(gate.signum)
            try:
                proc.wait(timeout=limit)
            finally:
                if gate is not None:
                    gate.armed = False
        except subprocess.TimeoutExpired:
            stopped = "time_limit"
        except _StopRequested as exc:
            stopped = _STOP_REASONS.get(exc.signum, "interrupted")
        if stopped is not None:
            _terminate(proc, group)
    finally:
        if proc.poll() is None:
            _signal_tree(proc, signal.SIGKILL, group)
        proc.wait()
        if group:
            _signal_tree(proc, signal.SIGKILL, group)  # grandchildren left behind
    return stopped


def _settle_views(pid: Any, wait_s: float) -> None:
    """Let the spectra-export child started by init finish, or end it, before the run closes."""
    if not isinstance(pid, int) or pid <= 0:
        return
    deadline = time.monotonic() + wait_s
    while True:
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return  # already reaped (or not ours)
        if done:
            return
        if time.monotonic() >= deadline:
            break
        time.sleep(0.2)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pid, sig)  # the child leads its own session
        except (ProcessLookupError, PermissionError):
            return
        try:
            time.sleep(1.0)
            if os.waitpid(pid, os.WNOHANG)[0]:
                return
        except ChildProcessError:
            return


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
    """Start the harness, wait, copy transcripts and close the run. Never leaves an open run.

    SIGTERM (and SIGINT in a headless run) ends the harness with everything it started and
    closes the run as interrupted; the result then carries the signal number.
    """
    headless = bool(prepared["headless"])
    with _SignalGate(sigint=headless) as gate:
        return _launch(prepared, extra_args, gate)


def _run_is_settled(run_dir: Path) -> bool:
    """The agent closed the run, or the log holds a valid, current declaration (no write)."""
    from ailsa.record.fold import fold
    from ailsa.record.log import read_events

    try:
        log = read_events(run_dir)
        events = log["events"]
        if any(e.get("type") == "run.finished" for e in events):
            return True
        final = fold(events, log["integrity"]).get("final") or {}
    except Exception:  # noqa: BLE001 - an unreadable log means: keep the plain outcome
        return False
    return bool(final.get("valid")) and not final.get("stale")


def _launch(
    prepared: dict[str, Any], extra_args: Sequence[str], gate: _SignalGate
) -> dict[str, Any]:
    from ailsa.record.render import render_run

    run_dir = Path(prepared["run_dir"])
    first_argv = list(prepared["argv"]) + list(extra_args)
    headless = bool(prepared["headless"])
    time_limit = prepared.get("time_limit_s")
    max_attempts = int(prepared.get("resume_attempts") or 1)
    deadline_s = prepared.get("deadline_s")
    deadline_at = time.monotonic() + deadline_s if deadline_s else None
    exit_code: int | None = None
    reason = "exited"
    out_path = run_dir / "transcript" / "harness-output.log"
    closed: dict[str, Any] = {}
    attempts = 0
    deadline_hit = False
    try:
        if prepared.get("session_id"):
            # The launched session is bound to this run; hooks of other sessions never record.
            append_event(
                run_dir,
                "run.bound",
                {
                    "session_id": prepared["session_id"],
                    "harness": prepared["harness"],
                    "via": "launcher",
                },
                actor=_ACTOR,
            )
        append_event(
            run_dir,
            "agent.model_reported",
            {
                "agent": "main",
                "requested": prepared["model"],
                "actual": None,
                "source": "launcher",
            },
            actor=_ACTOR,
        )
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            limit = time_limit
            if deadline_at is not None:
                remaining = max(1, int(deadline_at - time.monotonic() + 0.999))
                limit = remaining if limit is None else min(limit, remaining)
            if attempt == 1:
                argv = first_argv
            else:
                argv = build_resume_argv(
                    model=prepared["model"],
                    nudge=RESUME_NUDGE,
                    session_id=prepared["session_id"],
                    run_dir=run_dir,
                    dataset=prepared["dataset"],
                    confidential=bool(prepared.get("confidential")),
                    extra=[*prepared.get("extra_args", ()), *extra_args],
                )
            started = time.monotonic()
            exit_code = None
            reason = "exited"
            append_event(
                run_dir,
                "run.attempt.started",
                {
                    "attempt": attempt,
                    "harness": prepared["harness"],
                    "time_limit_s": limit,
                    "argv": [scrub_home(a)[:ARGV_ITEM_CAP] for a in argv],
                },
                actor=_ACTOR,
                fsync=True,
            )
            spawned = False
            if gate.signum is not None:
                reason = _STOP_REASONS.get(gate.signum, "interrupted") + " before start"
            else:
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
                        # Interactive: the TUI needs the terminal's foreground process group,
                        # so it gets no session of its own; _terminate signals its tree.
                        proc = subprocess.Popen(
                            argv, cwd=prepared["agent_dir"], env=prepared["env"]
                        )
                except OSError as exc:
                    reason = f"spawn_failed: {type(exc).__name__}: {exc}"[:200]
                else:
                    spawned = True
                    stopped = _wait_with_limit(proc, limit, headless, gate)
                    exit_code = proc.returncode
                    if stopped is not None:
                        reason = stopped
            try:
                append_event(
                    run_dir,
                    "run.attempt.ended",
                    {
                        "attempt": attempt,
                        "exit_code": exit_code,
                        "reason": reason,
                        "elapsed_s": round(time.monotonic() - started, 3),
                    },
                    actor=_ACTOR,
                    fsync=True,
                )
            except RecordWriteRefused:
                pass  # the agent closed the run itself: a finished record takes no more events
            if not spawned or gate.signum is not None or attempt == max_attempts:
                break
            if _run_is_settled(run_dir):
                break
            if deadline_at is not None and time.monotonic() >= deadline_at:
                deadline_hit = True
                break
        if prepared.get("transcript") and prepared.get("session_id"):
            try:
                _copy_transcripts(run_dir, prepared["session_id"])
            except Exception as exc:  # noqa: BLE001 - a transcript problem never blocks closing
                append_event(
                    run_dir,
                    "warning.raised",
                    {
                        "code": "transcript_copy_failed",
                        "message": f"{type(exc).__name__}: {exc}",
                    },
                    actor=_ACTOR,
                )
    finally:
        # Always ends the run, whatever happened above (REC-23).
        _settle_views(prepared.get("views_pid"), VIEWS_WAIT_S)
        if deadline_hit:
            close_reason = "deadline"
        elif reason == "time_limit":
            close_reason = "time limit"
        elif reason.startswith(("interrupted", "terminated")):
            close_reason = f"{reason} (signal {gate.signum})"
        else:
            close_reason = "harness exited"
        closed = _close_quietly(run_dir, close_reason)
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
        "signal": gate.signum,
        "attempts": attempts,
    }
