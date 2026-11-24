"""ailsa model: atom model recorded in a run (REC-04).

``ailsa model import FILE`` records an atom model in one call. Nothing heavy is imported at
module level.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import click

ELEMENTS = frozenset({"C", "H", "N", "O", "S", "P", "F", "Cl", "Br", "I", "Si", "B", "Se"})


@click.group()
def model() -> None:
    """Atom model recorded in a run."""


@model.command("import")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Validate and count without writing.")
@click.option("--run", "run_ref", default=None, help="Run folder or id (default: active run).")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def import_model(file: Path, dry_run: bool, run_ref: str | None, fmt: str) -> None:
    """Record an atom model (atoms, correlations, evidence) as one artefact."""
    from pydantic import ValidationError

    from ailsa.cli.peaks import (
        _actor,
        _emit,
        _fail,
        _known_peak_ids,
        _load_json,
        _report,
        _resolve_run,
    )
    from ailsa.record.artefacts import _write_new, run_target
    from ailsa.record.events import artefact_id
    from ailsa.record.fsutil import sha256_bytes
    from ailsa.record.log import log_session
    from ailsa.record.models import AtomModel

    run = _resolve_run("model import", run_ref)
    raw = _load_json(file)
    if not isinstance(raw, dict):
        _fail("model file must be a JSON object with 'atoms' and 'correlations'")
    problems: list[str] = []
    try:
        atom_model = AtomModel.model_validate(raw)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(x) for x in err["loc"]) or "model"
            problems.append(f"{loc}: {err['msg']}")
        _report(problems, "model import")
        return

    atom_ids: set[str] = set()
    for a in atom_model.atoms:
        if a.id in atom_ids:
            problems.append(f"duplicate atom id {a.id}")
        atom_ids.add(a.id)
        if a.element not in ELEMENTS:
            problems.append(f"{a.id}: unknown element {a.element}")
    cor_ids: set[str] = set()
    for c in atom_model.correlations:
        if c.id in cor_ids:
            problems.append(f"duplicate correlation id {c.id}")
        cor_ids.add(c.id)
        for at in c.atoms:
            if at not in atom_ids:
                problems.append(f"{c.id}: unknown atom {at}")
    known = _known_peak_ids(run.run_dir)
    known_any = known | atom_ids | cor_ids

    def check_peak(owner: str, pid: str) -> None:
        if pid not in known:
            problems.append(f"{owner}: unknown peak id {pid}")

    for a in atom_model.atoms:
        for ev in a.evidence:
            if ev not in known_any:
                problems.append(f"{a.id}: evidence {ev} is not a registered id")
    for c in atom_model.correlations:
        for pid in c.peaks:
            check_peak(c.id, pid)
    _report(problems, "model import")

    counts = {"atoms": len(atom_model.atoms), "correlations": len(atom_model.correlations)}
    if dry_run:
        _emit(
            {"dry_run": True, **counts},
            fmt,
            f"{counts['atoms']} atoms, {counts['correlations']} correlations ok",
        )
        return

    blob = (
        json.dumps(atom_model.model_dump(mode="json", by_alias=True), sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")
    with log_session(run.run_dir) as lg:
        if lg.finished():
            _fail("run finished: no new artefacts")
        n = lg.next_counter("art:atom-model")
        rel = f"model/atoms.{n}.json"
        try:
            target = run_target(run.run_dir, rel)
        except ValueError as exc:
            _fail(str(exc))
        if os.path.lexists(target):
            _fail(f"artefact path already exists: {rel}")
        supersedes = artefact_id("atom-model", n - 1) if n > 1 else None
        art: dict[str, Any] = {
            "id": artefact_id("atom-model", n),
            "kind": "atom-model",
            "path": rel,
            "sha256": sha256_bytes(blob),
            "bytes": len(blob),
            "supersedes": supersedes,
        }
        _write_new(target, blob, False)
        lg.append(
            "model.imported",
            dict(counts),
            actor=_actor("model import"),
            artefacts=[art],
        )
    _emit(
        {**counts, "artefact": art["id"], "supersedes": supersedes},
        fmt,
        f"recorded {counts['atoms']} atoms, {counts['correlations']} correlations ({art['id']})",
    )
