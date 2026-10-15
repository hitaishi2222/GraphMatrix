"""Curve digitizer tests (M9)."""

from __future__ import annotations

import numpy as np
import pytest

from respot.core.analysis.digitize import digitize_curve


def _line_image(slope_px: float = -0.8, thickness: int = 2) -> np.ndarray:
    """A black line on white: ``row = 180 - slope*(col-10)*`` over ``col`` in 10..190."""
    height = width = 200
    image = np.ones((height, width, 3), dtype=float)
    for col in range(10, 191):
        row = int(round(180 + slope_px * (col - 10)))
        for offset in range(thickness):
            if 0 <= row + offset < height:
                image[row + offset, col] = 0.0
    return image


def test_recovers_known_slope():
    image = _line_image()
    result = digitize_curve(
        image,
        x_anchors=((10.0, 0.0), (190.0, 9.0)),
        y_anchors=((180.0, 0.0), (20.0, 8.0)),
    )
    x, y = result.curves["Digitized"]
    assert x.size == 181
    slope, _ = np.polyfit(x, y, 1)
    # 0.8 in data units: x spans 9 over 180 px, y spans 8 over 160 px.
    assert slope == pytest.approx(0.8, abs=0.02)
    assert result.summary["N points"] == 181


def test_color_isolation_picks_the_trace():
    rng = np.random.default_rng(0)
    image = rng.uniform(0.0, 0.4, size=(120, 160, 3))
    image[..., 2] += 0.4  # bluish background
    image = np.clip(image, 0, 1)
    for col in range(20, 140):
        row = int(round(100 - 0.5 * (col - 20)))
        image[row, col] = (1.0, 0.0, 0.0)
    result = digitize_curve(
        image,
        x_anchors=((20.0, 0.0), (140.0, 12.0)),
        y_anchors=((100.0, 0.0), (40.0, 6.0)),
        color=(1.0, 0.0, 0.0),
        tolerance=0.2,
    )
    x, y = result.curves["Digitized"]
    assert x.size == 120
    slope, _ = np.polyfit(x, y, 1)
    assert slope == pytest.approx(0.5, abs=0.02)


def test_x_region_restriction():
    image = _line_image()
    result = digitize_curve(
        image,
        x_anchors=((10.0, 0.0), (190.0, 9.0)),
        y_anchors=((180.0, 0.0), (20.0, 8.0)),
        x_start=2.0,
        x_end=4.0,
    )
    x, _ = result.curves["Digitized"]
    assert x.min() >= 2.0
    assert x.max() <= 4.0


def test_bad_anchor_raises():
    image = _line_image()
    with pytest.raises(ValueError):
        digitize_curve(
            image,
            x_anchors=((10.0, 0.0), (10.0, 9.0)),
            y_anchors=((180.0, 0.0), (20.0, 8.0)),
        )
