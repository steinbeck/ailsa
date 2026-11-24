"""Copy Claude Code transcripts into the run folder and read models from them (stdlib only).

Transcripts are evidence copies: a copy is overwritten when the source changed, and every
copy is recorded with its sha256 in a ``transcript.copied`` event. Regular files only
(symlinks are skipped), with a total size cap.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ailsa.record.fsutil import atomic_write_bytes, is_regular_file_no_symlink, sha256_bytes
from ailsa.record.log import RecordWriteRefused, append_event, read_events
from ailsa.record.resolve import SESSION_ID_RE

PROJECTS_ROOT_ENV = "AILSA_CLAUDE_PROJECTS"
DEFAULT_MAX_TOTAL = 200 * 1024 * 1024
TRANSCRIPT_DIR = "transcript"


def _projects_root(projects_root: str | os.PathLike[str] | None) -> Path:
    if projects_root is not None:
        return Path(projects_root)
    env = os.environ.get(PROJECTS_ROOT_ENV)
    if env:
        return Path(env).expanduser()
    return Path.home() / ".claude" / "projects"


def find_session_transcript(
    session_id: str | None, projects_root: str | os.PathLike[str] | None = None
) -> Path | None:
    if not session_id or not SESSION_ID_RE.match(session_id):
        return None
    root = _projects_root(projects_root)
    try:
        for folder in sorted(root.iterdir()):
            candidate = folder / f"{session_id}.jsonl"
            if is_regular_file_no_symlink(candidate):
                return candidate
    except OSError:
        return None
    return None


def _sources(main: Path) -> list[tuple[Path, str]]:
    """(source file, name below transcript/) for the main transcript and its subagents."""
    found: list[tuple[Path, str]] = [(main, main.name)]
    sub_dir = main.with_suffix("") / "subagents"
    try:
        entries = sorted(sub_dir.iterdir())
    except OSError:
        entries = []
    for entry in entries:
        if entry.name.endswith((".jsonl", ".meta.json")):
            found.append((entry, f"subagents/{entry.name}"))
    return found


def _actor(via: str) -> dict[str, Any]:
    kind = "hook" if via == "session_end" else "launcher" if via == "launcher" else "tool"
    return {"kind": kind, "name": f"transcript.{via}"}


def copy_transcripts(
    run_dir: str | os.PathLike[str],
    transcript_path: str | os.PathLike[str] | None,
    session_id: str | None,
    *,
    via: str,
    max_total: int = DEFAULT_MAX_TOTAL,
) -> list[dict[str, Any]]:
    run = Path(run_dir)
    main = Path(transcript_path) if transcript_path else None
    if main is None or not is_regular_file_no_symlink(main):
        main = find_session_transcript(session_id)
    if main is None or not is_regular_file_no_symlink(main):
        return []
    target_root = run / TRANSCRIPT_DIR
    copied: list[dict[str, Any]] = []
    total = 0
    cut_off = False
    for src, name in _sources(main):
        if not is_regular_file_no_symlink(src):
            continue
        try:
            data = src.read_bytes()
        except OSError:
            continue
        total += len(data)
        if total > max_total:
            cut_off = True
            break
        digest = sha256_bytes(data)
        target = target_root / name
        if is_regular_file_no_symlink(target):
            try:
                if sha256_bytes(target.read_bytes()) == digest:
                    continue
            except OSError:
                pass
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        atomic_write_bytes(target, data)
        copied.append({"name": name, "sha256": digest, "bytes": len(data)})
    try:
        if copied:
            append_event(
                run,
                "transcript.copied",
                {"files": copied, "via": via},
                actor=_actor(via),
                allow_after_finish=True,
            )
        if cut_off:
            append_event(
                run,
                "warning.raised",
                {
                    "code": "transcript_size_cap",
                    "message": f"transcript copy stopped above {max_total} bytes",
                },
                actor=_actor(via),
            )
    except RecordWriteRefused:
        pass
    return copied


def models_from_transcript(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """First assistant line per agent: requested (``requestedModel``) and actual model."""
    seen: dict[str, dict[str, Any]] = {}
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return []
    with fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict) or obj.get("type") != "assistant":
                continue
            message = obj.get("message")
            actual = message.get("model") if isinstance(message, dict) else None
            requested = obj.get("requestedModel")
            if not actual and not requested:
                continue
            agent = str(obj.get("agentId") or "main")
            if agent not in seen:
                seen[agent] = {"agent": agent, "requested": requested, "actual": actual}
    return list(seen.values())


def record_transcript_models(run_dir: str | os.PathLike[str], files: list[Path]) -> int:
    """Append one agent.model_reported (source transcript) per agent; no duplicates."""
    run = Path(run_dir)
    known = {
        str((ev.get("payload") or {}).get("agent"))
        for ev in read_events(run)["events"]
        if ev.get("type") == "agent.model_reported"
        and (ev.get("payload") or {}).get("source") == "transcript"
    }
    added = 0
    for file in files:
        if not str(file).endswith(".jsonl"):
            continue
        for entry in models_from_transcript(file):
            if entry["agent"] in known:
                continue
            known.add(entry["agent"])
            payload = {**entry, "source": "transcript"}
            try:
                append_event(
                    run,
                    "agent.model_reported",
                    payload,
                    actor={"kind": "hook", "name": "transcript"},
                    allow_after_finish=True,
                )
            except RecordWriteRefused:
                continue
            added += 1
    return added
