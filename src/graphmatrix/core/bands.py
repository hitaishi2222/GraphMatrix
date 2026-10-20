"""Band layout for the stacked-line template.

A stacked-line figure draws several curves that share one X axis inside a
single panel: every curve gets its own horizontal band, so the curves can be
read as waveforms instead of as absolute values on a shared Y scale.

The maths lives here (and not in the canvas or in the exporter) so the live
canvas and the exported figure can not drift apart.
"""

from __future__ import annotations

import numpy as np

#: Vertical gap between two bands, in band units.
BAND_GAP = 0.2

#: Height of a normalised band (its values run from 0 to 1).
NORMALISED_BAND_HEIGHT = 1.0

#: The Y modes a layer can be drawn in.
Y_MODE_ABSOLUTE = "absolute"
Y_MODE_NORMALIZED = "normalized"

#: Every Y mode the UI and the API accept.
Y_MODES = (Y_MODE_ABSOLUTE, Y_MODE_NORMALIZED)


def finite_range(values) -> tuple[float, float]:
    """The smallest and largest finite value; ``(0.0, 0.0)`` when there is none."""
    y = np.asarray(values, dtype=float)
    finite = y[np.isfinite(y)]
    if finite.size == 0:
        return 0.0, 0.0
    return float(finite.min()), float(finite.max())


def scale_to_band(values, low: float, high: float) -> np.ndarray:
    """Scale the values into 0..1 over the given range.

    A flat series (an empty range) is drawn flat at the bottom of its band
    instead of dividing by zero; missing values stay missing.
    """
    y = np.asarray(values, dtype=float)
    if high - low <= 0:
        return np.where(np.isfinite(y), 0.0, np.nan)
    return (y - low) / (high - low)


def log_transform(values) -> np.ndarray:
    """The base-10 logarithm of the values; non-positive values become NaN."""
    y = np.asarray(values, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log10(np.where(y > 0, y, np.nan))


def band_height(values) -> float:
    """How tall a band of these values is."""
    low, high = finite_range(values)
    return max(0.0, high - low)


def band_baselines(heights, pitch: float) -> list[float]:
    """The baseline (bottom) of every band, from the bottom up.

    ``heights`` are the band heights in band units and ``pitch`` is the
    distance between two normalised bands. A band that is taller than the
    pitch (an absolute or log layer) pushes the bands above it up, so the
    bands never overlap.
    """
    baselines: list[float] = []
    current = 0.0
    for height in heights:
        baselines.append(current)
        current += max(float(pitch), float(height) + BAND_GAP)
    return baselines


def layer_band_transform(
    values,
    *,
    mode: str = Y_MODE_ABSOLUTE,
    log: bool = False,
):
    """How one layer's values are drawn: ``(transform, height, error factor)``.

    ``transform`` maps the layer's own values to the values that are drawn,
    ``height`` is how tall the band is, and the error factor scales the
    error bars with the values.

    ``mode`` is ``"absolute"`` (the values are kept as they are) or
    ``"normalized"`` (the values are scaled to 0..1 over their own range).
    A log layer is never rescaled in linear space: its values are drawn on a
    log-transformed vertical scale, which keeps the shape of the log curve
    and leaves the band as tall as the data's log range.
    """
    y = np.asarray(values, dtype=float)
    if log:
        # The log scale is the point of the layer: it is not rescaled.
        return log_transform, band_height(log_transform(y)), 1.0
    if mode == Y_MODE_NORMALIZED:
        low, high = finite_range(y)
        factor = 1.0 / (high - low) if high > low else 0.0
        return (
            lambda values: scale_to_band(values, low, high),
            NORMALISED_BAND_HEIGHT,
            factor,
        )
    return lambda values: np.asarray(values, dtype=float), band_height(y), 1.0


def layer_is_normalized(layer) -> bool:
    """True when the layer is drawn as a 0..1 band of its own shape."""
    mode = str(getattr(layer, "y_mode", Y_MODE_ABSOLUTE) or Y_MODE_ABSOLUTE)
    return mode == Y_MODE_NORMALIZED


__all__ = [
    "BAND_GAP",
    "NORMALISED_BAND_HEIGHT",
    "Y_MODES",
    "Y_MODE_ABSOLUTE",
    "Y_MODE_NORMALIZED",
    "band_baselines",
    "band_height",
    "finite_range",
    "layer_band_transform",
    "layer_is_normalized",
    "log_transform",
    "scale_to_band",
]
