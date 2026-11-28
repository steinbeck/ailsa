"""Create or reuse a run: ``ailsa run init`` (REC-06, REC-06a, REC-24, REC-28, REC-33, D-03..D-06).

Order: launcher reuse (``AILSA_RUN_DIR``), dataset checks, overlap check, fingerprint, session
reuse, then under the workspace lock the prior-run and legacy scans (blind refusal), the run
folder and ``run.created``. Environment, session binding, inventory and the view export follow
outside the lock. A failure after ``run.created`` becomes a ``warning.raised`` event and a
returned warning, never an exception: a run never aborts over bookkeeping.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ailsa.record.events import AGENT_DIR, FINISHED, INDEX, MARKER, RUN_CLASSES, WEB_TOOLS
from ailsa.record.fsutil import atomic_write_json, home_relative, scrub_home
from ailsa.record.log import append_event, first_event, read_events
from ailsa.record.workspace import (
    create_run_dir,
    host_alias,
    sanitize_label,
    workspace_lock,
    workspace_root,
    workspace_warnings,
)

NOT_BLIND_REASON = "not blind: earlier results were readable"
OPEN_SESSION_WEB_WARNING = (
    "web tools cannot be switched off from inside an open session; "
    "start the run with ailsa run start"
)
_TOOL = {"kind": "tool", "name": "ailsa run init"}
_PACKAGED_SKILLS = "skills"
# Blind runs: the agent can read the run folder (../events.jsonl), so values that could name
# the compound are never stored there. The options and their values leave the recorded argv.
BLIND_WITHHELD = "withheld (blind)"
_BLIND_SCRUBBED_OPTIONS = ("--label", "--source", "--licence", "--prompt")


def scrub_blind_args(args: Sequence[str]) -> list[str]:
    """``args`` without the options of _BLIND_SCRUBBED_OPTIONS and their values."""
    out: list[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg in _BLIND_SCRUBBED_OPTIONS:
            skip = True
            continue
        if arg.startswith(tuple(f"{opt}=" for opt in _BLIND_SCRUBBED_OPTIONS)):
            continue
        out.append(arg)
    return out


class InitRefused(Exception):
    """``init_run`` refuses to start; ``code`` names the reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _result(
    run_id: str, run_dir: Path, created: bool, warnings: list[str], views_pid: int | None
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "work_dir": str(run_dir / AGENT_DIR),
        "created": created,
        "warnings": warnings,
        "views_pid": views_pid,
    }


