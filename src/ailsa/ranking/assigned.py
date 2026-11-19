"""Rank LSD solutions atom by atom against the observed 13C shifts.

LSD numbers the atoms of every solution as in its input file. The predicted shift of each
carbon can therefore be compared with the observed shift of that same atom instead of with
the nearest observed line. A wrong structure can then no longer borrow lines that belong to
other atoms, which makes the comparison much sharper, for example between regioisomers.

The observed shift of each carbon is read from the LSD input: from ``SHIX`` lines if there
are any, otherwise from the first number in the comment of its ``MULT`` line
(``MULT 1 C 2 0 ; 155.71 Cq``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from rdkit import Chem, RDLogger

from ailsa.lsd.analyzer import LSDSolutionAnalyzer, SolutionGraph
from ailsa.prediction.models import PredictionResult

_SHIX = re.compile(r"^\s*SHIX\s+(\d+)\s+(-?\d+(?:\.\d+)?)", re.IGNORECASE | re.MULTILINE)
_MULT = re.compile(
    r"^\s*MULT\s+(\d+)\s+C\s+\d\s+\d\s*;\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE | re.MULTILINE
)
_DUPL1 = re.compile(r"^\s*DUPL\s+1\b", re.IGNORECASE | re.MULTILINE)


class Predictor(Protocol):
    def predict_from_smiles(self, smiles: str) -> PredictionResult: ...


@dataclass
class AtomError:
    """One carbon: observed and predicted shift; error is predicted minus observed."""

    lsd_atom: int
    observed: float
    predicted: float
    error: float


@dataclass
class AssignedCandidate:
    """One distinct structure with its best-fitting atom assignment."""

    rank: int
    smiles: str
    inchikey: str
    mae: float
    within_tolerance: int
    compared: int
    carbons: int
    max_error: float
    worst_atom: int
    source: str
    solution: int
    atoms: list[AtomError] = field(default_factory=list)


@dataclass
class AssignedRanking:
    total: int
    distinct: int
    skipped: int
    observed: dict[int, float]
    candidates: list[AssignedCandidate]
    warnings: list[str] = field(default_factory=list)


def observed_shifts(lsd_text: str) -> dict[int, float]:
    """Observed 13C shift of each LSD carbon, from SHIX lines or the MULT comments."""
    shix = {int(a): float(s) for a, s in _SHIX.findall(lsd_text)}
    if shix:
        return shix
    return {int(a): float(s) for a, s in _MULT.findall(lsd_text) if -20.0 <= float(s) <= 260.0}


def _molecule(graph: SolutionGraph) -> tuple[Chem.Mol, str, list[int]] | None:
    """Sanitised molecule, canonical SMILES, and the LSD number of each SMILES atom in order."""
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


def rank_assigned(
    lsd_files: list[Path], predictor: Predictor, tolerance: float = 3.0
) -> AssignedRanking:
    """Rank the solutions of one or more LSD runs; each run's ``.sol`` lies next to its input.

    Raises ValueError when an input names no observed shifts, FileNotFoundError when a
    ``.sol`` file is missing.
    """
    RDLogger.DisableLog("rdApp.*")  # type: ignore[attr-defined]
    best: dict[str, AssignedCandidate] = {}
    predicted: dict[str, PredictionResult] = {}
    observed_all: dict[int, float] = {}
    warnings: list[str] = []
    total = skipped = 0
    for lsd_file in lsd_files:
        text = lsd_file.read_text(errors="replace")
        observed = observed_shifts(text)
        if not observed:
            raise ValueError(
                f"{lsd_file}: no observed 13C shifts (write SHIX lines, or the shift first in "
                "each carbon's MULT comment, e.g. 'MULT 1 C 2 0 ; 155.71')"
            )
        if not _DUPL1.search(text):
            warnings.append(
                f"{lsd_file.name}: no DUPL 1, so LSD kept only one atom assignment per structure; "
                "add DUPL 1 to compare every assignment"
            )
        observed_all.update(observed)
        sol = lsd_file.with_suffix(".sol")
        if not sol.exists():
            raise FileNotFoundError(f"{sol} not found (run LSD on {lsd_file.name} first)")
        for number, graph in enumerate(LSDSolutionAnalyzer.parse_sol_file(sol), start=1):
            total += 1
            parsed = _molecule(graph)
            if parsed is None:
                skipped += 1
                continue
            mol, smiles, lsd_order = parsed
            if smiles not in predicted:  # one structure, many assignments: predict once
                predicted[smiles] = predictor.predict_from_smiles(smiles)
            errors = [
                AtomError(lsd, observed[lsd], round(p.shift, 2), round(p.shift - observed[lsd], 2))
                for p in predicted[smiles].predictions
                if (lsd := lsd_order[p.atom_index]) in observed
            ]
            if not errors:
                skipped += 1
                continue
            mae = sum(abs(e.error) for e in errors) / len(errors)
            worst = max(errors, key=lambda e: abs(e.error))
            key = Chem.MolToInchiKey(mol) or smiles  # type: ignore[no-untyped-call]
            cand = AssignedCandidate(
                rank=0,
                smiles=smiles,
                inchikey=key,
                mae=round(mae, 3),
                within_tolerance=sum(1 for e in errors if abs(e.error) <= tolerance),
                compared=len(errors),
                carbons=sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "C"),
                max_error=round(abs(worst.error), 2),
                worst_atom=worst.lsd_atom,
                source=lsd_file.name if len(lsd_files) == 1 else str(lsd_file),
                solution=number,
                atoms=sorted(errors, key=lambda e: e.lsd_atom),
            )
            old = best.get(key)
            if old is None or cand.mae < old.mae:
                best[key] = cand
    ranked = sorted(best.values(), key=lambda c: (c.mae, -c.within_tolerance, c.max_error))
    for i, cand in enumerate(ranked, start=1):
        cand.rank = i
    return AssignedRanking(
        total=total,
        distinct=len(ranked),
        skipped=skipped,
        observed=dict(sorted(observed_all.items())),
        candidates=ranked,
        warnings=warnings,
    )
