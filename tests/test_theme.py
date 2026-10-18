"""Theme preset tests: palette integrity, fallbacks, and QSS templating."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from graphmatrix.ui import theme  # noqa: E402

_TOKEN_KEYS = {
    "window",
    "panel",
    "base",
    "alt",
    "border",
    "text",
    "muted",
    "accent",
    "accent_text",
    "hover",
    "disabled",
    "canvas_bg",
    "canvas_fg",
    "canvas_grid",
    "danger",
}


def test_presets_cover_the_four_variants():
    ids = [p.id for p in theme.presets()]
    assert ids == ["classic-dark", "classic-light", "modern-dark", "modern-light"]


def test_every_preset_has_the_same_palette_tokens():
    for p in theme.presets():
        assert set(p.palette) == _TOKEN_KEYS, p.id


def test_dark_and_modern_flags():
    assert (
        theme.PRESETS["classic-dark"].dark and not theme.PRESETS["classic-dark"].modern
    )
    assert (
        not theme.PRESETS["classic-light"].dark
        and not theme.PRESETS["classic-light"].modern
    )
    assert theme.PRESETS["modern-dark"].dark and theme.PRESETS["modern-dark"].modern
    assert (
        not theme.PRESETS["modern-light"].dark and theme.PRESETS["modern-light"].modern
    )


def test_unknown_preset_falls_back_to_default():
    assert theme.preset("does-not-exist").id == theme.DEFAULT_PRESET
    assert theme.set_preset("does-not-exist") == theme.DEFAULT_PRESET


def test_canvas_colors_tuple():
    bg, fg, alpha = theme.canvas_colors("modern-dark")
    assert bg.startswith("#") and fg.startswith("#")
    assert isinstance(alpha, float)


def test_stylesheet_has_no_unsubstituted_tokens():
    for p in theme.presets():
        qss = theme._stylesheet(p)
        assert "$" not in qss, p.id


def test_modern_layer_differs_from_classic():
    classic = theme._stylesheet(theme.PRESETS["classic-dark"])
    modern = theme._stylesheet(theme.PRESETS["modern-dark"])
    assert len(modern) > len(classic)
    # The modern layer rounds corners more aggressively than the classic base.
    assert "border-radius: 9px" in modern


def test_state_helpers_track_the_active_preset():
    original = theme.current_preset()
    try:
        theme.set_preset("modern-light")
        assert theme.current_preset() == "modern-light"
        assert theme.is_dark() is False
        assert theme.is_modern() is True
        theme.set_preset("classic-dark")
        assert theme.is_dark() is True
        assert theme.is_modern() is False
    finally:
        theme.set_preset(original)
