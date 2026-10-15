"""Resolve plot specs to arrays; shared by the canvas and the exporters.

Keeping this in `core` means the live canvas (pyqtgraph) and the publication
exporter (matplotlib) plot *the same* data with the same fallbacks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import Graph, Layer, PlotSpec, Project


@dataclass
class ResolvedSeries:
    x: np.ndarray
    y: np.ndarray
    yerr: np.ndarray | None
    xerr: np.ndarray | None
    x_label: str
    y_label: str
    legend: str


def _label(col) -> str:
    if col is None:
        return ""
    text = str(col.name)
    if getattr(col, "units", ""):
        text += f" ({col.units})"
    return text


def resolve_plot(project: Project, spec: PlotSpec) -> ResolvedSeries | None:
    """Resolve one plot spec to numeric arrays, or None if the source is gone."""
    sheet = project.sheet(spec.source)
    if sheet is None:
        return None
    xcol = sheet.column(spec.x)
    ycol = sheet.column(spec.y)
    if xcol is None or ycol is None:
        return None
    yerrcol = sheet.column(spec.yerr) if spec.yerr else None
    xerrcol = sheet.column(spec.xerr) if spec.xerr else None

    x = xcol.float_data()
    y = ycol.float_data()
    n = min(x.size, y.size)
    x, y = x[:n], y[:n]
    yerr = yerrcol.float_data()[:n] if yerrcol is not None else None
    xerr = xerrcol.float_data()[:n] if xerrcol is not None else None

    legend = spec.legend or ycol.name
    return ResolvedSeries(x, y, yerr, xerr, _label(xcol), _label(ycol), legend)


def resolve_layer(project: Project, layer: Layer) -> list[ResolvedSeries]:
    series = []
    for spec in layer.plots:
        resolved = resolve_plot(project, spec)
        if resolved is not None:
            series.append(resolved)
    return series


def auto_axis_labels(project: Project, layer: Layer) -> tuple[str, str]:
    """Axis labels: explicit override, else derived from the first plot."""
    x_label, y_label = layer.x_label, layer.y_label
    if (not x_label or not y_label) and layer.plots:
        resolved = resolve_plot(project, layer.plots[0])
        if resolved is not None:
            x_label = x_label or resolved.x_label
            y_label = y_label or resolved.y_label
    return x_label, y_label


def first_xy(project: Project) -> tuple[np.ndarray, np.ndarray, str, str] | None:
    """First plottable X/Y pair in the project (used to seed a new graph)."""
    from .model import ColumnType

    for book in project.workbooks:
        for sheet in book.sheets:
            xcol = next((c for c in sheet.columns if c.col_type == ColumnType.X and len(c)), None)
            ycol = next((c for c in sheet.columns if c.col_type == ColumnType.Y and len(c)), None)
            if xcol is not None and ycol is not None and xcol is not ycol:
                return (
                    xcol.float_data(), ycol.float_data(),
                    _label(xcol), _label(ycol),
                )
    return None


def make_default_graph(project: Project, name: str) -> Graph | None:
    """Create a graph pre-populated with the project's first X/Y pair."""
    from .model import ColumnType, PlotSpec, PlotStyle

    graph = Graph(name)
    pair = None
    for book in project.workbooks:
        for sheet in book.sheets:
            xcol = next((c for c in sheet.columns if c.col_type == ColumnType.X and len(c)), None)
            ycol = next((c for c in sheet.columns if c.col_type == ColumnType.Y and len(c)), None)
            if xcol is not None and ycol is not None and xcol is not ycol:
                pair = (f"{book.name}/{sheet.name}", xcol.name, ycol.name)
                break
        if pair:
            break
    if pair:
        graph.first_layer.add_plot(PlotSpec(source=pair[0], x=pair[1], y=pair[2]))
    return graph
