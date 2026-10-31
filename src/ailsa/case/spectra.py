"""Peak lists that can be trusted: cleanup of raw picks from 1D and 2D spectra.

The raw pickers report every local maximum above the noise floor. For a solver input
that is too much: solvent multiplets, truncation wiggles beside strong lines, proton
multiplets split into several 2D peaks, and t1-noise streaks in the HMBC. The
functions here remove that systematically, so that no agent has to curate peak lists
by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ailsa.models import Spectrum1D, Spectrum2D
from ailsa.processing.peak_picker import AdaptivePeakPicker
from ailsa.processing.peak_picker_2d import PeakPicker2D

# Residual solvent signals: 13C multiplet windows (ppm) and the C-H residual (13C, 1H).
# Windows cover the deuterium multiplet at 100-150 MHz plus a small margin.
SOLVENTS: dict[str, dict[str, list[tuple[float, float]]]] = {
    "cdcl3": {"c": [(76.6, 77.7)], "ch": [(77.16, 7.26)]},
    "dmso": {"c": [(38.8, 40.3)], "ch": [(39.52, 2.50)]},
    "cd3od": {"c": [(48.3, 49.7)], "ch": [(49.00, 3.31)]},
    "acetone": {"c": [(29.2, 30.5), (205.8, 206.7)], "ch": [(29.84, 2.05)]},
    "c6d6": {"c": [(127.7, 128.4)], "ch": [(128.06, 7.16)]},
    "cd2cl2": {"c": [(53.3, 54.4)], "ch": [(53.84, 5.32)]},
    "cd3cn": {"c": [(0.6, 2.0), (117.8, 118.7)], "ch": [(1.32, 1.94)]},
    "thf": {"c": [(24.9, 25.8), (66.8, 67.9)], "ch": [(25.31, 1.72), (67.21, 3.58)]},
    "pyridine": {
        "c": [(123.2, 124.0), (135.2, 136.0), (149.5, 150.3)],
        "ch": [(123.5, 7.22), (135.5, 7.58), (149.9, 8.74)],
    },
}

_SOLVENT_ALIASES = {
    "chloroform": "cdcl3",
    "dmso-d6": "dmso",
    "dmsod6": "dmso",
    "meod": "cd3od",
    "methanol": "cd3od",
    "acetone-d6": "acetone",
    "acetoned6": "acetone",
    "benzene": "c6d6",
    "thf-d8": "thf",
    "pyr": "pyridine",
}


def solvent_key(solvent: str | None) -> str | None:
    """Normalised key into :data:`SOLVENTS`, or ``None`` if the solvent is unknown."""
    if not solvent:
        return None
    key = solvent.strip().lower().replace("_", "-")
    key = _SOLVENT_ALIASES.get(key, key)
    if key in SOLVENTS:
        return key
    for name in SOLVENTS:
        if key.startswith(name):
            return name
    return None


@dataclass
class Line:
    """A 1D peak after cleanup."""

    shift: float
    intensity: float
    snr: float

    @property
    def sign(self) -> int:
        return 1 if self.intensity >= 0 else -1


@dataclass
class Cluster:
    """One 2D cross-peak: the peaks of one proton multiplet at one carbon."""

    c_shift: float
    h_shift: float
    intensity: float
    peak_max: float
    sign: int
    n_peaks: int
    mixed: bool = False


@dataclass
class Peak2DLite:
    """A 2D peak position with its signal-to-noise ratio."""

    c_shift: float
    h_shift: float
    intensity: float
    snr: float


@dataclass
class CarbonLines:
    """Cleaned carbon lines and what was removed, for the report."""

    lines: list[Line]
    removed_solvent: list[Line] = field(default_factory=list)
    removed_satellites: list[Line] = field(default_factory=list)


def _in_windows(shift: float, windows: list[tuple[float, float]]) -> bool:
    return any(lo <= shift <= hi for lo, hi in windows)


def pick_lines(spectrum: Spectrum1D, signed: bool) -> list[Line]:
    """All lines above the default signal-to-noise floor."""
    peaks = AdaptivePeakPicker.pick_peaks(spectrum, detect_negative=signed, snr_floor=5.0)
    return [
        Line(shift=p.position, intensity=p.intensity, snr=float(p.snr or 0.0)) for p in peaks.peaks
    ]


def drop_satellites(lines: list[Line]) -> tuple[list[Line], list[Line]]:
    """Remove weak lines that sit beside a much stronger one.

    Truncation wiggles and line-shape artefacts appear within a few tenths of a ppm of
    an intense line at a few per cent of its height. Two tiers: within 0.05 ppm (inside
    the line itself) a line five times weaker goes; within 0.35 ppm a line fifteen
    times weaker goes. Real neighbouring carbons are rarely that much weaker at that
    distance; a quaternary carbon beside a protonated one is typically 3-10 times
    weaker and is kept.
    """
    kept: list[Line] = []
    dropped: list[Line] = []
    for line in lines:
        satellite = any(
            o is not line
            and (
                (abs(o.shift - line.shift) <= 0.05 and o.snr >= 5.0 * line.snr)
                or (abs(o.shift - line.shift) <= 0.35 and o.snr >= 15.0 * line.snr)
            )
            for o in lines
        )
        (dropped if satellite else kept).append(line)
    return kept, dropped


# Expected centre (ppm) and number of lines of deuterated-solvent 13C multiplets.
_SOLVENT_MULTIPLETS: dict[str, list[tuple[float, int]]] = {
    "cdcl3": [(77.16, 3)],
    "dmso": [(39.52, 7)],
    "cd3od": [(49.00, 7)],
    "acetone": [(29.84, 7)],
    "c6d6": [(128.06, 3)],
    "cd2cl2": [(53.84, 5)],
    "cd3cn": [(1.32, 7)],
    "thf": [(25.31, 5), (67.21, 3)],
}


def find_solvent_multiplets(lines: list[Line]) -> tuple[list[Line], str | None, float]:
    """Lines that form a deuterated-solvent multiplet, its solvent, and its offset.

    Detected from the data, not from the acquisition parameters, which are sometimes
    wrong. A multiplet is at least three lines within 2.5 ppm of the expected centre
    (spectra are not always referenced to the solvent), with a regular spacing of
    0.15-0.45 ppm (the C-D coupling at 75-175 MHz) and no line weaker than a tenth of
    the strongest. The offset is the measured centre minus the expected one; it also
    locates the solvent's residual C-H cross-peak in the HSQC.
    """
    best: list[Line] = []
    best_name: str | None = None
    best_offset = 0.0
    for name, patterns in _SOLVENT_MULTIPLETS.items():
        found: list[Line] = []
        offsets: list[float] = []
        for centre, n_lines in patterns:
            near = sorted(
                (ln for ln in lines if abs(ln.shift - centre) <= 2.5), key=lambda ln: ln.shift
            )
            run = _regular_run(near, min_lines=min(3, n_lines))
            if run:
                found.extend(run)
                offsets.append(float(np.mean([ln.shift for ln in run])) - centre)
        if len(found) > len(best):
            best, best_name = found, name
            best_offset = offsets[0] if offsets else 0.0
    return best, best_name, best_offset


def _regular_run(lines: list[Line], min_lines: int) -> list[Line]:
    """The longest run of comparable lines with a near-constant spacing."""
    best: list[Line] = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            step = lines[j].shift - lines[i].shift
            if not 0.15 <= step <= 0.45:
                continue
            run = [lines[i], lines[j]]
            while True:
                target = run[-1].shift + step
                nxt = [ln for ln in lines if abs(ln.shift - target) <= 0.05]
                if not nxt:
                    break
                run.append(max(nxt, key=lambda ln: ln.snr))
            top = max(ln.snr for ln in run)
            if all(ln.snr >= 0.1 * top for ln in run) and len(run) > len(best):
                best = run
    return best if len(best) >= min_lines else []


def carbon_lines(spectrum: Spectrum1D, solvent: str | None, signed: bool = False) -> CarbonLines:
    """Clean carbon lines of a 13C (or APT) spectrum.

    In order: line-shape satellites; a deuterated-solvent multiplet found in the data,
    plus anything left in the labelled solvent's window; a reference signal near
    0 ppm and lines outside the carbon range; lines weaker than 4 % of the median of
    the stronger half, which no carbon of the molecule is.
    """
    lines = pick_lines(spectrum, signed=signed)
    lines, satellites = drop_satellites(lines)
    solvent_lines, detected, offset = find_solvent_multiplets(lines)
    windows: list[tuple[float, float]] = []
    labelled = solvent_key(solvent)
    if labelled and labelled != detected:
        windows.extend(SOLVENTS[labelled]["c"])
    if detected:
        windows.extend((lo + offset, hi + offset) for lo, hi in SOLVENTS[detected]["c"])
    solvent_lines += [
        ln for ln in lines if _in_windows(ln.shift, windows) and ln not in solvent_lines
    ]
    lines = [ln for ln in lines if ln not in solvent_lines]
    kept = [ln for ln in lines if -5.0 < ln.shift < 235.0 and abs(ln.shift) > 1.0]
    if kept:
        strong = sorted((ln.snr for ln in kept), reverse=True)[: max(1, len(kept) // 2)]
        floor = 0.04 * float(np.median(strong))
        satellites.extend(ln for ln in kept if ln.snr < floor)
        kept = [ln for ln in kept if ln.snr >= floor]
    kept.sort(key=lambda ln: -ln.shift)
    return CarbonLines(lines=kept, removed_solvent=solvent_lines, removed_satellites=satellites)


def detected_solvent(spectrum: Spectrum1D, signed: bool = False) -> tuple[str | None, float]:
    """The deuterated solvent whose 13C multiplet is in the spectrum, and its offset."""
    lines, _ = drop_satellites(pick_lines(spectrum, signed=signed))
    _, name, offset = find_solvent_multiplets(lines)
    return name, offset


def match_lines(
    reference: list[float], lines: list[Line], tolerance: float = 0.25
) -> dict[int, Line]:
    """Map reference shifts (by index) to the nearest line within ``tolerance``.

    Each line is used at most once, nearest pairs first.
    """
    pairs = sorted(
        (abs(r - ln.shift), i, j)
        for i, r in enumerate(reference)
        for j, ln in enumerate(lines)
        if abs(r - ln.shift) <= tolerance
    )
    used_ref: set[int] = set()
    used_line: set[int] = set()
    result: dict[int, Line] = {}
    for _, i, j in pairs:
        if i in used_ref or j in used_line:
            continue
        used_ref.add(i)
        used_line.add(j)
        result[i] = lines[j]
    return result


def resolution(scale: NDArray[np.float64]) -> float:
    """Digital resolution of an axis in ppm per point."""
    if len(scale) < 2:
        return 1.0
    return float(abs(scale[-1] - scale[0]) / (len(scale) - 1))


def local_maxima_2d(
    spectrum: Spectrum2D, threshold: float, signed: bool
) -> list[tuple[float, float, float]]:
    """(F1 ppm, F2 ppm, intensity) of every local maximum of ``|data|`` above ``threshold``.

    Unlike a connected-region picker, neighbouring cross-peaks stay separate however
    low the threshold: a point is reported when it is the largest in its 3 x 3
    neighbourhood. Negative maxima are reported only when ``signed``.
    """
    from scipy.ndimage import maximum_filter  # type: ignore[import-untyped]

    data = spectrum.data
    magnitude = np.abs(data) if signed else np.where(data > 0, data, 0.0)
    peaks = (magnitude == maximum_filter(magnitude, size=3)) & (magnitude >= threshold)
    rows, cols = np.nonzero(peaks)
    f1 = spectrum.f1_ppm_scale
    f2 = spectrum.f2_ppm_scale
    return [
        (float(f1[r]), float(f2[c]), float(data[r, c])) for r, c in zip(rows, cols, strict=True)
    ]


def hsqc_clusters(spectrum: Spectrum2D, signed: bool, threshold: float = 0.01) -> list[Cluster]:
    """Cross-peaks of an HSQC, one per proton multiplet and carbon.

    Local maxima above ``threshold`` times the largest value are grouped: the lines of
    a proton multiplet appear as several maxima at the same carbon. Maxima within the
    multiplet width (0.06 ppm) and a carbon distance of 1.5 points (at least 0.3 ppm)
    are merged, whatever their sign: phase errors in an edited HSQC put lobes of both
    signs into one cross-peak. The cluster takes the sign of its strongest member and
    is marked ``mixed`` when the other sign carries more than a third of the intensity.
    Positions are intensity-weighted means.
    """
    data = spectrum.data
    items = local_maxima_2d(spectrum, threshold * float(np.max(np.abs(data))), signed)
    c_link = max(0.3, 1.5 * resolution(spectrum.f1_ppm_scale))
    h_link = 0.06
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = sorted(range(len(items)), key=lambda i: items[i][1])
    for a, i in enumerate(order):
        for j in order[a + 1 :]:
            if items[j][1] - items[i][1] > h_link:
                break
            if abs(items[i][0] - items[j][0]) <= c_link:
                parent[find(i)] = find(j)

    groups: dict[int, list[tuple[float, float, float]]] = {}
    for i, item in enumerate(items):
        groups.setdefault(find(i), []).append(item)

    clusters: list[Cluster] = []
    for members in groups.values():
        weights = np.array([abs(m[2]) for m in members])
        c = float(np.average([m[0] for m in members], weights=weights))
        h = float(np.average([m[1] for m in members], weights=weights))
        strongest = max(members, key=lambda m: abs(m[2]))
        sign = 1 if strongest[2] > 0 else -1
        other = sum(abs(m[2]) for m in members if (m[2] > 0) != (sign > 0))
        clusters.append(
            Cluster(
                c_shift=c,
                h_shift=h,
                intensity=float(weights.sum()),
                peak_max=float(weights.max()),
                sign=sign,
                n_peaks=len(members),
                mixed=other > float(weights.sum()) / 3,
            )
        )
    clusters.sort(key=lambda cl: (-cl.c_shift, -cl.h_shift))
    return clusters


def drop_column_artifacts(
    clusters: list[Cluster], h_window: float = 0.04, ratio: float = 10.0
) -> tuple[list[Cluster], list[Cluster]]:
    """Remove cross-peaks that are t1-noise or phase artefacts of a stronger one.

    Such artefacts appear in the proton column of an intense cross-peak at other carbon
    positions, at a few per cent of its height. A real second carbon carrying a proton
    at the same shift is rarely ten times weaker.
    """
    kept: list[Cluster] = []
    dropped: list[Cluster] = []
    for cl in clusters:
        artefact = any(
            o is not cl
            and abs(o.h_shift - cl.h_shift) <= h_window
            and o.peak_max >= ratio * cl.peak_max
            for o in clusters
        )
        (dropped if artefact else kept).append(cl)
    return kept, dropped


def is_solvent_ch(
    c_shift: float, h_shift: float, solvent: str | None, c_offset: float = 0.0
) -> bool:
    """Whether a C-H cross-peak is the residual signal of the solvent.

    ``c_offset`` is the solvent's measured 13C offset (see :func:`find_solvent_multiplets`).
    """
    key = solvent_key(solvent)
    if key is None:
        return False
    return any(
        abs(c_shift - (c + c_offset)) <= 0.8 and abs(h_shift - h) <= 0.04
        for c, h in SOLVENTS[key]["ch"]
    )


def peaks_2d(spectrum: Spectrum2D, snr_floor: float = 5.0) -> list[Peak2DLite]:
    """All positive 2D peaks above the noise floor, with their SNR."""
    peaks = PeakPicker2D.pick_peaks(spectrum, snr_floor=snr_floor, use_snr=True)
    return [
        Peak2DLite(
            c_shift=p.f1_position,
            h_shift=p.f2_position,
            intensity=p.intensity,
            snr=float(p.snr or 0.0),
        )
        for p in peaks.peaks
    ]
