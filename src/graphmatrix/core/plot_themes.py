"""Plot-specific colour themes, independent of the application UI theme.

These themes control the canvas background/foreground and the default colour
cycle used for series. They are intentionally separate from the UI theme presets
in :mod:`graphmatrix.ui.theme` so a graph can look "publication dark" while the rest
of the application stays light.

The tables live in the Qt-free core on purpose: the live canvas and the
exporter must agree on every colour, and the exporter may not import the UI
layer. :mod:`graphmatrix.ui.theme` reads its canvas colours from here too.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlotTheme:
    """One named canvas theme."""

    id: str
    label: str
    description: str
    canvas_bg: str
    canvas_fg: str
    grid: float
    palette: tuple[str, ...]


#: Canvas colours of the *application* presets (the ones the UI theme
#: switches between): ``(background, foreground, grid alpha)``.
APP_CANVAS_THEMES: dict[str, tuple[str, str, float]] = {
    "classic-dark": ("#191a1d", "#d7dae0", 0.16),
    "classic-light": ("#ffffff", "#202124", 0.25),
    "modern-dark": ("#0e1015", "#dde1ea", 0.14),
    "modern-light": ("#ffffff", "#1b1e2b", 0.20),
}

#: The application theme used when nothing else is specified.
DEFAULT_APP_THEME = "classic-dark"

#: Default series colours (matplotlib's classic cycle). The canvas and the
#: exporter share it, so a series keeps its colour in the preview and in the
#: exported file — including series drawn on a secondary axis.
DEFAULT_PALETTE: tuple[str, ...] = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#e377c2",
)


def series_color(index: int) -> str:
    """Colour of the ``index``-th series of a panel."""
    return DEFAULT_PALETTE[int(index) % len(DEFAULT_PALETTE)]


_CLASSIC = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#e377c2",
)
_VIBRANT = (
    "#e41a1c",
    "#377eb8",
    "#4daf4a",
    "#984ea3",
    "#ff7f00",
    "#a65628",
    "#f781bf",
    "#999999",
)
_EARTH = (
    "#8c510a",
    "#bf812d",
    "#dfc27d",
    "#f6e8c3",
    "#c7eae5",
    "#80cdc1",
    "#35978f",
    "#01665e",
)
_MONO = (
    "#222222",
    "#555555",
    "#888888",
    "#aaaaaa",
    "#cccccc",
    "#444444",
    "#666666",
    "#333333",
)

PLOT_THEMES: dict[str, PlotTheme] = {
    "plot-classic-light": PlotTheme(
        "plot-classic-light",
        "Classic (light)",
        "White canvas, classic colour cycle.",
        "#ffffff",
        "#202124",
        0.25,
        _CLASSIC,
    ),
    "plot-classic-dark": PlotTheme(
        "plot-classic-dark",
        "Classic (dark)",
        "Dark canvas, classic colour cycle.",
        "#191a1d",
        "#d7dae0",
        0.16,
        _CLASSIC,
    ),
    "plot-seaborn": PlotTheme(
        "plot-seaborn",
        "Seaborn",
        "Soft grey canvas with vibrant colours.",
        "#f0f0f0",
        "#262626",
        0.3,
        _VIBRANT,
    ),
    "plot-earth": PlotTheme(
        "plot-earth",
        "Earth",
        "Warm, muted tones on a cream canvas.",
        "#f6f1e7",
        "#3b2f2f",
        0.25,
        _EARTH,
    ),
    "plot-monochrome": PlotTheme(
        "plot-monochrome",
        "Monochrome",
        "Greys only, for print-friendly figures.",
        "#ffffff",
        "#000000",
        0.2,
        _MONO,
    ),
    "plot-publication": PlotTheme(
        "plot-publication",
        "Publication",
        "White canvas, high-contrast, print-safe palette.",
        "#ffffff",
        "#000000",
        0.15,
        _CLASSIC,
    ),
}

DEFAULT_PLOT_THEME = ""  # empty = follow the application UI theme


def get(theme_id: str | None) -> PlotTheme | None:
    if not theme_id:
        return None
    return PLOT_THEMES.get(theme_id)


def canvas_colors(theme_id: str) -> tuple[str, str, float] | None:
    """Canvas colours of a plot theme or an application preset.

    Returns ``(background, foreground, grid alpha)`` or ``None`` when the id is
    unknown.
    """
    theme = get(theme_id)
    if theme is not None:
        return theme.canvas_bg, theme.canvas_fg, theme.grid
    return APP_CANVAS_THEMES.get(theme_id)


def resolve_theme(plot_theme: str = "", app_theme: str = "") -> tuple[str, str, float]:
    """Resolve the colours a figure should be drawn with.

    ``plot_theme`` is the graph's own theme (highest priority), ``app_theme``
    the application preset the canvas follows when the graph has none. The
    preview and the export both call this, which is what keeps them in sync.
    """
    for candidate in (plot_theme, app_theme):
        colors = canvas_colors(candidate) if candidate else None
        if colors is not None:
            return colors
    return APP_CANVAS_THEMES[DEFAULT_APP_THEME]


__all__ = [
    "APP_CANVAS_THEMES",
    "DEFAULT_APP_THEME",
    "DEFAULT_PALETTE",
    "DEFAULT_PLOT_THEME",
    "PLOT_THEMES",
    "PlotTheme",
    "canvas_colors",
    "get",
    "resolve_theme",
    "series_color",
]
