"""ailsa: AI-agent powered Computer-Assisted Structure Elucidation.

Public names are resolved lazily (PEP 562) so that ``import ailsa`` and the
CLI start without loading rdkit, scipy, nmrglue or numpy (REC-04).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from ailsa._version import __version__ as __version__

if TYPE_CHECKING:
    from ailsa.analysis import (
        HydrogenBudgetAnalyzer,
        IntensityReporter,
        SymmetryAnalyzer,
    )
    from ailsa.lsd import LSDInputGenerator, LSDProblem, LSDRunner
    from ailsa.models import (
        Peak1D,
        Peak2D,
        PeakList1D,
        PeakList2D,
        Spectrum1D,
        Spectrum2D,
    )
    from ailsa.nmrxiv import NMRXivClient
    from ailsa.prediction import C13Predictor, HOSECodeGenerator, HOSELookupTable
    from ailsa.processing import (
        AdaptivePeakPicker,
        DEPTGuidedPicker,
        DEPTGuidedResult,
        PeakPicker2D,
        PeakValidator,
        ValidationResult,
    )
    from ailsa.ranking import SolutionRanker
    from ailsa.readers import BrukerReader

_LAZY: dict[str, str] = {
    # Readers
    "BrukerReader": "ailsa.readers",
    # Models
    "Peak1D": "ailsa.models",
    "Peak2D": "ailsa.models",
    "PeakList1D": "ailsa.models",
    "PeakList2D": "ailsa.models",
    "Spectrum1D": "ailsa.models",
    "Spectrum2D": "ailsa.models",
    # Processing
    "AdaptivePeakPicker": "ailsa.processing",
    "DEPTGuidedPicker": "ailsa.processing",
    "DEPTGuidedResult": "ailsa.processing",
    "PeakPicker2D": "ailsa.processing",
    "PeakValidator": "ailsa.processing",
    "ValidationResult": "ailsa.processing",
    # Analysis
    "HydrogenBudgetAnalyzer": "ailsa.analysis",
    "IntensityReporter": "ailsa.analysis",
    "SymmetryAnalyzer": "ailsa.analysis",
    # Prediction
    "C13Predictor": "ailsa.prediction",
    "HOSECodeGenerator": "ailsa.prediction",
    "HOSELookupTable": "ailsa.prediction",
    # LSD
    "LSDInputGenerator": "ailsa.lsd",
    "LSDProblem": "ailsa.lsd",
    "LSDRunner": "ailsa.lsd",
    # Ranking
    "SolutionRanker": "ailsa.ranking",
    # NMRXiv
    "NMRXivClient": "ailsa.nmrxiv",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module 'ailsa' has no attribute {name!r}")
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
    # Readers
    "BrukerReader",
    # Models
    "Peak1D",
    "Peak2D",
    "PeakList1D",
    "PeakList2D",
    "Spectrum1D",
    "Spectrum2D",
    # Processing
    "AdaptivePeakPicker",
    "DEPTGuidedPicker",
    "DEPTGuidedResult",
    "PeakPicker2D",
    "PeakValidator",
    "ValidationResult",
    # Analysis
    "HydrogenBudgetAnalyzer",
    "IntensityReporter",
    "SymmetryAnalyzer",
    # Prediction
    "C13Predictor",
    "HOSECodeGenerator",
    "HOSELookupTable",
    # LSD
    "LSDInputGenerator",
    "LSDProblem",
    "LSDRunner",
    # Ranking
    "SolutionRanker",
    # NMRXiv
    "NMRXivClient",
]
