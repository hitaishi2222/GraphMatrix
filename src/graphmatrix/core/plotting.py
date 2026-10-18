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
    z: np.ndarray | None = None
    z_label: str = ""


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
    zcol = sheet.column(spec.z) if getattr(spec, "z", "") else None

    x = xcol.float_data()
    y = ycol.float_data()
    n = min(x.size, y.size)
    x, y = x[:n], y[:n]
    yerr = yerrcol.float_data()[:n] if yerrcol is not None else None
    xerr = xerrcol.float_data()[:n] if xerrcol is not None else None
    z = zcol.float_data()[:n] if zcol is not None else None

    legend = spec.legend or ycol.name
    return ResolvedSeries(
        x, y, yerr, xerr, _label(xcol), _label(ycol), legend, z=z, z_label=_label(zcol)
    )


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
            xcol = next(
                (c for c in sheet.columns if c.col_type == ColumnType.X and len(c)),
                None,
            )
            ycol = next(
                (c for c in sheet.columns if c.col_type == ColumnType.Y and len(c)),
                None,
            )
            if xcol is not None and ycol is not None and xcol is not ycol:
                return (
                    xcol.float_data(),
                    ycol.float_data(),
                    _label(xcol),
                    _label(ycol),
                )
    return None


def make_plot_for_column(project: Project, source: str, name: str) -> PlotSpec | None:
    """Build a sensible plot spec for a single dragged column.

    An X column is paired with the sheet's first Y column; a Y column is paired with
    the sheet's first X column. Returns None if nothing sensible can be paired.
    """
    from .model import ColumnType, PlotSpec

    sheet = project.sheet(source)
    if sheet is None:
        return None
    column = sheet.column(name)
    if column is None:
        return None
    if column.col_type == ColumnType.X:
        partner = next(
            (
                c
                for c in sheet.columns
                if c.col_type == ColumnType.Y and c is not column
            ),
            None,
        )
        if partner is None:
            return None
        return PlotSpec(source=source, x=name, y=partner.name)
    partner = next(
        (c for c in sheet.columns if c.col_type == ColumnType.X and c is not column),
        None,
    )
    if partner is None:
        partner = next((c for c in sheet.columns if c is not column), None)
    if partner is None:
        return None
    return PlotSpec(source=source, x=partner.name, y=name)


def make_default_graph(project: Project, name: str) -> Graph | None:
    """Create a graph pre-populated with the project's first X/Y pair."""
    from .model import ColumnType, PlotSpec, PlotStyle

    graph = Graph(name)
    pair = None
    for book in project.workbooks:
        for sheet in book.sheets:
            xcol = next(
                (c for c in sheet.columns if c.col_type == ColumnType.X and len(c)),
                None,
            )
            ycol = next(
                (c for c in sheet.columns if c.col_type == ColumnType.Y and len(c)),
                None,
            )
            if xcol is not None and ycol is not None and xcol is not ycol:
                pair = (f"{book.name}/{sheet.name}", xcol.name, ycol.name)
                break
        if pair:
            break
    if pair:
        graph.first_layer.add_plot(PlotSpec(source=pair[0], x=pair[1], y=pair[2]))
    return graph


def grid_xyz(
    x: Sequence[float],
    y: Sequence[float],
    z: Sequence[float],
    *,
    nx: int = 80,
    ny: int = 80,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Grid scattered X-Y-Z samples onto a regular mesh for heatmap/3D-surface.

    Returns ``(gx, gy, grid)`` where ``gx``/``gy`` are the 1-D axes and ``grid``
    is a ``(ny, nx)`` matrix of interpolated values (linear interpolation with a
    nearest-neighbour fill at the convex hull edge). Points with non-finite
    coordinates are dropped; if there is not enough usable data every cell is NaN.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    z = np.asarray(z, dtype=float)
    if x.shape != y.shape or x.shape != z.shape:
        x, y, z = np.broadcast_arrays(x, y, z)
        x, y, z = x.astype(float), y.astype(float), z.astype(float)
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x, y, z = x[mask], y[mask], z[mask]
    if x.size < 4 or x.min() >= x.max() or y.min() >= y.max():
        gx = (
            np.linspace(0, 1, nx)
            if x.max() <= x.min()
            else np.linspace(x.min(), x.max(), nx)
        )
        gy = (
            np.linspace(0, 1, ny)
            if y.max() <= y.min()
            else np.linspace(y.min(), y.max(), ny)
        )
        grid = np.full((ny, nx), np.nan)
        return gx, gy, grid

    gx = np.linspace(float(x.min()), float(x.max()), nx)
    gy = np.linspace(float(y.min()), float(y.max()), ny)
    gxx, gyy = np.meshgrid(gx, gy)

    from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

    linear = LinearNDInterpolator(np.column_stack([x, y]), z)
    nearest = NearestNDInterpolator(np.column_stack([x, y]), z)
    grid = linear(gxx, gyy)
    holes = ~np.isfinite(grid)
    if holes.any():
        grid[holes] = nearest(gxx, gyy)[holes]
    return gx, gy, grid


__all__ = [
    "resolve_plot",
    "resolve_layer",
    "auto_axis_labels",
    "first_xy",
    "make_plot_for_column",
    "make_default_graph",
    "grid_xyz",
]
