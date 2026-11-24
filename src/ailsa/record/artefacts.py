"""Typed artefact registration (standard library only).

One writer per artefact: the file is written atomically under the log lock, its sha256 goes
into the event, and a registered path is never overwritten. A correction is a new artefact
that names the one it supersedes (REC-01, REC-02).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from ailsa.record.events import artefact_id
from ailsa.record.fsutil import atomic_write_bytes, sha256_bytes, sha256_file
from ailsa.record.log import RecordWriteRefused, log_session

DEFAULT_MAX_BYTES = 200 * 1024 * 1024


def safe_relpath(run_dir: str | os.PathLike[str], rel_path: str) -> str:
    """Return a normalised relative path inside the run folder or raise ValueError."""
    if not rel_path or "\x00" in rel_path:
        raise ValueError("empty or invalid artefact path")
    if os.path.isabs(rel_path) or rel_path.startswith(("/", "\\")):
        raise ValueError(f"artefact path must be relative: {rel_path}")
    pure = PurePosixPath(rel_path.replace("\\", "/"))
    if any(part == ".." for part in pure.parts) or not pure.parts:
        raise ValueError(f"artefact path must not leave the run folder: {rel_path}")
    base = Path(run_dir).resolve()
    current = base
    for part in pure.parts:
        if part == ".":
            continue
        current = current / part
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(st.st_mode):
            raise ValueError(f"artefact path passes through a symlink: {rel_path}")
    resolved = current.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"artefact path resolves outside the run folder: {rel_path}")
    return str(pure)


def run_target(run_dir: str | os.PathLike[str], rel_path: str) -> Path:
    """``run_dir / rel_path`` for a tool write, after ``safe_relpath``.

    Raises ValueError when a component is a symlink or the path leaves the run folder, so a
    writer never creates folders or files through a link the agent placed in the run folder.
    """
    return Path(run_dir) / safe_relpath(run_dir, rel_path)


def _read_source(src: Path, max_bytes: int) -> bytes:
    st = os.lstat(src)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"not a regular file (symlinks are refused): {src}")
    if st.st_size > max_bytes:
        raise ValueError(f"file larger than {max_bytes} bytes: {src}")
    return Path(src).read_bytes()


def _write_new(target: Path, data: bytes, fsync: bool) -> None:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_write_bytes(target, data, fsync=fsync, mode=0o600)


def copy_into_run(
    run_dir: str | os.PathLike[str],
    src: str | os.PathLike[str],
    rel_path: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[str, str, int]:
    rel = safe_relpath(run_dir, rel_path)
    target = Path(run_dir) / rel
    if os.path.lexists(target):
        raise FileExistsError(f"path already exists in the run folder: {rel}")
    data = _read_source(Path(src), max_bytes)
    _write_new(target, data, False)
    return rel, sha256_bytes(data), len(data)


def register_artefact(
    run_dir: str | os.PathLike[str],
    *,
    kind: str,
    rel_path: str,
    data: bytes | Path,
    event_type: str,
    payload: dict[str, Any],
    actor: dict[str, Any],
    refs: list[str] | None = None,
    span: dict[str, Any] | None = None,
    supersedes: str | None = None,
    fsync: bool = False,
) -> dict[str, Any]:
    rel = safe_relpath(run_dir, rel_path)
    target = Path(run_dir) / rel
    blob = data if isinstance(data, bytes) else _read_source(Path(data), DEFAULT_MAX_BYTES)
    with log_session(run_dir) as lg:
        if lg.finished():
            raise RecordWriteRefused("run finished: no new artefacts")
        if os.path.lexists(target):
            raise FileExistsError(f"artefact path already exists: {rel}")
        n = lg.next_counter("art:" + kind)
        entry: dict[str, Any] = {
            "id": artefact_id(kind, n),
            "kind": kind,
            "path": rel,
            "sha256": sha256_bytes(blob),
            "bytes": len(blob),
            "supersedes": supersedes,
        }
        _write_new(target, blob, fsync)
        lg.append(
            event_type,
            payload,
            actor=actor,
            refs=refs,
            span=span,
            artefacts=[entry],
            fsync=fsync,
        )
    return entry


def register_existing(
    run_dir: str | os.PathLike[str],
    *,
    kind: str,
    rel_path: str,
    event_type: str,
    payload: dict[str, Any],
    actor: dict[str, Any],
    refs: list[str] | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    """Register a file a tool already placed inside the run folder; it is hashed, not rewritten."""
    rel = safe_relpath(run_dir, rel_path)
    target = Path(run_dir) / rel
    st = os.lstat(target)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"not a regular file: {rel}")
    with log_session(run_dir) as lg:
        if lg.finished():
            raise RecordWriteRefused("run finished: no new artefacts")
        n = lg.next_counter("art:" + kind)
        entry: dict[str, Any] = {
            "id": artefact_id(kind, n),
            "kind": kind,
            "path": rel,
            "sha256": sha256_file(target),
            "bytes": st.st_size,
            "supersedes": supersedes,
        }
        lg.append(event_type, payload, actor=actor, refs=refs, artefacts=[entry])
    return entry


def artefact_index(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for ev in events:
        for art in ev.get("artefacts") or []:
            aid = art.get("id")
            if not aid:
                continue
            index[aid] = {**art, "event_seq": ev.get("seq"), "superseded_by": None}
    for aid, art in index.items():
        old = art.get("supersedes")
        if old and old in index:
            index[old]["superseded_by"] = aid
    return index


def find_artefacts(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    found = [a for a in artefact_index(events).values() if a.get("kind") == kind]
    return sorted(found, key=lambda a: int(a.get("event_seq") or 0))
