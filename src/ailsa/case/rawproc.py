"""Process raw Bruker data when a dataset has no processed spectrum.

Many deposited datasets contain the raw FID or SER of an experiment but no processed
spectrum (``pdata/1/1r`` or ``2rr``). The guided workflow only needs peak positions, so
the processing here aims at robust positions, not publication spectra:

- 1D: exponential line broadening, zero filling, Fourier transform, automatic phase
  correction. Signs survive (DEPT, APT), up to a global sign that the multiplicity
  logic calibrates from the data.
- 2D: squared sine bell in both dimensions, zero filling, and the magnitude of the
  hypercomplex spectrum, which needs no phase correction. Echo-antiecho, States and
  States-TPPI data are combined into a frequency-discriminated F1. Signs are lost, so an
  edited HSQC processed here counts as not edited.

The conventions were checked against datasets that carry both the raw and the
processed spectrum: peak positions agree to about one data point.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import nmrglue as ng  # type: ignore[import-untyped]
import numpy as np

from ailsa.models import Spectrum1D, Spectrum2D

FNMODE_ECHO_ANTIECHO = 6
FNMODE_STATES = (4, 5)


def has_raw(path: Path, two_d: bool) -> bool:
    """Whether the experiment folder holds raw data to process."""
    return (path / ("ser" if two_d else "fid")).is_file()


def _param(dic: dict[str, Any], block: str, key: str, default: Any = None) -> Any:
    try:
        return dic[block][key]
    except KeyError:
        return default


def process_1d(path: Path, signed: bool = False, line_broadening_hz: float = 1.0) -> Spectrum1D:
    """A real 1D spectrum from the FID in ``path``.

    With ``signed`` (DEPT, APT) a spectrum whose automatic phase correction failed is
    rejected, because its signs would mislead; otherwise the magnitude spectrum is used.
    """
    dic, data = ng.bruker.read(str(path))
    data = ng.bruker.remove_digital_filter(dic, data)
    sw = float(_param(dic, "acqus", "SW_h", 1.0))
    data = ng.proc_base.em(data, lb=line_broadening_hz / sw)
    size = 1 << int(np.ceil(np.log2(max(len(data), 2))) + 1)
    data = ng.proc_base.zf_size(data, min(size, 1 << 18))
    data = ng.proc_base.fft(data)
    data = data[::-1]
    magnitude = np.abs(data).astype(np.float64)
    try:
        phased = np.real(ng.proc_autophase.autops(data, "acme", disp=False))
    except Exception:  # autophase can fail on pure noise
        phased = None
    if phased is not None and phased.min() > -0.15 * phased.max():
        spectrum = phased.astype(np.float64)
    elif signed:
        raise ValueError("automatic phase correction failed; the signs would be unreliable")
    else:
        # The phase correction failed (typically a dominant solvent line); positions
        # are still exact in the magnitude spectrum.
        spectrum = magnitude
    spectrum -= float(np.median(spectrum))
    udic = ng.bruker.guess_udic(dic, spectrum)
    ppm = ng.fileiobase.uc_from_udic(udic).ppm_scale()
    nucleus = str(_param(dic, "acqus", "NUC1", "13C")).strip("<>")
    solvent = _param(dic, "acqus", "SOLVENT")
    return Spectrum1D(
        data=spectrum,
        ppm_scale=np.asarray(ppm, dtype=np.float64),
        nucleus=nucleus,
        frequency=float(_param(dic, "acqus", "SFO1", 0.0)),
        solvent=str(solvent).strip("<>") if solvent else None,
        metadata={"processed_by": "ailsa case (raw FID)"},
    )


def _f1(x: np.ndarray[Any, Any], size: int) -> np.ndarray[Any, Any]:
    x = ng.proc_base.sp(x.T, off=0.5, end=1.0, pow=2)
    x = ng.proc_base.zf_size(x, size)
    return np.asarray(ng.proc_base.fft(x).T)


def process_2d(
    path: Path, experiment_type: str, size: tuple[int, int] = (1024, 2048)
) -> Spectrum2D:
    """A magnitude 2D spectrum from the SER in ``path``."""
    dic, data = ng.bruker.read(str(path))
    data = ng.bruker.remove_digital_filter(dic, data)
    fnmode = int(_param(dic, "acqu2s", "FnMODE", 0) or 0)
    data = ng.proc_base.sp(data, off=0.5, end=1.0, pow=2)
    data = ng.proc_base.zf_size(data, size[1])
    data = ng.proc_base.fft(data)[:, ::-1]
    if fnmode == FNMODE_ECHO_ANTIECHO:
        echo, antiecho = data[::2], data[1::2]
        real, imag = echo + antiecho, -1j * (echo - antiecho)
    elif fnmode in FNMODE_STATES:
        real, imag = data[::2], data[1::2]
    else:
        real, imag = data, None
    if imag is None:
        magnitude = np.abs(_f1(real, size[0]))
    else:
        magnitude = np.sqrt(
            np.abs(_f1(real.real + 1j * imag.real, size[0])) ** 2
            + np.abs(_f1(real.imag + 1j * imag.imag, size[0])) ** 2
        )
    magnitude = magnitude.astype(np.float64)
    udic = ng.bruker.guess_udic(dic, magnitude)
    f1 = ng.fileiobase.uc_from_udic(udic, 0).ppm_scale()
    f2 = ng.fileiobase.uc_from_udic(udic, 1).ppm_scale()
    return Spectrum2D(
        data=magnitude,
        f1_ppm_scale=np.asarray(f1, dtype=np.float64),
        f2_ppm_scale=np.asarray(f2, dtype=np.float64),
        f1_nucleus=str(_param(dic, "acqu2s", "NUC1", "13C")).strip("<>"),
        f2_nucleus=str(_param(dic, "acqus", "NUC1", "1H")).strip("<>"),
        experiment_type=experiment_type,
        frequency=float(_param(dic, "acqus", "SFO1", 0.0)),
        metadata={"processed_by": "ailsa case (raw SER, magnitude)"},
    )
