"""PyVista (VTK) implementation of the plot canvas — the 3D backend.

M10 decision (locked): **PyVista** hosts the interactive 3D view. This canvas
implements the same :class:`PlotCanvas` interface as its 2D siblings, so a graph
whose layers contain the ``3d scatter`` / ``3d surface`` styles renders here
without touching the window or the graph model. 2D styles are honoured too
(drawn in the z = 0 plane) so a mixed graph never goes blank, but the intended
workflow is one 3D scene per graph.

Publication export stays matplotlib-3D (vector PDF via the same exporter); this
class is only ever the *live* view. Requires the ``plot3d`` extra:
``pip install graphmatrix[plot3d]`` (pyvista + pyvistaqt).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .base import PlotCanvas

_LINE_WIDEN = 2.0


class PyVistaCanvas(PlotCanvas):
    """A PyVista/VTK-backed 3D canvas embedded in the Qt window."""

    def __init__(self) -> None:
        try:
            from pyvistaqt import QtInteractor
        except Exception as exc:  # noqa: BLE001 - optional dependency missing
            raise RuntimeError(
                "The 3D canvas needs the plot3d extra: pip install pyvista pyvistaqt"
            ) from exc

        self._interactor = QtInteractor()
        self._container = QWidget()
        lay = QVBoxLayout(self._container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._interactor)

        self._grid_rows = 1
        self._grid_cols = 1
        self._hover_enabled = False
        self._limits: tuple | None = None
        self._labels: dict[str, str] = {}
        self._title_text = ""
        self._title_size = 14.0
        self._legend_on = True
        self._theme_bg = "#191a1d"
        self._theme_fg = "#d7dae0"
        self._axes_labels: tuple[str, str, str] = ("X", "Y", "Z")

        self.set_background()
        self._interactor.add_axes(
            xlabel="X", ylabel="Y", zlabel="Z", line_width=1.5,
        )

    # -- PlotCanvas ----------------------------------------------------------
    def widget(self):
        return self._container

    def clear(self) -> None:
        saved = dict(self._labels)
        self._interactor.clear_actors()
        self._labels = saved
        self._show_axes()

    def plot(
        self,
        x, y, *,
        style: str = "line",
        color: str = "",
        width: float = 2.0,
        symbol: str = "o",
        symbol_size: float = 7.0,
        name: str | None = None,
        yerr=None, xerr=None,
        y_axis: str = "left",
        line_style: str = "solid",
        z=None,
    ) -> None:
        import pyvista as pv

        xs = np.asarray(list(x), dtype=float)
        ys = np.asarray(list(y), dtype=float)
        zs = np.zeros_like(xs) if z is None else np.asarray(list(z), dtype=float)
        n = min(xs.size, ys.size, zs.size)
        xs, ys, zs = xs[:n], ys[:n], zs[:n]
        mask = np.isfinite(xs) & np.isfinite(ys) & np.isfinite(zs)
        xs, ys, zs = xs[mask], ys[mask], zs[mask]
        if xs.size == 0:
            return

        actor_color = self._color(color or self._theme_fg)
        line_width = max(1.5, float(width) * _LINE_WIDEN)

        if style == "3d surface":
            grid = pv.PolyData(
                np.column_stack([xs, ys, zs])
            ).delaunay_2d()
            z_rng = (float(np.min(zs)), float(np.max(zs))) if zs.size > 1 else (0.0, 1.0)
            self._interactor.add_mesh(
                grid, scalars=grid.points[:, 2], cmap="viridis", show_edges=False,
                show_scalar_bar=self._legend_on, clim=z_rng,
            )
            return

        if style == "3d scatter" or z is not None:
            points = pv.PolyData(np.column_stack([xs, ys, zs]))
            kwargs = dict(
                render_points_as_spheres=True,
                point_size=max(3.0, float(symbol_size) * 2.5),
                show_scalar_bar=False,
            )
            if z is not None and zs.max() != zs.min():
                kwargs.update(scalars=zs, cmap="viridis", color=None)
            else:
                kwargs.update(color=actor_color)
            self._interactor.add_points(points, **kwargs)
            if self._legend_on and name:
                self._add_legend_entry(name, actor_color)
            return

        # 2D styles: draw in the z = 0 plane so a mixed graph still renders.
        if xs.size >= 2 and style in ("line", "line+symbol", "line_symbol", "step", "area"):
            polyline = pv.lines_from_points(np.column_stack([xs, ys, zs]))
            self._interactor.add_mesh(polyline, color=actor_color, line_width=line_width)
            if self._legend_on and name:
                self._add_legend_entry(name, actor_color)
        if style in ("scatter", "line+symbol", "line_symbol"):
            points = pv.PolyData(np.column_stack([xs, ys, zs]))
            self._interactor.add_points(
                points, color=actor_color, render_points_as_spheres=True,
                point_size=max(3.0, float(symbol_size) * 2.5),
            )

    def add_reference_line(self, orientation, position, *, color="#888888",
                           width=1.5, line_style="dash", label="") -> None:
        """Approximate an h/v guide in the 3D scene: a line across the axes box."""
        import pyvista as pv

        bounds = self._xy_bounds()
        if orientation == "v":
            span = ((position, bounds[2], 0.0), (position, bounds[3], 0.0))
        else:
            span = ((bounds[0], position, 0.0), (bounds[1], position, 0.0))
        line = pv.lines_from_points(span)
        self._interactor.add_mesh(line, color=self._color(color or "#888888"),
                                  line_width=max(2.0, width * _LINE_WIDEN), opacity=0.75)

    def set_hover(self, enabled: bool) -> None:
        # The nearest-point readout is a per-2D-canvas interaction; in 3D the
        # pick-interactor already reports what's under the cursor.
        self._hover_enabled = bool(enabled)

    def add_annotation(self, text, x, y, *, color="#000000", size=11.0) -> None:
        self._interactor.add_text(
            text, position=(max(0.0, min(float(x), 1.0)), max(0.0, min(float(y), 1.0))),
            viewport=(0, 0), font_size=int(max(6, size)), color=self._color(color or self._theme_fg),
        )

    def set_title(self, text: str, *, fontfamily: str = "", fontsize: float = 14.0,
                  color: str = "") -> None:
        self._title_text, self._title_size = text, fontsize
        self._show_title()

    def set_grid(self, rows: int = 1, cols: int = 1) -> None:
        # The 3D scene is a single panel; multi-panel graphs belong on 2D.
        self._grid_rows = max(1, rows)
        self._grid_cols = max(1, cols)

    def set_current_panel(self, index: int) -> None:
        pass

    def set_labels(self, *, bottom=None, left=None, right=None, fontfamily: str = "",
                   fontsize: float = 12.0, color: str = "") -> None:
        if bottom:
            self._labels["x"] = str(bottom)
        if left:
            self._labels["y"] = str(left)
        if right:
            self._labels["z"] = str(right)  # on a 3D scene the right label is Z
        self._show_axes()

    def set_scales(self, *, x: str = "linear", y: str = "linear") -> None:
        pass  # log-scale 3D axes are not supported in M10

    def set_ticks(self, *, minor: bool = True, direction: str = "out") -> None:
        pass

    def set_limits(self, *, x=None, y=None, z=None) -> None:
        self._limits = (x, y, z if (z is not None and hasattr(z, "__len__") and len(z) == 2) else None)
        self._apply_limits()

    def show_legend(self, flag: bool) -> None:
        self._legend_on = bool(flag)

    def set_downsampling(self, flag: bool) -> None:
        pass

    def set_theme(self, preset: str) -> None:
        from graphmatrix.ui import plot_themes, theme

        colors = plot_themes.canvas_colors(preset)
        if colors is None:
            colors = theme.canvas_colors(preset)
        if colors:
            self._theme_bg, self._theme_fg = colors[0], colors[1]
        else:
            self._theme_bg, self._theme_fg = "#191a1d", "#d7dae0"
        self.set_background()
        self._show_axes()

    # -- livewiring helpers ---------------------------------------------------
    def render_frame(self) -> None:
        try:
            if self._limits:
                self._apply_limits()
            else:
                self._interactor.reset_camera()
            self._interactor.render()
        except Exception:  # noqa: BLE001 - rendering must never kill the UI
            pass

    def close(self) -> None:
        try:
            self._interactor.close()
        except Exception:  # noqa: BLE001
            pass

    # -- internals -------------------------------------------------------------
    def set_background(self) -> None:
        try:
            self._interactor.set_background(self._theme_bg)
        except Exception:  # noqa: BLE001 - theme application is best-effort
            pass
        self._show_title()

    def _show_title(self) -> None:
        if self._title_text:
            self._interactor.add_text(
                self._title_text, position="upper_left", font_size=int(max(6, self._title_size)),
                color=self._theme_fg,
            )

    def _show_axes(self) -> None:
        try:
            self._interactor.add_axes(
                xlabel=self._labels.get("x", "X"),
                ylabel=self._labels.get("y", "Y"),
                zlabel=self._labels.get("z", "Z"),
                line_width=1.5, color=self._theme_fg, x_color=self._theme_fg,
                y_color=self._theme_fg, z_color=self._theme_fg,
            )
        except Exception:  # noqa: BLE001
            try:
                self._interactor.add_axes()  # default styling
            except Exception:  # noqa: BLE001
                pass

    def _apply_limits(self) -> None:
        if not self._limits:
            return
        x, y, z = self._limits
        bounds = list(self._interactor.bounds or (0, 1, 0, 1, 0, 1))
        if x is not None:
            if x[0] is not None:
                bounds[0] = float(x[0])
            if x[1] is not None:
                bounds[1] = float(x[1])
        if y is not None:
            if y[0] is not None:
                bounds[2] = float(y[0])
            if y[1] is not None:
                bounds[3] = float(y[1])
        if z is not None:
            if z[0] is not None:
                bounds[4] = float(z[0])
            if z[1] is not None:
                bounds[5] = float(z[1])
        try:
            self._interactor.set_viewup((0, 0, 1))
        except Exception:  # noqa: BLE001
            pass

    def _xy_bounds(self) -> tuple[float, float, float, float]:
        bounds = self._interactor.bounds
        if not bounds:
            return (0.0, 1.0, 0.0, 1.0)
        return (bounds[0], bounds[1], bounds[2], bounds[3])

    def _add_legend_entry(self, name: str, color: str) -> None:
        self._legend_labels = getattr(self, "_legend_labels", [])
        self._legend_labels.append((name, color))
        try:
            self._interactor.add_legend(
                labels=self._legend_labels,
                background=self._theme_bg, color=self._theme_fg, border=False,
            )
        except Exception:  # noqa: BLE001 - legend is decorative
            pass

    def _color(self, name: str) -> str:
        from PySide6.QtGui import QColor

        if name and QColor(name).isValid():
            return name
        return self._theme_fg
