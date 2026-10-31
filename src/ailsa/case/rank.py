"""Rank the solver's candidate structures against the observed 13C shifts.

LSD reports every candidate with its atoms numbered as in the input, so each
predicted carbon shift can be compared with the observed shift of exactly that atom.
This assigned error is a sharper test than matching each prediction to the nearest
observed line, which lets a wrong structure borrow lines that belong to other atoms.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rdkit import Chem, RDLogger

from ailsa.case.lsdfile import lsd_index
from ailsa.case.model import Problem
from ailsa.identity import derive_identity
from ailsa.lsd.analyzer import LSDSolutionAnalyzer, SolutionGraph
from ailsa.prediction.resolver import resolve_c13_predictor

RANKING_FILE = "ranking.json"


@dataclass
class Candidate:
    """One distinct candidate structure and how well it fits."""

    rank: int
    smiles: str
    inchikey: str
    mae: float
    max_error: float
    worst_atom: str
    predicted: int
    carbons: int
    violated: list[str] = field(default_factory=list)
    aromatic: bool = False
    run: int = 0
    elim: int = 0
    identity: dict[str, object] | None = None


@dataclass
class RankResult:
    """The ranked candidates of the latest solver runs."""

    runs: list[int]
    total: int
    candidates: list[Candidate]
    distinct: int = 0
    skipped: int = 0


def _latest_batch(problem: Problem) -> list[int]:
    """Run numbers of the latest ``solve`` call that produced structures."""
    batches: dict[int, list[int]] = {}
    for r in problem.runs:
        batches.setdefault(r.batch, []).append(r.number)
    for batch in sorted(batches, reverse=True):
        numbers = batches[batch]
        if any(r.solutions > 0 for r in problem.runs if r.number in numbers):
            return numbers
    return []


def _graph_smiles(graph: SolutionGraph) -> tuple[Chem.Mol, str, list[int]] | None:
    """Sanitised molecule, SMILES, and LSD index of each SMILES atom (in order)."""
    mol = graph.to_rdkit_mol()
    if mol is None:
        return None
    lsd_of = [a.GetAtomMapNum() for a in mol.GetAtoms()]
    for a in mol.GetAtoms():
        a.SetAtomMapNum(0)
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        return None
    smiles = Chem.MolToSmiles(mol)
    order = [int(i) for i in mol.GetProp("_smilesAtomOutputOrder").strip("[],").split(",") if i]
    return mol, smiles, [lsd_of[i] for i in order]


def rank_problem(problem: Problem, analysis_dir: Path, top: int = 10) -> RankResult:
    """Rank the candidates of the latest solver runs; write ``ranking.json``."""
    RDLogger.DisableLog("rdApp.*")  # type: ignore[attr-defined]
    run_numbers = _latest_batch(problem)
    if not run_numbers:
        raise ValueError("no solver run with structures yet: run `ailsa case solve` first")
    predictor = resolve_c13_predictor()
    idx = lsd_index(problem)
    atom_of = {v: problem.atom(k) for k, v in idx.items()}
    used = [c for c in problem.correlations if c.use and c.kind == "HMBC"]
    best: dict[str, Candidate] = {}
    total = skipped = 0
    for record in problem.runs:
        if record.number not in run_numbers or record.solutions == 0:
            continue
        sol = analysis_dir / record.directory / "compound.sol"
        if not sol.exists():
            continue
        for graph in LSDSolutionAnalyzer.parse_sol_file(sol):
            total += 1
            parsed = _graph_smiles(graph)
            if parsed is None:
                skipped += 1
                continue
            mol, smiles, lsd_order = parsed
            prediction = predictor.predict_from_smiles(smiles)
            errors: list[tuple[float, str]] = []
            for p in prediction.predictions:
                atom = atom_of.get(lsd_order[p.atom_index])
                if atom is not None and atom.shift is not None:
                    errors.append((abs(p.shift - atom.shift), atom.label))
            n_carbons = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "C")
            if not errors:
                skipped += 1
                continue
            mae = sum(e for e, _ in errors) / len(errors)
            worst = max(errors)
            violated = [
                c.id
                for c in used
                if not any(2 <= graph.shortest_path(idx[x], idx[c.y]) + 1 <= 3 for x in c.x)
            ]
            key = Chem.MolToInchiKey(mol) or smiles  # type: ignore[no-untyped-call]
            cand = Candidate(
                rank=0,
                smiles=smiles,
                inchikey=key,
                mae=round(mae, 3),
                max_error=round(worst[0], 2),
                worst_atom=worst[1],
                predicted=len(errors),
                carbons=n_carbons,
                violated=violated,
                aromatic=any(a.GetIsAromatic() for a in mol.GetAtoms()),
                run=record.number,
                elim=record.elim,
            )
            old = best.get(key)
            if old is None or (cand.mae, len(cand.violated)) < (old.mae, len(old.violated)):
                best[key] = cand
    ranked = sorted(best.values(), key=lambda c: (c.mae, len(c.violated), c.max_error))
    for i, cand in enumerate(ranked, start=1):
        cand.rank = i
    for cand in ranked[:3]:
        cand.identity = derive_identity(cand.smiles)
    result = RankResult(
        runs=run_numbers,
        total=total,
        candidates=ranked[:top],
        distinct=len(ranked),
        skipped=skipped,
    )
    payload = {
        "runs": run_numbers,
        "total_solutions": total,
        "distinct_structures": len(ranked),
        "skipped": skipped,
        "candidates": [asdict(c) for c in ranked[: max(top, 50)]],
    }
    (analysis_dir / RANKING_FILE).write_text(json.dumps(payload, indent=1) + "\n")
    problem.log("rank", f"{len(ranked)} distinct structures from runs {run_numbers}")
    return result
