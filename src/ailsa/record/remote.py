"""Run LSD on a compute host over SSH (REC-31).

The solve runs detached on the host and is polled, so a dropped connection does not kill it.
Inputs go up as one tar stream, outputs come back as one tar stream into the caller's folder,
and the remote scratch folder is removed afterwards. Nothing here writes into a run folder.

Only the host *alias* (from the user's ``~/.ssh/config``) is ever used or recorded.
"""

from __future__ import annotations

import io
import os
import re
import secrets
import shlex
import signal
import subprocess
import tarfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_SCRATCH_RE = re.compile(r"^/[^\s\x00'\"\\]*/ailsa-lsd\.[A-Za-z0-9]{6}$")
_FETCH_OTHER = ("solncounter", "lsd.out", "lsd.err", "solutions.smi")
_GRACE_S = 60.0


class RemoteError(RuntimeError):
    """A remote step failed."""


class RemoteUnreachable(RemoteError):
    """The host could not be reached over SSH."""


@dataclass
class RemoteResult:
    host: str
    scratch_dir: str | None
    lsd: dict[str, Any]
    outlsd: dict[str, Any]
    elapsed_s: float
    timed_out: bool
    partial_count: int | None
    count: int
    outcome: str
    smiles_absent_reason: str | None
    error_line: str | None
    exit_code: int | None
    stdout: str
    stderr: str
    limit: int | None = None


def validate_alias(alias: str) -> str:
    if not isinstance(alias, str) or not ALIAS_RE.match(alias) or ".." in alias:
        raise ValueError(f"invalid host alias: {alias!r}")
    return alias


def _ssh(
    alias: str,
    script: str,
    *,
    stdin: bytes | None = None,
    timeout: float = 60,
) -> subprocess.CompletedProcess[bytes]:
    """Run ``script`` in a login shell on the host; stdout holds only what the script printed.

    A login shell may print banners (conda, module systems, echo in a profile) before the
    script runs. The script first prints a marker line unique to this call, and everything up
    to it is dropped, so the probe, the poll and the fetched tar stream are never corrupted.
    """
    marker = f"AILSA-OUT-{secrets.token_hex(8)}"
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "--",
        validate_alias(alias),
        "bash -lc " + shlex.quote(f"printf '%s\\n' {marker}\n{script}"),
    ]
    try:
        proc = subprocess.run(
            argv,
            input=stdin if stdin is not None else b"",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 255, b"", b"ssh call timed out")
    token = marker.encode("ascii") + b"\n"
    at = proc.stdout.find(token)
    if at >= 0:
        proc.stdout = proc.stdout[at + len(token) :]
    return proc


def _text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def _host_overrides(alias: str) -> dict[str, Any]:
    from ailsa.record.workspace import load_config

    hosts = load_config().get("hosts")
    entry = hosts.get(alias) if isinstance(hosts, dict) else None
    return entry if isinstance(entry, dict) else {}


def _probe_script(overrides: dict[str, Any]) -> str:
    scratch = overrides.get("scratch")
    root = shlex.quote(str(scratch)) if scratch else "${TMPDIR:-/tmp}"
    lsd = shlex.quote(str(overrides["lsd"])) if overrides.get("lsd") else (
        '$(command -v LSD || command -v lsd)'
    )
    outlsd = shlex.quote(str(overrides["outlsd"])) if overrides.get("outlsd") else (
        "$(command -v outlsd)"
    )
    return f"""set -u
root={root}
root=${{root%/}}
d=$(mktemp -d "$root/ailsa-lsd.XXXXXX") || exit 3
echo "root=$root"
echo "scratch=$d"
lsd={lsd}
ol={outlsd}
h() {{
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}}
t=""
if command -v timeout >/dev/null 2>&1; then t="timeout 10"; fi
echo "lsd=$lsd"
if [ -n "$lsd" ] && [ -x "$lsd" ]; then
  mkdir "$d/probe"
  echo "banner=$(cd "$d/probe" && $t "$lsd" </dev/null 2>&1 | head -3 | tr '\\n' ' ')"
  echo "lsd_sha=$(h "$lsd")"
fi
echo "outlsd=$ol"
if [ -n "$ol" ] && [ -x "$ol" ]; then echo "outlsd_sha=$(h "$ol")"; fi
if command -v setsid >/dev/null 2>&1; then echo "setsid=1"; fi
if command -v timeout >/dev/null 2>&1; then echo "timeout=1"; fi
"""


