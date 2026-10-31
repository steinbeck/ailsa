"""Tests for the guided CASE workflow (ailsa.case) that need no spectra."""

from __future__ import annotations

import shutil

import pytest

from ailsa.case import edit as ed
from ailsa.case.build import CarbonSignal, resolve_counts
from ailsa.case.checks import check_problem
from ailsa.case.lsdfile import lsd_index, render
from ailsa.case.model import Atom, Bond, Correlation, Problem, dbe, parse_formula
from ailsa.case.scan import classify
from ailsa.case.spectra import Line, drop_satellites, find_solvent_multiplets


class TestFormula:
    def test_parse(self) -> None:
        assert parse_formula("C10H16O") == {"C": 10, "H": 16, "O": 1}
        assert parse_formula("C13H9BrO") == {"C": 13, "H": 9, "Br": 1, "O": 1}

    def test_reject(self) -> None:
        with pytest.raises(ValueError):
            parse_formula("c10h16")

    def test_dbe(self) -> None:
        assert dbe({"C": 6, "H": 6}) == 4
        assert dbe({"C": 8, "H": 10, "N": 4, "O": 2}) == 6
        assert dbe({"C": 13, "H": 9, "Br": 1, "O": 1}) == 9


class TestClassify:
    @pytest.mark.parametrize(
        ("pp", "nuc", "f1", "is2d", "kind"),
        [
            ("zgpg30", "13C", None, False, "13C"),
            ("udeft", "13C", None, False, "13C"),
            ("dept135", "13C", None, False, "DEPT-135"),
            ("deptsp90", "13C", None, False, "DEPT-90"),
            ("jmod", "13C", None, False, "APT"),
            ("aptsp.ber", "13C", None, False, "APT"),
            ("hsqcedetgpsisp2.3", "1H", "13C", True, "HSQC"),
            ("inv4gpqf", "1H", "13C", True, "HSQC"),
            ("inv4gplplrndqf", "1H", "13C", True, "HMBC"),
            ("hmbcgplpndqf", "1H", "13C", True, "HMBC"),
            ("hmqcetgp", "1H", "15N", True, "HSQC-15N"),
            ("cosygpqf", "1H", "1H", True, "COSY"),
            ("noesygpph", "1H", "1H", True, "NOESY"),
        ],
    )
    def test_kinds(self, pp: str, nuc: str, f1: str | None, is2d: bool, kind: str) -> None:
        assert classify(pp, nuc, f1, is2d) == kind


class TestLines:
    def test_satellites(self) -> None:
        lines = [Line(129.38, 1, 450), Line(129.42, 1, 8), Line(130.16, 1, 23), Line(45.0, 1, 200)]
        kept, dropped = drop_satellites(lines)
        assert [ln.shift for ln in dropped] == [129.42]
        assert 130.16 in [ln.shift for ln in kept]  # a weak quaternary beside a strong CH stays

    def test_solvent_triplet_with_offset(self) -> None:
        lines = [Line(76.6, 1, 400), Line(76.92, 1, 410), Line(77.24, 1, 405), Line(70.1, 1, 90)]
        found, name, offset = find_solvent_multiplets(lines)
        assert name == "cdcl3"
        assert sorted(ln.shift for ln in found) == [76.6, 76.92, 77.24]
        assert offset == pytest.approx(-0.24, abs=0.01)


def _problem() -> Problem:
    """A small ester-like problem: C5H10O2 (DBE 1)."""
    atoms = [
        Atom(id=1, element="C", shift=173.0, hydrogens=0, hyb=2),
        Atom(id=2, element="C", shift=60.5, hydrogens=2, hyb=3, h_shifts=[4.1]),
        Atom(id=3, element="C", shift=27.5, hydrogens=2, hyb=3, h_shifts=[2.3]),
        Atom(id=4, element="C", shift=14.2, hydrogens=3, hyb=3, h_shifts=[1.25]),
        Atom(id=5, element="C", shift=9.1, hydrogens=3, hyb=3, h_shifts=[1.1]),
        Atom(id=6, element="O", hydrogens=0, hyb=2),
        Atom(id=7, element="O", hydrogens=0, hyb=3),
    ]
    corrs = [
        Correlation(id="B1", kind="HMBC", x=[1], y=2, c_shift=173.0, h_shift=4.1),
        Correlation(id="B2", kind="HMBC", x=[1], y=3, c_shift=173.0, h_shift=2.3),
        Correlation(id="B3", kind="HMBC", x=[3], y=5, c_shift=27.5, h_shift=1.1),
    ]
    return Problem(
        formula="C5H10O2",
        dataset="x",
        atoms=atoms,
        correlations=corrs,
        bonds=[Bond(a=1, b=6, reason="C=O")],
    )


