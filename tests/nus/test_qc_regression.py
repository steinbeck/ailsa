"""QC-02: the discrimination regression floor.

The calibration anchor for the whole QC gate (D-02/D-04): the real
known-bad home-IST HSQC/HMBC/COSY lists MUST verdict FAIL (via the
critical quaternary-exclusion + signal-to-ridge checks); the
hand-authored synthetic-clean set MUST verdict PASS when the quaternary
carbons are known (Plan 01's own load-bearing fixture, rebuilt 2026-11-23
from the confirmed C20H32O2 assignment). Neither fixture has a DEPT, so
without an explicit quaternary list the classification-dependent checks are
not checkable and the clean set verdicts PARTIAL (PROV-01).
"""

from __future__ import annotations


def test_known_bad_dir_fails(known_bad_peaks_dir) -> None:
    """`run_qc_checks(known_bad_peaks_dir)` must verdict FAIL even with no
    quaternary classification -- the signal-to-ridge violation (COSY 7/7
    sharing h1a=5.32) is critical on its own (RESEARCH.md Pitfall #5).

    Implementing plan: Plan 02 (`ailsa.nus.qc.run_qc_checks`).
    """
    from ailsa.models.nus import QcVerdict
    from ailsa.nus.qc import run_qc_checks

    report = run_qc_checks(known_bad_peaks_dir)
    assert report.verdict == QcVerdict.FAIL
    assert "signal_to_ridge" in report.critical_violations()
    assert "quaternary_exclusion" in report.unchecked_checks()


def test_known_bad_dir_trips_quaternary_exclusion_when_classified(
    known_bad_peaks_dir, c20h32o2_quaternary_shifts
) -> None:
    """With the confirmed quaternary carbons supplied, the known-bad HSQC's
    cross-peaks at 51.63 and 35.23 are critical violations too."""
    from ailsa.models.nus import QcVerdict
    from ailsa.nus.qc import QcConfig, run_qc_checks

    config = QcConfig(known_quaternary_shifts=tuple(c20h32o2_quaternary_shifts))
    report = run_qc_checks(known_bad_peaks_dir, config)
    assert report.verdict == QcVerdict.FAIL
    assert "quaternary_exclusion" in report.critical_violations()
    assert report.unchecked_checks() == []


def test_synthetic_clean_dir_passes_when_classified(
    clean_peaks_dir, c20h32o2_quaternary_shifts
) -> None:
    """`run_qc_checks(clean_peaks_dir, config)` must verdict PASS -- the
    synthetic-clean fixture has zero HSQC hits at the confirmed quaternary
    carbons, full coverage of the protonated ones, no ridge, self-consistent
    edited signs, and diagonal-symmetric COSY.

    Implementing plan: Plan 02 (`ailsa.nus.qc.run_qc_checks`).
    """
    from ailsa.models.nus import QcVerdict
    from ailsa.nus.qc import QcConfig, run_qc_checks

    config = QcConfig(known_quaternary_shifts=tuple(c20h32o2_quaternary_shifts))
    report = run_qc_checks(clean_peaks_dir, config)
    assert report.verdict == QcVerdict.PASS, report.summary()


def test_synthetic_clean_dir_without_classification_is_partial(clean_peaks_dir) -> None:
    """No DEPT and no explicit list: the two classification-dependent checks
    are not checkable, which caps a clean set at PARTIAL -- never PASS,
    never FAIL. No compiled-in compound list may stand in (PROV-01)."""
    from ailsa.models.nus import QcVerdict
    from ailsa.nus.qc import QcConfig, run_qc_checks

    assert QcConfig.default().known_quaternary_shifts == ()
    report = run_qc_checks(clean_peaks_dir)
    assert report.verdict == QcVerdict.PARTIAL
    assert sorted(report.unchecked_checks()) == ["hsqc_coverage", "quaternary_exclusion"]
    assert report.violated_checks() == []
