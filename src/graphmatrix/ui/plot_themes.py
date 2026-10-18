"""Plot-specific colour themes, independent of the application UI theme.

These themes control the canvas background/foreground and the default colour
cycle used for series. They are intentionally separate from the UI theme presets
in :mod:`graphmatrix.ui.theme` so a graph can look "publication dark" while the rest
of the application stays light.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlotTheme:
    id: str
    label: str
    description: str
    canvas_bg: str
    canvas_fg: str
    grid: float
    palette: tuple[str, ...]


_CLASSIC = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2")
_VIBRANT = ("#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#a65628", "#f781bf", "#999999")
_EARTH = ("#8c510a", "#bf812d", "#dfc27d", "#f6e8c3", "#c7eae5", "#80cdc1", "#35978f", "#01665e")
_MONO = ("#222222", "#555555", "#888888", "#aaaaaa", "#cccccc", "#444444", "#666666", "#333333")

PLOT_THEMES: dict[str, PlotTheme] = {
    "plot-classic-light": PlotTheme("plot-classic-light", "Classic (light)", "White canvas, classic colour cycle.", "#ffffff", "#202124", 0.25, _CLASSIC),
    "plot-classic-dark": PlotTheme("plot-classic-dark", "Classic (dark)", "Dark canvas, classic colour cycle.", "#191a1d", "#d7dae0", 0.16, _CLASSIC),
    "plot-seaborn": PlotTheme("plot-seaborn", "Seaborn", "Soft grey canvas with vibrant colours.", "#f0f0f0", "#262626", 0.3, _VIBRANT),
    "plot-earth": PlotTheme("plot-earth", "Earth", "Warm, muted tones on a cream canvas.", "#f6f1e7", "#3b2f2f", 0.25, _EARTH),
    "plot-monochrome": PlotTheme("plot-monochrome", "Monochrome", "Greys only, for print-friendly figures.", "#ffffff", "#000000", 0.2, _MONO),
    "plot-publication": PlotTheme("plot-publication", "Publication", "White canvas, high-contrast, print-safe palette.", "#ffffff", "#000000", 0.15, _CLASSIC),
}

DEFAULT_PLOT_THEME = ""  # empty = follow the application UI theme


def get(theme_id: str | None) -> PlotTheme | None:
    if not theme_id:
        return None
    return PLOT_THEMES.get(theme_id)


def canvas_colors(theme_id: str) -> tuple[str, str, float] | None:
    t = get(theme_id)
    if t is None:
        return None
    return t.canvas_bg, t.canvas_fg, t.grid


__all__ = ["PlotTheme", "PLOT_THEMES", "DEFAULT_PLOT_THEME", "get", "canvas_colors"]