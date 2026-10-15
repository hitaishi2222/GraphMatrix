"""Numerical analysis toolkit.

Every routine returns an :class:`AnalysisResult` (see ``result.py``). Grouped by
domain:

- ``descriptive`` — summary statistics
- ``regression`` — linear / polynomial / multiple linear
- ``fitting`` — nonlinear curve fitting (lmfit)
- ``peaks`` — peak finding and characterisation
- ``signal`` — FFT, smoothing, filters, calculus, interpolation, baseline
- ``statistics`` — t-tests, ANOVA, correlation, histogram
"""

from .result import AnalysisResult, ParamRow, r_squared

__all__ = ["AnalysisResult", "ParamRow", "r_squared"]
