"""Curve digitizer: recover data points from a picture of a plot.

Given a raster image (PNG/JPEG/TIFF or a numpy array) and two *axis anchors* per
axis — the pixel position and the data value of two calibration points — this walks
the curve's pixels column by column and inverts the linear pixel→data map.

It is intentionally small and dependency-light: Pillow reads the image, numpy does
the rest. Use a *color* target plus tolerance to pull out one trace from a busy
figure, or the default darkness threshold for a simple black-on-white plot.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np

from .result import AnalysisResult

#: pixel-value pairs: ``((pixel_a, value_a), (pixel_b, value_b))``.
AnchorPair = tuple[tuple[float, float], tuple[float, float]]

_AGGREGATES = ("median", "mean", "top", "bottom")


def _load_rgb(image: str | Path | np.ndarray) -> np.ndarray:
    """Load ``image`` as an ``(H, W, 3)`` float array in ``[0, 1]``."""
    if isinstance(image, np.ndarray):
        arr = np.asarray(image, dtype=float)
    else:
        from PIL import Image

        with Image.open(image) as handle:
            arr = np.asarray(handle.convert("RGB"), dtype=float)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.ndim == 3 and arr.shape[-1] >= 3:
        arr = arr[..., :3]
    else:
        raise ValueError("image must be 2-D grayscale or 3-channel RGB")
    if arr.size and arr.max() > 1.0 + 1e-9:
        arr = arr / 255.0
    return np.clip(arr, 0.0, 1.0)


def _luminance(rgb: np.ndarray) -> np.ndarray:
    weights = np.array([0.2126, 0.7152, 0.0722])
    return rgb @ weights


def _linear(pixel: float, p_a: float, v_a: float, p_b: float, v_b: float) -> float:
    if p_b == p_a:
        raise ValueError("the two anchors for an axis share the same pixel coordinate")
    return v_a + (pixel - p_a) * (v_b - v_a) / (p_b - p_a)


def _curve_mask(
    rgb: np.ndarray,
    *,
    threshold: float,
    invert: bool,
    color: Sequence[float] | None,
    tolerance: float,
) -> np.ndarray:
    if color is not None:
        target = np.asarray(color, dtype=float)
        if target.max() > 1.0 + 1e-9:
            target = target / 255.0
        distance = np.sqrt(((rgb - target[:3]) ** 2).sum(axis=-1))
        return distance <= tolerance
    gray = _luminance(rgb)
    if invert:
        return gray >= (1.0 - threshold)
    return gray <= threshold


def _row_span(y_anchors: AnchorPair, height: int) -> tuple[int, int]:
    (p0, _), (p1, _) = y_anchors
    lo = max(0, math.floor(min(p0, p1)))
    hi = min(height - 1, math.ceil(max(p0, p1)))
    return lo, hi


def digitize_curve(
    image: str | Path | np.ndarray,
    *,
    x_anchors: AnchorPair,
    y_anchors: AnchorPair,
    threshold: float = 0.5,
    invert: bool = False,
    color: Sequence[float] | None = None,
    tolerance: float = 0.12,
    x_start: float | None = None,
    x_end: float | None = None,
    aggregate: str = "median",
) -> AnalysisResult:
    """Extract ``(x, y)`` points from a plotted curve in ``image``.

    ``x_anchors`` and ``y_anchors`` each map two pixel coordinates to two data values;
    the two points must differ in pixel coordinate (that is the calibration). Use
    ``color`` (an RGB triple) with ``tolerance`` to isolate a coloured trace; otherwise
    pixels darker than ``threshold`` are treated as the curve (``invert`` flips this to
    light-on-dark).
    """
    if aggregate not in _AGGREGATES:
        raise ValueError(f"aggregate must be one of {_AGGREGATES}, got {aggregate!r}")

    rgb = _load_rgb(image)
    height, width = rgb.shape[:2]
    mask = _curve_mask(
        rgb, threshold=threshold, invert=invert, color=color, tolerance=tolerance
    )

    (px_a, vx_a), (px_b, vx_b) = x_anchors
    (py_a, vy_a), (py_b, vy_b) = y_anchors
    row_lo, row_hi = _row_span(y_anchors, height)

    col_lo = max(0, math.ceil(min(px_a, px_b)))
    col_hi = min(width - 1, math.floor(max(px_a, px_b)))
    if x_start is not None or x_end is not None:
        xs = np.array(
            [
                _linear(col_lo, px_a, vx_a, px_b, vx_b),
                _linear(col_hi, px_a, vx_a, px_b, vx_b),
            ]
        )
        lo_val, hi_val = min(xs), max(xs)
        if x_start is not None:
            lo_val = max(lo_val, x_start)
        if x_end is not None:
            hi_val = min(hi_val, x_end)
        col_lo = max(col_lo, math.ceil(_pixel_for(lo_val, px_a, vx_a, px_b, vx_b)))
        col_hi = min(col_hi, math.floor(_pixel_for(hi_val, px_a, vx_a, px_b, vx_b)))

    xs: list[float] = []
    ys: list[float] = []
    for col in range(col_lo, col_hi + 1):
        rows = np.flatnonzero(mask[row_lo : row_hi + 1, col])
        if rows.size == 0:
            continue
        rows = rows + row_lo
        if aggregate == "median":
            row = float(np.median(rows))
        elif aggregate == "mean":
            row = float(rows.mean())
        elif aggregate == "top":
            row = float(rows.min())
        else:  # bottom
            row = float(rows.max())
        xs.append(_linear(col, px_a, vx_a, px_b, vx_b))
        ys.append(_linear(row, py_a, vy_a, py_b, vy_b))

    order = np.argsort(xs, kind="stable")
    x = np.asarray(xs, dtype=float)[order]
    y = np.asarray(ys, dtype=float)[order]

    summary: dict[str, float] = {"N points": float(x.size)}
    if x.size:
        summary["x min"] = float(x.min())
        summary["x max"] = float(x.max())
        summary["y min"] = float(np.nanmin(y))
        summary["y max"] = float(np.nanmax(y))
    notes = (
        "Digitized from image pixels. The result depends on the calibration anchors; "
        "verify by overlaying the recovered points on the source image."
    )
    return AnalysisResult(
        kind="digitize",
        title="Digitized Curve",
        summary=summary,
        curves={"Digitized": (x, y)},
        notes=notes,
    )


def _pixel_for(value: float, p_a: float, v_a: float, p_b: float, v_b: float) -> float:
    if v_b == v_a:
        raise ValueError("the two anchors for an axis share the same value")
    return p_a + (value - v_a) * (p_b - p_a) / (v_b - v_a)


def anchor_pairs(
    anchors: Iterable[tuple[float, float]],
) -> AnchorPair:  # pragma: no cover - helper
    """Coerce a 2-element iterable of ``(pixel, value)`` into an :data:`AnchorPair`."""
    items = list(anchors)
    if len(items) != 2:
        raise ValueError("an axis needs exactly two anchors")
    return (tuple(items[0]), tuple(items[1]))  # type: ignore[return-value]


__all__ = ["AnchorPair", "anchor_pairs", "digitize_curve"]
