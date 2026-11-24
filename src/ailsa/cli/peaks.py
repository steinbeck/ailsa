"""ailsa peaks: peak decisions recorded in a run (REC-04, REC-17).

``ailsa peaks decide --from TABLE`` records many decisions in one locked batch. Nothing
heavy is imported at module level.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import click

MAX_TABLE_BYTES = 5 * 1024 * 1024
MAX_TABLE_ROWS = 10_000
_PEAK_RE = re.compile(r"^pk:[^:\s]+:\d+:\d+$")


def _fail(message: str) -> None:
    click.echo(f"Error: {message}", err=True)
    sys.exit(1)


def _resolve_run(command: str, explicit: str | None) -> Any:
    """Return the active RunRef or exit 1 with the standard message."""
    from ailsa.record.resolve import current_run_for_tool, find_active_run

    run = find_active_run(explicit=explicit) if explicit else current_run_for_tool(command)
    if run is None or (run.run_dir / "finished.json").exists():
        _fail(f"{command} needs an active run (start one with ailsa run init)")
    return run


def _load_json(path: Path) -> Any:
    """Read a JSON input file, refusing huge or unparsable ones."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        _fail(f"cannot read {path}: {exc}")
    if size > MAX_TABLE_BYTES:
        _fail(f"{path.name} is larger than {MAX_TABLE_BYTES // (1024 * 1024)} MB; split the table")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail(f"{path.name} is not valid JSON: {exc}")


def _known_peak_ids(run_dir: Path) -> set[str]:
    """Peak ids of every registered peak-pick artefact whose sha256 still matches."""
    from ailsa.record.artefacts import find_artefacts
    from ailsa.record.fsutil import sha256_file
    from ailsa.record.log import read_events

    events = read_events(run_dir)["events"]
    ids: set[str] = set()
    problems: list[str] = []
    for art in find_artefacts(events, "peak-pick"):
        path = run_dir / art["path"]
        try:
            if sha256_file(path) != art["sha256"]:
                problems.append(f"{art['path']} no longer matches its recorded sha256")
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{art['path']} unreadable: {exc}")
            continue
        ids.update(str(p["id"]) for p in data.get("peaks", []) if "id" in p)
    if problems:
        _fail("; ".join(problems))
    return ids


def _actor(command: str) -> dict[str, Any]:
    return {
        "kind": "agent",
        "role": os.environ.get("AILSA_AGENT_ROLE") or "agent",
        "name": f"ailsa {command}",
    }


def _report(problems: list[str], what: str) -> None:
    if problems:
        click.echo(f"Error: {what} refused, nothing written:", err=True)
        for p in problems:
            click.echo(f"  - {p}", err=True)
        sys.exit(1)


def _emit(result: dict[str, Any], fmt: str, text: str) -> None:
    if fmt == "json":
        click.echo(json.dumps(result, sort_keys=True))
    else:
        click.echo(text)


@click.group()
def peaks() -> None:
    """Peak decisions recorded in a run."""


@peaks.command("decide")
@click.option(
    "--from",
    "table_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON table of decisions ({'decisions': [...]} or a bare list).",
)
@click.option("--dry-run", is_flag=True, help="Validate and count without writing.")
@click.option("--run", "run_ref", default=None, help="Run folder or id (default: active run).")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def decide(table_path: Path, dry_run: bool, run_ref: str | None, fmt: str) -> None:
    """Record many peak decisions (accept, reject, merge, assign) in one batch."""
    from pydantic import ValidationError

    from ailsa.record.events import PEAK_ACTIONS, artefact_id
    from ailsa.record.fsutil import sha256_bytes
    from ailsa.record.log import log_session
    from ailsa.record.models import PeakDecision, PeakDecisionTable

    run = _resolve_run("peaks decide", run_ref)
    raw = _load_json(table_path)
    rows = raw.get("decisions") if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or not rows:
        _fail("table must be a non-empty list or an object with a 'decisions' list")
    if len(rows) > MAX_TABLE_ROWS:
        _fail(f"table has {len(rows)} rows; the limit is {MAX_TABLE_ROWS}")

    known = _known_peak_ids(run.run_dir)
    problems: list[str] = []
    decisions: list[PeakDecision] = []
    for i, row in enumerate(rows, start=1):
        try:
            d = PeakDecision.model_validate(row)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(x) for x in err["loc"]) or "row"
                problems.append(f"row {i}: {loc}: {err['msg']}")
            continue
        if d.action not in PEAK_ACTIONS:
            problems.append(f"row {i}: unknown action {d.action}")
        if d.action == "reject" and d.category is None:
            problems.append(f"row {i}: a reject needs a category")
        ids = [*d.peaks, *d.evidence, *([d.target] if d.target else [])]
        for pid in d.peaks:
            if not _PEAK_RE.match(pid):
                problems.append(f"row {i}: not a peak id: {pid}")
        for pid in ids:
            if _PEAK_RE.match(pid) and pid not in known:
                problems.append(f"row {i}: unknown peak id {pid}")
        decisions.append(d)
    _report(problems, "peaks decide")

    if dry_run:
        _emit({"dry_run": True, "recorded": len(decisions)}, fmt, f"{len(decisions)} valid")
        return

    table = PeakDecisionTable(decisions=decisions)
    blob = (
        json.dumps(table.model_dump(mode="json", by_alias=True), sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    from ailsa.record.artefacts import _write_new

    with log_session(run.run_dir) as lg:
        if lg.finished():
            _fail("run finished: no new artefacts")
        n = lg.next_counter("art:peak-decisions")
        rel = f"peaks/decisions.{n}.json"
        target = run.run_dir / rel
        if os.path.lexists(target):
            _fail(f"artefact path already exists: {rel}")
        art = {
            "id": artefact_id("peak-decisions", n),
            "kind": "peak-decisions",
            "path": rel,
            "sha256": sha256_bytes(blob),
            "bytes": len(blob),
            "supersedes": None,
        }
        _write_new(target, blob, False)
        for k, d in enumerate(decisions):
            payload: dict[str, Any] = {
                "peaks": d.peaks,
                "action": d.action,
                "category": d.category,
                "reason": d.reason,
                "evidence": d.evidence,
                "target": d.target,
            }
            lg.append(
                "peak.decided",
                payload,
                actor=_actor("peaks decide"),
                refs=list(d.peaks),
                artefacts=[art] if k == 0 else None,
            )
    _emit(
        {"recorded": len(decisions), "artefact": art["id"]},
        fmt,
        f"recorded {len(decisions)} decisions ({art['id']})",
    )
