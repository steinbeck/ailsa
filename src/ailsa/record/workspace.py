"""Workspace, configuration, host alias, run id minting and run folder creation.

Standard library only. POSIX only (``fcntl``): Windows is out of scope.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import secrets
import socket
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ailsa.record.events import (
    AGENT_DIR,
    MARKER,
    SCHEMA_VERSION,
    WORKSPACE_LOCK,
)
from ailsa.record.fsutil import atomic_write_json

WORKSPACE_ENV = "AILSA_WORKSPACE"
CONFIG_ENV = "AILSA_CONFIG"

_SUFFIX_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
_LABEL_MAX = 40
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def config_path() -> Path:
    env = os.environ.get(CONFIG_ENV)
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ailsa" / "config.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        print(f"ailsa: warning: config file {path} is not valid JSON; ignored", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def workspace_root(create: bool = True) -> Path:
    env = os.environ.get(WORKSPACE_ENV)
    if env:
        root = Path(env).expanduser()
    else:
        cfg = load_config().get("workspace")
        root = Path(str(cfg)).expanduser() if cfg else Path.home() / "ailsa-runs"
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def workspace_warnings(root: str | os.PathLike[str]) -> list[str]:
    warnings: list[str] = []
    if "dropbox" in str(root).lower():
        warnings.append(
            "workspace is inside a Dropbox folder: file locks and the one-writer rule "
            "are unreliable on sync folders"
        )
    return warnings


def sanitize_label(text: str) -> str:
    label = _SAFE.sub("_", text or "")
    label = re.sub(r"\.{2,}", ".", label)
    label = label.lstrip(".-")[:_LABEL_MAX].rstrip(".")
    return label or "run"


def host_alias() -> str:
    cfg = load_config().get("host_alias")
    raw = str(cfg) if cfg else socket.gethostname().split(".")[0]
    return sanitize_label(raw.lower()).lower()


def _suffix() -> str:
    return "".join(secrets.choice(_SUFFIX_ALPHABET) for _ in range(4))


def mint_run_id(label: str, now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    return f"{moment.strftime('%Y-%m-%dT%H%M')}Z_{sanitize_label(label)}_{_suffix()}"


def create_run_dir(
    root: str | os.PathLike[str], label: str, now: datetime | None = None
) -> tuple[str, Path]:
    base = Path(root)
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    for _ in range(20):
        run_id = mint_run_id(label, now)
        run_dir = base / run_id
        try:
            os.mkdir(run_dir, 0o700)
        except FileExistsError:
            continue
        os.chmod(run_dir, 0o700)
        os.mkdir(run_dir / AGENT_DIR, 0o700)
        atomic_write_json(run_dir / MARKER, {"run_id": run_id, "schema_version": SCHEMA_VERSION})
        return run_id, run_dir
    raise FileExistsError("could not create a unique run folder after 20 attempts")


@contextmanager
def workspace_lock(root: str | os.PathLike[str], timeout: float = 30.0) -> Iterator[None]:
    fd = os.open(os.path.join(root, WORKSPACE_LOCK), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise TimeoutError("workspace lock busy") from None
                time.sleep(0.02)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def find_run(root: str | os.PathLike[str], run_id_or_path: str) -> Path | None:
    if not run_id_or_path:
        return None
    if os.path.isabs(run_id_or_path):
        path = Path(run_id_or_path)
        return path if path.is_dir() else None
    if "/" in run_id_or_path or ".." in run_id_or_path or run_id_or_path.startswith("."):
        return None
    path = Path(root) / run_id_or_path
    return path if path.is_dir() else None
