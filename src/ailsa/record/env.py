"""Environment probe for the run record (REC-24).

Records named fields only (never the process environment). Every external call has a 5 s
timeout and every sub-probe fails soft. Standard library only at module level.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ailsa.record.fsutil import sha256_file

DATABASE_DOI = "10.6084/m9.figshare.31073554"
_BANNER = re.compile(r"LSD-(\d+(?:\.\d+){1,2})")


def parse_lsd_banner(text: str) -> str | None:
    match = _BANNER.search(text or "")
    return match.group(1) if match else None


def _run(cmd: list[str], cwd: str | None = None) -> str:
    """Stdout plus stderr of a short command; the exit code is deliberately ignored."""
    proc = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=5,
        cwd=cwd,
    )
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def probe_binary(
    names: tuple[str, ...], *, banner: bool, path: str | os.PathLike[str] | None = None
) -> dict[str, Any]:
    """Version and sha256 of ``path`` (the binary that ran), or of the first of ``names``
    on PATH when no path is given."""
    found: str | None = str(path) if path else None
    if found is None:
        for name in names:
            found = shutil.which(name)
            if found:
                break
    if not found or not os.path.isfile(found):
        return {"path": None, "version": None, "sha256": None}
    version = None
    if banner:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                version = parse_lsd_banner(_run([found], cwd=tmp))
        except (OSError, subprocess.SubprocessError):
            version = None
    try:
        digest: str | None = sha256_file(found)
    except OSError:
        digest = None
    return {"path": found, "version": version, "sha256": digest}


def probe_lsd(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    return probe_binary(("LSD", "lsd"), banner=True, path=path)


def probe_outlsd(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    return probe_binary(("outlsd",), banner=False, path=path)


def _package_root() -> Path:
    return Path(__file__).resolve().parents[3]


def ailsa_version_info() -> dict[str, Any]:
    from ailsa._version import __version__

    info: dict[str, Any] = {"version": __version__, "commit": None, "dirty": None}
    root = _package_root()
    if not (root / ".git").exists():
        return info
    try:
        commit = _run(["git", "-C", str(root), "rev-parse", "HEAD"]).strip().splitlines()[0]
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError, IndexError):
        return info
    if re.fullmatch(r"[0-9a-f]{40}", commit):
        info["commit"] = commit
        info["dirty"] = bool(status.stdout.strip())
    return info


def _cache_file() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "ailsa" / "db-sha256.json"


def _cached_sha256(path: Path) -> str:
    st = path.stat()
    key = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    cache_path = _cache_file()
    cache: dict[str, str] = {}
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    if key in cache:
        return cache[key]
    digest = sha256_file(path)
    cache[key] = digest
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        pass
    return digest


def resolve_database_path() -> Path | None:
    env_db = os.environ.get("LUCY_DATABASE")
    if env_db and Path(env_db).is_file():
        return Path(env_db)
    from ailsa.database.finder import DatabaseFinder

    return DatabaseFinder.find_hose_database()


def database_info(path: Path | None) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": None,
        "doi": DATABASE_DOI,
        "sha256": None,
        "schema_version": None,
        "compound_count": None,
    }
    if path is None or not Path(path).is_file():
        return info
    path = Path(path)
    info["path"] = str(path)
    info["sha256"] = _cached_sha256(path)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    try:
        try:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = ?", ("schema_version",)
            ).fetchone()
            info["schema_version"] = int(row[0]) if row else None
        except sqlite3.Error:
            pass
        try:
            row = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()
            info["compound_count"] = int(row[0]) if row else None
        except sqlite3.Error:
            pass
    finally:
        conn.close()
    return info


def skill_file_hashes(skill_dir: Path) -> dict[str, str]:
    root = Path(skill_dir)
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not (Path(dirpath) / d).is_symlink())
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            out[path.relative_to(root).as_posix()] = sha256_file(path)
    return out


def skill_info(skill_dir: Path | None) -> dict[str, Any]:
    if skill_dir is None:
        return {"name": None, "version": None, "files": {}}
    root = Path(skill_dir)
    name = version = None
    skill_md = root / "SKILL.md"
    if skill_md.is_file():
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        v = re.search(r'^\s+version:\s*"?([^"\n]+)"?', text, re.MULTILINE)
        name = m.group(1) if m else None
        version = v.group(1).strip() if v else None
    return {"name": name or root.name, "version": version, "files": skill_file_hashes(root)}


def detect_harness(env: Mapping[str, str] | None = None) -> str:
    env_map: Mapping[str, str] = os.environ if env is None else env
    named = env_map.get("AILSA_HARNESS")
    if named in ("claude-code", "opencode", "other"):
        return named
    if env_map.get("CLAUDECODE") == "1":
        return "claude-code"
    return "other"


def harness_version(name: str) -> str | None:
    exe = {"claude-code": "claude", "opencode": "opencode"}.get(name)
    if not exe or not shutil.which(exe):
        return None
    try:
        text = _run([exe, "--version"]).strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return text.splitlines()[0] if text else None


def _soft(fn: Any) -> Any:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - one failed probe must not stop the record
        return {"error": f"{type(exc).__name__}: {exc}"}


def probe_environment(
    *,
    skill_dir: Path | None = None,
    mode: str,
    time_limit_s: int | None = None,
    web_tools: str = "unknown",
    harness: str | None = None,
    predictor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    harness_name = harness or _soft(detect_harness)
    db_path = _soft(resolve_database_path)
    if isinstance(db_path, dict):
        database: Any = db_path
        db_path = None
    else:
        database = _soft(lambda: database_info(db_path))
    if predictor is None:
        predictor = {"backend": "sqlite" if db_path else None, "max_radius": 6}
    return {
        "ailsa": _soft(ailsa_version_info),
        "skill": _soft(lambda: skill_info(skill_dir)),
        "lsd": _soft(probe_lsd),
        "outlsd": _soft(probe_outlsd),
        "database": database,
        "predictor": predictor,
        "harness": {
            "name": harness_name,
            "version": _soft(lambda: harness_version(str(harness_name))),
        },
        "mode": mode,
        "time_limit_s": time_limit_s,
        "web_tools": web_tools,
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "node": socket.gethostname().split(".")[0],
        },
        "python": sys.version.split()[0],
    }
