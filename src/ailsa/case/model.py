"""The state of a guided CASE run: atoms, correlations, edits and solver runs.

Everything the solver is told is stored here, together with the observation it came
from and every change made to it. The LSD input file is rendered from this state for
each solver run (see :mod:`ailsa.case.lsdfile`) and is never edited by hand, so no
constraint can be lost between runs.

Atom ids are stable for the life of a problem: removing an atom leaves a gap, a new
atom gets the next free id. The LSD file maps ids to consecutive solver indices.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

PROBLEM_FILE = "problem.json"

# Maximum number of hydrogens an atom of each heteroatom element may carry.
HETERO_MAX_H: dict[str, int] = {"O": 1, "N": 2, "S": 1, "P": 0, "Si": 0, "B": 0}
HALOGENS = ("F", "Cl", "Br", "I")

MULT_TO_H: dict[str, int] = {"C": 0, "CH": 1, "CH2": 2, "CH3": 3}
H_TO_MULT: dict[int, str] = {v: k for k, v in MULT_TO_H.items()}


def utc_now() -> str:
    """Current UTC time, second precision, ISO 8601 with a Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Atom(BaseModel):
    """One heavy atom of the molecule."""

    id: int
    element: str
    shift: float | None = None
    hydrogens: int = 0
    hyb: int = 3
    h_shifts: list[float] = Field(default_factory=list)
    copy_of: int | None = None
    snr: float | None = None
    mult_source: str = ""
    hyb_source: str = ""
    notes: list[str] = Field(default_factory=list)

    @property
    def label(self) -> str:
        """Short human label, e.g. ``C3`` or ``O12``."""
        return f"{self.element}{self.id}"

    @property
    def mult(self) -> str:
        """Carbon multiplicity name (C, CH, CH2, CH3); element + H count otherwise."""
        if self.element == "C":
            return H_TO_MULT.get(self.hydrogens, f"CH{self.hydrogens}")
        return f"{self.element}H{self.hydrogens}" if self.hydrogens else self.element


class Correlation(BaseModel):
    """One HMBC or COSY correlation, traced to the peak it came from.

    ``x`` is the LSD P1 side (HMBC: one or more candidate carbons; COSY: one or more
    candidate proton-bearing atoms), ``y`` the proton-bearing atom of P2.
    """

    id: str
    kind: Literal["HMBC", "COSY"]
    x: list[int]
    y: int
    c_shift: float
    h_shift: float
    snr: float | None = None
    use: bool = True
    reason: str = ""


class Bond(BaseModel):
    """A bond the solver must contain."""

    a: int
    b: int
    reason: str = ""


class Assumption(BaseModel):
    """Something setup decided that the model should verify."""

    code: str
    text: str
    fix: str = ""


class Unassigned(BaseModel):
    """A peak that could not be tied to an atom but may matter."""

    kind: str
    c_shift: float | None = None
    h_shift: float | None = None
    snr: float | None = None
    text: str = ""


class HistoryEntry(BaseModel):
    """One change to the problem."""

    time: str
    action: str
    detail: str
    reason: str = ""


class RunRecord(BaseModel):
    """One solver run; runs of one ``solve`` call share a batch number."""

    number: int
    batch: int = 1
    variant: str = ""
    directory: str
    elim: int
    solutions: int
    max_solutions: int
    limit_reached: bool = False
    success: bool = True
    error: str = ""
    time: str = ""


class Problem(BaseModel):
    """The complete state of a guided CASE run."""

    version: int = 1
    formula: str
    dataset: str
    solvent: str | None = None
    solvent_offset: float = 0.0
    spectra: dict[str, str] = Field(default_factory=dict)
    hsqc_edited: bool | None = None
    atoms: list[Atom] = Field(default_factory=list)
    correlations: list[Correlation] = Field(default_factory=list)
    bonds: list[Bond] = Field(default_factory=list)
    small_rings_allowed: bool = False
    assumptions: list[Assumption] = Field(default_factory=list)
    unassigned: list[Unassigned] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    runs: list[RunRecord] = Field(default_factory=list)

    # ------------------------------------------------------------------ lookups

    def atom(self, atom_id: int) -> Atom:
        """Return the atom with ``atom_id``; raise ``KeyError`` if there is none."""
        for a in self.atoms:
            if a.id == atom_id:
                return a
        raise KeyError(f"no atom {atom_id}")

    def carbons(self) -> list[Atom]:
        """All carbon atoms, in id order."""
        return [a for a in self.atoms if a.element == "C"]

    def signals(self) -> list[Atom]:
        """Carbons that are observed signals (not symmetry copies)."""
        return [a for a in self.carbons() if a.copy_of is None]

    def copies_of(self, atom_id: int) -> list[Atom]:
        """Symmetry copies of ``atom_id`` (excluding the atom itself)."""
        return [a for a in self.atoms if a.copy_of == atom_id]

    def group_of(self, atom_id: int) -> list[int]:
        """The atom and its symmetry copies, as ids."""
        root = self.atom(atom_id).copy_of or atom_id
        return [root] + [a.id for a in self.copies_of(root)]

    def next_atom_id(self) -> int:
        """The next unused atom id."""
        return max((a.id for a in self.atoms), default=0) + 1

    def correlation(self, corr_id: str) -> Correlation:
        """Return the correlation with ``corr_id``; raise ``KeyError`` if there is none."""
        for c in self.correlations:
            if c.id.lower() == corr_id.lower():
                return c
        raise KeyError(f"no correlation {corr_id}")

    def log(self, action: str, detail: str, reason: str = "") -> None:
        """Append a history entry."""
        self.history.append(
            HistoryEntry(time=utc_now(), action=action, detail=detail, reason=reason)
        )

    # --------------------------------------------------------------- persistence

    def save(self, analysis_dir: Path) -> Path:
        """Write ``problem.json`` into ``analysis_dir``."""
        analysis_dir.mkdir(parents=True, exist_ok=True)
        path = analysis_dir / PROBLEM_FILE
        path.write_text(json.dumps(self.model_dump(mode="json"), indent=1) + "\n")
        return path

    @classmethod
    def load(cls, analysis_dir: Path) -> Problem:
        """Read ``problem.json`` from ``analysis_dir``."""
        path = analysis_dir / PROBLEM_FILE
        return cls.model_validate_json(path.read_text())


def parse_formula(formula: str) -> dict[str, int]:
    """Element counts of a molecular formula such as ``C10H16O``.

    Raises ``ValueError`` on anything that is not a plain formula.
    """
    import re

    text = formula.strip()
    if not re.fullmatch(r"([A-Z][a-z]?\d*)+", text):
        raise ValueError(f"not a molecular formula: {formula!r}")
    counts: dict[str, int] = {}
    for element, number in re.findall(r"([A-Z][a-z]?)(\d*)", text):
        counts[element] = counts.get(element, 0) + (int(number) if number else 1)
    return counts


def dbe(counts: dict[str, int]) -> float:
    """Degree of unsaturation (rings plus double bonds) of a formula."""
    c = counts.get("C", 0) + counts.get("Si", 0)
    n = counts.get("N", 0) + counts.get("P", 0)
    h = counts.get("H", 0) + sum(counts.get(x, 0) for x in HALOGENS)
    return (2 * c + 2 + n - h) / 2
