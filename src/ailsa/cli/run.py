"""ailsa run: the run record (REC-06, REC-09, REC-16, REC-22).

Subcommands here: init, note, status, verify, render, index. Plan 17 adds start and
finalize. Nothing heavy is imported at module level; ``note`` loads no pydantic, numpy or
rdkit (REC-04).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import click

_FORMAT = click.Choice(["text", "json"])
_RECORD_FILES = frozenset(
    {
        "events.jsonl",
        "events.lock",
        ".counters.json",
        "finished.json",
        "manifest.json",
        "heartbeat.json",
        "hooks.json",
        "hook-errors.log",
        ".ailsa-run",
    }
)
_KNOWN_PATHS = frozenset({"spectra/export.log"})
_FREE_DIRS = frozenset({"agent", "transcript", "renderings"})


@click.group()
def run() -> None:
    """Run record: create, note, finalize, render, verify."""


def _emit(data: Any, fmt: str, lines: list[str] | None = None) -> None:
    if fmt == "json":
        click.echo(json.dumps(data, indent=2, sort_keys=True, default=str))
    else:
        for line in lines or []:
            click.echo(line)


@run.command("init")
@click.argument("dataset", type=click.Path(path_type=Path))
@click.option("--blind", is_flag=True, help="Blind run: refuse when earlier results are readable.")
@click.option(
    "--allow-prior-runs",
    is_flag=True,
    help="Start a blind run despite earlier runs or results; the run is marked not blind.",
)
@click.option(
    "--class",
    "run_class",
    type=click.Choice(["public", "internal", "confidential"]),
    default="internal",
    show_default=True,
    help="Data class of the run.",
)
@click.option("--label", default=None, help="Dataset label (ignored in blind mode).")
@click.option("--formula", default=None, help="Molecular formula, if known.")
@click.option("--source", default=None, help="Where the data come from.")
@click.option("--licence", default=None, help="Licence or acknowledgement of the data.")
@click.option("--skill", default=None, help="Skill that runs, for example ailsa-lite.")
@click.option(
    "--mode",
    type=click.Choice(["lean", "team", "headless", "manual"]),
    default="manual",
    show_default=True,
)
@click.option("--no-views", is_flag=True, help="Do not export the spectra view products.")
@click.option("--format", "fmt", type=_FORMAT, default="text", show_default=True)
def init_cmd(
    dataset: Path,
    blind: bool,
    allow_prior_runs: bool,
    run_class: str,
    label: str | None,
    formula: str | None,
    source: str | None,
    licence: str | None,
    skill: str | None,
    mode: str,
    no_views: bool,
    fmt: str,
) -> None:
    """Create the run record for DATASET (or reuse the one of this session)."""
    from ailsa.record.env import detect_harness
    from ailsa.record.events import ARGV_ITEM_CAP
    from ailsa.record.runinit import InitRefused, init_run

    try:
        result = init_run(
            dataset,
            blind=blind,
            allow_prior_runs=allow_prior_runs,
            run_class=run_class,
            label=label,
            formula=formula,
            source=source,
            licence=licence,
            skill=skill,
            skill_version=None,
            mode=mode,
            harness=detect_harness(),
            prompt=None,
            args=[a[:ARGV_ITEM_CAP] for a in sys.argv[1:40]],
            context_files=[],
            time_limit_s=None,
            web_tools="unknown",
            views=not no_views,
        )
    except InitRefused as exc:
        click.echo(f"ailsa: {exc}", err=True)
        raise SystemExit(2) from None
    for warning in result["warnings"]:
        click.echo(f"ailsa: warning: {warning}", err=True)
    _emit(
        result,
        fmt,
        [f"RUN: {result['run_id']}", f"WORK: {result['work_dir']}"],
    )


@run.command("note")
@click.argument("text")
@click.option("--phase", default=None, help="Name of the phase this note starts or belongs to.")
@click.option("--sender", default=None, help="Who writes the note (default: AILSA_AGENT_ROLE).")
@click.option("--self-reported-model", "model", default=None, help="Model the sender reports.")
@click.option("--run", "run_ref", default=None, help="Run folder path or id.")
@click.option("--format", "fmt", type=_FORMAT, default="text", show_default=True)
def note_cmd(
    text: str,
    phase: str | None,
    sender: str | None,
    model: str | None,
    run_ref: str | None,
    fmt: str,
) -> None:
    """Add a note to the run record; never fails a run."""
    import io

    from ailsa.record.events import TEXT_CAP
    from ailsa.record.log import append_event, read_events
    from ailsa.record.resolve import current_run_for_tool, find_active_run

    who = sender or os.environ.get("AILSA_AGENT_ROLE") or "agent"
    actor = {"kind": "agent", "name": who, "role": who}
    try:
        warned = io.StringIO()
        if run_ref:
            ref = find_active_run(run_ref)
        else:
            ref = current_run_for_tool("run note", stream=warned)
        if ref is None:
            message = warned.getvalue().strip() or "ailsa: not recorded: no active run"
            click.echo(message, err=True)
            return
        if phase:
            last = None
            for ev in read_events(ref.run_dir)["events"]:
                if ev.get("type") == "phase.started":
                    last = (ev.get("payload") or {}).get("name")
            if last != phase:
                append_event(ref.run_dir, "phase.started", {"name": phase}, actor=actor)
        ev = append_event(
            ref.run_dir,
            "note.added",
            {"text": text[:TEXT_CAP], "sender": who},
            actor=actor,
        )
        if model:
            append_event(
                ref.run_dir,
                "agent.model_reported",
                {"agent": who, "requested": None, "actual": model, "source": "self-report"},
                actor=actor,
            )
        _emit({"recorded": True, "run_id": ref.run_id, "seq": ev.get("seq")}, fmt)
    except Exception as exc:  # noqa: BLE001 - a note never fails a run
        click.echo(f"ailsa: not recorded: {exc}", err=True)


def _resolve_run(run_ref: str | None) -> Path:
    from ailsa.record.resolve import find_active_run

    ref = find_active_run(run_ref)
    if ref is None:
        if run_ref:
            raise click.ClickException(f"run not found: {run_ref}")
        raise click.ClickException("no run given and no active run")
    return ref.run_dir


def _run_option(f: Any) -> Any:
    return click.option("--run", "run_ref", default=None, help="Run folder path or id.")(f)


def _format_option(f: Any) -> Any:
    return click.option("--format", "fmt", type=_FORMAT, default="text", show_default=True)(f)


@run.command("status")
@_run_option
@_format_option
def status_cmd(run_ref: str | None, fmt: str) -> None:
    """Rebuild the manifest from the log and show the state of the run."""
    from ailsa.record.fold import rebuild_manifest

    run_dir = _resolve_run(run_ref)
    m = rebuild_manifest(run_dir)
    status = m.get("status") or {}
    final = m.get("final") or {}
    solver = (m.get("spans") or {}).get("solver") or []
    last_outcome = None
    if solver:
        last_outcome = (m.get("iterations") or {}).get(str(solver[-1].get("name")), {}).get(
            "outcome"
        )
    data = {
        "run_id": m.get("run_id"),
        "state": status.get("state"),
        "label": status.get("label"),
        "inferred": status.get("inferred"),
        "integrity": {
            k: (m.get("integrity") or {}).get(k) for k in ("clean", "first_bad_seq", "reason")
        },
        "events": (m.get("integrity") or {}).get("events"),
        "iterations": len(m.get("iterations") or {}),
        "last_solver_outcome": last_outcome,
        "final": {k: final.get(k) for k in ("outcome", "valid", "stale")},
        "hooks_recorded": (m.get("harness") or {}).get("hooks_recorded"),
        "heartbeat_utc": status.get("heartbeat_utc"),
    }
    _emit(data, fmt, [f"{k}: {v}" for k, v in data.items()])


def _scan_unregistered(run_dir: Path, registered: set[str]) -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(run_dir, followlinks=False):
        here = Path(dirpath)
        rel_dir = here.relative_to(run_dir)
        if rel_dir == Path("."):
            dirnames[:] = sorted(d for d in dirnames if d not in _FREE_DIRS)
        else:
            dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            rel = (rel_dir / name).as_posix()
            if rel_dir == Path(".") and name in _RECORD_FILES:
                continue
            if rel in registered or rel in _KNOWN_PATHS:
                continue
            if name.startswith(".") and name.endswith(".tmp"):
                continue
            found.append(rel)
    return sorted(found)


_NOW_KEYS = ("state", "inferred", "label", "reason", "counts_as_clean")


def _manifest_matches(run_dir: Path, expected: dict[str, Any]) -> tuple[bool, bool]:
    """(matches, present). Keys that depend on the clock are ignored for live runs."""
    try:
        disk = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True, False
    want = json.loads(json.dumps(expected))
    live = {"running", "no_heartbeat"}
    if (disk.get("status") or {}).get("state") in live and (want.get("status") or {}).get(
        "state"
    ) in live:
        for key in _NOW_KEYS:
            (disk.get("status") or {}).pop(key, None)
            want["status"].pop(key, None)
    return disk == want, True


@run.command("verify")
@_run_option
@_format_option
def verify_cmd(run_ref: str | None, fmt: str) -> None:
    """Check the hash chain, the manifest and the artefact hashes of a run."""
    from ailsa.record.artefacts import artefact_index
    from ailsa.record.fold import fold
    from ailsa.record.fsutil import sha256_file
    from ailsa.record.log import read_events
    from ailsa.record.runinit import read_index
    from ailsa.record.workspace import workspace_root

    run_dir = _resolve_run(run_ref)
    result = read_events(run_dir)
    integrity = result["integrity"]
    events = result["events"]
    heartbeat = None
    try:
        heartbeat = json.loads((run_dir / "heartbeat.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    expected = fold(events, integrity, heartbeat=heartbeat)
    matches, present = _manifest_matches(run_dir, expected)

    index = artefact_index(events)
    bad: list[dict[str, str]] = []
    for aid, art in sorted(index.items()):
        rel = str(art.get("path"))
        target = run_dir / rel
        if not target.is_file() or target.is_symlink():
            bad.append({"id": aid, "path": rel, "reason": "missing"})
        elif sha256_file(target) != art.get("sha256"):
            bad.append({"id": aid, "path": rel, "reason": "sha256 differs"})
    unregistered = _scan_unregistered(run_dir, {str(a.get("path")) for a in index.values()})

    index_ok = True
    finished = run_dir / "finished.json"
    if finished.is_file():
        try:
            head = json.loads(finished.read_text(encoding="utf-8")).get("head")
            for entry in read_index(workspace_root(create=False)):
                if entry.get("run_id") == expected.get("run_id") and entry.get("head"):
                    index_ok = entry.get("head") == head
        except (OSError, ValueError):
            pass

    ok = bool(integrity["clean"]) and matches and not bad and index_ok
    data = {
        "run_id": expected.get("run_id"),
        "clean": bool(integrity["clean"]),
        "first_bad_seq": integrity.get("first_bad_seq"),
        "reason": integrity.get("reason"),
        "manifest_matches": matches,
        "manifest_present": present,
        "artefacts_ok": not bad,
        "bad_artefacts": bad,
        "index_head_ok": index_ok,
        "unregistered": unregistered,
    }
    lines: list[str] = []
    if ok:
        lines.append("clean")
    else:
        if not integrity["clean"]:
            lines.append(
                f"record changed or incomplete from event {integrity['first_bad_seq']}: "
                f"{integrity['reason']}"
            )
        if not matches:
            lines.append("manifest.json differs from the event log")
        for item in bad:
            lines.append(f"artefact {item['path']}: {item['reason']}")
        if not index_ok:
            lines.append("runs.json head differs from finished.json")
    for rel in unregistered:
        lines.append(f"warning: unregistered file {rel}")
    _emit(data, fmt, lines)
    if not ok:
        raise SystemExit(1)


@run.command("render")
@_run_option
@_format_option
def render_cmd(run_ref: str | None, fmt: str) -> None:
    """Write the Markdown renderings of a run (derived files)."""
    from ailsa.record.render import render_run

    run_dir = _resolve_run(run_ref)
    paths = [str(p) for p in render_run(run_dir)]
    _emit({"files": paths}, fmt, paths)


@run.command("index")
@click.option("--rebuild", is_flag=True, help="Rescan the workspace first.")
@_format_option
def index_cmd(rebuild: bool, fmt: str) -> None:
    """List the runs of the workspace."""
    from ailsa.record.runinit import read_index, rebuild_index
    from ailsa.record.workspace import workspace_root

    root = workspace_root(create=True)
    runs = rebuild_index(root) if rebuild else read_index(root)
    lines = [
        f"{r.get('run_id')}  {r.get('state')}  {'blind' if r.get('blind') else '-'}" for r in runs
    ]
    _emit({"workspace": str(root), "runs": runs}, fmt, lines)