class TestChecks:
    def test_ready(self) -> None:
        result = check_problem(_problem())
        assert result.ready, result.errors
        assert result.facts["rings"] == 0

    def test_hydrogen_budget(self) -> None:
        p = _problem()
        p.atom(4).hydrogens = 2
        assert any("hydrogens" in e for e in check_problem(p).errors)

    def test_parity(self) -> None:
        p = _problem()
        p.atom(6).hyb = 3
        assert any("even" in e for e in check_problem(p).errors)

    def test_carbon_count(self) -> None:
        p = _problem()
        p.atoms = [a for a in p.atoms if a.id != 5]
        errors = check_problem(p).errors
        assert any(e.startswith("C:") for e in errors)


class TestRender:
    def test_order_and_content(self) -> None:
        text = render(_problem(), elim=1, max_solutions=100)
        lines = [ln.split(";")[0].strip() for ln in text.splitlines()]
        commands = [ln.split()[0] for ln in lines if ln]
        assert commands.index("HSQC") < commands.index("HMBC")
        assert "ELIM 1 0" in lines
        assert "MAXS 100" in lines
        assert 'FEXP "NOT F1 AND NOT F2"' in lines
        assert "BOND 1 6" in lines
        assert lines[-1] == "EXIT" or "EXIT" in lines

    def test_gaps_are_renumbered(self) -> None:
        p = _problem()
        ed.remove_atom(p, "4")
        ed.add_carbon(p, "14.0:CH3")
        idx = lsd_index(p)
        assert sorted(idx.values()) == list(range(1, len(p.atoms) + 1))

    def test_group_syntax(self) -> None:
        p = _problem()
        p.correlations[0].x = [1, 3]
        assert "HMBC (1 3) 2" in render(p, elim=0, max_solutions=10)


class TestEdit:
    def test_copies_regroup_correlations(self) -> None:
        p = _problem()
        ed.set_copies(p, "3=2")
        copy = p.copies_of(3)[0]
        assert p.correlation("B3").x == [3, copy.id]
        ed.set_copies(p, "3=1")
        assert p.correlation("B3").x == [3]

    def test_mult_and_reasonless_errors(self) -> None:
        p = _problem()
        ed.set_mult(p, "C4=CH2")
        assert p.atom(4).hydrogens == 2
        with pytest.raises(ed.EditError):
            ed.set_mult(p, "4=CH4")
        with pytest.raises(ed.EditError):
            ed.set_mult(p, "99=CH")

    def test_drop_and_use(self) -> None:
        p = _problem()
        ed.set_use(p, "B1,B2", use=False)
        assert not p.correlation("B1").use
        ed.set_use(p, "b1", use=True)
        assert p.correlation("B1").use


class TestCounts:
    def test_symmetry_from_intensity_and_hydrogens(self) -> None:
        # Four lines for six carbons; the two strong CH lines are the doubled ones.
        signals = [
            CarbonSignal(shift=158.0, snr=40, hydrogens=0),
            CarbonSignal(shift=130.0, snr=400, hydrogens=1),
            CarbonSignal(shift=121.0, snr=210, hydrogens=1),
            CarbonSignal(shift=115.0, snr=420, hydrogens=1),
        ]
        copies, changed, left, _ = resolve_counts(signals, {"C": 6, "H": 6, "O": 1})
        assert copies == [1, 2, 1, 2]
        assert left == 1 and not changed


def test_lsd_solves_small_problem(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """End to end with the real solver, when it is installed."""
    from ailsa.case.solve import solve
    from ailsa.lsd.runner import LSDRunner

    if not (LSDRunner.is_available() and LSDRunner.is_outlsd_available()):
        pytest.skip("LSD not installed")
    p = _problem()
    result = solve(p, tmp_path)
    assert result.final is not None and result.final.solutions >= 1
    assert (tmp_path / result.final.directory / "solutions.smi").exists()
    shutil.rmtree(tmp_path / "runs")
