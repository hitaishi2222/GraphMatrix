"""Peak finding and characterisation."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy.signal import find_peaks, peak_widths

from .result import AnalysisResult


def find_peaks_result(
    x: Sequence[float],
    y: Sequence[float],
    *,
    height: float | None = None,
    prominence: float | None = None,
    distance: float | None = None,
    width: float | None = None,
) -> AnalysisResult:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    result = AnalysisResult(kind="peaks", title="Peak Analysis")

    indices, props = find_peaks(
        y, height=height, prominence=prominence, distance=distance, width=width
    )
    if indices.size == 0:
        result.notes = "No peaks found with the given criteria."
        return result

    widths, _, left_ips, right_ips = peak_widths(y, indices, rel_height=0.5)
    if x.size > 1 and x.max() != x.min():
        scale = (x.max() - x.min()) / (x.size - 1)
        fwhm = widths * scale
    else:
        fwhm = widths

    heights = y[indices]
    prominences = props.get("prominences", np.full(indices.size, np.nan))

    table = [["#", "X", "Y", "Height", "Prominence", "FWHM"]]
    for i, idx in enumerate(indices):
        table.append([
            str(i + 1), f"{x[idx]:.6g}", f"{y[idx]:.6g}",
            f"{heights[i]:.6g}", f"{prominences[i]:.6g}", f"{fwhm[i]:.6g}",
        ])
    result.tables["Peaks"] = table
    result.summary = {
        "Peaks": float(indices.size),
        "Max height": float(np.max(heights)),
        "Mean FWHM": float(np.mean(fwhm)),
    }
    result.curves["Peaks"] = (x[indices], heights)
    return result


__all__ = ["find_peaks_result"]
