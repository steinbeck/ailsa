"""Changes to a problem, each logged with its reason.

The model never edits ``problem.json`` itself; it calls ``ailsa case edit``, which
goes through these functions, so every change is validated and recorded.
"""

from __future__ import annotations

from ailsa.case.model import MULT_TO_H, Atom, Bond, Problem

HYB = {"sp": 1, "sp2": 2, "sp3": 3, "1": 1, "2": 2, "3": 3}


class EditError(ValueError):
    """An edit that cannot be applied."""


def _atom_id(problem: Problem, text: str) -> int:
    raw = text.strip().upper().lstrip("CONSPFIBH")
    try:
        atom_id = int(raw)
        problem.atom(atom_id)
    except (ValueError, KeyError) as exc:
        raise EditError(f"no atom {text!r} (use the number from `ailsa case check`)") from exc
    return atom_id


def _pair(text: str, sep: str = "=") -> tuple[str, str]:
    if sep not in text:
        raise EditError(f"expected ID{sep}VALUE, got {text!r}")
    left, right = text.split(sep, 1)
    return left.strip(), right.strip()


def set_mult(problem: Problem, spec: str) -> str:
    left, right = _pair(spec)
    atom_id = _atom_id(problem, left)
    mult = right.upper()
    if mult not in MULT_TO_H:
        raise EditError(f"multiplicity must be C, CH, CH2 or CH3, got {right!r}")
    for aid in problem.group_of(atom_id):
        atom = problem.atom(aid)
        if atom.element != "C":
            raise EditError(f"{atom.label} is not a carbon; use --hetero-h")
        atom.hydrogens = MULT_TO_H[mult]
        atom.mult_source = "edit"
    return f"C{atom_id} is {mult}"


def set_hyb(problem: Problem, spec: str) -> str:
    left, right = _pair(spec)
    atom_id = _atom_id(problem, left)
    if right.lower() not in HYB:
        raise EditError(f"hybridisation must be sp, sp2 or sp3, got {right!r}")
    for aid in problem.group_of(atom_id):
        problem.atom(aid).hyb = HYB[right.lower()]
        problem.atom(aid).hyb_source = "edit"
    return f"{problem.atom(atom_id).label} is {right.lower()}"


def set_copies(problem: Problem, spec: str) -> str:
    left, right = _pair(spec)
    atom_id = _atom_id(problem, left)
    root = problem.atom(atom_id).copy_of or atom_id
    try:
        wanted = int(right)
    except ValueError as exc:
        raise EditError(f"copies must be a number, got {right!r}") from exc
    if not 1 <= wanted <= 6:
        raise EditError("copies must be between 1 and 6")
    current = problem.group_of(root)
    base = problem.atom(root)
    while len(current) < wanted:
        new = base.model_copy(deep=True)
        new.id = problem.next_atom_id()
        new.copy_of = root
        problem.atoms.insert(problem.atoms.index(problem.atom(current[-1])) + 1, new)
        current.append(new.id)
    while len(current) > wanted:
        _drop_atom(problem, current.pop())
    regroup(problem)
    return f"C{root} stands for {wanted} carbon(s)"


def regroup(problem: Problem) -> None:
    """Make every correlation name all symmetry copies of the carbons it names."""
    ids = {a.id for a in problem.atoms}
    for c in problem.correlations:
        roots = {problem.atom(x).copy_of or x for x in c.x if x in ids}
        group = sorted({g for r in roots if r in ids for g in problem.group_of(r)})
        c.x = group
        if not group:
            c.use, c.reason = False, "its carbons were removed"
        elif len(group) > 4 and c.use:
            c.use, c.reason = False, "more than four candidate carbons"


def _exists(problem: Problem, atom_id: int) -> bool:
    return any(a.id == atom_id for a in problem.atoms)


