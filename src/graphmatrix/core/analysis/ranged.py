"""Range-scoped analysis: fit within an X window.

The first member is :func:`slope_between`, the "measure the slope here" tool. It is
deliberately a *core* function rather than a canvas gesture so the same numbers drive
the dialog, a script line, and a future drag-to-fit interaction.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .result import AnalysisResult, r_squared


def _clean(x: Sequence[float], y: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def slope_between(
    x: Sequence[float],
    y: Sequence[float],
    x0: float | None = None,
    x1: float | None = None,
) -> AnalysisResult:
    """Linear fit of ``y`` against ``x`` restricted to ``x0 <= x <= x1``.

    ``x0``/``x1`` may be ``None`` to leave that end open. The fit reports slope,
    intercept, R², the standard error of the slope, and the raw Δy/Δx across the
    window, so it can back both "what is the gradient here?" and "what changed?".
    """
    result = AnalysisResult(kind="slope", title="Slope over X range")
    x, y = _clean(x, y)
    if x.size < 2:
        result.notes = "Not enough finite points to fit."
        return result

    if x0 is not None or x1 is not None:
        if x0 is not None and x1 is not None and x0 > x1:
            x0, x1 = x1, x0
        low = -np.inf if x0 is None else x0
        high = np.inf if x1 is None else x1
        mask = (x >= low) & (x <= high)
        xs, ys = x[mask], y[mask]
    else:
        xs, ys = x, y

    if xs.size < 2:
        result.notes = "The selected X range contains fewer than two points."
        return result

    slope, intercept = np.polyfit(xs, ys, 1)
    fit = slope * xs + intercept
    n = int(xs.size)
    r2 = r_squared(ys, fit)

    # Standard error of the slope, when the fit has enough residual freedom.
    if n > 2:
        residuals = ys - fit
        dof = n - 2
        sxx = float(np.sum((xs - xs.mean()) ** 2))
        slope_err = (
            float(np.sqrt(np.sum(residuals**2) / dof / sxx))
            if sxx > 0
            else float("nan")
        )
    else:
        slope_err = float("nan")

    x_lo, x_hi = float(xs.min()), float(xs.max())
    dy = float(ys[-1] - ys[0]) if np.all(np.diff(xs) >= 0) else float("nan")

    order = np.argsort(xs)
    line_x = xs[order]
    line_y = fit[order]
    result.curves["Fit"] = (line_x, line_y)
    result.summary = {
        "Slope": float(slope),
        "Intercept": float(intercept),
        "R²": float(r2),
        "Slope std err": slope_err,
        "N points": float(n),
        "X min": x_lo,
        "X max": x_hi,
    }
    if np.isfinite(dy):
        result.summary["Δy"] = dy
        result.summary["Δx"] = float(xs[-1] - xs[0])
    return result


__all__ = ["slope_between"]
