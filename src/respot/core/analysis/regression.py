"""Linear, polynomial, and multiple linear regression."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy import stats

from .result import AnalysisResult, ParamRow, r_squared


def linear_fit(x: Sequence[float], y: Sequence[float]) -> AnalysisResult:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    result = AnalysisResult(kind="regression", title="Linear Regression")
    if x.size < 2:
        result.notes = "Need at least two points."
        return result

    slope, intercept, r, p, stderr = stats.linregress(x, y)
    y_fit = slope * x + intercept
    n = x.size
    result.parameters = [
        ParamRow("Slope", float(slope), float(stderr)),
        ParamRow("Intercept", float(intercept), None),
    ]
    result.summary = {
        "R": float(r), "R²": float(r * r), "Adj R²": 1 - (1 - r * r) * (n - 1) / (n - 2) if n > 2 else float("nan"),
        "Slope StdErr": float(stderr), "p-value": float(p), "N": float(n),
    }
    result.curves["Fit"] = (x, y_fit)
    result.notes = f"y = {slope:.6g}·x + {intercept:.6g}"
    return result


def polynomial_fit(x: Sequence[float], y: Sequence[float], degree: int = 2) -> AnalysisResult:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    result = AnalysisResult(kind="regression", title=f"Polynomial Regression (deg {degree})")
    if x.size <= degree:
        result.notes = "Not enough points for this degree."
        return result

    coeffs = np.polyfit(x, y, degree)
    poly = np.poly1d(coeffs)
    y_fit = poly(x)
    xs = np.linspace(x.min(), x.max(), 400)
    result.parameters = [
        ParamRow(f"c{degree - i}", float(c)) for i, c in enumerate(coeffs)
    ]
    result.summary = {
        "R²": r_squared(y, y_fit),
        "RMSE": float(np.sqrt(np.mean((y - y_fit) ** 2))),
        "Degree": float(degree),
        "N": float(x.size),
    }
    result.curves["Fit"] = (xs, poly(xs))
    result.notes = "y = " + " + ".join(f"{c:.6g}·x^{degree - i}" for i, c in enumerate(coeffs))
    return result


def multiple_regression(X: np.ndarray, y: Sequence[float], names: Sequence[str]) -> AnalysisResult:
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    names = list(names)
    result = AnalysisResult(kind="regression", title="Multiple Linear Regression")
    A = np.column_stack([np.ones(X.shape[0]), X])
    labels = ["Intercept", *names]

    coeffs, *_ = np.linalg.lstsq(A, y, rcond=None)
    y_fit = A @ coeffs
    n, k = A.shape
    residuals = y - y_fit
    dof = max(n - k, 1)
    sigma2 = float(np.sum(residuals ** 2) / dof)
    try:
        cov = sigma2 * np.linalg.inv(A.T @ A)
        errors = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        errors = np.full(k, np.nan)

    r2 = r_squared(y, y_fit)
    n_terms = X.shape[1]
    result.parameters = [ParamRow(lbl, float(c), float(e)) for lbl, c, e in zip(labels, coeffs, errors)]
    result.summary = {
        "R²": r2,
        "Adj R²": 1 - (1 - r2) * (n - 1) / dof,
        "RMSE": float(np.sqrt(np.mean(residuals ** 2))),
        "N": float(n), "Predictors": float(n_terms),
    }
    result.curves["Residuals"] = (y_fit, residuals)
    return result


__all__ = ["linear_fit", "polynomial_fit", "multiple_regression"]