def _marker_id(run_dir: Path) -> str | None:
    try:
        return str(json.loads((run_dir / MARKER).read_text(encoding="utf-8"))["run_id"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _run_fingerprint(run_dir: Path) -> str | None:
    event = first_event(run_dir)
    payload = event.get("payload") if event else None
    dataset = payload.get("dataset") if isinstance(payload, dict) else None
    value = dataset.get("fingerprint") if isinstance(dataset, dict) else None
    return str(value) if value else None


def _dataset_format(dataset: Path) -> str:
    has_bruker = has_jcamp = False
    try:
        children = list(dataset.iterdir())
    except OSError:
        return "unknown"
    for child in children:
        if child.is_dir() and (child / "acqus").is_file():
            has_bruker = True
        elif child.is_file() and child.suffix.lower() in (".jdx", ".dx", ".jcamp"):
            has_jcamp = True
    if has_bruker and has_jcamp:
        return "mixed"
    return "bruker" if has_bruker else "jcamp" if has_jcamp else "unknown"


def _packaged_skill(name: str) -> Path | None:
    from importlib.resources import as_file, files

    try:
        with as_file(files("ailsa") / _PACKAGED_SKILLS / name) as path:
            return Path(path) if Path(path).is_dir() else None
    except (OSError, ModuleNotFoundError):
        return None


_COMMAND_SKILL_PARTS = ("INDEX.md", "commands/", "agents/", "references/")


def _skill_location(
    name: str | None,
) -> tuple[Path | None, str | None, bool | None, dict[str, str] | None]:
    """(folder hashed, label of the place, hashes equal the packaged copy, installed files).

    The last item is set only for an installed command skill (label ``global-claude-commands``).
    """
    if not name:
        return None, None, None, None
    from ailsa.record.env import claude_config_dir

    cwd = Path.cwd()
    home = Path.home()
    candidates = (
        ("project-claude", cwd / ".claude" / "skills" / name),
        ("global-claude", claude_config_dir() / "skills" / name),
        ("project-opencode", cwd / ".opencode" / "skills" / name),
        ("global-opencode", home / ".config" / "opencode" / "skills" / name),
    )
    packaged = _packaged_skill(name)
    is_command_skill = (
        packaged is not None
        and (packaged / "INDEX.md").is_file()
        and (packaged / "commands").is_dir()
    )
    if packaged is not None and is_command_skill:
        from ailsa.record.env import command_skill_files, skill_file_hashes

        installed = command_skill_files()
        if installed is not None:
            wanted = {
                k: v
                for k, v in skill_file_hashes(packaged).items()
                if k.startswith(_COMMAND_SKILL_PARTS)
            }
            return packaged, "global-claude-commands", installed == wanted, installed
    chosen: tuple[Path, str] | None = None
    for label, path in candidates:
        if path.is_dir():
            chosen = (path, label)
            break
    if chosen is None:
        return (packaged, "packaged", True, None) if packaged else (None, None, None, None)
    from ailsa.record.env import skill_file_hashes

    same = None
    if packaged is not None:
        same = skill_file_hashes(chosen[0]) == skill_file_hashes(packaged)
    return chosen[0], chosen[1], same, None


def _entry_from_log(run_dir: Path, run_id: str) -> dict[str, Any]:
    """Index entry of a run, folded from its log (no manifest write)."""
    from ailsa.record.fold import fold

    result = read_events(run_dir)
    manifest = fold(result["events"], result["integrity"])
    dataset = manifest.get("dataset") or {}
    status = manifest.get("status") or {}
    return {
        "run_id": run_id,
        "label": dataset.get("label"),
        "created_utc": status.get("started_utc"),
        "fingerprint": dataset.get("fingerprint"),
        "blind": bool(manifest.get("blind")),
        "state": status.get("state"),
    }


def read_index(workspace: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads((workspace / INDEX).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    runs = data.get("runs") if isinstance(data, dict) else None
    return [r for r in runs if isinstance(r, dict)] if isinstance(runs, list) else []


def _write_index(workspace: Path, runs: list[dict[str, Any]]) -> None:
    runs = sorted(runs, key=lambda r: str(r.get("run_id")))
    atomic_write_json(
        workspace / INDEX, {"schema": "ailsa.run-index", "schema_version": "1", "runs": runs}
    )


def _put_entry(workspace: Path, entry: dict[str, Any]) -> None:
    runs = [r for r in read_index(workspace) if r.get("run_id") != entry["run_id"]]
    runs.append(entry)
    _write_index(workspace, runs)


def update_index(workspace: str | os.PathLike[str], entry: dict[str, Any]) -> None:
    """Add or replace one entry of ``runs.json`` under the workspace lock."""
    ws = Path(workspace)
    ws.mkdir(mode=0o700, parents=True, exist_ok=True)
    with workspace_lock(ws):
        _put_entry(ws, entry)


def rebuild_index(workspace: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Rescan every run folder of the workspace and rewrite ``runs.json``."""
    ws = Path(workspace)
    ws.mkdir(mode=0o700, parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    with workspace_lock(ws):
        for child in sorted(ws.iterdir()):
            if not child.is_dir() or not (child / MARKER).is_file():
                continue
            try:
                runs.append(_entry_from_log(child, _marker_id(child) or child.name))
            except Exception:  # noqa: BLE001 - one broken run must not hide the others
                runs.append({"run_id": child.name, "state": "unreadable"})
        _write_index(ws, runs)
    return runs


def _prior_message(code: str, prior: list[str], legacy: list[str]) -> str:
    parts: list[str] = []
    if prior:
        shown = ", ".join(prior[:5]) + (" ..." if len(prior) > 5 else "")
        parts.append(f"the workspace holds {len(prior)} earlier run(s) on this data ({shown})")
    if legacy:
        shown = ", ".join(legacy[:5]) + (" ..." if len(legacy) > 5 else "")
        parts.append(f"the dataset folder contains earlier results ({shown})")
    return (
        "blind run refused: "
        + " and ".join(parts)
        + ". Earlier results could be read by the agents. Use a fresh copy of the raw data, "
        "or pass --allow-prior-runs to start anyway; the run is then marked "
        f"'{NOT_BLIND_REASON}'."
    )


def _step(
    run_dir: Path, name: str, fn: Callable[[], Any], warnings: list[str]
) -> tuple[bool, Any]:
    try:
        return True, fn()
    except Exception as exc:  # noqa: BLE001 - bookkeeping never aborts a run
        message = f"{name} failed: {type(exc).__name__}: {exc}"
        warnings.append(message)
        try:
            append_event(
                run_dir, "warning.raised", {"code": f"init.{name}", "message": message}, actor=_TOOL
            )
        except Exception:  # noqa: BLE001
            pass
        return False, None


def _start_views(dataset: Path, run_dir: Path, environ: Mapping[str, str]) -> int:
    log_path = run_dir / "spectra" / "export.log"
    log_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    child_env = dict(environ)
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-I",  # never import modules from the inherited working folder
                "-m",
                "ailsa.cli",
                "spectra",
                "export",
                str(dataset),
                "--run",
                str(run_dir),
                "--format",
                "json",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=child_env,
        )
    return proc.pid


def init_run(
    dataset: Path,
    *,
    blind: bool = False,
    allow_prior_runs: bool = False,
    run_class: str = "internal",
    label: str | None = None,
    formula: str | None = None,
    source: str | None = None,
    licence: str | None = None,
    skill: str | None = None,
    skill_version: str | None = None,
    mode: str = "manual",
    harness: str | None = None,
    prompt: str | None = None,
    args: Sequence[str] = (),
    context_files: Sequence[Any] = (),
    time_limit_s: int | None = None,
    web_tools: str = "unknown",
    web_tools_enforced: bool = False,
    views: bool = True,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    from ailsa.record.resolve import (
        RUN_DIR_ENV,
        SESSION_ENV,
        bind_session,
        find_active_run,
        session_pointer_path,
    )

    environ: Mapping[str, str] = os.environ if env is None else env
    if run_class not in RUN_CLASSES:
        raise InitRefused("bad_class", f"unknown run class {run_class!r}")
    if web_tools not in WEB_TOOLS:
        raise InitRefused("bad_web_tools", f"unknown web_tools value {web_tools!r}")

    # 1. Launcher: the run exists already.
    launcher_dir = environ.get(RUN_DIR_ENV)
    if launcher_dir:
        ref = find_active_run(env={RUN_DIR_ENV: launcher_dir}, session_id="", cwd="/")
        if ref is not None and ref.via == "env" and not (ref.run_dir / FINISHED).exists():
            return _result(ref.run_id, ref.run_dir, False, [], None)

    # 2. Dataset checks.
    ds = Path(dataset).expanduser()
    if not ds.is_dir():
        raise InitRefused("not_a_dataset", f"dataset folder not found: {ds}")
    ds = ds.resolve()
    root = workspace_root(create=True).resolve()
    overlap = workspace_overlaps_message(root, ds)
    if overlap:
        raise InitRefused("overlap", f"{overlap} (workspace {root}, dataset {ds})")

    from ailsa.record.fingerprint import dataset_fingerprint, find_prior_runs, legacy_results

    fp = dataset_fingerprint(ds)
    fingerprint = str(fp["fingerprint"])

    # 3. Session reuse.
    sid = environ.get(SESSION_ENV)
    pointer = session_pointer_path(root, sid)
    if pointer is not None:
        ref = find_active_run(session_id=sid, cwd="/", env={})
        if ref is not None and ref.via == "session" and not (ref.run_dir / FINISHED).exists():
            if _run_fingerprint(ref.run_dir) == fingerprint:
                return _result(ref.run_id, ref.run_dir, False, [], None)
            raise InitRefused(
                "bound_elsewhere",
                f"this session is bound to run {ref.run_id} on another dataset; "
                "finish that run or start a new session",
            )

    warnings = list(workspace_warnings(root))
    run_label = sanitize_label(ds.name if blind else (label or ds.name))

    if formula:
        formula_value: str | None = formula
        formula_source: str | None = "request"
    else:
        from ailsa.case.scan import find_formula

        formula_value, found_in = find_formula(ds)
        formula_source = f"sidecar:{found_in}" if found_in else None

    # 4. Check and create under the workspace lock.
    with workspace_lock(root):
        prior = find_prior_runs(root, fingerprint)
        legacy = legacy_results(ds)
        readable = bool(prior or legacy)
        overridden = False
        if blind and readable:
            if not allow_prior_runs:
                code = "prior_runs" if prior else "legacy_results"
                raise InitRefused(code, _prior_message(code, prior, legacy))
            overridden = True
        not_blind_reason = NOT_BLIND_REASON if overridden else None
        run_id, run_dir = create_run_dir(root, run_label, now)
        dataset_info = {
            # No user name in the record (WR-13): home-relative, and only the folder name in
            # a public-class record, which is meant to be shared.
            "path": ds.name if run_class == "public" else home_relative(ds),
            "label": run_label,
            "format": _dataset_format(ds),
            "fingerprint": fingerprint,
            "fingerprint_mode": fp["mode"],
            "formula": formula_value,
            "formula_source": formula_source,
            "blind": bool(blind and not overridden),
            "blind_requested": bool(blind),
            "source": (BLIND_WITHHELD if source else None) if blind else source,
            "licence": (BLIND_WITHHELD if licence else None) if blind else licence,
        }
        recorded_args = [scrub_home(a) for a in (scrub_blind_args(args) if blind else args)]
        append_event(
            run_dir,
            "run.created",
            {
                "dataset": dataset_info,
                "class": run_class,
                "request": {
                    "skill": skill,
                    "skill_version": skill_version,
                    "mode": mode,
                    "harness": harness,
                    "prompt": scrub_home(prompt) if prompt else prompt,
                    "args": recorded_args,
                    "options": {
                        "blind": bool(blind),
                        "allow_prior_runs": bool(allow_prior_runs),
                        "views": bool(views),
                        "time_limit_s": time_limit_s,
                    },
                    "context_files": list(context_files),
                },
                "prior_runs": {
                    "found": len(prior),
                    "legacy": legacy,
                    "readable": readable,
                    "allowed": overridden,
                },
                "writer_host": host_alias(),
                "not_blind_reason": not_blind_reason,
            },
            actor=_TOOL,
            fsync=True,
        )
        try:
            _put_entry(
                root,
                {
                    "run_id": run_id,
                    "label": run_label,
                    "created_utc": _now_utc(),
                    "fingerprint": fingerprint,
                    "blind": bool(blind and not overridden),
                    "state": "running",
                },
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"index update failed: {exc}")

    # 5. Environment (outside the lock).
    effective_web = web_tools
    web_unknown = run_class == "confidential" and not web_tools_enforced
    if web_unknown:
        effective_web = "unknown"
        warnings.append(OPEN_SESSION_WEB_WARNING)

    def capture_env() -> None:
        from ailsa.record.env import detect_harness, probe_environment

        skill_dir, where, same, installed = _skill_location(skill)
        harness_name = harness or detect_harness(dict(environ))
        payload = probe_environment(
            skill_dir=skill_dir,
            mode=mode,
            time_limit_s=time_limit_s,
            web_tools=effective_web,
            harness=harness_name,
        )
        if installed is not None and isinstance(payload.get("skill"), dict):
            # What actually ran: the installed files, name and version; the packaged
            # version is kept beside it so a stale install shows.
            from ailsa.record.env import command_skill_meta

            name, version = command_skill_meta()
            packaged_version = payload["skill"].get("version")
            payload["skill"]["files"] = installed
            payload["skill"]["name"] = name or payload["skill"].get("name")
            payload["skill"]["version"] = version
            payload["skill"]["packaged_version"] = packaged_version
        payload["skill_location"] = where
        payload["skill_matches_packaged"] = same
        append_event(run_dir, "env.captured", payload, actor=_TOOL, fsync=True)

    _step(run_dir, "env", capture_env, warnings)

    if web_unknown:
        _step(
            run_dir,
            "web_tools",
            lambda: append_event(
                run_dir,
                "warning.raised",
                {"code": "web_tools_unknown", "message": OPEN_SESSION_WEB_WARNING},
                actor=_TOOL,
            ),
            warnings,
        )

    # 6. Session binding.
    def bind() -> None:
        from ailsa.record.env import detect_harness

        if sid and bind_session(root, sid, run_dir):
            append_event(
                run_dir,
                "run.bound",
                {
                    "session_id": sid,
                    "harness": harness or detect_harness(dict(environ)),
                    "via": "init",
                },
                actor=_TOOL,
            )

    _step(run_dir, "bind", bind, warnings)

    # 7. Inventory.
    def inventory() -> None:
        from ailsa.record.artefacts import register_artefact
        from ailsa.record.inventory import build_inventory, scanned_payload

        inv = build_inventory(ds, blind=bool(blind and not overridden), fingerprint=fingerprint)
        register_artefact(
            run_dir,
            kind="experiment-inventory",
            rel_path="spectra/inventory.json",
            data=(json.dumps(inv, sort_keys=True, indent=2) + "\n").encode("utf-8"),
            event_type="spectra.scanned",
            payload=scanned_payload(inv),
            actor=_TOOL,
        )

    ok, _ = _step(run_dir, "inventory", inventory, warnings)

    # 8. View export: one detached, self-terminating child.
    views_pid: int | None = None
    if views and ok:
        started, pid = _step(run_dir, "views", lambda: _start_views(ds, run_dir, environ), warnings)
        views_pid = pid if started else None

    return _result(run_id, run_dir, True, warnings, views_pid)


def workspace_overlaps_message(root: Path, dataset: Path) -> str | None:
    from ailsa.record.fingerprint import workspace_overlaps

    return workspace_overlaps(root, dataset)
