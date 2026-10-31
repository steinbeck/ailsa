"""Turn the spectra of a dataset into a solver problem.

``build_problem`` does what an NMR chemist does before the first solver run: decide
which lines are carbons, how many hydrogens each carries, which carbons are sp2,
which signals stand for two or more symmetry-equivalent carbons, where the
heteroatoms and their hydrogens go, and which HMBC and COSY peaks are trustworthy.

Every decision that is not forced by the data is recorded as an assumption with the
``ailsa case edit`` command that reverses it.
"""

from __future__ import annotations

import functools
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ailsa.case import rawproc
from ailsa.case import spectra as sp
from ailsa.case.model import (
    HALOGENS,
    HETERO_MAX_H,
    Assumption,
    Atom,
    Bond,
    Correlation,
    Problem,
    Unassigned,
    parse_formula,
)
from ailsa.case.scan import Experiment, ScanResult
from ailsa.models import Spectrum1D, Spectrum2D
from ailsa.processing.peak_picker_2d import _compute_2d_noise_sigma as noise_sigma_2d
from ailsa.readers import BrukerReader

# t1 noise in an HMBC proton column: a peak on a carbon must exceed this factor times
# this percentile of the peaks in the same column that hit no carbon.
HMBC_NOISE_PERCENTILE = 90
HMBC_NOISE_FACTOR = 2.0
# Peaks this much weaker than the strongest peak of the same proton were mostly wrong.
HMBC_WEAK = 0.05

# A carbonyl carbon is fixed as C=O from these shifts; below, C=O and C=C/C=N overlap.
CARBONYL_C = 168.0
ALDEHYDE_C = 188.0


@dataclass
class CarbonSignal:
    """Evidence collected for one carbon line."""

    shift: float
    snr: float
    apt_sign: int | None = None
    dept135: int | None = None
    dept135_snr: float = 0.0
    dept90_snr: float | None = None
    clusters: list[sp.Cluster] = field(default_factory=list)
    hydrogens: int = 0
    mult_source: str = ""
    mult_certain: bool = True
    hyb: int = 3
    hyb_source: str = ""
    hyb_certain: bool = True
    copies: int = 1
    options: dict[int, float] = field(default_factory=dict)
    from_hsqc: bool = False
    extra_evidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def protonated(self) -> bool:
        return bool(self.clusters) or self.dept135 in (1, -1)

    @property
    def main_cluster(self) -> sp.Cluster | None:
        return max(self.clusters, key=lambda c: c.peak_max) if self.clusters else None

    @property
    def h_shifts(self) -> list[float]:
        """Proton shifts: two for a CH2 with distinct protons, otherwise one.

        Cross-peaks of one proton multiplet that the picker split are averaged.
        """
        main = self.main_cluster
        if main is None:
            return []
        if self.hydrogens == 2:
            others = [
                c
                for c in self.clusters
                if abs(c.h_shift - main.h_shift) >= 0.1 and c.peak_max >= 0.3 * main.peak_max
            ]
            if others:
                partner = max(others, key=lambda c: c.peak_max)
                return sorted({round(main.h_shift, 3), round(partner.h_shift, 3)})
        near = [c for c in self.clusters if abs(c.h_shift - main.h_shift) <= 0.15]
        weights = [c.intensity for c in near]
        return [round(float(np.average([c.h_shift for c in near], weights=weights)), 3)]


@dataclass
class BuildInput:
    """The experiments used for one problem."""

    dataset: Path
    formula: str
    experiments: dict[str, Experiment]
    solvent: str | None = None


def choose_experiments(scan: ScanResult, overrides: dict[str, str]) -> dict[str, Experiment]:
    """The experiment per kind: the scan's choice unless an expno is given."""
    chosen = dict(scan.chosen)
    by_expno = {e.expno: e for e in scan.experiments}
    for kind, expno in overrides.items():
        if expno in ("", "none"):
            chosen.pop(kind, None)
            continue
        if expno not in by_expno:
            raise ValueError(f"no experiment {expno} in {scan.dataset}")
        chosen[kind] = by_expno[expno]
    return chosen


# --------------------------------------------------------------------------- carbons


def _collect_carbons(inp: BuildInput, problem: Problem) -> list[CarbonSignal]:
    exps = inp.experiments
    source = exps.get("13C") or exps.get("APT")
    if source is None:
        raise ValueError("the dataset has no processed 13C or APT spectrum")
    is_apt = source.kind == "APT"
    spectrum = _read_1d(source)
    detected, offset = sp.detected_solvent(spectrum, signed=is_apt)
    if detected:
        problem.solvent = detected
        problem.solvent_offset = round(offset, 2)
    cleaned = sp.carbon_lines(spectrum, problem.solvent, signed=is_apt)
    signals = [CarbonSignal(shift=round(ln.shift, 2), snr=ln.snr) for ln in cleaned.lines]
    if is_apt:
        for sig, ln in zip(signals, cleaned.lines, strict=True):
            sig.apt_sign = ln.sign
    for kind, tag in (("APT", "apt"), ("DEPT-135", "dept135"), ("DEPT-90", "dept90")):
        if kind in exps and not (kind == "APT" and is_apt):
            step = functools.partial(_attach_1d, signals, exps[kind], problem.solvent, tag)
            _optional(problem, kind, step)
    return signals


def _read_1d(exp: Experiment) -> Spectrum1D:
    """The processed 1D spectrum, or one processed here from the raw FID."""
    if exp.processed:
        return BrukerReader.read_1d(exp.path)
    return rawproc.process_1d(exp.path, signed=exp.kind not in ("13C", "1H"))


