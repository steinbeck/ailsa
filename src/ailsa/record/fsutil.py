"""Atomic file helpers and hashing (standard library only)."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_bytes(
    path: str | os.PathLike[str], data: bytes, *, fsync: bool = False, mode: int = 0o600
) -> None:
    """Write ``data`` to ``path`` via a temp file in the same folder and ``os.replace``."""
    target = Path(path)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        try:
            os.write(fd, data)
            if fsync:
                os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path: str | os.PathLike[str], obj: Any, *, fsync: bool = False) -> None:
    """Write ``obj`` as sorted, two-space-indented JSON with a trailing newline."""
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    atomic_write_bytes(path, text.encode("utf-8"), fsync=fsync)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | os.PathLike[str], chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def is_regular_file_no_symlink(path: str | os.PathLike[str]) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode)
