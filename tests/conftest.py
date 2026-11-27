"""Pytest fixtures for ailsa tests."""


import numpy as np
import pytest

from ailsa.models import Peak1D, Peak2D, PeakList1D, PeakList2D, Spectrum1D, Spectrum2D


@pytest.fixture
def sample_1d_data() -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic 1D spectrum data.

    Returns a tuple of (intensity_data, ppm_scale) representing
    a simple 1H spectrum with a few peaks.
    """
    # Create ppm scale from 12 to 0 (typical 1H range)
    ppm_scale = np.linspace(12.0, 0.0, 4096)

    # Create intensity data with some Lorentzian peaks
    data = np.zeros(4096)

    # Add peaks at typical chemical shifts
    peak_positions = [7.2, 3.8, 1.2]  # aromatic, OCH3, CH3
    for pos in peak_positions:
        idx = int((12.0 - pos) / 12.0 * 4096)
        # Simple Lorentzian-like shape
        for i in range(max(0, idx - 50), min(4096, idx + 50)):
            data[i] += 1000 / (1 + ((i - idx) / 5) ** 2)

    return data, ppm_scale


@pytest.fixture
def sample_2d_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic 2D HSQC spectrum data.

    Returns a tuple of (intensity_data, f1_ppm_scale, f2_ppm_scale).
    """
    # F1 (13C): 200 to 0 ppm
    f1_ppm_scale = np.linspace(200.0, 0.0, 256)
    # F2 (1H): 12 to 0 ppm
    f2_ppm_scale = np.linspace(12.0, 0.0, 1024)

    # Create 2D data matrix
    data = np.zeros((256, 1024))

    # Add correlation peaks (f1_ppm, f2_ppm)
    correlations = [
        (125.0, 7.2),  # aromatic CH
        (55.0, 3.8),  # OCH3
        (20.0, 1.2),  # CH3
    ]

    for f1_pos, f2_pos in correlations:
        f1_idx = int((200.0 - f1_pos) / 200.0 * 256)
        f2_idx = int((12.0 - f2_pos) / 12.0 * 1024)
        # Add 2D peak
        for i in range(max(0, f1_idx - 5), min(256, f1_idx + 5)):
            for j in range(max(0, f2_idx - 10), min(1024, f2_idx + 10)):
                dist_sq = ((i - f1_idx) / 2) ** 2 + ((j - f2_idx) / 5) ** 2
                data[i, j] += 1000 / (1 + dist_sq)

    return data, f1_ppm_scale, f2_ppm_scale


@pytest.fixture
def sample_spectrum_1d(sample_1d_data: tuple[np.ndarray, np.ndarray]) -> Spectrum1D:
    """Create a Spectrum1D instance with test data."""
    data, ppm_scale = sample_1d_data
    return Spectrum1D(
        data=data,
        ppm_scale=ppm_scale,
        nucleus="1H",
        frequency=600.0,
        solvent="CDCl3",
        metadata={"experiment": "zg30", "ns": 16},
    )


@pytest.fixture
def sample_spectrum_2d(
    sample_2d_data: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> Spectrum2D:
    """Create a Spectrum2D instance with test data."""
    data, f1_ppm_scale, f2_ppm_scale = sample_2d_data
    return Spectrum2D(
        data=data,
        f1_ppm_scale=f1_ppm_scale,
        f2_ppm_scale=f2_ppm_scale,
        f1_nucleus="13C",
        f2_nucleus="1H",
        experiment_type="HSQC",
        frequency=600.0,
        metadata={"experiment": "hsqcedetgp", "ns": 4},
    )


@pytest.fixture
def sample_peak_1d() -> Peak1D:
    """Create a sample 1D peak."""
    return Peak1D(
        position=7.26,
        intensity=1000.0,
        assignment="H-1",
        multiplicity="s",
    )


@pytest.fixture
def sample_peak_2d() -> Peak2D:
    """Create a sample 2D peak."""
    return Peak2D(
        f1_position=125.0,
        f2_position=7.26,
        intensity=1000.0,
        f1_assignment="C-1",
        f2_assignment="H-1",
    )


@pytest.fixture
def sample_peak_list_1d() -> PeakList1D:
    """Create a sample 1D peak list."""
    peaks = [
        Peak1D(position=7.26, intensity=1000.0, multiplicity="s"),
        Peak1D(position=3.85, intensity=800.0, multiplicity="s"),
        Peak1D(position=1.25, intensity=1200.0, multiplicity="t"),
    ]
    return PeakList1D(peaks=peaks, nucleus="1H", spectrum_id="test_1h")


@pytest.fixture
def sample_peak_list_2d() -> PeakList2D:
    """Create a sample 2D peak list."""
    peaks = [
        Peak2D(f1_position=125.0, f2_position=7.26, intensity=1000.0),
        Peak2D(f1_position=55.0, f2_position=3.85, intensity=800.0),
        Peak2D(f1_position=20.0, f2_position=1.25, intensity=1200.0),
    ]
    return PeakList2D(
        peaks=peaks,
        f1_nucleus="13C",
        f2_nucleus="1H",
        experiment_type="HSQC",
        spectrum_id="test_hsqc",
    )
