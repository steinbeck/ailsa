"""Consistency checks a problem must pass before the solver runs.

Errors make the solver input impossible or certainly wrong; ``ailsa case solve``
refuses to run while any is present. Everything else that setup assumed is listed for
verification but does not block.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ailsa.case.model import HALOGENS, HETERO_MAX_H, Problem, dbe, parse_formula

MAX_ATOMS = 60
MAX_CORRELATIONS = 100


@dataclass
class CheckResult:
    """Errors (blocking) and the facts behind them."""

    errors: list[str] = field(default_factory=list)
    facts: dict[str, object] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return not self.errors


def check_problem(problem: Problem) -> CheckResult:
    """Run every check on ``problem``."""
    result = CheckResult()
    counts = parse_formula(problem.formula)
    atoms = problem.atoms

    by_element: dict[str, int] = {}
    for a in atoms:
        by_element[a.element] = by_element.get(a.element, 0) + 1
    for el in sorted(set(counts) | set(by_element)):
        if el == "H":
            continue
        want, have = counts.get(el, 0), by_element.get(el, 0)
        if want != have:
            result.errors.append(
                f"{el}: the formula has {want}, the problem has {have} "
                + _count_hint(el, want - have)
            )

    h_total = sum(a.hydrogens for a in atoms)
    result.facts["hydrogens"] = h_total
    if h_total != counts.get("H", 0):
        diff = counts.get("H", 0) - h_total
        result.errors.append(
            f"hydrogens: the formula has {counts.get('H', 0)}, the atoms carry {h_total} "
            f"({'add' if diff > 0 else 'remove'} {abs(diff)}: check CH/CH3/CH2 and the "
            "hydrogens on O/N)"
        )
    for a in atoms:
        cap = HETERO_MAX_H.get(a.element)
        if a.element in HALOGENS and a.hydrogens:
            result.errors.append(f"{a.label}: a halogen cannot carry hydrogen")
        elif cap is not None and a.element != "C" and a.hydrogens > cap:
            result.errors.append(f"{a.label}: {a.hydrogens} hydrogens, at most {cap} allowed")
        if a.element == "C" and a.hydrogens > 3:
            result.errors.append(f"{a.label}: a carbon cannot carry {a.hydrogens} hydrogens")
        if a.hyb == 1 and a.hydrogens > 1:
            result.errors.append(f"{a.label}: an sp atom carries at most one hydrogen")

    n_sp2 = sum(1 for a in atoms if a.hyb == 2)
    n_sp = sum(1 for a in atoms if a.hyb == 1)
    result.facts["sp2"] = n_sp2
    if n_sp2 % 2:
        result.errors.append(
            f"{n_sp2} sp2 atoms: the number must be even, because every double bond joins "
            "two of them (make one more atom sp2, typically a carbonyl O, or one less)"
        )
    unsaturation = dbe(counts)
    rings = unsaturation - n_sp2 / 2 - n_sp
    result.facts["dbe"] = unsaturation
    result.facts["rings"] = rings
    if unsaturation != int(unsaturation):
        result.errors.append(f"the formula has a non-integer DBE ({unsaturation}); check it")
    elif rings < 0:
        result.errors.append(
            f"too many sp2/sp atoms: {n_sp2} sp2 give {n_sp2 // 2} double bonds, but the "
            f"formula allows only {int(unsaturation)} rings plus double bonds"
        )

    if len(atoms) > MAX_ATOMS:
        result.errors.append(f"{len(atoms)} atoms: the solver handles at most {MAX_ATOMS}")

    ids = {a.id for a in atoms}
    used = [c for c in problem.correlations if c.use]
    result.facts["correlations_used"] = len(used)
    if len(used) > MAX_CORRELATIONS:
        result.errors.append(
            f"{len(used)} correlations in use: the solver accepts at most {MAX_CORRELATIONS}"
        )
    for c in used:
        missing = [x for x in [*c.x, c.y] if x not in ids]
        if missing:
            result.errors.append(f"{c.id} refers to removed atom(s) {missing}: drop it")
            continue
        if problem.atom(c.y).hydrogens == 0:
            result.errors.append(
                f"{c.id}: its proton sits on {problem.atom(c.y).label}, which has no "
                "hydrogen now: drop the correlation or fix the multiplicity"
            )
        if len(c.x) > 4:
            result.errors.append(f"{c.id}: more than four candidate atoms")
    for b in problem.bonds:
        if b.a not in ids or b.b not in ids:
            result.errors.append(f"bond {b.a}-{b.b} refers to a removed atom: unbond it")
    return result


def _count_hint(element: str, missing: int) -> str:
    if element != "C":
        return "(the formula decides the heteroatoms)"
    if missing > 0:
        return (
            f"(add {missing}: a line standing for equivalent carbons --copies ID=2, or a "
            "carbon missing from the 13C list --add-carbon SHIFT:MULT)"
        )
    return f"(remove {-missing}: a noise or impurity line --remove ID, or fewer --copies)"
