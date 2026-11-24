"""Find the active run of a tool call (standard library only).

Order: explicit path or id, ``AILSA_RUN_DIR``, the session pointer keyed by
``CLAUDE_CODE_SESSION_ID``, the nearest ``.ailsa-run`` marker above the working folder.

D-07: outside any run nothing is printed. The one-line warning appears only when a record
was expected (``AILSA_REQUIRE_RUN=1``, or ``AILSA_RUN_DIR`` / a session pointer exists but
cannot be resolved).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from ailsa.record.events import FINISHED, MARKER, SESSIONS_DIR
from ailsa.record.fsutil import atomic_write_bytes
from ailsa.record.workspace import find_run, workspace_root

RUN_DIR_ENV = "AILSA_RUN_DIR"
REQUIRE_ENV = "AILSA_REQUIRE_RUN"
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,79}$")

_warned = False


@dataclass(frozen=True)
class RunRef:
    run_dir: Path
    run_id: str
    via: str


def _marker_run_id(run_dir: Path) -> str | None:
    try:
        data = json.loads((run_dir / MARKER).read_text(encoding="utf-8"))
        return str(data["run_id"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _ref(run_dir: Path | None, via: str) -> RunRef | None:
    if run_dir is None or not run_dir.is_dir():
        return None
    run_id = _marker_run_id(run_dir)
    if run_id is None:
        return None
    return RunRef(run_dir=run_dir, run_id=run_id, via=via)


def session_pointer_path(workspace: str | os.PathLike[str], session_id: str | None) -> Path | None:
    if not session_id or not SESSION_ID_RE.match(session_id):
        return None
    return Path(workspace) / SESSIONS_DIR / session_id


def _read_pointer(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Path(text) if text and os.path.isabs(text) else None


def find_active_run(
    explicit: str | None = None,
    *,
    session_id: str | None = None,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> RunRef | None:
    environ = os.environ if env is None else env
    if explicit:
        ref = _ref(find_run(workspace_root(create=False), explicit), "flag")
        if ref:
            return ref
    env_dir = environ.get(RUN_DIR_ENV)
    if env_dir:
        ref = _ref(Path(env_dir).expanduser(), "env")
        if ref:
            return ref
    sid = session_id if session_id is not None else environ.get(SESSION_ENV)
    pointer = session_pointer_path(workspace_root(create=False), sid)
    ref = _ref(_read_pointer(pointer), "session")
    if ref:
        return ref
    here = Path(cwd) if cwd is not None else Path.cwd()
    try:
        here = here.resolve()
    except OSError:
        pass
    for folder in (here, *here.parents):
        if (folder / MARKER).is_file():
            ref = _ref(folder, "cwd")
            if ref:
                return ref
    return None


def bind_session(
    workspace: str | os.PathLike[str], session_id: str, run_dir: str | os.PathLike[str]
) -> bool:
    pointer = session_pointer_path(workspace, session_id)
    if pointer is None:
        return False
    pointer.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_write_bytes(pointer, (str(Path(run_dir).resolve()) + "\n").encode("utf-8"))
    return True


def unbind_session(workspace: str | os.PathLike[str], session_id: str) -> None:
    pointer = session_pointer_path(workspace, session_id)
    if pointer is None:
        return
    try:
        pointer.unlink()
    except OSError:
        pass


def expected_run(env: Mapping[str, str] | None = None) -> tuple[bool, str]:
    environ = os.environ if env is None else env
    if environ.get(REQUIRE_ENV) == "1":
        return True, "AILSA_REQUIRE_RUN is set"
    if environ.get(RUN_DIR_ENV):
        return True, "AILSA_RUN_DIR not found"
    pointer = session_pointer_path(workspace_root(create=False), environ.get(SESSION_ENV))
    if pointer is not None and pointer.exists():
        return True, "session pointer does not resolve"
    return False, ""


def _warn(reason: str, stream: TextIO) -> None:
    global _warned
    if _warned:
        return
    _warned = True
    print(f"ailsa: not recorded: no active run ({reason})", file=stream)


def current_run_for_tool(
    command: str,
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
    stream: TextIO | None = None,
) -> RunRef | None:
    out = stream if stream is not None else sys.stderr
    try:
        ref = find_active_run(env=env, cwd=cwd)
        if ref is not None:
            if (ref.run_dir / FINISHED).exists():
                expected, _ = expected_run(env)
                if expected or ref.via != "cwd":
                    global _warned
                    if not _warned:
                        _warned = True
                        print("ailsa: not recorded: run finished", file=out)
                return None
            return ref
        expected, reason = expected_run(env)
        if expected:
            _warn(reason, out)
        return None
    except Exception as exc:  # never raise out of the resolver
        try:
            _warn(f"resolver error: {type(exc).__name__}", out)
        except Exception:
            pass
        return None
