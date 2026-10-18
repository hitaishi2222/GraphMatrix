"""Journal figure presets.

A preset bundles the *physical* conventions a journal expects: figure width and
height in millimetres, a base font size, legend/label sizes, and recommended line
widths and marker sizes. Applying one to a graph both restyles its plots (so the
live canvas matches) and records the preset name on the graph, which the exporter
then honours for fonts and default dimensions.

Sizes follow each publisher's author guidelines at the time of writing; they are a
sensible default, not a guarantee — always check the current guide for authors.
"""

from __future__ import annotations

from typing import Any

from .model import Graph

#: preset name -> physical + typographic settings.
JOURNAL_PRESETS: dict[str, dict[str, float]] = {
    "Default": {
        "width_mm": 100.0,
        "height_mm": 75.0,
        "dpi": 300.0,
        "font_pt": 10.0,
        "label_pt": 11.0,
        "legend_pt": 9.0,
        "tick_pt": 9.0,
        "line_width": 2.0,
        "symbol_size": 7.0,
    },
    "Nature (single column)": {
        "width_mm": 89.0,
        "height_mm": 70.0,
        "dpi": 600.0,
        "font_pt": 7.0,
        "label_pt": 8.0,
        "legend_pt": 6.0,
        "tick_pt": 6.0,
        "line_width": 1.0,
        "symbol_size": 3.5,
    },
    "Nature (double column)": {
        "width_mm": 183.0,
        "height_mm": 120.0,
        "dpi": 600.0,
        "font_pt": 7.0,
        "label_pt": 8.0,
        "legend_pt": 6.0,
        "tick_pt": 6.0,
        "line_width": 1.0,
        "symbol_size": 3.5,
    },
    "Science (single column)": {
        "width_mm": 55.0,
        "height_mm": 45.0,
        "dpi": 600.0,
        "font_pt": 6.0,
        "label_pt": 7.0,
        "legend_pt": 6.0,
        "tick_pt": 6.0,
        "line_width": 1.0,
        "symbol_size": 3.0,
    },
    "Science (double column)": {
        "width_mm": 120.0,
        "height_mm": 90.0,
        "dpi": 600.0,
        "font_pt": 6.0,
        "label_pt": 7.0,
        "legend_pt": 6.0,
        "tick_pt": 6.0,
        "line_width": 1.0,
        "symbol_size": 3.0,
    },
    "APS (single column)": {
        "width_mm": 85.0,
        "height_mm": 65.0,
        "dpi": 600.0,
        "font_pt": 8.0,
        "label_pt": 9.0,
        "legend_pt": 8.0,
        "tick_pt": 8.0,
        "line_width": 1.0,
        "symbol_size": 4.0,
    },
    "IEEE (single column)": {
        "width_mm": 88.0,
        "height_mm": 66.0,
        "dpi": 600.0,
        "font_pt": 8.0,
        "label_pt": 9.0,
        "legend_pt": 8.0,
        "tick_pt": 8.0,
        "line_width": 1.0,
        "symbol_size": 4.0,
    },
    "IEEE (double column)": {
        "width_mm": 181.0,
        "height_mm": 120.0,
        "dpi": 600.0,
        "font_pt": 8.0,
        "label_pt": 9.0,
        "legend_pt": 8.0,
        "tick_pt": 8.0,
        "line_width": 1.0,
        "symbol_size": 4.0,
    },
}


def journal_names() -> list[str]:
    """Preset names in menu order (``Default`` first)."""
    return list(JOURNAL_PRESETS)


def preset(name: str) -> dict[str, float]:
    """Return a preset by name, falling back to ``Default`` for unknown names."""
    return JOURNAL_PRESETS.get(name, JOURNAL_PRESETS["Default"])


def apply_journal_preset(graph: Graph, name: str) -> dict[str, float]:
    """Record ``name`` on ``graph`` and restyle every plot to match.

    Line widths and symbol sizes are set to the preset's absolute values, so applying
    a preset twice is idempotent (unlike scaling, which would compound).
    """
    settings = preset(name)
    graph.journal_preset = name if name in JOURNAL_PRESETS else ""
    for layer in graph.layers:
        for spec in layer.plots:
            spec.line_width = float(settings["line_width"])
            spec.symbol_size = float(settings["symbol_size"])
    return settings


def figure_size(preset_name: str) -> tuple[float, float]:
    """``(width_mm, height_mm)`` for a preset."""
    settings = preset(preset_name)
    return float(settings["width_mm"]), float(settings["height_mm"])


def export_rcparams(preset_name: str) -> dict[str, Any]:
    """matplotlib rcParams that reproduce a preset's typography on export."""
    settings = preset(preset_name)
    line_width = float(settings["line_width"])
    return {
        "font.size": float(settings["font_pt"]),
        "axes.labelsize": float(settings["label_pt"]),
        "axes.titlesize": float(settings["label_pt"]),
        "legend.fontsize": float(settings["legend_pt"]),
        "xtick.labelsize": float(settings["tick_pt"]),
        "ytick.labelsize": float(settings["tick_pt"]),
        "lines.linewidth": line_width,
        "lines.markersize": float(settings["symbol_size"]) * 0.6,
        "axes.linewidth": max(0.5, line_width * 0.8),
    }


__all__ = [
    "JOURNAL_PRESETS",
    "journal_names",
    "preset",
    "apply_journal_preset",
    "figure_size",
    "export_rcparams",
]
