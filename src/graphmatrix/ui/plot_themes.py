"""Plot-specific colour themes (re-exported from the Qt-free core).

The tables live in :mod:`graphmatrix.core.plot_themes` so the live canvas and
the exporter share one source of truth. This module keeps the historical
``graphmatrix.ui.plot_themes`` import path working.
"""

from __future__ import annotations

from graphmatrix.core.plot_themes import (
    APP_CANVAS_THEMES,
    DEFAULT_APP_THEME,
    DEFAULT_PLOT_THEME,
    PLOT_THEMES,
    PlotTheme,
    canvas_colors,
    get,
    resolve_theme,
)

__all__ = [
    "APP_CANVAS_THEMES",
    "DEFAULT_APP_THEME",
    "DEFAULT_PLOT_THEME",
    "PLOT_THEMES",
    "PlotTheme",
    "canvas_colors",
    "get",
    "resolve_theme",
]
