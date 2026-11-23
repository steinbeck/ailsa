"""QC-01: the six individual QC check functions.

Implemented in Plan 02 (`ailsa.nus.qc`). One class per check (per D-02's
critical/soft split), each documenting the intended callable name.

Critical checks (D-02, any violation -> FAIL): quaternary exclusion, ppm
calibration, signal-to-ridge, HSQC coverage.
Soft checks (D-02, violation -> PARTIAL): edited-sign self-consistency,
COSY diagonal symmetry.
"""

from __future__ import annotations


class TestQuaternaryExclusion:
    """Critical check: no HSQC 1-bond correlation within tolerance of a
    known-quaternary shift (RESEARCH.md Pitfall 3; the primary defense
    against the known-bad HSQC's 4/27 false quaternary hits).

    Intended callable: `ailsa.nus.qc.quaternary_exclusion(hsqc_peaks,
    known_quaternary_shifts, tol=0.5) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir, c20h32o2_quaternary_shifts) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.quaternary_exclusion`)."""
        import json

        from ailsa.nus.qc import quaternary_exclusion

        peaks = json.loads((clean_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        result = quaternary_exclusion(peaks, c20h32o2_quaternary_shifts)
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir, c20h32o2_quaternary_shifts) -> None:
        """The July home-IST HSQC has cross-peaks at the quaternary carbons
        51.63 and 35.23 (confirmed 2026-11-23)."""
        import json

        from ailsa.nus.qc import quaternary_exclusion

        peaks = json.loads((known_bad_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        result = quaternary_exclusion(peaks, c20h32o2_quaternary_shifts)
        assert result.passed is False
        assert "51.63" in result.details
        assert "35.23" in result.details

    def test_no_classification_is_not_checkable(self, clean_peaks_dir) -> None:
        """Without DEPT or an explicit list the check is unchecked, not failed."""
        import json

        from ailsa.nus.qc import QcReferenceData, check_quaternary_exclusion

        peaks = json.loads((clean_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        ref = QcReferenceData(
            trusted_c13=[], trusted_h1=[], quaternary_shifts=None,
            classification_source="insufficient_reference_data",
        )
        result = check_quaternary_exclusion(peaks, ref)
        assert result.passed is False
        assert result.checkable is False


class TestPpmCalibration:
    """Critical check: reuse `nus/postprocess.py::check_calibration()`
    against the dataset's own 1D 13C list (Don't Hand-Roll -- do not reimplement).

    Intended callable: `ailsa.nus.qc.qc_check_ppm_calibration(hsqc_c13_shifts,
    reference_c13_shifts, tol=DEFAULT_CALIBRATION_TOL) -> QcCheckResult`.
    """

    @staticmethod
    def _trusted_c13(peaks_dir) -> list[float]:
        import json

        data = json.loads((peaks_dir / "13C_exp7_wide.json").read_text())
        return [p["ppm"] for p in data["peaks"]]

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.qc_check_ppm_calibration`)."""
        import json

        from ailsa.nus.qc import qc_check_ppm_calibration

        peaks = json.loads((clean_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        shifts = [p["c13_ppm"] for p in peaks]
        result = qc_check_ppm_calibration(shifts, self._trusted_c13(clean_peaks_dir))
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.qc_check_ppm_calibration`)."""
        import json

        from ailsa.nus.qc import qc_check_ppm_calibration

        peaks = json.loads((known_bad_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        shifts = [p["c13_ppm"] + 5.0 for p in peaks]  # simulate a gross offset
        result = qc_check_ppm_calibration(shifts, self._trusted_c13(known_bad_peaks_dir))
        assert result.passed is False

    def test_offset_is_measured_against_the_given_list(self) -> None:
        """The reference is the caller's list, not a compiled-in one: a 2 ppm
        offset is caught against the matching 13C list."""
        from ailsa.nus.qc import qc_check_ppm_calibration

        reference = [128.4, 77.0, 55.1, 40.2, 21.3]
        assert qc_check_ppm_calibration(reference, reference).passed is True
        shifted = [s + 2.0 for s in reference]
        assert qc_check_ppm_calibration(shifted, reference).passed is False

    def test_no_1d_reference_is_not_checkable(self) -> None:
        from ailsa.nus.qc import qc_check_ppm_calibration

        result = qc_check_ppm_calibration([30.0, 40.0], [])
        assert result.passed is False
        assert result.checkable is False


class TestSignalToRidge:
    """Critical check: peak-list-only ridge_fraction() clustering (Pattern
    3, RESEARCH.md Pitfall 5). Known-bad COSY: 7/7 peaks share h1a=5.32
    (ridge_fraction == 1.0). Recommended starting FAIL threshold 0.5.

    Intended callable: `ailsa.nus.qc.ridge_fraction(peaks, axis_key,
    tol=0.05) -> float`, wrapped by `ailsa.nus.qc.signal_to_ridge(peaks,
    axis_key, threshold=0.5) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.signal_to_ridge`)."""
        import json

        from ailsa.nus.qc import signal_to_ridge

        peaks = json.loads((clean_peaks_dir / "COSY_exp2.json").read_text())["cross_peaks"]
        result = signal_to_ridge(peaks, "h1a_ppm")
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.signal_to_ridge`)."""
        import json

        from ailsa.nus.qc import signal_to_ridge

        peaks = json.loads((known_bad_peaks_dir / "COSY_exp2.json").read_text())["cross_peaks"]
        result = signal_to_ridge(peaks, "h1a_ppm")
        assert result.passed is False


class TestHsqcCoverage:
    """Critical check: >= floor fraction of trusted protonated carbons show
    >=1 HSQC correlation (RESEARCH.md Pitfall 3 -- does NOT catch the
    known-bad fixture alone, coverage is 100% there; quaternary-exclusion
    is the primary defense for that failure mode). Recommended floor 0.8.

    Intended callable: `ailsa.nus.qc.hsqc_coverage(hsqc_peaks,
    protonated_reference_shifts, floor=0.8) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir, c20h32o2_protonated_shifts) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.hsqc_coverage`)."""
        import json

        from ailsa.nus.qc import hsqc_coverage

        peaks = json.loads((clean_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        result = hsqc_coverage(peaks, c20h32o2_protonated_shifts)
        assert result.passed is True
        assert result.value == 1.0

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.hsqc_coverage`)."""
        import json

        from ailsa.nus.qc import hsqc_coverage

        peaks = json.loads((known_bad_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        # Force a deliberately incomplete reference list to exercise the
        # violation path (the known-bad fixture alone is 100% coverage).
        protonated = [69.06, 67.06, 51.63, 999.99, 998.88, 997.77]
        result = hsqc_coverage(peaks, protonated, floor=0.8)
        assert result.passed is False


class TestEditedSignConsistency:
    """Soft check: every carbon with >1 HSQC peak must share ONE
    multiplicity_hint (RESEARCH.md Pitfall 4 / Code Examples). Known-bad
    HSQC: violations at 22.63, 23.43, 67.06 (3 of 7 multi-peak carbons).

    Intended callable: `ailsa.nus.qc.edited_sign_self_consistent(hsqc_peaks,
    tol=0.5) -> tuple[bool, list[float]]`, wrapped by
    `ailsa.nus.qc.edited_sign_consistency(hsqc_peaks) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.edited_sign_consistency`)."""
        import json

        from ailsa.nus.qc import edited_sign_consistency

        peaks = json.loads((clean_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        result = edited_sign_consistency(peaks)
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.edited_sign_consistency`)."""
        import json

        from ailsa.nus.qc import edited_sign_consistency

        peaks = json.loads((known_bad_peaks_dir / "HSQC_exp3.json").read_text())["cross_peaks"]
        result = edited_sign_consistency(peaks)
        assert result.passed is False


class TestCosyDiagonalSymmetry:
    """Soft check: for every (h1a, h1b) COSY cross-peak, a mirror (h1b, h1a)
    should also be present within tolerance -- known-bad COSY is a
    textbook one-sided t1-ridge (all 7 share h1a=5.32, no diagonal
    symmetry), synthetic-clean COSY is diagonal-symmetric by construction.

    Intended callable: `ailsa.nus.qc.cosy_diagonal_symmetry(cosy_peaks,
    tol=0.05) -> QcCheckResult`.
    """

    def test_clean_passes(self, clean_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.cosy_diagonal_symmetry`)."""
        import json

        from ailsa.nus.qc import cosy_diagonal_symmetry

        peaks = json.loads((clean_peaks_dir / "COSY_exp2.json").read_text())["cross_peaks"]
        result = cosy_diagonal_symmetry(peaks)
        assert result.passed is True

    def test_violation_trips(self, known_bad_peaks_dir) -> None:
        """Implementing plan: Plan 02 (`ailsa.nus.qc.cosy_diagonal_symmetry`)."""
        import json

        from ailsa.nus.qc import cosy_diagonal_symmetry

        peaks = json.loads((known_bad_peaks_dir / "COSY_exp2.json").read_text())["cross_peaks"]
        result = cosy_diagonal_symmetry(peaks)
        assert result.passed is False