def probe_remote(alias: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """One round trip: scratch folder, binaries, versions, hashes, available tools."""
    from ailsa.record.env import parse_lsd_banner

    ov = _host_overrides(alias) if overrides is None else overrides
    proc = _ssh(alias, _probe_script(ov), timeout=60)
    if proc.returncode == 255:
        raise RemoteUnreachable(alias)
    if proc.returncode != 0:
        raise RemoteError(f"remote probe failed on {alias}: {_text(proc.stderr)[:200]}")
    kv = _kv(_text(proc.stdout))
    scratch = kv.get("scratch", "")
    root = kv.get("root", "")
    if not _scratch_ok(root, scratch):
        raise RemoteError("remote scratch folder has an unexpected name")
    return {
        "root": root,
        "scratch": scratch,
        "lsd": {
            "path": kv.get("lsd") or None,
            "version": parse_lsd_banner(kv.get("banner", "")),
            "sha256": kv.get("lsd_sha") or None,
        },
        "outlsd": {
            "path": kv.get("outlsd") or None,
            "version": None,
            "sha256": kv.get("outlsd_sha") or None,
        },
        "setsid": kv.get("setsid") == "1",
        "timeout": kv.get("timeout") == "1",
    }


def _scratch_ok(root: str, path: str) -> bool:
    if not root or ".." in root or not root.startswith("/") or not _SCRATCH_RE.match(path):
        return False
    return path.rsplit("/", 1)[0] == root


def _safe_name(name: str) -> str:
    if name != os.path.basename(name) or not _NAME_RE.match(name) or name.startswith(".."):
        raise ValueError(f"unsafe file name in LSD input: {name!r}")
    return name


def _deff_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(";") or not stripped.upper().startswith("DEFF"):
            continue
        for quoted in re.findall(r'"([^"]*)"', stripped):
            names.append(_safe_name(quoted))
    return names


def stage_inputs(
    input_file: str | os.PathLike[str], stage_dir: str | os.PathLike[str]
) -> list[str]:
    """Copy the input, ring3/ring4 and files named by DEFF lines (basename only) into stage_dir."""
    from ailsa.lsd.generator import LSDInputGenerator

    src = Path(input_file)
    stage = Path(stage_dir)
    stage.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8", errors="replace")
    wanted = _deff_names(text)
    name = _safe_name(src.name)
    (stage / name).write_bytes(src.read_bytes())
    LSDInputGenerator._write_filter_files(stage)
    staged = [name, "ring3", "ring4"]
    for extra in wanted:
        if extra in staged:
            continue
        candidate = src.parent / extra
        if candidate.is_file() and not candidate.is_symlink():
            (stage / extra).write_bytes(candidate.read_bytes())
            staged.append(extra)
    return staged


def _tar_bytes(stage: Path, names: list[str], run_sh: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name in names:
            tar.add(str(stage / name), arcname=name, recursive=False)
        data = run_sh.encode("utf-8")
        info = tarfile.TarInfo("run.sh")
        info.size = len(data)
        info.mode = 0o755
        info.mtime = int(time.time())
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _run_sh(
    stem: str, name: str, lsd: str, outlsd: str | None, timeout_s: int, use_timeout: bool
) -> str:
    prefix = f"timeout {int(timeout_s)} " if use_timeout else ""
    convert = ""
    if outlsd:
        convert = (
            f"if [ -f {shlex.quote(stem + '.sol')} ] && "
            "! grep -qE 'No solution found|^ *error [0-9]' lsd.out lsd.err 2>/dev/null; then\n"
            f"  {shlex.quote(outlsd)} 5 < {shlex.quote(stem + '.sol')} "
            "> solutions.smi 2>outlsd.err\n"
            "fi\n"
        )
    return (
        "#!/bin/bash\n"
        'cd "$(dirname "$0")" || exit 1\n'
        f"{prefix}{shlex.quote(lsd)} {shlex.quote(name)} >lsd.out 2>lsd.err &\n"
        "echo $! > lsdpid\n"
        "wait $!\n"
        "code=$?\n"
        f"{convert}"
        "echo $code > rc.tmp\n"
        "mv rc.tmp rc\n"
    )


def _kill_script(scratch: str) -> str:
    return (
        f"cd {shlex.quote(scratch)} || exit 0\n"
        "for f in pid lsdpid; do\n"
        '  p=$(cat "$f" 2>/dev/null)\n'
        '  if [ -n "$p" ]; then kill -TERM -- "-$p" 2>/dev/null; kill -TERM "$p" 2>/dev/null; fi\n'
        "done\n"
        "true\n"
    )


def _extract_outputs(blob: bytes, out_dir: Path, allowed: set[str]) -> None:
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r") as tar:
        for member in tar.getmembers():
            name = member.name
            if name.startswith("./"):
                name = name[2:]
            if (
                not member.isreg()
                or "/" in name
                or name.startswith("..")
                or name not in allowed
            ):
                raise RemoteError(f"unexpected member in fetched archive: {member.name!r}")
            fh = tar.extractfile(member)
            if fh is None:
                raise RemoteError(f"unreadable member in fetched archive: {member.name!r}")
            _write_no_follow(out_dir / name, fh.read())


def _write_no_follow(path: Path, data: bytes, *, exclusive: bool = False) -> None:
    """Write a file, refusing (OSError) when ``path`` is a symlink: never write through one."""
    from ailsa.record.fsutil import write_all

    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_EXCL if exclusive else os.O_TRUNC)
    if os.path.islink(path):
        raise OSError(f"refusing to write through a symlink: {path}")
    fd = os.open(path, flags, 0o644)
    try:
        write_all(fd, data)
    finally:
        os.close(fd)


def _smiles_ok(path: Path) -> bool:
    try:
        lines = [ln.strip() for ln in path.read_text(errors="replace").splitlines() if ln.strip()]
    except OSError:
        return False
    if not lines:
        return False
    first = lines[0]
    if first.startswith("outlsd:") or "This is not a file for OUTLSD" in first:
        return False
    try:
        from rdkit import Chem, RDLogger

        RDLogger.DisableLog("rdApp.*")  # type: ignore[attr-defined]
        return Chem.MolFromSmiles(first.split()[0]) is not None
    except ImportError:
        return True


def _count_text(out: str, err: str, out_dir: Path) -> int:
    for text in (out, err):
        for line in text.splitlines():
            match = re.search(r"(\d+)\s+solution", line.lower())
            if match:
                return int(match.group(1))
    from ailsa.lsd.runner import read_solncounter

    counter = read_solncounter(out_dir)
    return counter if counter is not None else 0


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _classify(
    input_file: Path,
    out_dir: Path,
    *,
    code: int | None,
    killed: bool,
    last_counter: int | None,
) -> tuple[str, str | None, int, int | None, str | None, bool, str, str, int | None]:
    from ailsa.lsd.runner import (
        _TIME_STOP,
        LSDRunner,
        classify_outcome,
        maxs_limit,
        read_solncounter,
    )

    out = _read(out_dir / "lsd.out")
    err = _read(out_dir / "lsd.err")
    combined = out + "\n" + err
    limit = maxs_limit(_read(input_file))
    error_line = LSDRunner._lsd_error(combined) or None
    timed_out = killed or code == 124 or bool(_TIME_STOP.search(combined))
    sol = out_dir / f"{input_file.stem}.sol"
    partial: int | None = None
    if timed_out:
        partial = read_solncounter(out_dir)
        if partial is None:
            partial = last_counter if last_counter is not None else 0
        count = partial
    else:
        count = _count_text(out, err, out_dir)
    smi = out_dir / "solutions.smi"
    smiles_ok = _smiles_ok(smi) if smi.exists() else False
    outcome, absent = classify_outcome(
        started=True,
        blocked=False,
        error_line=error_line,
        timed_out=timed_out and not error_line,
        count=count,
        limit=limit,
        no_solution_text="No solution found" in combined,
        sol_exists=sol.exists(),
        smiles_ok=smiles_ok if count > 0 and not timed_out else None,
        conversion_skipped=False,
    )
    return outcome, absent, count, partial, error_line, timed_out, out, err, limit


def _cleanup(alias: str, root: str, scratch: str) -> bool:
    if not _scratch_ok(root, scratch):
        return False
    proc = _ssh(alias, f"rm -rf -- {shlex.quote(scratch)}", timeout=60)
    return proc.returncode == 0


def _tool(info: dict[str, Any]) -> dict[str, Any]:
    path = info.get("path")
    return {
        "path": os.path.basename(path) if path else None,
        "version": info.get("version"),
        "sha256": info.get("sha256"),
    }


def solve_remote(
    alias: str,
    input_file: str | os.PathLike[str],
    local_output_dir: str | os.PathLike[str],
    *,
    timeout_s: int,
    poll_s: float | None = None,
) -> RemoteResult:
    """Upload, start detached, poll, fetch into ``local_output_dir``, remove the scratch folder."""
    alias = validate_alias(alias)
    src = Path(input_file)
    out_dir = Path(local_output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if poll_s is None:
        poll_s = float(os.environ.get("AILSA_REMOTE_POLL_S") or 10)
    name = _safe_name(src.name)
    stem = src.stem

    info = probe_remote(alias)
    with _sigterm_raises():
        try:
            return _solve_probed(alias, src, out_dir, info, name, stem, timeout_s, poll_s)
        except BaseException as exc:
            # Interrupt (Ctrl-C), SIGTERM (e.g. a Bash-tool timeout) or an unexpected error
            # after the probe: never leave LSD running or the scratch folder behind. The
            # RemoteError paths have already cleaned up.
            if not isinstance(exc, RemoteError):
                _abort_remote(alias, info["root"], info["scratch"])
            raise


class _Terminated(BaseException):
    """SIGTERM arrived during a remote solve."""


@contextmanager
def _sigterm_raises() -> Iterator[None]:
    """Turn SIGTERM into an exception (main thread only) so the remote cleanup runs."""
    import threading

    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def handler(signum: int, frame: Any) -> None:
        raise _Terminated(signum)

    old = signal.signal(signal.SIGTERM, handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, old)


def _abort_remote(alias: str, root: str, scratch: str) -> None:
    """Best effort: stop the remote solve and remove its scratch folder."""
    try:
        _ssh(alias, _kill_script(scratch), timeout=30)
        _cleanup(alias, root, scratch)
    except BaseException:  # noqa: BLE001 - never mask the exception being handled
        pass


def _solve_probed(
    alias: str,
    src: Path,
    out_dir: Path,
    info: dict[str, Any],
    name: str,
    stem: str,
    timeout_s: int,
    poll_s: float,
) -> RemoteResult:
    import tempfile

    root, scratch = info["root"], info["scratch"]
    lsd_path = info["lsd"]["path"]
    result_tools = (_tool(info["lsd"]), _tool(info["outlsd"]))

    def _finish_early(reason: str) -> RemoteResult:
        kept = None if _cleanup(alias, root, scratch) else scratch
        return RemoteResult(
            host=alias,
            scratch_dir=kept,
            lsd=result_tools[0],
            outlsd=result_tools[1],
            elapsed_s=0.0,
            timed_out=False,
            partial_count=None,
            count=0,
            outcome="not_run",
            smiles_absent_reason="not_run",
            error_line=reason,
            exit_code=None,
            stdout="",
            stderr=reason,
        )

    if not lsd_path or not info["lsd"]["sha256"]:
        return _finish_early(f"LSD not found on host {alias}")

    with tempfile.TemporaryDirectory(prefix="ailsa-stage-") as stage_name:
        stage = Path(stage_name)
        try:
            staged = stage_inputs(src, stage)
        except ValueError:
            _cleanup(alias, root, scratch)
            raise
        for filt in ("ring3", "ring4"):
            if not os.path.lexists(out_dir / filt):
                try:
                    _write_no_follow(out_dir / filt, (stage / filt).read_bytes(), exclusive=True)
                except OSError:
                    pass
        outlsd_path = info["outlsd"]["path"] if info["outlsd"]["sha256"] else None
        script = _run_sh(stem, name, lsd_path, outlsd_path, timeout_s, info["timeout"])
        blob = _tar_bytes(stage, staged, script)

    up = _ssh(alias, f"cd {shlex.quote(scratch)} && tar xf -", stdin=blob, timeout=120)
    if up.returncode != 0:
        kept = None if _cleanup(alias, root, scratch) else scratch
        raise RemoteError(
            f"upload to {alias} failed: {_text(up.stderr)[:200]}"
            + (f" (scratch kept: {kept})" if kept else "")
        )

    start = (
        f"cd {shlex.quote(scratch)} || exit 1\n"
        + (
            "setsid nohup bash run.sh >/dev/null 2>&1 </dev/null &\n"
            if info["setsid"]
            else "nohup bash run.sh >/dev/null 2>&1 </dev/null &\n"
        )
        + "echo $! > pid\n"
    )
    t0 = time.monotonic()
    started = _ssh(alias, start, timeout=60)
    if started.returncode != 0:
        kept = None if _cleanup(alias, root, scratch) else scratch
        note = f" (scratch kept: {kept})" if kept else ""
        raise RemoteError(f"could not start LSD on {alias}{note}")

    deadline = timeout_s + (_GRACE_S if info["timeout"] else 0)
    poll = (
        f"cd {shlex.quote(scratch)} || exit 0\n"
        '[ -f rc ] && echo "rc=$(cat rc)"\n'
        '[ -f solncounter ] && echo "cnt=$(head -1 solncounter | cut -d" " -f1)"\n'
        "true\n"
    )
    code: int | None = None
    last_counter: int | None = None
    killed = False
    while True:
        proc = _ssh(alias, poll, timeout=60)
        if proc.returncode == 0:
            kv = _kv(_text(proc.stdout))
            if kv.get("cnt", "").isdigit():
                last_counter = int(kv["cnt"])
            if kv.get("rc", "").lstrip("-").isdigit():
                code = int(kv["rc"])
                break
        if time.monotonic() - t0 > deadline:
            _ssh(alias, _kill_script(scratch), timeout=60)
            killed = True
            time.sleep(min(poll_s, 1.0))
            break
        time.sleep(poll_s)
    elapsed = time.monotonic() - t0

    names = [f"{stem}.sol", *_FETCH_OTHER]
    # Local files of an earlier solve must never be read or recorded as this solve's result:
    # only what this solve fetches below may be there afterwards.
    from ailsa.lsd.runner import clear_solver_outputs

    clear_solver_outputs(out_dir, stem, extra=tuple(_FETCH_OTHER))
    fetch = (
        f"cd {shlex.quote(scratch)} || exit 1\n"
        'files=""\n'
        f"for f in {' '.join(shlex.quote(n) for n in names)}; do\n"
        '  [ -f "$f" ] && files="$files $f"\n'
        "done\n"
        '[ -n "$files" ] && tar cf - $files\n'
        "true\n"
    )
    got = _ssh(alias, fetch, timeout=180)
    fetched = got.returncode == 0
    if fetched:
        try:
            if got.stdout:
                _extract_outputs(got.stdout, out_dir, set(names))
        except (RemoteError, tarfile.TarError, OSError):
            fetched = False
    if not fetched:
        return RemoteResult(
            host=alias,
            scratch_dir=scratch,
            lsd=result_tools[0],
            outlsd=result_tools[1],
            elapsed_s=elapsed,
            timed_out=killed,
            partial_count=last_counter if killed else None,
            count=0,
            outcome="error",
            smiles_absent_reason="error",
            error_line="fetch of solver outputs failed",
            exit_code=code,
            stdout="",
            stderr="fetch of solver outputs failed",
        )

    outcome, absent, count, partial, error_line, timed_out, out, err, limit = _classify(
        src, out_dir, code=code, killed=killed, last_counter=last_counter
    )
    kept = None if _cleanup(alias, root, scratch) else scratch
    return RemoteResult(
        host=alias,
        scratch_dir=kept,
        lsd=result_tools[0],
        outlsd=result_tools[1],
        elapsed_s=elapsed,
        timed_out=timed_out,
        partial_count=partial,
        count=count,
        outcome=outcome,
        smiles_absent_reason=absent,
        error_line=error_line,
        exit_code=code,
        stdout=out,
        stderr=err,
        limit=limit,
    )
