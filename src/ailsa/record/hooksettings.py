"""Generate and install the Claude Code hook settings of the run record (stdlib only).

One definition (``HOOK_EVENTS``) serves the launcher's per-run ``--settings`` file and the
reversible merge into a user settings file. Exec form is used (proven in the hook spike).
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ailsa.record.fsutil import atomic_write_bytes

MODULE = "ailsa.record.hook"
OWN_MARKERS = ("ailsa.record.hook", "ailsa-hook")
TOOL_MATCHER = "Bash|Agent|SendMessage|SubagentHandback"

# (event name, matcher, handler options)
HOOK_EVENTS: list[tuple[str, str | None, dict[str, Any]]] = [
    ("SessionStart", None, {"timeout": 10}),
    ("UserPromptSubmit", None, {"timeout": 10}),
    ("Notification", None, {"timeout": 10}),
    ("PermissionRequest", None, {"timeout": 10}),
    ("SubagentStart", None, {"timeout": 10}),
    ("SubagentStop", None, {"timeout": 10}),
    ("PostToolUse", TOOL_MATCHER, {"timeout": 10, "async": True}),
    ("PreCompact", None, {"timeout": 10}),
    ("PostCompact", None, {"timeout": 10}),
    ("Stop", None, {"timeout": 10}),
    ("StopFailure", None, {"timeout": 10}),
    ("SessionEnd", None, {"timeout": 30}),
    ("PostModelSwitch", None, {"timeout": 10}),
]


def handler(python_exe: str, **options: Any) -> dict[str, Any]:
    # -I (isolated mode): Claude Code runs hooks in the session's folder, and plain ``-m`` would
    # put that folder first on sys.path, so a planted json.py there would run on every event.
    out: dict[str, Any] = {
        "type": "command",
        "command": python_exe,
        "args": ["-I", "-m", MODULE],
    }
    out.update(options)
    return out


def build_settings(
    python_exe: str = sys.executable, *, auto_memory: bool | None = None
) -> dict[str, Any]:
    hooks: dict[str, list[dict[str, Any]]] = {}
    for event, matcher, options in HOOK_EVENTS:
        group: dict[str, Any] = {"hooks": [handler(python_exe, **options)]}
        if matcher is not None:
            group["matcher"] = matcher
        hooks.setdefault(event, []).append(group)
    settings: dict[str, Any] = {"hooks": hooks}
    if auto_memory is False:
        settings["autoMemoryEnabled"] = False
    return settings


def is_ours(h: Any) -> bool:
    if not isinstance(h, dict):
        return False
    parts = [str(h.get("command", ""))]
    args = h.get("args")
    if isinstance(args, list):
        parts.extend(str(a) for a in args)
    text = " ".join(parts)
    return any(marker in text for marker in OWN_MARKERS)


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"settings file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"settings file is not a JSON object: {path}")
    return data


def _strip_ours(data: dict[str, Any]) -> int:
    """Remove our handlers in place; drop emptied groups and event lists."""
    removed = 0
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept = []
        for group in groups:
            inner = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(inner, list):
                kept.append(group)
                continue
            mine = [h for h in inner if is_ours(h)]
            removed += len(mine)
            if not mine:
                kept.append(group)
            elif len(mine) < len(inner):
                kept.append({**group, "hooks": [h for h in inner if not is_ours(h)]})
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks:
        data.pop("hooks", None)
    return removed


def _backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = path.with_name(f"{path.name}.ailsa-backup-{stamp}")
    shutil.copy2(path, target)
    return target


def _indent_of(text: str) -> int | str:
    """The indentation the user's file uses (first indented line), default two spaces."""
    for line in text.splitlines()[1:]:
        body = line.lstrip(" \t")
        if body and len(body) < len(line):
            lead = line[: len(line) - len(body)]
            return "\t" if lead.startswith("\t") else len(lead)
    return 2


def _write_settings(path: Path, data: dict[str, Any]) -> None:
    """Write the merged settings without disturbing the user's file more than needed.

    A symlinked settings file (dotfile managers) is written through to its target, never
    replaced by a regular file; key order, indentation and the file mode are kept.
    """
    target = Path(os.path.realpath(path))
    try:
        original = target.read_text(encoding="utf-8")
        mode = stat.S_IMODE(os.stat(target).st_mode)
    except OSError:
        original, mode = "", 0o600
    text = json.dumps(data, indent=_indent_of(original), ensure_ascii=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(target, text.encode("utf-8"), mode=mode)


def install(settings_path: str | os.PathLike[str], python_exe: str = sys.executable) -> Path | None:
    path = Path(settings_path)
    data = _load(path)
    original = copy.deepcopy(data)
    _strip_ours(data)
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"'hooks' is not an object in {path}")
    for event, groups in build_settings(python_exe)["hooks"].items():
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            raise ValueError(f"hooks.{event} is not a list in {path}")
        existing.extend(groups)
    if data == original and path.exists():
        return None
    backup = _backup(path) if path.exists() else None
    _write_settings(path, data)
    return backup


def uninstall(settings_path: str | os.PathLike[str]) -> int:
    path = Path(settings_path)
    if not path.exists():
        return 0
    data = _load(path)
    removed = _strip_ours(data)
    if removed:
        _backup(path)
        _write_settings(path, data)
    return removed
