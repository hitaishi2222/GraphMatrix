"""Peak finding, characterisation, and integration."""

from __future__ import annotations

from collections.abc import Sequence

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
    integrate: bool = False,
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
    if integrate:
        # Re-find with a trivial threshold so the base arrays
        # (left_bases/right_bases) are always populated: bases are the valleys
        # the peak rises out of and define the integration bounds.
        _indices, props = find_peaks(
            y,
            height=height,
            prominence=0.0 if prominence is None else prominence,
            distance=distance,
            width=width,
        )
        if _indices.size:
            indices = _indices

    widths, _, _left_ips, _right_ips = peak_widths(y, indices, rel_height=0.5)
    if x.size > 1 and x.max() != x.min():
        scale = (x.max() - x.min()) / (x.size - 1)
        fwhm = widths * scale
    else:
        fwhm = widths

    heights = y[indices]
    prominences = props.get("prominences", np.full(indices.size, np.nan))

    header = ["#", "X", "Y", "Height", "Prominence", "FWHM"]
    if integrate:
        header.append("Area")
    table = [header]

    for i, idx in enumerate(indices):
        row = [
            str(i + 1),
            f"{x[idx]:.6g}",
            f"{y[idx]:.6g}",
            f"{heights[i]:.6g}",
            f"{prominences[i]:.6g}",
            f"{fwhm[i]:.6g}",
        ]
        if integrate:
            area = _area_for_peak(x, y, props, i, int(idx))
            row.append(f"{area:.6g}")
            result.summary[f"Area {i + 1}"] = area
        table.append(row)
    result.tables["Peaks"] = table
    result.summary.setdefault("Peaks", float(indices.size))
    result.summary.setdefault("Max height", float(np.max(heights)))
    result.summary.setdefault("Mean FWHM", float(np.mean(fwhm)))
    if integrate:
        result.notes = (
            "Areas integrate the signal between each peak's prominence bases "
            "(local valleys), with the bound minimum subtracted as a baseline."
        )
    result.curves["Peaks"] = (x[indices], heights)
    return result


def _area_for_peak(
    x: np.ndarray, y: np.ndarray, props: dict, j: int, idx: int
) -> float:
    """Per-peak trapezoidal area between the peak's prominence bases.

    ``props`` may be empty (partial-match indices are unused in that path).
    ``j`` indexes the peak order *within this call's find_peaks result*, so the
    base arrays must be looked up with ``j`` (they are per-peak).
    """
    if not y.size:
        return 0.0
    left = int(props["left_bases"][j]) if "left_bases" in props else max(0, idx - 1)
    right = (
        int(props["right_bases"][j])
        if "right_bases" in props
        else min(y.size - 1, idx + 1)
    )
    left = max(0, min(left, len(y) - 1))
    right = max(left, min(right, len(y) - 1))
    left = min(left, idx)
    right = max(right, idx)
    segment = y[left : right + 1]
    if segment.size < 2:
        return 0.0
    segment = segment - float(np.min(segment))
    return float(np.trapezoid(segment, x[left : right + 1]))


__all__ = ["find_peaks_result"]
