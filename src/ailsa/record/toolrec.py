"""Record every ailsa tool call as one ``tool.invoked`` event (standard library only).

Used by ``LazyGroup.invoke``. Outside a run nothing changes. A recording failure prints one
stderr line and never changes the command's output or exit code (D-07). Environment
variables are never recorded; stdout is stored as size and sha256 only.
"""

from __future__ import annotations

import hashlib
import os
import stat
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ailsa.record.artefacts import artefact_index
from ailsa.record.events import ARGV_ITEM_CAP, artefact_id
from ailsa.record.log import log_session, read_events
from ailsa.record.resolve import RunRef, current_run_for_tool

EXCLUDED = frozenset({"run", "skill", "database"})
ARGV_MAX_ITEMS = 40
LOCK_TIMEOUT = 5.0
# Output trees only tools write into (REC-05 redirects): files a call writes there are
# registered on its tool.invoked event.
TOOL_TREES = (("nus", "nus-stage"), ("peaks/nus", "nus-peaks"), ("jcamp", "jcamp-output"))


class _Counter:
    def __init__(self) -> None:
        self.bytes = 0
        self.digest = hashlib.sha256()

    def add(self, data: bytes) -> None:
        self.bytes += len(data)
        self.digest.update(data)


class _BufferProxy:
    def __init__(self, real: Any, counter: _Counter) -> None:
        self._real = real
        self._counter = counter

    def write(self, data: Any) -> Any:
        written = self._real.write(data)
        try:
            self._counter.add(bytes(data))
        except (TypeError, ValueError):
            pass
        return written

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class _StdoutProxy:
    """Forward every write unchanged while counting bytes and hashing them."""

    def __init__(self, real: Any, counter: _Counter) -> None:
        self._real = real
        self._counter = counter

    def write(self, text: str) -> int:
        result: int = self._real.write(text)
        encoding = getattr(self._real, "encoding", None) or "utf-8"
        self._counter.add(text.encode(encoding, "replace"))
        return result

    def writelines(self, lines: Any) -> None:
        for line in lines:
            self.write(line)

    @property
    def buffer(self) -> Any:
        return _BufferProxy(self._real.buffer, self._counter)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def _pending_argv(ctx: Any) -> list[str]:
    protected = list(getattr(ctx, "_protected_args", None) or [])
    return protected + list(getattr(ctx, "args", None) or [])


def _cap_argv(argv: list[str]) -> list[str]:
    return [item[:ARGV_ITEM_CAP] for item in argv[:ARGV_MAX_ITEMS]]


def _exit_code(exc: BaseException) -> int:
    import click

    if isinstance(exc, SystemExit):
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    if isinstance(exc, click.exceptions.Exit):
        return int(exc.exit_code)
    if isinstance(exc, click.ClickException):
        return int(exc.exit_code)
    return 1


def _actor_name(argv: list[str]) -> str:
    words = [a for a in argv if not a.startswith("-")][:2]
    return "ailsa " + " ".join(words)


def _cwd_label(run_dir: Path) -> str:
    try:
        return str(Path.cwd().resolve().relative_to(run_dir.resolve())) or "."
    except (ValueError, OSError):
        return "outside run"


def _kind_of(rel: str) -> str | None:
    for root, kind in TOOL_TREES:
        if rel.startswith(root + "/"):
            return kind
    return None


def _snapshot(run_dir: Path) -> dict[str, tuple[int, int]]:
    """Regular files in the tool-owned output trees: relative path -> (size, mtime_ns)."""
    out: dict[str, tuple[int, int]] = {}
    for root, _kind in TOOL_TREES:
        base = run_dir / root
        if base.is_symlink() or not base.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(base, followlinks=False):
            for name in filenames:
                path = Path(dirpath) / name
                try:
                    st = os.lstat(path)
                except OSError:
                    continue
                if stat.S_ISREG(st.st_mode):
                    out[path.relative_to(run_dir).as_posix()] = (st.st_size, st.st_mtime_ns)
    return out


def _written_files(
    run_dir: Path, before: dict[str, tuple[int, int]]
) -> list[tuple[str, str, int]]:
    """(path, sha256, bytes) of files the call created or rewrote in the tool-owned trees."""
    from ailsa.record.fsutil import sha256_file

    found: list[tuple[str, str, int]] = []
    for rel, sig in sorted(_snapshot(run_dir).items()):
        if before.get(rel) == sig:
            continue
        try:
            found.append((rel, sha256_file(run_dir / rel), sig[0]))
        except OSError:
            continue
    return found


def _record(
    ref: RunRef,
    argv: list[str],
    exit_code: int,
    started: float,
    counter: _Counter,
    before: dict[str, tuple[int, int]] | None = None,
) -> None:
    try:
        run_dir = Path(ref.run_dir)
        written = _written_files(run_dir, before) if before is not None else []
        with log_session(run_dir, timeout=LOCK_TIMEOUT) as lg:
            artefacts: list[dict[str, Any]] = []
            if written:
                # NUS stages, NUS peaks and JCAMP output are tool-written (REC-01): register
                # them so finalize and verify do not report them as unverified agent files.
                # A file rewritten in place supersedes its earlier registration.
                latest = {
                    str(a.get("path")): aid
                    for aid, a in artefact_index(read_events(run_dir)["events"]).items()
                }
                for rel, sha, size in written:
                    kind = _kind_of(rel) or "tool-output"
                    artefacts.append(
                        {
                            "id": artefact_id(kind, lg.next_counter("art:" + kind)),
                            "kind": kind,
                            "path": rel,
                            "sha256": sha,
                            "bytes": size,
                            "supersedes": latest.get(rel),
                        }
                    )
            lg.append(
                "tool.invoked",
                {
                    "argv": _cap_argv(argv),
                    "exit_code": exit_code,
                    "duration_s": round(time.monotonic() - started, 3),
                    "cwd": _cwd_label(run_dir),
                    "stdout_bytes": counter.bytes,
                    "stdout_sha256": counter.digest.hexdigest(),
                },
                actor={"kind": "tool", "name": _actor_name(argv)},
                artefacts=artefacts,
            )
    except Exception as exc:
        print(f"ailsa: record write failed: {exc}", file=sys.stderr)


def invoke_recorded(invoke: Callable[[Any], Any], ctx: Any) -> Any:
    argv = _pending_argv(ctx)
    name = argv[0] if argv else ""
    if not name or name in EXCLUDED or "--help" in argv or "--version" in argv:
        return invoke(ctx)
    try:
        ref = current_run_for_tool(name)
    except Exception:
        ref = None
    if ref is None:
        return invoke(ctx)

    try:
        before: dict[str, tuple[int, int]] | None = _snapshot(Path(ref.run_dir))
    except OSError:
        before = None
    counter = _Counter()
    real_stdout = sys.stdout
    sys.stdout = _StdoutProxy(real_stdout, counter)
    started = time.monotonic()
    exit_code = 0
    try:
        return invoke(ctx)
    except BaseException as exc:
        exit_code = _exit_code(exc)
        raise
    finally:
        sys.stdout = real_stdout
        _record(ref, argv, exit_code, started, counter, before)