def _drop_atom(problem: Problem, atom_id: int) -> None:
    problem.atoms = [a for a in problem.atoms if a.id != atom_id]
    problem.bonds = [b for b in problem.bonds if atom_id not in (b.a, b.b)]
    for c in problem.correlations:
        if atom_id in c.x:
            c.x = [x for x in c.x if x != atom_id]
        if c.y == atom_id or not c.x:
            c.use, c.reason = False, f"atom {atom_id} removed"


def remove_atom(problem: Problem, spec: str) -> str:
    atom_id = _atom_id(problem, spec)
    atom = problem.atom(atom_id)
    if atom.element != "C":
        raise EditError("only carbons can be removed; heteroatoms follow the formula")
    for aid in reversed(problem.group_of(atom_id)):
        _drop_atom(problem, aid)
    return f"removed {atom.label} ({atom.shift} ppm)"


def add_carbon(problem: Problem, spec: str) -> str:
    parts = [p.strip() for p in spec.split(":")]
    try:
        shift = float(parts[0])
    except ValueError as exc:
        raise EditError(f"expected SHIFT[:MULT[:HYB]], got {spec!r}") from exc
    mult = parts[1].upper() if len(parts) > 1 and parts[1] else "C"
    if mult not in MULT_TO_H:
        raise EditError(f"multiplicity must be C, CH, CH2 or CH3, got {parts[1]!r}")
    hyb_text = (
        parts[2].lower() if len(parts) > 2 and parts[2] else ("sp2" if shift >= 100 else "sp3")
    )
    if hyb_text not in HYB:
        raise EditError(f"hybridisation must be sp, sp2 or sp3, got {parts[2]!r}")
    atom = Atom(
        id=problem.next_atom_id(),
        element="C",
        shift=shift,
        hydrogens=MULT_TO_H[mult],
        hyb=HYB[hyb_text],
        mult_source="edit",
        hyb_source="edit",
    )
    carbons = problem.carbons()
    position = len(carbons)
    for i, other in enumerate(carbons):
        if other.shift is not None and other.shift < shift and other.copy_of is None:
            position = i
            break
    problem.atoms.insert(position, atom)
    return f"added C{atom.id} {shift} ppm {mult} {hyb_text}"


def set_hetero_h(problem: Problem, spec: str) -> str:
    left, right = _pair(spec)
    atom_id = _atom_id(problem, left)
    atom = problem.atom(atom_id)
    if atom.element == "C":
        raise EditError(f"{atom.label} is a carbon; use --mult")
    try:
        atom.hydrogens = int(right)
    except ValueError as exc:
        raise EditError(f"hydrogen count must be a number, got {right!r}") from exc
    return f"{atom.label} carries {atom.hydrogens} H"


def set_use(problem: Problem, ids: str, use: bool) -> str:
    changed = []
    for corr_id in [x for x in ids.replace(" ", ",").split(",") if x]:
        try:
            corr = problem.correlation(corr_id)
        except KeyError as exc:
            raise EditError(f"no correlation {corr_id!r}") from exc
        if use and len(corr.x) > 4:
            raise EditError(f"{corr.id} has more than four candidate carbons")
        corr.use = use
        corr.reason = "" if use else "dropped by edit"
        changed.append(corr.id)
    return ("using " if use else "dropped ") + ", ".join(changed)


def set_bond(problem: Problem, spec: str, present: bool) -> str:
    left, right = _pair(spec, "-")
    a, b = _atom_id(problem, left), _atom_id(problem, right)
    if present:
        if any({x.a, x.b} == {a, b} for x in problem.bonds):
            return f"bond {a}-{b} already required"
        problem.bonds.append(Bond(a=a, b=b, reason="edit"))
        return f"bond {a}-{b} required"
    before = len(problem.bonds)
    problem.bonds = [x for x in problem.bonds if {x.a, x.b} != {a, b}]
    if len(problem.bonds) == before:
        raise EditError(f"no required bond {a}-{b}")
    return f"bond {a}-{b} no longer required"
