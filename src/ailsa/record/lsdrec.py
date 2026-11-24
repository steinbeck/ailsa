"""Solver runs in the run record: iterations, outcomes, copies (REC-01, REC-14, REC-18).

``begin_solver_run`` registers the LSD input before the solver starts; ``finish_solver_run``
copies what the solver left behind into ``iterations/itNN/`` and writes the typed solver-run
artefact. ``import_solver_outputs`` brings in output produced any other way and labels it
imported. Standard library only at module level; pydantic is imported inside the writers.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ailsa.record.artefacts import _write_new, copy_into_run
from ailsa.record.events import DIFF_CAP, ITERATION_PURPOSES, artefact_id, iteration_id
from ailsa.record.fsutil import sha256_bytes
from ailsa.record.log import RecordWriteRefused, log_session, read_events
from ailsa.record.resolve import RunRef
from ailsa.record.workspace import host_alias

_MULT = re.compile(r"^\s*MULT\s+(\d+)\s+([A-Za-z]{1,2})\s+(\d+)\s+(\d+)", re.MULTILINE)
_ACTOR = {"kind": "tool", "name": "ailsa lsd run"}
_SOLVER_FILES = ("ring3", "ring4", "solncounter")


@dataclass
class SolverRecord:
    """What ``begin_solver_run`` registered; handed to ``finish_solver_run``."""

    run: RunRef
    iteration: str
    purpose: str
    parent: str | None
    host: str
    remote: bool
    timeout_s: int | None
    input_name: str
    input_rel: str
    lsd_sha256: str

    @property
    def iteration_dir(self) -> Path:
        return Path(self.run.run_dir) / "iterations" / self.iteration


def index_map(lsd_text: str) -> dict[str, dict[str, Any]]:
    """LSD atom index -> element, hybridisation, hydrogen count, from the MULT lines."""
    out: dict[str, dict[str, Any]] = {}
    for m in _MULT.finditer(lsd_text):
        out[m.group(1)] = {
            "element": m.group(2),
            "hybridisation": int(m.group(3)),
            "h": int(m.group(4)),
        }
    return out


def _registered(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in events if e.get("type") == "lsd.input.registered"]


def latest_main_iteration(events: list[dict[str, Any]]) -> str | None:
    last: str | None = None
    for e in _registered(events):
        payload = e.get("payload") or {}
        if payload.get("purpose") == "main":
            last = payload.get("iteration")
    return last


def find_iteration_by_sha(events: list[dict[str, Any]], sha: str) -> str | None:
    found: str | None = None
    for e in _registered(events):
        payload = e.get("payload") or {}
        if payload.get("lsd_sha256") == sha:
            found = payload.get("iteration")
    return found


def _input_path_label(run_dir: Path, input_file: Path) -> str:
    try:
        return str(input_file.resolve().relative_to(run_dir.resolve()))
    except ValueError:
        return input_file.name


def _unified_diff(old: str, new: str, old_name: str, new_name: str) -> str | None:
    text = "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=old_name,
            tofile=new_name,
        )
    )
    return text[:DIFF_CAP]


def begin_solver_run(
    run: RunRef,
    *,
    input_file: str | os.PathLike[str],
    purpose: str = "main",
    parent: str | None = None,
    host: str | None = None,
    timeout_s: int | None = None,
    remote: bool = False,
    provenance: str = "run",
) -> SolverRecord:
    """Register the input and ``solver.started`` before the solver runs."""
    if purpose not in ITERATION_PURPOSES:
        raise ValueError(f"unknown iteration purpose: {purpose}")
    run_dir = Path(run.run_dir)
    src = Path(input_file)
    text = src.read_text(encoding="utf-8", errors="replace")
    where = host or host_alias()
    with log_session(run_dir) as lg:
        if lg.finished():
            raise RecordWriteRefused("run finished: no new iterations")
        events = read_events(run_dir)["events"]
        registered = {(e.get("payload") or {}).get("iteration"): e for e in _registered(events)}
        if parent is not None and parent not in registered:
            raise ValueError(f"unknown parent iteration: {parent}")
        if parent is None:
            parent = latest_main_iteration(events)
        iteration = iteration_id(lg.next_counter("iteration"))
        rel, sha, size = copy_into_run(run_dir, src, f"iterations/{iteration}/{src.name}")
        diff: str | None = None
        if parent is not None:
            old_path = Path(run_dir) / str(
                (registered[parent].get("payload") or {}).get("copy", "")
            )
            try:
                diff = _unified_diff(
                    old_path.read_text(encoding="utf-8", errors="replace"), text, parent, iteration
                )
            except OSError:
                diff = None
        entry = {
            "id": artefact_id("lsd-input", lg.next_counter("art:lsd-input")),
            "kind": "lsd-input",
            "path": rel,
            "sha256": sha,
            "bytes": size,
            "supersedes": None,
        }
        lg.append(
            "lsd.input.registered",
            {
                "iteration": iteration,
                "parent": parent,
                "purpose": purpose,
                "lsd_sha256": sha,
                "path": _input_path_label(run_dir, src),
                "copy": rel,
                "index_map": index_map(text),
                "diff": diff,
            },
            actor=_ACTOR,
            refs=[iteration],
            artefacts=[entry],
        )
        lg.append(
            "solver.started",
            {
                "iteration": iteration,
                "host": where,
                "timeout_s": timeout_s,
                "remote": remote,
                "provenance": provenance,
            },
            actor=_ACTOR,
            refs=[iteration],
        )
    return SolverRecord(
        run=run,
        iteration=iteration,
        purpose=purpose,
        parent=parent,
        host=where,
        remote=remote,
        timeout_s=timeout_s,
        input_name=src.name,
        input_rel=rel,
        lsd_sha256=sha,
    )


def _file_info(run_dir: Path, rel: str, blob: bytes) -> dict[str, Any]:
    return {"path": rel, "sha256": sha256_bytes(blob), "bytes": len(blob)}


def _copy_if_present(
    record: SolverRecord, src: Path, name: str, files: dict[str, Any], key: str
) -> None:
    if not src.is_file() or src.is_symlink():
        return
    try:
        rel, sha, size = copy_into_run(
            record.run.run_dir, src, f"iterations/{record.iteration}/{name}"
        )
    except (OSError, ValueError):
        return
    files[key] = {"path": rel, "sha256": sha, "bytes": size}


def _write_text_file(
    record: SolverRecord, name: str, text: str, files: dict[str, Any], key: str
) -> None:
    rel = f"iterations/{record.iteration}/{name}"
    blob = text.encode("utf-8", errors="replace")
    try:
        _write_new(Path(record.run.run_dir) / rel, blob, False)
    except (OSError, ValueError):
        return
    files[key] = _file_info(Path(record.run.run_dir), rel, blob)


def _tool_info(info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not info:
        return None
    return {k: info.get(k) for k in ("path", "version", "sha256")}


def finish_solver_run(
    record: SolverRecord,
    result: Any,
    *,
    output_dir: str | os.PathLike[str],
    outlsd_info: dict[str, Any] | None = None,
    lsd_info: dict[str, Any] | None = None,
    host: str | None = None,
    provenance: str = "run",
    elapsed_s: float | None = None,
    exit_code: int | None = None,
) -> dict[str, Any]:
    """Copy the solver's files into the iteration and write solver.json plus its events."""
    from ailsa.record.artefacts import register_artefact
    from ailsa.record.models import SolverRun

    out = Path(output_dir)
    run_dir = Path(record.run.run_dir)
    stem = Path(record.input_name).stem
    files: dict[str, Any] = {
        "input": {
            "path": record.input_rel,
            "sha256": record.lsd_sha256,
            "bytes": (run_dir / record.input_rel).stat().st_size,
        }
    }
    _copy_if_present(record, out / f"{stem}.sol", f"{stem}.sol", files, "sol")
    _copy_if_present(record, out / "solutions.smi", "solutions.smi", files, "smiles")
    for name in _SOLVER_FILES:
        _copy_if_present(record, out / name, name, files, name)
    if provenance == "run":
        _write_text_file(record, "lsd.out", getattr(result, "stdout", "") or "", files, "stdout")
        _write_text_file(record, "lsd.err", getattr(result, "stderr", "") or "", files, "stderr")

    outcome = str(result.outcome)
    partial = result.partial_count
    count = int(
        partial if outcome == "timeout" and partial is not None else result.found_count or 0
    )
    if not result.found_count and outcome in ("solutions", "limit_reached"):
        count = int(result.solution_count or 0)
    absent = None if "smiles" in files else result.smiles_absent_reason
    elapsed = result.elapsed_s if elapsed_s is None else elapsed_s
    code = result.return_code if exit_code is None and provenance == "run" else exit_code
    where = host or record.host
    model = SolverRun.model_validate(
        dict(
            iteration=record.iteration,
            purpose=record.purpose,
            parent=record.parent,
            host=where,
            remote=record.remote,
            provenance=provenance,
            outcome=outcome,
            count=count,
            partial_count=partial,
            limit=result.limit,
            elapsed_s=elapsed if provenance == "run" else None,
            timeout_s=record.timeout_s,
            exit_code=code,
            error_line=result.error_line,
            lsd=_tool_info(lsd_info),
            outlsd=_tool_info(outlsd_info),
            files=files,
            smiles_absent_reason=absent,
        )
    )
    blob = (
        json.dumps(model.model_dump(mode="json", by_alias=True), sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    payload = {
        "iteration": record.iteration,
        "outcome": outcome,
        "count": count,
        "elapsed_s": model.elapsed_s,
        "host": where,
        "provenance": provenance,
        "partial_count": partial,
        "limit": result.limit,
        "error_line": result.error_line,
        "smiles_absent_reason": absent,
        "lsd": _tool_info(lsd_info),
        "outlsd": _tool_info(outlsd_info),
    }
    register_artefact(
        run_dir,
        kind="solver-run",
        rel_path=f"iterations/{record.iteration}/solver.json",
        data=blob,
        event_type="solver.finished",
        payload=payload,
        actor=_ACTOR,
        refs=[record.iteration],
    )
    with log_session(run_dir) as lg:
        lg.append(
            "solutions.converted",
            {
                "iteration": record.iteration,
                "count": count,
                "status": "converted" if "smiles" in files else (absent or "none"),
            },
            actor=_ACTOR,
            refs=[record.iteration],
        )
    return {
        "iteration": record.iteration,
        "outcome": outcome,
        "count": count,
        "partial_count": partial,
        "elapsed_s": model.elapsed_s,
    }


def _imported_result(folder: Path, stem: str) -> Any:
    """Classify files found in a folder the tool did not run LSD in."""
    from ailsa.lsd.runner import LSDResult, classify_outcome, maxs_limit, read_solncounter

    sol = folder / f"{stem}.sol"
    smi = folder / "solutions.smi"
    counter = read_solncounter(folder)
    smiles_lines = 0
    if smi.is_file():
        smiles_lines = len(
            [ln for ln in smi.read_text(errors="replace").splitlines() if ln.strip()]
        )
    out_text = ""
    for name in ("lsd.out", "lsd.err"):
        p = folder / name
        if p.is_file():
            out_text += p.read_text(errors="replace") + "\n"
    try:
        limit = maxs_limit((folder / f"{stem}.lsd").read_text(errors="replace"))
    except OSError:
        limit = None
    if sol.is_file():
        count = counter if counter is not None else smiles_lines
        timed_out = False
    else:
        count = counter or 0
        timed_out = counter is not None
    started = sol.is_file() or counter is not None or bool(out_text.strip())
    outcome, absent = classify_outcome(
        started=started,
        blocked=False,
        error_line=None,
        timed_out=timed_out,
        count=count,
        limit=limit,
        no_solution_text="No solution found" in out_text,
        sol_exists=sol.is_file(),
        smiles_ok=smi.is_file() if count > 0 else None,
        conversion_skipped=False,
    )
    return LSDResult(
        success=outcome in ("solutions", "limit_reached"),
        solution_count=count,
        outcome=outcome,
        partial_count=count if timed_out else None,
        limit=limit,
        smiles_absent_reason=absent,
        found_count=count,
        timed_out=timed_out,
    )


def import_solver_outputs(
    run: RunRef,
    folder: str | os.PathLike[str],
    *,
    input_file: str | os.PathLike[str],
    purpose: str = "main",
    parent: str | None = None,
) -> dict[str, Any]:
    """Register solver output produced elsewhere as an iteration marked ``imported``."""
    src = Path(folder)
    inp = Path(input_file)
    result = _imported_result(src, inp.stem)
    record = begin_solver_run(
        run,
        input_file=inp,
        purpose=purpose,
        parent=parent,
        timeout_s=None,
        provenance="imported",
    )
    info = finish_solver_run(record, result, output_dir=src, provenance="imported")
    return {**info, "provenance": "imported"}
