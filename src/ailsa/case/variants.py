"""Alternative atom tables the solver should also try.

Some choices cannot be made from the spectra alone. The most consequential is how many
oxygen and nitrogen atoms take part in a double bond: an unprotonated carbon at
140-168 ppm can be a C=O, a C=N or a ring carbon bonded to O or N, and the choice moves
one degree of unsaturation between a double bond and a ring. Instead of guessing,
``solve`` runs each plausible count and the ranking decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ailsa.case.model import Problem, dbe, parse_formula


@dataclass
class Variant:
    """Hybridisation changes applied on top of the problem for one set of solver runs."""

    label: str
    hyb: dict[int, int] = field(default_factory=dict)

    def apply(self, problem: Problem) -> Problem:
        """A copy of ``problem`` with this variant's changes."""
        copy = problem.model_copy(deep=True)
        for atom_id, hyb in self.hyb.items():
            copy.atom(atom_id).hyb = hyb
        return copy


def _ambiguous_carbons(problem: Problem) -> int:
    """Unprotonated carbons at 140-168 ppm not already bonded as a carbonyl."""
    bonded = {b.a for b in problem.bonds} | {b.b for b in problem.bonds}
    return sum(
        1
        for a in problem.signals()
        if a.hydrogens == 0 and a.shift is not None and 140 <= a.shift < 168 and a.id not in bonded
    ) + sum(1 for a in problem.signals() if a.hydrogens == 1 and a.shift and 135 <= a.shift < 168)


def heteroatom_variants(problem: Problem) -> list[Variant]:
    """Variants with two more or two fewer sp2 heteroatoms, oxygen first or nitrogen first.

    Only heteroatoms without hydrogen and without a required bond can change. A variant
    must keep the number of sp2 atoms even and leave the formula's unsaturation enough
    for the rings it implies (no negative ring count). Returns no variant when no
    carbon is ambiguous or no heteroatom can change.
    """
    counts = parse_formula(problem.formula)
    if not (counts.get("O") or counts.get("N")) or _ambiguous_carbons(problem) == 0:
        return []
    bonded = {b.a for b in problem.bonds} | {b.b for b in problem.bonds}
    free = [
        a
        for a in problem.atoms
        if a.element in ("O", "N") and a.hydrogens == 0 and a.id not in bonded
    ]
    sp2_now = [a for a in free if a.hyb == 2]
    sp3_now = [a for a in free if a.hyb == 3]
    n_sp2 = sum(1 for a in problem.atoms if a.hyb == 2)
    n_sp = sum(1 for a in problem.atoms if a.hyb == 1)
    unsaturation = dbe(counts)
    variants: list[Variant] = []

    def rings_ok(total_sp2: int) -> bool:
        return unsaturation - total_sp2 / 2 - n_sp >= 0

    if len(sp3_now) >= 2 and rings_ok(n_sp2 + 2):
        for first in ("O", "N"):
            order = sorted(sp3_now, key=lambda a: (a.element != first, a.id))
            pick = sorted(order[:2], key=lambda a: a.id)
            label = "+2 sp2: " + ", ".join(a.label for a in pick)
            if all(v.label != label for v in variants):
                variants.append(Variant(label=label, hyb={a.id: 2 for a in pick}))
    if len(sp2_now) >= 2:
        pick = sorted(sp2_now, key=lambda a: a.id)[:2]
        variants.append(
            Variant(
                label="-2 sp2: " + ", ".join(a.label for a in pick), hyb={a.id: 3 for a in pick}
            )
        )
    return variants
