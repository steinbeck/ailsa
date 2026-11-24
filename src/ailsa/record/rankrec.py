"""Rankings and correlation analyses in the run record (REC-01, REC-15, REC-20).

The ranking and the analyser already compute the atom map, the per-atom prediction basis, the
per-correlation path lengths and the correlations an ELIM command may drop. This module keeps
them: ``record_ranking`` and ``record_nearest_line`` write a versioned ranking artefact,
``record_analysis`` writes the per-solution correlation analysis.

Coupling convention: ``path_length`` is the number of bonds between the two atoms of a
correlation line; ``j_coupling`` is the coupling in the spectroscopist's sense, ``path_length + 1``
for an HMBC line (as the analyser reports it) and ``path_length + 2`` for a COSY line (H-C-C-H is
a 3J coupling over one C-C bond). The nominal LSD window is 2J-3J for HMBC and 3J for COSY.

ELIM (LSD manual, command ELIM P1 P2): P1 is the largest number of correlations that may be
eliminated; an eliminated HMBC correlation is a 4J coupling up to P2J, an eliminated COSY
correlation a 5J coupling up to (P2 + 1)J, and P2 = 0 means no upper limit. A line that
carries an explicit lower and upper limit is never eliminated.

Pydantic is imported inside the writers; the rest is standard library.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ailsa.record.artefacts import _write_new
from ailsa.record.events import artefact_id, candidate_id, ranking_id, solution_id
from ailsa.record.fsutil import sha256_bytes, sha256_file
from ailsa.record.log import log_session, read_events
from ailsa.record.lsdrec import _input_path_label, find_iteration_by_sha
from ailsa.record.resolve import RunRef

ANALYSIS_CAP = 500
CORRELATIONS_CAP = 10
CANDIDATE_CAP = 500
NOMINAL_MAX_J = 3

_ELIM = re.compile(r"^\s*ELIM\s+(\d+)(?:\s+(\d+))?", re.IGNORECASE | re.MULTILINE)
_LINE = re.compile(r"^\s*(HMBC|COSY)\s+(.+)$", re.IGNORECASE)
_TOKEN = re.compile(r"\(([^)]*)\)|(\d+)")

_ACTOR = {"kind": "tool", "name": "ailsa lsd rank"}
_ACTOR_ANALYZE = {"kind": "tool", "name": "ailsa lsd analyze"}

NOT_REGISTERED = "input not registered by ailsa lsd run"
SOL_DIFFERS = "solutions file differs from the recorded solver output"


# --------------------------------------------------------------------------- LSD input


def parse_elim(lsd_text: str) -> dict[str, int | None] | None:
    """The ELIM command of an LSD input: ``max_eliminated`` and ``max_bonds`` (None = no limit)."""
    m = _ELIM.search(lsd_text)
    if m is None:
        return None
    bonds = int(m.group(2)) if m.group(2) is not None else 0
    return {"max_eliminated": int(m.group(1)), "max_bonds": bonds or None}


def parse_correlations(lsd_text: str) -> list[dict[str, Any]]:
    """HMBC and COSY lines of an LSD input, atom lists expanded to one entry per atom.

    Each entry: ``kind`` ("HMBC"/"COSY"), ``a`` (carbon, or first hydrogen), ``b`` (the proton
    of an HMBC line, or the second hydrogen), ``lower`` and ``upper`` (explicit coupling
    limits of the line, else None).
    """
    out: list[dict[str, Any]] = []
    for raw in lsd_text.splitlines():
        line = raw.split(";", 1)[0]
        m = _LINE.match(line)
        if m is None:
            continue
        groups: list[list[int]] = []
        numbers: list[int] = []
        for lst, num in _TOKEN.findall(m.group(2)):
            if lst:
                groups.append([int(x) for x in lst.split()])
            elif len(groups) < 2:
                groups.append([int(num)])
            else:
                numbers.append(int(num))
        if len(groups) < 2:
            continue
        lower = numbers[0] if numbers else None
        upper = numbers[1] if len(numbers) > 1 else None
        for a in groups[0]:
            for b in groups[1]:
                out.append(
                    {
                        "kind": m.group(1).upper(),
                        "a": a,
                        "b": b,
                        "lower": lower,
                        "upper": upper,
                    }
                )
    return out


def allowed_max_bonds(
    line: dict[str, Any], elim: dict[str, int | None] | None = None
) -> int | None:
    """Largest coupling (nJ) the nominal window of a line allows; None means unbounded.

    An explicit upper limit wins; a single explicit limit is the only possible coupling; an
    upper limit of 0 means "greater than the lower limit" (unbounded); otherwise the nominal
    window is 3J for HMBC and COSY. ``elim`` is accepted for symmetry with ``elim_window``:
    ELIM only extends what may be eliminated and does not change the nominal window.
    """
    upper = line.get("upper")
    lower = line.get("lower")
    if upper is not None:
        return int(upper) if upper > 0 else None
    if lower is not None:
        return int(lower)
    return NOMINAL_MAX_J


def elim_window(kind: str, elim: dict[str, int | None] | None) -> int | None:
    """Highest coupling an eliminated correlation may have; None when ELIM sets no limit."""
    if elim is None or elim.get("max_bonds") is None:
        return None
    bonds = int(elim["max_bonds"] or 0)
    return bonds + 1 if kind == "COSY" else bonds


def _explicit_range(line: dict[str, Any]) -> bool:
    return line.get("lower") is not None and line.get("upper") is not None


def correlation_paths(lines: Sequence[dict[str, Any]], graph: Any) -> list[dict[str, Any]]:
    """Path length and coupling of every correlation line in one solution graph."""
    out: list[dict[str, Any]] = []
    for ln in lines:
        path = graph.shortest_path(ln["a"], ln["b"])
        length = path if path >= 0 else None
        extra = 2 if ln["kind"] == "COSY" else 1
        out.append(
            {
                "kind": ln["kind"],
                "carbon": ln["a"],
                "proton": ln["b"],
                "path_length": length,
                "j_coupling": None if length is None else length + extra,
            }
        )
    return out


# --------------------------------------------------------------------------- helpers


def _dump(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _file_sha(path: Path) -> str | None:
    try:
        return sha256_file(path) if path.is_file() else None
    except OSError:
        return None


def _registered_copy(events: list[dict[str, Any]], iteration: str) -> str | None:
    found: str | None = None
    for e in events:
        if e.get("type") == "lsd.input.registered":
            payload = e.get("payload") or {}
            if payload.get("iteration") == iteration:
                found = payload.get("copy")
    return found


def _iteration_by_smiles_sha(run_dir: Path, events: list[dict[str, Any]], sha: str) -> str | None:
    found: str | None = None
    for e in events:
        if e.get("type") != "solver.finished":
            continue
        it = (e.get("payload") or {}).get("iteration")
        try:
            data = json.loads((run_dir / "iterations" / str(it) / "solver.json").read_text())
            if ((data.get("files") or {}).get("smiles") or {}).get("sha256") == sha:
                found = it
        except (OSError, ValueError, AttributeError):
            continue
    return found


def predictor_info(predictor: Any) -> dict[str, Any]:
    """Backend, HOSE radius and (cached) database hash of a resolved predictor."""
    lookup = getattr(predictor, "_lookup", None)
    backend = type(lookup).__name__ if lookup is not None else type(predictor).__name__
    info: dict[str, Any] = {
        "backend": backend,
        "database_sha256": None,
        "max_radius": getattr(predictor, "_max_radius", None),
    }
    db_path = getattr(getattr(lookup, "_db", None), "db_path", None)
    if db_path is not None:
        info["database_sha256"] = _cached_db_sha(Path(db_path))
    return info


def _cached_db_sha(path: Path) -> str | None:
    """Database hash from the environment cache only; the 2.8 GB file is never hashed here."""
    try:
        from ailsa.record.env import _cache_file

        st = path.stat()
        key = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"
        cache = json.loads(_cache_file().read_text(encoding="utf-8"))
        value = cache.get(key)
        return str(value) if value else None
    except (OSError, ValueError, AttributeError):
        return None


def _basis(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    out = dict(raw)
    if out.get("confidence") is not None:
        out["confidence"] = f"{float(out['confidence']):g}"
    return out


# --------------------------------------------------------------------------- assigned ranking


def build_ranking_artefact(
    result: Any,
    *,
    ranking_id: str,
    method: str,
    tolerance: float,
    inputs: list[dict[str, Any]],
    predictor_info: dict[str, Any],
    correlations_by_candidate: dict[int, list[dict[str, Any]]],
    cap: int,
    solutions_by_source: dict[str, str | None] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """The Ranking artefact (as a plain dict) for an ``AssignedRanking``."""
    solutions_by_source = solutions_by_source or {}
    notes = list(warnings if warnings is not None else result.warnings)
    shown = result.candidates[:CANDIDATE_CAP]
    if len(result.candidates) > len(shown):
        notes.append(
            f"only the top {len(shown)} of {len(result.candidates)} distinct structures "
            "are recorded"
        )
    candidates: list[dict[str, Any]] = []
    for c in shown:
        det = result.details.get(c.inchikey, {})
        basis = det.get("basis", {})
        iteration = solutions_by_source.get(c.source)
        candidates.append(
            {
                "id": candidate_id(ranking_id, c.rank),
                "rank": c.rank,
                "smiles": c.smiles,
                "inchikey": c.inchikey,
                "mae": c.mae,
                "within_tolerance": c.within_tolerance,
                "compared": c.compared,
                "carbons": c.carbons,
                "max_error": c.max_error,
                "worst_atom": c.worst_atom,
                "solutions": [solution_id(iteration, c.solution)] if iteration else [],
                "mapping_status": det.get("mapping_status", "unavailable"),
                "atom_map": det.get("atom_map", []),
                "atoms": [
                    {
                        "lsd_atom": a.lsd_atom,
                        "observed": a.observed,
                        "predicted": a.predicted,
                        "error": a.error,
                        "basis": _basis(basis.get(a.lsd_atom)),
                    }
                    for a in c.atoms
                ],
                "correlations": correlations_by_candidate.get(c.rank),
            }
        )
    return {
        "ranking_id": ranking_id,
        "method": method,
        "tolerance": tolerance,
        "inputs": inputs,
        "predictor": predictor_info,
        "total_solutions": result.total,
        "distinct_structures": result.distinct,
        "skipped": result.skipped,
        "observed_shifts": {str(k): v for k, v in result.observed.items()},
        "warnings": notes,
        "correlations_cap": cap,
        "candidates": candidates,
    }


def _write_ranking(
    run: RunRef,
    method: str,
    build: Any,
    inputs: list[dict[str, Any]],
    candidate_count_of: Any,
) -> str:
    """Mint ``rkNN``, validate and write the artefact, append ``ranking.computed``."""
    from ailsa.record.models import Ranking

    run_dir = Path(run.run_dir)
    with log_session(run_dir) as lg:
        if lg.finished():
            from ailsa.record.log import RecordWriteRefused

            raise RecordWriteRefused("run finished: no new rankings")
        rk = ranking_id(lg.next_counter("ranking"))
        model = Ranking.model_validate(build(rk))
        blob = _dump(model.model_dump(mode="json", by_alias=True))
        rel = f"rankings/{rk}.json"
        target = run_dir / rel
        if os.path.lexists(target):
            raise FileExistsError(f"artefact path already exists: {rel}")
        sha = sha256_bytes(blob)
        art = {
            "id": artefact_id("ranking", lg.next_counter("art:ranking")),
            "kind": "ranking",
            "path": rel,
            "sha256": sha,
            "bytes": len(blob),
            "supersedes": None,
        }
        _write_new(target, blob, False)
        lg.append(
            "ranking.computed",
            {
                "ranking_id": rk,
                "method": method,
                "inputs": inputs,
                "candidate_count": candidate_count_of(model),
                "sha256": sha,
            },
            actor=_ACTOR,
            refs=[rk],
            artefacts=[art],
        )
    return rk


def record_ranking(
    run: RunRef,
    result: Any,
    *,
    lsd_files: Sequence[Path],
    method: str = "assigned",
    tolerance: float,
    predictor_info: dict[str, Any],
) -> str:
    """Write the atom-by-atom ranking as ``rankings/rkNN.json``; returns the ranking id."""
    from ailsa.lsd.analyzer import LSDSolutionAnalyzer

    run_dir = Path(run.run_dir)
    events = read_events(run_dir)["events"]
    inputs: list[dict[str, Any]] = []
    warnings = list(result.warnings)
    by_source: dict[str, str | None] = {}
    files: dict[str, Path] = {}
    for f in lsd_files:
        label = f.name if len(lsd_files) == 1 else str(f)
        files[label] = f
        sha = sha256_file(f)
        sol = f.with_suffix(".sol")
        sol_sha = _file_sha(sol)
        iteration = find_iteration_by_sha(events, sha)
        if iteration is None:
            if NOT_REGISTERED not in warnings:
                warnings.append(NOT_REGISTERED)
        else:
            copy = _registered_copy(events, iteration)
            recorded = _file_sha(run_dir / Path(copy).with_suffix(".sol")) if copy else None
            if recorded is None or recorded != sol_sha:
                if SOL_DIFFERS not in warnings:
                    warnings.append(SOL_DIFFERS)
        by_source[label] = iteration
        inputs.append(
            {
                "iteration": iteration,
                "path": _input_path_label(run_dir, f),
                "lsd_sha256": sha,
                "sol_sha256": sol_sha,
            }
        )

    graphs: dict[str, dict[int, Any]] = {}
    lines: dict[str, list[dict[str, Any]]] = {}
    correlations: dict[int, list[dict[str, Any]]] = {}
    for c in result.candidates[:CORRELATIONS_CAP]:
        f = files.get(c.source)
        if f is None:
            continue
        if c.source not in graphs:
            sol = f.with_suffix(".sol")
            graphs[c.source] = {
                g.solution_number: g for g in LSDSolutionAnalyzer.parse_sol_file(sol)
            }
            lines[c.source] = parse_correlations(f.read_text(errors="replace"))
        graph = graphs[c.source].get(c.solution)
        if graph is not None:
            correlations[c.rank] = correlation_paths(lines[c.source], graph)

    def build(rk: str) -> dict[str, Any]:
        return build_ranking_artefact(
            result,
            ranking_id=rk,
            method=method,
            tolerance=tolerance,
            inputs=inputs,
            predictor_info=predictor_info,
            correlations_by_candidate=correlations,
            cap=CORRELATIONS_CAP,
            solutions_by_source=by_source,
            warnings=warnings,
        )

    return _write_ranking(run, method, build, inputs, lambda m: len(m.candidates))


# --------------------------------------------------------------------------- nearest-line


def record_nearest_line(
    run: RunRef,
    ranker_result: Any,
    *,
    smiles_file: Path,
    shifts: Sequence[float],
    tolerance: float,
    predictor_info: dict[str, Any] | None = None,
) -> str:
    """Write the nearest-line ranking in the same schema; the atom map is not applicable."""
    run_dir = Path(run.run_dir)
    events = read_events(run_dir)["events"]
    sha = sha256_file(smiles_file)
    iteration = _iteration_by_smiles_sha(run_dir, events, sha)
    inputs = [
        {
            "iteration": iteration,
            "path": _input_path_label(run_dir, smiles_file),
            "smiles_sha256": sha,
        }
    ]
    warnings = list(ranker_result.warnings)
    if iteration is None:
        warnings.append("input not registered by ailsa lsd run")

    def build(rk: str) -> dict[str, Any]:
        cands = []
        for i, sol in enumerate(ranker_result.solutions, start=1):
            cands.append(
                {
                    "id": candidate_id(rk, i),
                    "rank": i,
                    "smiles": sol.smiles,
                    "mae": round(sol.mae, 3),
                    "within_tolerance": sol.within_tolerance(tolerance),
                    "compared": len(sol.assignments) or sol.total_carbons,
                    "carbons": sol.total_carbons,
                    "max_error": round(sol.max_deviation, 2),
                    "solutions": (
                        [solution_id(iteration, sol.solution_index)] if iteration else []
                    ),
                    "mapping_status": "not_applicable",
                    "atom_map": [],
                    "atoms": [],
                    "correlations": None,
                }
            )
        return {
            "ranking_id": rk,
            "method": "nearest-line",
            "tolerance": tolerance,
            "inputs": inputs,
            "predictor": predictor_info or {"backend": "unknown"},
            "total_solutions": ranker_result.total_solutions,
            "distinct_structures": ranker_result.ranked_count,
            "skipped": ranker_result.skipped_count,
            "observed_shifts": {str(i): v for i, v in enumerate(shifts, start=1)},
            "warnings": warnings,
            "correlations_cap": None,
            "candidates": cands,
        }

    return _write_ranking(run, "nearest-line", build, inputs, lambda m: len(m.candidates))


# --------------------------------------------------------------------------- analysis


def record_analysis(
    run: RunRef,
    results: Sequence[Any],
    *,
    sol_file: Path,
    lsd_file: Path,
    total: int | None = None,
) -> str | None:
    """Save the per-solution correlation analysis; returns its path in the run, or None when
    the LSD input is not a registered iteration (nothing is written then)."""
    from ailsa.record.models import SolutionAnalysis

    run_dir = Path(run.run_dir)
    events = read_events(run_dir)["events"]
    lsd_sha = sha256_file(lsd_file)
    iteration = find_iteration_by_sha(events, lsd_sha)
    if iteration is None:
        return None
    if total is None:
        from ailsa.lsd.analyzer import LSDSolutionAnalyzer

        total = len(LSDSolutionAnalyzer.parse_sol_file(sol_file))
    text = lsd_file.read_text(errors="replace")
    elim = parse_elim(text)
    lines = parse_correlations(text)
    truncated = len(results) > ANALYSIS_CAP
    kept = list(results)[:ANALYSIS_CAP]
    entries: list[dict[str, Any]] = []
    for r in kept:
        corrs = correlation_paths(lines, r.graph)
        dropped: list[int] = []
        for index, (corr, ln) in enumerate(zip(corrs, lines, strict=True)):
            limit = allowed_max_bonds(ln, elim)
            j = corr["j_coupling"]
            corr["allowed_max"] = limit
            corr["exceeds_window"] = j is not None and limit is not None and j > limit
            if elim is not None and corr["exceeds_window"] and not _explicit_range(ln):
                dropped.append(index)
        entries.append(
            {
                "solution": r.solution_number,
                "solution_id": solution_id(iteration, r.solution_number),
                "correlations": corrs,
                "dropped_by_elim": dropped,
            }
        )
    body: dict[str, Any] = {
        "iteration": iteration,
        "lsd_sha256": lsd_sha,
        "sol_sha256": _file_sha(sol_file),
        "cap": ANALYSIS_CAP,
        "analysed": len(kept),
        "total": total,
        "truncated": truncated,
        "elim_active": elim is not None,
        "elim": elim,
        "solutions": entries,
    }
    model = SolutionAnalysis.model_validate(body)
    blob = _dump(model.model_dump(mode="json", by_alias=True))
    with log_session(run_dir) as lg:
        if lg.finished():
            from ailsa.record.log import RecordWriteRefused

            raise RecordWriteRefused("run finished: no new analyses")
        n = lg.next_counter(f"analysis:{iteration}")
        rel = f"iterations/{iteration}/analysis.{n}.json"
        target = run_dir / rel
        if os.path.lexists(target):
            raise FileExistsError(f"artefact path already exists: {rel}")
        art = {
            "id": artefact_id("solution-analysis", lg.next_counter("art:solution-analysis")),
            "kind": "solution-analysis",
            "path": rel,
            "sha256": sha256_bytes(blob),
            "bytes": len(blob),
            "supersedes": None,
        }
        _write_new(target, blob, False)
        lg.append(
            "solutions.analysed",
            {
                "iteration": iteration,
                "analysed": len(kept),
                "cap": ANALYSIS_CAP,
                "truncated": truncated,
            },
            actor=_ACTOR_ANALYZE,
            refs=[iteration],
            artefacts=[art],
        )
    return rel