def _read_2d(exp: Experiment) -> Spectrum2D:
    """The processed 2D spectrum, or a magnitude spectrum processed here from the SER."""
    if exp.processed:
        return BrukerReader.read_2d(exp.path)
    return rawproc.process_2d(exp.path, exp.kind)


def _acquired_f1(exp: Experiment, spectrum: Spectrum2D) -> float:
    """F1 resolution as measured (ppm per increment), not as zero-filled for display.

    A 2D experiment often has only 128-256 increments; zero filling makes the axis look
    finer than the data are, and a peak's carbon shift is only as good as the measured
    increments allow.
    """
    acqu2s = exp.path / "acqu2s"
    try:
        text = acqu2s.read_text(errors="replace")
        td = int(float(re.search(r"^##\$TD=\s*(\S+)", text, re.MULTILINE).group(1)))  # type: ignore[union-attr]
        fnmode_match = re.search(r"^##\$FnMODE=\s*(\S+)", text, re.MULTILINE)
        fnmode = int(fnmode_match.group(1)) if fnmode_match else 0
    except (OSError, ValueError, AttributeError):
        return 0.0
    points = td // 2 if fnmode in (4, 5, 6) else td
    width = abs(float(spectrum.f1_ppm_scale[0] - spectrum.f1_ppm_scale[-1]))
    return width / max(points, 1)


def _optional(problem: Problem, kind: str, step: Callable[[], object]) -> object:
    """Run one spectrum's step; an unreadable spectrum is skipped and reported."""
    try:
        return step()
    except Exception as exc:  # unreadable or truncated data: carry on without it
        problem.spectra.pop(kind, None)
        problem.assumptions.append(
            Assumption(
                code="unreadable",
                text=f"{kind} could not be read and was not used ({type(exc).__name__})",
                fix="ailsa case setup DATASET --force --use KIND=EXPNO  (another experiment)",
            )
        )
        return None


