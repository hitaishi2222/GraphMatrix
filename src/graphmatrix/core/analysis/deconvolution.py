"""Peak deconvolution: fit a sum of overlapping peaks.

Given approximate peak centres (from ``peaks.find_peaks`` or the user), fit a
composite model of N Gaussian or Lorentzian peaks plus a constant baseline. This is
the "fit a multi-peak spectrum" workflow from the M3 acceptance criteria.

Implemented with ``scipy.optimize.curve_fit`` because the free-parameter vector grows
with the number of peaks — awkward to express as a fixed lmfit model signature.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .result import AnalysisResult, ParamRow, r_squared

_KINDS = ("gaussian", "lorentzian")

_AREA_FACTOR = {"gaussian": np.sqrt(2 * np.pi), "lorentzian": np.pi}


def _peak(x, kind: str, amplitude: float, center: float, width: float) -> np.ndarray:
    if kind == "lorentzian":
        return amplitude * width**2 / ((x - center) ** 2 + width**2)
    return amplitude * np.exp(-((x - center) ** 2) / (2 * width**2))


def deconvolve(
    x: Sequence[float],
    y: Sequence[float],
    centers: Sequence[float],
    *,
    kind: str = "gaussian",
    baseline: bool = True,
    width_guess: float | None = None,
) -> AnalysisResult:
    """Fit overlapping peaks at the given approximate ``centers``."""
    from scipy.optimize import curve_fit

    kind = kind.lower()
    n_peaks = len(centers)
    result = AnalysisResult(
        kind="deconvolution", title=f"Peak Deconvolution — {n_peaks}× {kind.title()}"
    )
    if kind not in _KINDS:
        result.notes = f"Unknown peak kind {kind!r}. Known: {', '.join(_KINDS)}"
        return result

    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    centers = [float(c) for c in centers]
    if n_peaks < 1:
        result.notes = "Provide at least one approximate peak centre."
        return result
    if x.size < 3 * n_peaks + (1 if baseline else 0) + 1:
        result.notes = "Not enough data points for the requested number of peaks."
        return result

    spacing = (
        float(np.min(np.diff(sorted(centers))))
        if n_peaks > 1
        else (x.max() - x.min()) / 6.0
    )
    default_width = width_guess or max(spacing / 2.5, (x.max() - x.min()) / 100.0)
    y_min = float(np.min(y))

    def model(xx, *p):
        total = np.zeros_like(np.asarray(xx, dtype=float))
        for index in range(n_peaks):
            total = total + _peak(
                xx, kind, p[3 * index], p[3 * index + 1], p[3 * index + 2]
            )
        if baseline:
            total = total + p[3 * n_peaks]
        return total

    p0: list[float] = []
    lower: list[float] = []
    upper: list[float] = []
    for center in centers:
        idx = int(np.argmin(np.abs(x - center)))
        p0 += [max(y[idx] - y_min, 1e-6), center, default_width]
        lower += [-np.inf, -np.inf, 1e-9]
        upper += [np.inf, np.inf, np.inf]
    if baseline:
        p0.append(y_min)
        lower.append(-np.inf)
        upper.append(np.inf)

    try:
        popt, pcov = curve_fit(model, x, y, p0=p0, bounds=(lower, upper), maxfev=20000)
    except Exception as exc:  # noqa: BLE001 - surface fit failures
        result.notes = f"Fit failed: {exc}"
        return result

    perr = (
        np.sqrt(np.abs(np.diag(pcov))) if pcov is not None else np.full(len(p0), np.nan)
    )
    y_fit = model(x, *popt)

    rows: list[ParamRow] = []
    xs = np.linspace(x.min(), x.max(), 400)
    area_factor = _AREA_FACTOR[kind]
    for index in range(n_peaks):
        amp, ctr, wid = (
            float(popt[3 * index]),
            float(popt[3 * index + 1]),
            float(popt[3 * index + 2]),
        )
        rows.append(
            ParamRow(f"Peak {index + 1} amplitude", amp, float(perr[3 * index]))
        )
        rows.append(
            ParamRow(f"Peak {index + 1} center", ctr, float(perr[3 * index + 1]))
        )
        rows.append(
            ParamRow(f"Peak {index + 1} width", wid, float(perr[3 * index + 2]))
        )
        rows.append(ParamRow(f"Peak {index + 1} area", amp * area_factor * wid))
        result.curves[f"Peak {index + 1}"] = (xs, _peak(xs, kind, amp, ctr, wid))
    if baseline:
        rows.append(
            ParamRow("Baseline", float(popt[3 * n_peaks]), float(perr[3 * n_peaks]))
        )

    result.parameters = rows
    result.summary = {
        "Peaks": float(n_peaks),
        "R²": float(r_squared(y, y_fit)),
        "RMSE": float(np.sqrt(np.nanmean((y - y_fit) ** 2))),
        "N": float(x.size),
    }
    result.curves["Composite"] = (xs, model(xs, *popt))
    result.curves["Residuals"] = (x, y - y_fit)
    result.notes = f"Deconvolved {n_peaks} {kind} peaks." + (
        " Baseline included." if baseline else " No baseline."
    )
    return result


def deconvolve_auto(
    x: Sequence[float],
    y: Sequence[float],
    *,
    max_peaks: int = 4,
    kind: str = "gaussian",
) -> AnalysisResult:
    """Detect peaks, then deconvolve the most prominent ``max_peaks`` of them."""
    from . import peaks as peaks_module

    found = peaks_module.find_peaks_result(x, y)
    table = found.tables.get("Peaks", [])
    centers: list[float] = []
    for row in table:
        if len(row) >= 2:
            try:
                centers.append(float(row[1]))
            except ValueError:
                continue  # header row
    centers = centers[:max_peaks]
    if not centers:
        result = AnalysisResult(kind="deconvolution", title="Peak Deconvolution")
        result.notes = "No peaks were detected to deconvolve."
        return result
    return deconvolve(x, y, centers, kind=kind)


__all__ = ["KINDS", "deconvolve", "deconvolve_auto"]
KINDS = list(_KINDS)