def _attach_1d(
    signals: list[CarbonSignal], exp: Experiment, solvent: str | None, kind: str
) -> None:
    """Match lines of an edited 1D spectrum (APT, DEPT) to the carbon lines.

    Lines weaker than 8 % of the median of the stronger half are leakage (a quaternary
    carbon in a DEPT, a CH3 in a DEPT-90) and do not count as a signal.
    """
    spectrum = _read_1d(exp)
    cleaned = sp.carbon_lines(spectrum, solvent, signed=kind != "dept90")
    lines = cleaned.lines
    if lines:
        strong = sorted((ln.snr for ln in lines), reverse=True)[: max(1, len(lines) // 2)]
        floor = 0.08 * float(np.median(strong))
    else:
        floor = 0.0
    matched = sp.match_lines([s.shift for s in signals], lines, tolerance=0.3)
    for i, sig in enumerate(signals):
        line = matched.get(i)
        if kind == "apt":
            sig.apt_sign = line.sign if line else None
        elif kind == "dept135":
            valid = line is not None and line.snr >= floor
            sig.dept135 = line.sign if (line and valid) else 0
            sig.dept135_snr = line.snr if (line and valid) else 0.0
        else:
            sig.dept90_snr = line.snr if line else 0.0


def _attach_hsqc(
    signals: list[CarbonSignal], exp: Experiment, problem: Problem
) -> list[sp.Cluster]:
    """Assign HSQC cross-peaks to carbons; return the unassigned strong ones.

    Filters, in order: the solvent's residual C-H; cross-peaks below eight times the
    noise or 1 % of the strongest; t1-noise and phase artefacts in the column of a much
    stronger cross-peak; carbon/proton shift pairs that cannot be one C-H (a carbon
    above 100 ppm carries a proton above 4 ppm, one below 50 ppm none above 6 ppm).
    A global carbon offset between HSQC and 13C referencing is estimated and removed.
    Where two carbon lines are close, a carbon that shows a DEPT signal is preferred.
    """
    spectrum = _read_2d(exp)
    clusters = sp.hsqc_clusters(spectrum, signed=True, threshold=0.01)
    clusters = [
        c
        for c in clusters
        if not sp.is_solvent_ch(c.c_shift, c.h_shift, problem.solvent, problem.solvent_offset)
    ]
    if clusters:
        sigma = noise_sigma_2d(spectrum.data)
        floor = max(8.0 * sigma, 0.01 * max(c.peak_max for c in clusters))
        clusters = [c for c in clusters if c.peak_max >= floor]
    clusters, _ = sp.drop_column_artifacts(clusters)
    clusters = [
        c
        for c in clusters
        if not (c.c_shift >= 100 and c.h_shift < 4.0) and not (c.c_shift < 50 and c.h_shift > 6.0)
    ]
    tol = max(0.6, 2.0 * sp.resolution(spectrum.f1_ppm_scale), 0.6 * _acquired_f1(exp, spectrum))
    offset = _hsqc_offset(signals, clusters)
    have_dept = any(s.dept135 is not None for s in signals)
    unassigned: list[sp.Cluster] = []
    for cl in clusters:
        c = cl.c_shift - offset
        near = [s for s in signals if abs(s.shift - c) <= tol]
        if have_dept and any(s.dept135 in (1, -1) for s in near):
            near = [s for s in near if s.dept135 in (1, -1)]
        if not near:
            unassigned.append(cl)
            continue
        min(near, key=lambda s: abs(s.shift - c)).clusters.append(cl)
    for sig in signals:
        if sig.clusters:
            strongest = max(c.peak_max for c in sig.clusters)
            sig.clusters = [c for c in sig.clusters if c.peak_max >= strongest / 8]
    problem.hsqc_edited = exp.edited and any(c.sign < 0 for s in signals for c in s.clusters)
    assigned = [c.peak_max for s in signals for c in s.clusters]
    level = float(np.median(assigned)) if assigned else 0.0
    return [c for c in unassigned if c.peak_max >= 0.2 * level]


def _hsqc_offset(signals: list[CarbonSignal], clusters: list[sp.Cluster]) -> float:
    """Median carbon offset of HSQC cross-peaks against the nearest carbon line."""
    diffs = []
    for cl in clusters:
        nearest = min(signals, key=lambda s: abs(s.shift - cl.c_shift), default=None)
        if nearest is not None and abs(nearest.shift - cl.c_shift) <= 1.5:
            diffs.append(cl.c_shift - nearest.shift)
    if len(diffs) < 3:
        return 0.0
    offset = float(np.median(diffs))
    return offset if abs(offset) > 0.05 else 0.0


def _calibrate_signs(signals: list[CarbonSignal], problem: Problem) -> tuple[int, int]:
    """Sign conventions of DEPT-135 and edited HSQC, read from the data.

    Returns factors that turn each experiment's sign into the convention "CH2
    negative". Reference: protonated carbons above 100 ppm with a proton above
    4.5 ppm are almost always CH, so they must come out positive. Without such
    carbons the two experiments are checked against each other; failing that, the
    standard convention is assumed.
    """
    ch_like = [
        s
        for s in signals
        if s.shift >= 100 and s.main_cluster is not None and s.main_cluster.h_shift >= 4.5
    ]

    def vote(values: list[int]) -> int | None:
        values = [v for v in values if v in (1, -1)]
        if not values:
            return None
        return 1 if sum(values) >= 0 else -1

    dept = vote([s.dept135 or 0 for s in ch_like])
    hsqc = vote(
        [s.main_cluster.sign for s in ch_like if s.main_cluster and not s.main_cluster.mixed]
    )
    if dept is None and hsqc is not None:
        agree = vote(
            [
                (s.dept135 or 0) * hsqc * s.main_cluster.sign
                for s in signals
                if s.main_cluster and not s.main_cluster.mixed
            ]
        )
        dept = agree
    if hsqc is None and dept is not None and problem.hsqc_edited:
        hsqc = vote(
            [
                dept * (s.dept135 or 0) * s.main_cluster.sign
                for s in signals
                if s.main_cluster and not s.main_cluster.mixed
            ]
        )
    return dept or 1, hsqc or 1


def _apt_even_sign(signals: list[CarbonSignal]) -> int | None:
    """The APT phase shared by C and CH2: the sign of the unprotonated carbons."""
    signs = [s.apt_sign for s in signals if s.apt_sign is not None and not s.clusters]
    if not signs:
        return None
    positive = sum(1 for x in signs if x > 0)
    if positive >= 0.8 * len(signs):
        return 1
    if positive <= 0.2 * len(signs):
        return -1
    return None


def _decide_multiplicities(
    signals: list[CarbonSignal], problem: Problem, counts: dict[str, int]
) -> None:
    """Hydrogen count of every carbon from the strongest evidence available.

    Decisive evidence: DEPT-135 negative, the APT phase of CH2, an edited-HSQC
    negative cross-peak (all sign-calibrated), DEPT-90 against DEPT-135. Where it is
    missing, the carbon gets probabilities for each hydrogen count (see
    :func:`_h_count_logp`) and the count search over the whole molecule decides.
    """
    dept_f, hsqc_f = _calibrate_signs(signals, problem)
    apt_even = _apt_even_sign(signals)
    has_dept = any(s.dept135 is not None for s in signals)
    mains = [s.main_cluster.peak_max for s in signals if s.main_cluster]
    level = float(np.median(mains)) if mains else 0.0
    for sig in signals:
        dept = (sig.dept135 or 0) * dept_f
        # A cross-peak far below the typical one does not make a carbon protonated
        # when a DEPT shows nothing there.
        if has_dept and dept == 0 and sig.clusters:
            sig.clusters = [c for c in sig.clusters if c.peak_max >= 0.15 * level]
        main = sig.main_cluster
        edited = main.sign * hsqc_f if (problem.hsqc_edited and main and not main.mixed) else 0
        apt_odd = apt_even is not None and sig.apt_sign is not None and sig.apt_sign != apt_even
        protonated = bool(sig.clusters) or dept != 0 or apt_odd
        if not protonated:
            sig.hydrogens, sig.mult_source = 0, "no HSQC or DEPT signal"
            if not problem.spectra.get("HSQC") and not has_dept and sig.apt_sign is None:
                sig.mult_source = "no HSQC and no DEPT: guessed from the shift"
                sig.options = _h_count_logp(sig, counts, level, (0, 1, 2, 3))
            continue
        odd_phase = dept == 1 or apt_odd  # CH or CH3 by DEPT-135 or APT
        if dept == -1:
            sig.hydrogens, sig.mult_source = 2, "DEPT-135 negative"
        elif apt_even is not None and sig.apt_sign == apt_even:
            sig.hydrogens, sig.mult_source = 2, "APT phase of CH2 and C"
        elif edited == -1 and not odd_phase:
            sig.hydrogens, sig.mult_source = 2, "edited HSQC negative"
        elif sig.dept90_snr is not None and dept == 1:
            sig.mult_source = "DEPT-90"
        elif odd_phase or edited == 1:
            basis = "DEPT/APT phase" if odd_phase else "edited HSQC positive"
            sig.mult_source = f"CH or CH3 ({basis}); chosen by shifts, intensity, formula"
            sig.options = _h_count_logp(sig, counts, level, (1, 3))
        else:
            sig.mult_source = "CH, CH2 or CH3 (HSQC only); chosen by shifts, intensity, formula"
            sig.options = _h_count_logp(sig, counts, level, (1, 2, 3))
    _apply_dept90(signals)
    for sig in signals:
        if sig.options:
            sig.mult_certain = False
            sig.hydrogens = max(sig.options, key=lambda h: sig.options[h])


def _two_protons(sig: CarbonSignal) -> bool:
    main = sig.main_cluster
    if main is None:
        return False
    return any(
        abs(c.h_shift - main.h_shift) >= 0.1 and c.peak_max >= 0.3 * main.peak_max
        for c in sig.clusters
    )


def _h_count_logp(
    sig: CarbonSignal, counts: dict[str, int], level: float, allowed: tuple[int, ...]
) -> dict[int, float]:
    """Log-probability of each allowed hydrogen count of one carbon.

    Prior from the carbon and proton shift (typical ranges of CH3, CH2 and CH groups,
    methoxy and N-methyl, terminal =CH2, acetals). Two clearly distinct protons make
    CH2 likely. The HSQC cross-peak intensity, compared with the typical cross-peak,
    adds a weak preference: more protons give a stronger cross-peak.
    """
    main = sig.main_cluster
    h = main.h_shift if main else None
    c = sig.shift
    o, n = counts.get("O", 0), counts.get("N", 0)
    if c >= 185 and (h is None or h >= 9.0):
        prior = {0: 0.3, 1: 0.7, 2: 0.0, 3: 0.0}
    elif c >= 100:
        if c <= 120 and h is not None and 4.4 <= h <= 5.4:
            prior = {0: 0.1, 1: 0.35, 2: 0.55, 3: 0.0}  # terminal =CH2
        else:
            prior = {0: 0.3, 1: 0.68, 2: 0.02, 3: 0.0}
    elif c >= 90:
        prior = {0: 0.2, 1: 0.55, 2: 0.25, 3: 0.0}
    elif c >= 60:
        prior = {0: 0.2, 1: 0.45, 2: 0.33, 3: 0.02}
    elif c >= 45:
        prior = {0: 0.15, 1: 0.35, 2: 0.35, 3: 0.15}
        if o and 50 <= c <= 62 and h is not None and 3.2 <= h <= 4.0:
            prior = {0: 0.05, 1: 0.3, 2: 0.2, 3: 0.45}  # methoxy
    elif c >= 30:
        prior = {0: 0.15, 1: 0.35, 2: 0.42, 3: 0.08}
        if n and h is not None and 2.1 <= h <= 4.1:
            prior = {0: 0.1, 1: 0.3, 2: 0.3, 3: 0.3}  # N-methyl possible
    elif c >= 22:
        prior = {0: 0.1, 1: 0.2, 2: 0.4, 3: 0.3}
        if n and h is not None and 2.8 <= h <= 4.1:
            prior = {0: 0.05, 1: 0.1, 2: 0.3, 3: 0.55}  # N-methyl on an amide or ring N
    else:
        prior = {0: 0.05, 1: 0.1, 2: 0.25, 3: 0.6}
    logp: dict[int, float] = {}
    for k in allowed:
        p = max(prior.get(k, 0.0), 1e-4)
        if k == 2 and _two_protons(sig):
            p = max(p, 0.8)
        lp = math.log(p)
        if main is not None and level > 0 and k > 0:
            # cross-peak intensity roughly proportional to the number of protons
            lp -= (math.log(main.peak_max / level) - math.log(k / 1.8)) ** 2 / (2 * 0.8**2)
        logp[k] = lp
    top = max(logp.values())
    return {k: v - top for k, v in logp.items()}


def _apply_dept90(signals: list[CarbonSignal]) -> None:
    """CH or CH3 from the DEPT-90/DEPT-135 intensity ratio.

    In DEPT-90 the CH lines are strong and CH2/CH3 lines appear only as weak leakage,
    so the ratio separates the two groups. A carbon counts as CH when its ratio is at
    least half the largest ratio.
    """
    pending = [s for s in signals if s.mult_source == "DEPT-90"]
    if not pending:
        return
    ratios = {id(s): (s.dept90_snr or 0.0) / max(s.dept135_snr, 1e-9) for s in pending}
    top = max(ratios.values())
    for s in pending:
        is_ch = top > 0 and ratios[id(s)] >= 0.5 * top
        s.hydrogens = 1 if is_ch else 3
        s.mult_source = "DEPT-90 present" if is_ch else "DEPT-90 absent"


def _decide_hybridisation(sig: CarbonSignal, counts: dict[str, int]) -> None:
    c = sig.shift
    h = sig.h_shifts[0] if sig.h_shifts else None
    if c >= 110:
        sig.hyb, sig.hyb_source = 2, "shift >= 110 ppm"
        if sig.hydrogens == 0 and 112 <= c <= 125 and counts.get("N"):
            sig.notes.append("could be a nitrile carbon (sp)")
        return
    if c < 90:
        sig.hyb, sig.hyb_source = 3, "shift < 90 ppm"
        if sig.hydrogens == 0 and 65 <= c <= 90 and not counts.get("O"):
            sig.notes.append("an unprotonated carbon at 65-90 ppm without oxygen: alkyne (sp)?")
        return
    # 90-110 ppm: acetal/ketal (sp3) or electron-rich alkene/aromatic carbon (sp2)
    sig.hyb_certain = False
    if sig.hydrogens == 2:
        if h is not None and h >= 5.6 and counts.get("O", 0) >= 2:
            sig.hyb, sig.hyb_source = 3, "CH2 at 90-110 ppm, H >= 5.6: O-CH2-O"
        else:
            sig.hyb, sig.hyb_source = 2, "CH2 at 90-110 ppm: exocyclic =CH2"
    elif sig.hydrogens == 1 and h is not None and h < 5.7 and counts.get("O", 0) >= 2:
        sig.hyb, sig.hyb_source = 3, "CH at 90-110 ppm, H < 5.7: acetal"
    elif sig.hydrogens == 0 and c < 100 and counts.get("O", 0) >= 2:
        sig.hyb, sig.hyb_source = 3, "C at 90-100 ppm: ketal"
    else:
        sig.hyb, sig.hyb_source = 2, "90-110 ppm: sp2 assumed"


# ------------------------------------------------------------------------ symmetry


def _evidence(signals: list[CarbonSignal]) -> list[float]:
    """How strongly each line looks like two or more carbons, as an intensity ratio."""
    protonated = [s.snr for s in signals if s.hydrogens > 0 and not s.from_hsqc]
    quaternary = [s.snr for s in signals if s.hydrogens == 0 and not s.from_hsqc]
    med_p = float(np.median(protonated)) if protonated else 1.0
    med_q = float(np.median(quaternary)) if quaternary else 1.0
    result = []
    for s in signals:
        ref = med_p if s.hydrogens > 0 else med_q
        result.append(s.snr / max(ref, 1e-9))
    return result


def resolve_counts(
    signals: list[CarbonSignal], counts: dict[str, int]
) -> tuple[list[int], dict[int, int], int, str]:
    """Copies and hydrogen count of every signal, chosen to fit the formula.

    For each signal the options are: how many carbons it stands for (0 drops a 13C line
    as noise or impurity, or leaves out an HSQC-only candidate; 2 or 3 for symmetry
    copies) and, where the spectra do not decide it, its hydrogen count. Each option has
    a log-likelihood:

    - copies: the line's intensity against the typical line, compared with the number
      of carbons it would stand for (log-normal, so a line twice as strong as the
      others fits two carbons);
    - dropping a 13C line: unlikely a priori, less so for a weak line without HSQC
      or DEPT signal;
    - adding an HSQC-only carbon: likely under the solvent signal, otherwise in
      proportion to its cross-peak;
    - hydrogen count: the signal's own probabilities; a count the spectra fixed can
      still change, at a high cost, so that a wrong cross-peak cannot make the formula
      unreachable.

    A dynamic programme over (carbons, hydrogens) finds the combination with the
    highest total whose carbon count equals the formula and whose remaining hydrogens
    fit the heteroatoms. Returns copies per signal, changed hydrogen counts by index,
    the hydrogens left for heteroatoms, and a note.
    """
    n_c = counts.get("C", 0)
    n_h = counts.get("H", 0)
    carbonyls = sum(
        1
        for s in signals
        if (s.hydrogens == 0 and s.shift >= CARBONYL_C)
        or (s.hydrogens == 1 and s.shift >= ALDEHYDE_C)
    )
    hetero_cap = sum(HETERO_MAX_H.get(el, 0) * k for el, k in counts.items())
    hetero_cap -= min(carbonyls, counts.get("O", 0)) * HETERO_MAX_H["O"]
    evidence = _evidence(signals)
    lines = [s for s in signals if not s.from_hsqc]
    strong = sorted((s.snr for s in lines), reverse=True)[: max(1, len(lines) // 2)]
    weak_level = 0.25 * float(np.median(strong)) if strong else 0.0

    def options(i: int) -> list[tuple[int, int, float]]:
        sig = signals[i]
        if sig.options:
            h_opts = dict(sig.options)
        else:
            h_opts = {sig.hydrogens: 0.0}
            for h in (0, 1, 2, 3):
                if h != sig.hydrogens:
                    h_opts[h] = -5.0 if (h == 0) != (sig.hydrogens == 0) else -4.0
        result: list[tuple[int, int, float]] = []
        if sig.from_hsqc:
            result.append((0, 0, 0.0))
            for h, lp in h_opts.items():
                if h > 0:
                    result.append((1, h, sig.extra_evidence + lp))
            return result
        weak = sig.snr < weak_level and not sig.protonated
        result.append((0, 0, -1.0 if weak else -4.0))
        ratio = max(evidence[i], 0.05)
        for c in (1, 2, 3):
            if c == 3 and not (sig.options.get(3, -9.0) > -9.0 or sig.hydrogens == 3):
                continue
            fit = -((math.log(ratio) - math.log(c)) ** 2) / (2 * 0.35**2)
            base = -((math.log(ratio)) ** 2) / (2 * 0.35**2)
            for h, lp in h_opts.items():
                if c == 3 and h != 3:
                    continue
                result.append((c, h, lp + fit - base))
        return result

    # best[(carbons, hydrogens)] = (score, choices)
    best: dict[tuple[int, int], tuple[float, tuple[tuple[int, int], ...]]] = {(0, 0): (0.0, ())}
    for i in range(len(signals)):
        nxt: dict[tuple[int, int], tuple[float, tuple[tuple[int, int], ...]]] = {}
        for (nc, nh), (score, path) in best.items():
            for c, h, lp in options(i):
                key = (nc + c, nh + c * h)
                if key[0] > n_c or key[1] > n_h:
                    continue
                cand = (score + lp, (*path, (c, h)))
                if key not in nxt or cand[0] > nxt[key][0]:
                    nxt[key] = cand
        best = nxt
    feasible = [
        (score, path, n_h - nh)
        for (nc, nh), (score, path) in best.items()
        if nc == n_c and 0 <= n_h - nh <= hetero_cap
    ]
    if not feasible:
        copies = [0 if s.from_hsqc else 1 for s in signals]
        h_carbon = sum(s.hydrogens for s, c in zip(signals, copies, strict=True) if c)
        return copies, {}, n_h - h_carbon, "no choice fits the formula"
    feasible.sort(key=lambda t: -t[0])
    score, path, left = feasible[0]
    copies = [c for c, _ in path]
    changed = {i: h for i, (c, h) in enumerate(path) if c and h != signals[i].hydrogens}
    margin = score - feasible[1][0] if len(feasible) > 1 else math.inf
    note = "clear" if margin >= 1.0 else "close alternatives exist"
    return copies, changed, left, note


def _option_gap(options: dict[int, float]) -> float:
    """How decided a carbon's hydrogen count is: best minus second-best log-probability."""
    values = sorted(options.values(), reverse=True)
    return values[0] - values[1] if len(values) > 1 else math.inf


def _chosen_gap(sig: CarbonSignal) -> float:
    """Log-probability margin of the chosen hydrogen count over the best alternative."""
    others = [v for k, v in sig.options.items() if k != sig.hydrogens]
    return sig.options.get(sig.hydrogens, -math.inf) - max(others) if others else math.inf


def _hsqc_only_carbons(
    clusters: list[sp.Cluster], problem: Problem, counts: dict[str, int], level: float
) -> list[CarbonSignal]:
    """Carbons seen only in the HSQC, as optional candidates for the count search.

    A carbon can be missing from the 13C list because the solvent multiplet covers it
    or because it is too weak. Such a candidate is preferred when it lies under the
    solvent, otherwise in proportion to its intensity.
    """
    key = sp.solvent_key(problem.solvent)
    windows = [
        (lo + problem.solvent_offset, hi + problem.solvent_offset)
        for lo, hi in (sp.SOLVENTS[key]["c"] if key else [])
    ]
    result = []
    for cl in clusters:
        sig = CarbonSignal(shift=round(cl.c_shift, 2), snr=0.0, clusters=[cl], from_hsqc=True)
        hidden = any(lo - 0.5 <= cl.c_shift <= hi + 0.5 for lo, hi in windows)
        sig.extra_evidence = 1.5 if hidden else math.log(max(cl.peak_max, 1e-9) / level) - 0.5
        sig.notes.append(
            "no 13C line: under the solvent signal" if hidden else "no 13C line: from the HSQC"
        )
        if problem.hsqc_edited and not cl.mixed and cl.sign < 0:
            sig.hydrogens, sig.mult_source = 2, "edited HSQC negative (HSQC only)"
        else:
            sig.mult_certain = False
            sig.mult_source = "CH, CH2 or CH3 (HSQC only); chosen by shifts, intensity, formula"
            sig.options = _h_count_logp(sig, counts, level, (1, 2, 3))
            sig.hydrogens = max(sig.options, key=lambda k: sig.options[k])
        result.append(sig)
    return result


# --------------------------------------------------------------------- assemble


def build_problem(inp: BuildInput) -> Problem:
    """Build the problem for ``inp``; raises ``ValueError`` on unusable input."""
    counts = parse_formula(inp.formula)
    problem = Problem(
        formula=inp.formula,
        dataset=str(inp.dataset),
        solvent=inp.solvent,
        spectra={k: e.expno for k, e in sorted(inp.experiments.items())},
    )
    signals = _collect_carbons(inp, problem)
    unassigned_hsqc: list[sp.Cluster] = []
    if "HSQC" in inp.experiments:
        hsqc = inp.experiments["HSQC"]
        found = _optional(problem, "HSQC", lambda: _attach_hsqc(signals, hsqc, problem))
        unassigned_hsqc = found if isinstance(found, list) else []
    _decide_multiplicities(signals, problem, counts)

    level = float(np.median([c.peak_max for x in signals for c in x.clusters] or [1.0]))
    signals += _hsqc_only_carbons(unassigned_hsqc, problem, counts, level)
    copies, changed, hetero_h, note = resolve_counts(signals, counts)
    for i, h in changed.items():
        signals[i].hydrogens = h
        signals[i].mult_source += "; set by the hydrogen count of the formula"
    for i, n in enumerate(copies):
        signals[i].copies = n
    dropped = [x for x in signals if not x.from_hsqc and not x.copies]
    if dropped:
        problem.assumptions.append(
            Assumption(
                code="surplus",
                text=(
                    "left out as noise or impurity (the formula has fewer carbons): "
                    + ", ".join(f"{x.shift:.2f} ppm" for x in dropped)
                ),
                fix="ailsa case edit DATASET --add-carbon SHIFT:TYPE  (to put one back)",
            )
        )
    added = [x for x in signals if x.from_hsqc and x.copies]
    unassigned_hsqc = [x.clusters[0] for x in signals if x.from_hsqc and not x.copies]
    signals = sorted((x for x in signals if x.copies), key=lambda x: -x.shift)
    for x in added:
        problem.assumptions.append(
            Assumption(
                code="hsqc-carbon",
                text=f"carbon at {x.shift:.2f} ppm added from the HSQC ({x.notes[0]})",
                fix="ailsa case edit DATASET --remove ID",
            )
        )
    for sig in signals:
        _decide_hybridisation(sig, counts)

    # Atoms: carbons in descending shift order, copies right after their line.
    atom_id = 1
    for sig in signals:
        root = atom_id
        for k in range(sig.copies):
            problem.atoms.append(
                Atom(
                    id=atom_id,
                    element="C",
                    shift=sig.shift,
                    hydrogens=sig.hydrogens,
                    hyb=sig.hyb,
                    h_shifts=sig.h_shifts,
                    copy_of=None if k == 0 else root,
                    snr=round(sig.snr, 1),
                    mult_source=sig.mult_source,
                    hyb_source=sig.hyb_source,
                    notes=list(sig.notes),
                )
            )
            atom_id += 1
    for sig, atom in zip(signals, problem.signals(), strict=True):
        if sig.options and _chosen_gap(sig) < 2.0:
            problem.assumptions.append(
                Assumption(
                    code="mult",
                    text=f"C{atom.id} {sig.shift:.2f} ppm taken as {atom.mult} ({sig.mult_source})",
                    fix=f"ailsa case edit DATASET --mult {atom.id}=CH3  (or CH, CH2, C)",
                )
            )
        if not sig.hyb_certain:
            problem.assumptions.append(
                Assumption(
                    code="hyb",
                    text=f"C{atom.id} {sig.shift:.2f} ppm taken as sp{atom.hyb} ({sig.hyb_source})",
                    fix=f"ailsa case edit DATASET --hyb {atom.id}=sp{5 - atom.hyb}",
                )
            )
        if sig.copies > 1:
            problem.assumptions.append(
                Assumption(
                    code="symmetry",
                    text=(
                        f"C{atom.id} {sig.shift:.2f} ppm stands for {sig.copies} "
                        "equivalent carbons "
                        f"(intense line, formula count; {note})"
                    ),
                    fix=f"ailsa case edit DATASET --copies {atom.id}=1",
                )
            )
    if len(problem.carbons()) != counts.get("C", 0):
        problem.assumptions.append(
            Assumption(
                code="count",
                text=(
                    f"{len(problem.carbons())} carbons from the spectrum, formula has "
                    f"{counts.get('C', 0)}; no symmetry assignment fits the hydrogen count"
                ),
                fix="ailsa case edit DATASET --copies ID=2 / --add-carbon SHIFT:MULT / --remove ID",
            )
        )

    _add_heteroatoms(problem, counts, hetero_h)
    for cl in unassigned_hsqc:
        problem.unassigned.append(
            Unassigned(
                kind="HSQC",
                c_shift=round(cl.c_shift, 2),
                h_shift=round(cl.h_shift, 2),
                text="cross-peak with no carbon line: a carbon missing from the 13C list?",
            )
        )
    if "HMBC" in inp.experiments:
        hmbc = inp.experiments["HMBC"]
        _optional(problem, "HMBC", lambda: _add_hmbc(problem, hmbc))
    if "COSY" in inp.experiments:
        cosy = inp.experiments["COSY"]
        _optional(problem, "COSY", lambda: _add_cosy(problem, cosy))
    problem.log("setup", f"built from {', '.join(f'{k}={v}' for k, v in problem.spectra.items())}")
    return problem


def _add_heteroatoms(problem: Problem, counts: dict[str, int], hetero_h: int) -> None:
    """Heteroatoms of the formula, their hydrogens, and carbonyl bonds."""
    order = ["O", "N", "S", "P", "Si", "B", *HALOGENS]
    elements = [el for el in order if counts.get(el)] + sorted(
        el for el in counts if el not in order and el not in ("C", "H")
    )
    hetero: list[Atom] = []
    for el in elements:
        for _ in range(counts[el]):
            hetero.append(
                Atom(
                    id=problem.next_atom_id(),
                    element=el,
                    hyb=3,
                    mult_source="formula",
                    hyb_source="default sp3",
                )
            )
            problem.atoms.append(hetero[-1])

    # Carbonyls: unprotonated carbons from 168 ppm, aldehyde CH from 188 ppm.
    oxygens = [a for a in hetero if a.element == "O"]
    carbonyls = [
        a
        for a in problem.carbons()
        if a.copy_of is None
        and a.shift is not None
        and (
            (a.hydrogens == 0 and a.shift >= CARBONYL_C)
            or (a.hydrogens == 1 and a.shift >= ALDEHYDE_C)
        )
    ]
    for c_atom, o_atom in zip(carbonyls, oxygens, strict=False):
        o_atom.hyb, o_atom.hyb_source = 2, f"carbonyl oxygen of C{c_atom.id}"
        problem.bonds.append(
            Bond(a=c_atom.id, b=o_atom.id, reason=f"C=O at {c_atom.shift:.1f} ppm")
        )
        problem.assumptions.append(
            Assumption(
                code="carbonyl",
                text=f"C{c_atom.id} {c_atom.shift:.2f} ppm bonded to O{o_atom.id} as C=O",
                fix=f"ailsa case edit DATASET --unbond {c_atom.id}-{o_atom.id}",
            )
        )

    # Hydrogens on heteroatoms: oxygen first, then nitrogen, then sulfur.
    left = hetero_h
    placed: list[str] = []
    for el in ("O", "N", "S"):
        for _ in range(HETERO_MAX_H[el]):
            for atom in hetero:
                if left <= 0:
                    break
                if atom.element == el and atom.hyb == 3 and atom.hydrogens < HETERO_MAX_H[el]:
                    atom.hydrogens += 1
                    left -= 1
                    placed.append(atom.label)
    if hetero_h:
        both = counts.get("O") and counts.get("N")
        problem.assumptions.append(
            Assumption(
                code="hetero-h",
                text=(
                    f"{hetero_h} hydrogen(s) not on carbon, placed on "
                    f"{', '.join(placed) or 'nothing'}"
                    + ("; could be on N instead of O" if both else "")
                ),
                fix="ailsa case edit DATASET --hetero-h ID=N",
            )
        )

    # Parity: LSD needs an even number of sp2 atoms.
    sp2 = [a for a in problem.atoms if a.hyb == 2]
    if len(sp2) % 2:
        free_o = [a for a in hetero if a.element == "O" and a.hyb == 3 and a.hydrogens == 0]
        free_n = [a for a in hetero if a.element == "N" and a.hyb == 3]
        candidates = free_o or free_n
        if candidates:
            pick = candidates[0]
            pick.hyb, pick.hyb_source = 2, "made sp2 for an even number of sp2 atoms"
            problem.assumptions.append(
                Assumption(
                    code="parity",
                    text=(
                        f"odd number of sp2 carbons; {pick.label} made sp2 "
                        "(a C=O or C=N whose carbon is below 168 ppm)"
                    ),
                    fix=f"ailsa case edit DATASET --hyb {pick.id}=sp3  (and make another atom sp2)",
                )
            )


# ---------------------------------------------------------------------- HMBC/COSY


def _proton_table(problem: Problem) -> list[tuple[float, int]]:
    """(proton shift, atom id) for every proton the solver knows, one per group."""
    table = []
    for atom in problem.atoms:
        if atom.copy_of is not None or atom.hydrogens == 0:
            continue
        for h in atom.h_shifts:
            table.append((h, atom.id))
    return table


def _match_proton(table: list[tuple[float, int]], h: float, tol: float) -> tuple[int | None, bool]:
    """The atom whose proton is nearest to ``h``, and whether another atom's is close too.

    A 2D peak lands anywhere within its proton's multiplet, so a second proton within
    the tolerance makes the attribution unreliable: on the benchmark data most strong
    HMBC correlations that contradicted the true structure were such cases.
    """
    near = sorted((abs(h - hs), aid) for hs, aid in table if abs(h - hs) <= tol)
    if not near:
        return None, False
    ids = {aid for _, aid in near}
    return near[0][1], len(ids) > 1


def _add_hmbc(problem: Problem, exp: Experiment) -> None:
    """HMBC correlations that survive the noise filters."""
    spectrum = _read_2d(exp)
    peaks = sp.peaks_2d(spectrum, snr_floor=5.0)
    c_tol = max(0.5, 1.5 * sp.resolution(spectrum.f1_ppm_scale), 0.75 * _acquired_f1(exp, spectrum))
    h_tol = 0.05
    protons = _proton_table(problem)
    carbons = problem.signals()

    def carbons_near(c: float) -> list[int]:
        return [a.id for a in carbons if a.shift is not None and abs(a.shift - c) <= c_tol]

    # t1 noise: per proton column, the level of peaks that hit no carbon.
    column_noise: dict[int, float] = {}
    by_column: dict[int, list[sp.Peak2DLite]] = {}
    for p in peaks:
        aid, _ = _match_proton(protons, p.h_shift, h_tol)
        if aid is None:
            continue
        by_column.setdefault(aid, []).append(p)
    for aid, col in by_column.items():
        off = [p.snr for p in col if not carbons_near(p.c_shift)]
        column_noise[aid] = float(np.percentile(off, HMBC_NOISE_PERCENTILE)) if off else 0.0

    best: dict[tuple[tuple[int, ...], int], sp.Peak2DLite] = {}
    notes: dict[tuple[tuple[int, ...], int], str] = {}
    for p in peaks:
        aid, ambiguous = _match_proton(protons, p.h_shift, h_tol)
        if aid is None:
            continue
        xs = carbons_near(p.c_shift)
        if not xs:
            continue
        own = set(problem.group_of(aid))
        xs = [x for x in xs if x not in own]
        if not xs:
            continue  # one-bond leakage onto the proton's own carbon
        if p.snr < max(5.0, HMBC_NOISE_FACTOR * column_noise.get(aid, 0.0)):
            continue
        group: list[int] = []
        for x in xs:
            group.extend(problem.group_of(x))
        key = (tuple(sorted(set(group))), aid)
        if key not in best or p.snr > best[key].snr:
            best[key] = p
            notes[key] = "proton overlaps another proton" if ambiguous else ""

    items = sorted(best.items(), key=lambda kv: -kv[1].snr)
    column_top: dict[int, float] = {}
    for (_, aid), p in items:
        column_top[aid] = max(column_top.get(aid, 0.0), p.snr)
    for n, ((xs_t, aid), p) in enumerate(items, start=1):
        xs_l = list(xs_t)
        reason = notes[(xs_t, aid)]
        if len(xs_l) > 4:
            reason = "more than four candidate carbons"
        elif p.snr < HMBC_WEAK * column_top[aid]:
            reason = "weak: below 5 % of the strongest peak of this proton"
        use = not reason
        problem.correlations.append(
            Correlation(
                id=f"B{n}",
                kind="HMBC",
                x=xs_l,
                y=aid,
                c_shift=round(p.c_shift, 2),
                h_shift=round(p.h_shift, 3),
                snr=round(p.snr, 1),
                use=use,
                reason=reason,
            )
        )
    _cap_correlations(problem)


def _add_cosy(problem: Problem, exp: Experiment) -> None:
    """COSY correlations between protons on different carbons (not used by default)."""
    spectrum = _read_2d(exp)
    peaks = sp.peaks_2d(spectrum, snr_floor=8.0)
    protons = _proton_table(problem)
    seen: dict[tuple[int, int], sp.Peak2DLite] = {}
    for p in peaks:
        a, amb_a = _match_proton(protons, p.c_shift, 0.03)
        b, amb_b = _match_proton(protons, p.h_shift, 0.03)
        if a is None or b is None or a == b or amb_a or amb_b:
            continue
        key = (min(a, b), max(a, b))
        if key not in seen or p.snr > seen[key].snr:
            seen[key] = p
    items = sorted(seen.items(), key=lambda kv: -kv[1].snr)
    for n, ((a, b), p) in enumerate(items, start=1):
        problem.correlations.append(
            Correlation(
                id=f"Y{n}",
                kind="COSY",
                x=[a],
                y=b,
                c_shift=round(p.c_shift, 3),
                h_shift=round(p.h_shift, 3),
                snr=round(p.snr, 1),
                use=False,
                reason="COSY is off by default",
            )
        )


def _cap_correlations(problem: Problem, limit: int = 100) -> None:
    """LSD accepts at most 100 HMBC plus COSY correlations; keep the strongest."""
    used = [c for c in problem.correlations if c.use]
    if len(used) <= limit:
        return
    for c in sorted(used, key=lambda c: -(c.snr or 0))[limit:]:
        c.use = False
        c.reason = "beyond the solver's limit of 100 correlations"
