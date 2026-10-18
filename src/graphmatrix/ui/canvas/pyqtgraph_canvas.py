"""pyqtgraph implementation of the plot canvas.

Supports a secondary Y axis (a second :class:`pyqtgraph.ViewBox` linked on X),
text annotations in axes-fraction coordinates, and automatic level-of-detail
downsampling for large series.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt

from .base import PlotCanvas
from .. import theme

PALETTE = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd",
           "#ff7f0e", "#17becf", "#8c564b", "#e377c2")

_PEN_STYLES = {
    "solid": Qt.PenStyle.SolidLine,
    "dash": Qt.PenStyle.DashLine,
    "dot": Qt.PenStyle.DotLine,
    "dashdot": Qt.PenStyle.DashDotLine,
    "longdash": Qt.PenStyle.DashDotDotLine,
}


def _pen_style(name: str) -> Qt.PenStyle:
    return _PEN_STYLES.get((name or "solid").lower(), Qt.PenStyle.SolidLine)


class PyQtGraphCanvas(PlotCanvas):
    """A pyqtgraph-backed 2D canvas."""

    def __init__(self) -> None:
        pg.setConfigOptions(antialias=True)
        self._widget = pg.PlotWidget()
        self._plot_item = self._widget.getPlotItem()
        self._main_view = self._plot_item.getViewBox()
        self._legend = None
        self._legend_right = None
        self._legend_visible = True
        self._index = 0
        self._annotations: list[Any] = []
        self._ref_lines: list[Any] = []
        self._series: list[tuple[str, np.ndarray, np.ndarray, bool]] = []
        self._downsampling = True
        self._title = ""
        self._fg = "#202124"

        # Hover readout: created lazily so the cost is zero when it is off.
        self._hover_enabled = False
        self._crosshair_v: Any = None
        self._crosshair_h: Any = None
        self._hover_label: Any = None
        self._hover_marker: Any = None
        self._hover_proxy: Any = None

        # Secondary Y axis: a parallax ViewBox sharing the X range. It is hidden
        # until a plot (or a label) actually targets the right axis.
        self._view_right = pg.ViewBox()
        self._plot_item.showAxis("right")
        self._plot_item.hideAxis("right")
        self._plot_item.scene().addItem(self._view_right)
        self._plot_item.getAxis("right").linkToView(self._view_right)
        self._view_right.setXLink(self._plot_item)
        self._main_view.sigResized.connect(self._sync_right_view)
        self._sync_right_view()
        self.set_downsampling(True)
        self.set_theme(theme.current_preset())

        # Double-clicking the canvas resets the view to its original (full) range.
        try:
            self._widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)
        except Exception:  # noqa: BLE001
            pass

    def _sync_right_view(self) -> None:
        self._view_right.setGeometry(self._main_view.sceneBoundingRect())
        self._view_right.linkedViewChanged(self._main_view, self._view_right.XAxis)

    def _on_mouse_clicked(self, ev) -> None:
        try:
            if ev.double():
                self._main_view.autoRange()
                if self._view_right is not None:
                    self._view_right.autoRange()
        except Exception:  # noqa: BLE001
            pass

    def _container(self, right: bool):
        return self._view_right if right else self._plot_item

    # -- PlotCanvas ----------------------------------------------------------
    def widget(self):
        return self._widget

    def clear(self) -> None:
        self._plot_item.clear()
        self._plot_item.hideAxis("right")
        for item in list(self._annotations):
            try:
                self._main_view.removeItem(item)
            except Exception:  # noqa: BLE001
                pass
        self._annotations.clear()
        for item in list(self._ref_lines):
            try:
                self._main_view.removeItem(item)
            except Exception:  # noqa: BLE001
                pass
        self._ref_lines.clear()
        self._series.clear()
        self._teardown_hover()
        for item in list(self._view_right.addedItems):
            if item is self._legend_right:
                continue
            self._view_right.removeItem(item)
        if self._legend is not None:
            self._legend.clear()
        if self._legend_right is not None:
            self._legend_right.clear()
        self._index = 0

    def _ensure_legend(self, right: bool) -> None:
        if right:
            if self._legend_right is None:
                self._legend_right = pg.LegendItem(offset=(10, 10))
                # A LegendItem needs a parent with geometryChanged, so anchor it to
                # the PlotItem rather than the (ChildGroup) ViewBox.
                self._legend_right.setParentItem(self._plot_item)
                self._legend_right.anchor((1, 0), (1, 0), offset=(-10, 10))
            self._legend_right.setVisible(self._legend_visible)
        else:
            if self._legend is None:
                self._legend = self._plot_item.addLegend()
            self._legend.setVisible(self._legend_visible)

    def plot(
        self, x: Sequence[float], y: Sequence[float], *,
        style: str = "line", color: str = "", width: float = 2.0,
        symbol: str = "o", symbol_size: float = 7.0, name: str | None = None,
        yerr: Sequence[float] | None = None, xerr: Sequence[float] | None = None,
        y_axis: str = "left", line_style: str = "solid",
        z: Sequence[float] | None = None,
    ) -> Any:
        # The legacy 2D pyqtgraph backend has no Z-carrying styles; GraphView
        # routes those graphs to matplotlib or the PyVista canvas instead.
        xs = np.asarray(x, dtype=float)
        ys = np.asarray(y, dtype=float)
        n = min(xs.size, ys.size)
        xs, ys = xs[:n], ys[:n]
        right = y_axis == "right"
        if right:
            self._plot_item.showAxis("right")
        pen_color = color or PALETTE[self._index % len(PALETTE)]
        pen = pg.mkPen(pen_color, width=width, style=_pen_style(line_style))
        brush = pg.mkBrush(pen_color)
        self._record_series(name, xs, ys, right)

        if name:
            self._ensure_legend(right)
        symbol_kwargs = dict(symbol=symbol, symbolSize=symbol_size,
                             symbolBrush=brush, symbolPen=pen) if symbol else {}

        def curve(**kwargs: Any):
            if right:
                item = pg.PlotDataItem(xs, ys, **kwargs)
                self._view_right.addItem(item)
                if name and self._legend_right is not None:
                    self._legend_right.addItem(item, name)
                return item
            return self._plot_item.plot(xs, ys, name=name, **kwargs)

        if style == "scatter":
            item = curve(pen=None, **symbol_kwargs)
        elif style == "line":
            item = curve(pen=pen)
        elif style in ("line+symbol", ""):
            item = curve(pen=pen, **symbol_kwargs)
        elif style == "step":
            item = curve(pen=pen, stepMode="center")
        elif style == "area":
            item = curve(pen=pen, fillLevel=0,
                         brush=pg.mkBrush(pen_color + "55") if len(pen_color) == 7 else brush)
        elif style == "bar":
            width_ = float(np.median(np.diff(xs))) * 0.8 if xs.size > 1 else 0.8
            item = pg.BarGraphItem(x=xs, height=ys, width=width_, brush=brush, pen=pen)
            self._container(right).addItem(item)
        elif style == "errorbar":
            item = curve(pen=pen, **symbol_kwargs)
            self._add_error_bars(xs, ys, yerr, xerr, pen, right)
        else:
            item = curve(pen=pen)

        self._index += 1
        return item

    def _add_error_bars(self, xs, ys, yerr, xerr, pen, right: bool) -> None:
        kw: dict[str, Any] = {"pen": pen, "beam": 0.0}
        if yerr is not None:
            ye = np.asarray(yerr, float)[:xs.size]
            kw["top"] = ye
            kw["bottom"] = ye
        if xerr is not None:
            xe = np.asarray(xerr, float)[:xs.size]
            kw["left"] = xe
            kw["right"] = xe
        if len(kw) > 2:
            self._container(right).addItem(pg.ErrorBarItem(x=xs, y=ys, **kw))

    def add_annotation(self, text: str, x: float, y: float, *, color: str = "#000000",
                       size: float = 11.0) -> None:
        item = pg.TextItem(text, color=color, anchor=(0, 1))
        item.setParentItem(self._main_view)
        xr, yr = self._main_view.viewRange()
        item.setPos(xr[0] + x * (xr[1] - xr[0]), yr[0] + y * (yr[1] - yr[0]))
        self._main_view.addItem(item, ignoreBounds=True)
        self._annotations.append(item)

    def _record_series(self, name: str | None, xs: np.ndarray, ys: np.ndarray, right: bool) -> None:
        """Keep an x-sorted copy of each series so hover search is O(log n)."""
        if xs.size == 0:
            return
        finite = np.isfinite(xs) & np.isfinite(ys)
        xs, ys = xs[finite], ys[finite]
        if xs.size == 0:
            return
        order = np.argsort(xs, kind="stable")
        self._series.append((name or "", xs[order], ys[order], right))

    def add_reference_line(
        self, orientation: str, position: float, *,
        color: str = "#888888", width: float = 1.5,
        line_style: str = "dash", label: str = "",
    ) -> None:
        angle = 90 if orientation == "v" else 0
        pen = pg.mkPen(color, width=width, style=_pen_style(line_style))
        kwargs: dict[str, Any] = {}
        if label:
            kwargs["label"] = label
            kwargs["labelOpts"] = {"color": color, "position": 0.96}
        item = pg.InfiniteLine(pos=float(position), angle=angle, movable=False, pen=pen, **kwargs)
        self._main_view.addItem(item, ignoreBounds=True)
        self._ref_lines.append(item)

    # -- hover readout -------------------------------------------------------
    def set_hover(self, enabled: bool) -> None:
        self._hover_enabled = bool(enabled)
        if self._hover_enabled:
            self._ensure_hover()
        else:
            self._show_hover(None)

    def _ensure_hover(self) -> None:
        if self._crosshair_v is None:
            pen = pg.mkPen(self._fg, width=1, style=Qt.PenStyle.DashLine)
            self._crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pen)
            self._crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pen)
            self._hover_label = pg.TextItem("", color=self._fg, anchor=(0, 1))
            self._hover_marker = pg.ScatterPlotItem(
                size=9, symbol="o", pen=pg.mkPen(self._fg, width=1),
                brush=pg.mkBrush(255, 196, 0, 220))
            for item in (self._crosshair_v, self._crosshair_h, self._hover_label, self._hover_marker):
                self._main_view.addItem(item, ignoreBounds=True)
        if self._hover_proxy is None:
            self._hover_proxy = pg.SignalProxy(
                self._plot_item.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved)
        self._show_hover(None)

    def _teardown_hover(self) -> None:
        for item in (self._crosshair_v, self._crosshair_h, self._hover_label, self._hover_marker):
            if item is None:
                continue
            try:
                self._main_view.removeItem(item)
            except Exception:  # noqa: BLE001
                pass
        self._crosshair_v = self._crosshair_h = self._hover_label = self._hover_marker = None

    def _show_hover(self, point: tuple[float, float, str] | None) -> None:
        if self._crosshair_v is None:
            return
        if point is None:
            self._crosshair_v.setVisible(False)
            self._crosshair_h.setVisible(False)
            self._hover_label.setVisible(False)
            self._hover_marker.setVisible(False)
            return
        x, y, name = point
        self._crosshair_v.setPos(x)
        self._crosshair_h.setPos(y)
        self._hover_marker.setData([x], [y])
        text = f"{x:.6g}, {y:.6g}"
        if name:
            text = f"{name}\n{text}"
        self._hover_label.setText(text)
        self._hover_label.setPos(x, y)
        for item in (self._crosshair_v, self._crosshair_h, self._hover_label, self._hover_marker):
            item.setVisible(True)

    def _on_mouse_moved(self, event) -> None:
        if not self._hover_enabled or self._crosshair_v is None:
            return
        try:
            scene_pos = event[0]
        except (TypeError, IndexError):
            return
        if not self._plot_item.sceneBoundingRect().contains(scene_pos):
            self._show_hover(None)
            return
        view_pos = self._main_view.mapSceneToView(scene_pos)
        best: tuple[float, float, float, str] | None = None
        for name, xs, ys, right in self._series:
            container = self._view_right if right else self._main_view
            (x0, x1), (y0, y1) = container.viewRange()
            span_x = (x1 - x0) or 1.0
            span_y = (y1 - y0) or 1.0
            idx = int(np.searchsorted(xs, view_pos.x()))
            for j in (idx - 1, idx, idx + 1):
                if j < 0 or j >= xs.size:
                    continue
                jx = xs[j]
                if not np.isfinite(jx) or not np.isfinite(ys[j]):
                    continue
                distance = (((jx - view_pos.x()) / span_x) ** 2
                            + ((ys[j] - view_pos.y()) / span_y) ** 2)
                if best is None or distance < best[0]:
                    best = (float(distance), float(jx), float(ys[j]), name)
        if best is None:
            self._show_hover(None)
        else:
            self._show_hover((best[1], best[2], best[3]))

    def set_title(self, text: str, *, fontfamily: str = "", fontsize: float = 14.0,
                  color: str = "") -> None:
        self._title = text
        self._plot_item.setTitle(text, color=color or self._fg, size=f"{int(fontsize)}pt")

    def set_grid(self, rows: int = 1, cols: int = 1) -> None:
        pass

    def set_current_panel(self, index: int) -> None:
        pass

    def set_labels(self, *, bottom: str | None = None, left: str | None = None,
                   right: str | None = None, fontfamily: str = "",
                   fontsize: float = 12.0, color: str = "") -> None:
        if bottom:
            self._plot_item.setLabel("bottom", bottom)
        if left:
            self._plot_item.setLabel("left", left)
        if right:
            self._plot_item.showAxis("right")
            self._plot_item.setLabel("right", right)

    def set_scales(self, *, x: str = "linear", y: str = "linear") -> None:
        self._plot_item.setLogMode(x=(x == "log"), y=(y == "log"))

    def set_ticks(self, *, minor: bool = True, direction: str = "out") -> None:
        return

    def set_limits(self, *, x=None, y=None) -> None:
        if x is not None and any(v is not None for v in x):
            self._plot_item.setXRange(x[0] if x[0] is not None else self._main_view.viewRange()[0][0],
                                      x[1] if x[1] is not None else self._main_view.viewRange()[0][1], padding=0)
        if y is not None and any(v is not None for v in y):
            then = self._main_view.viewRange()[1]
            self._plot_item.setYRange(y[0] if y[0] is not None else then[0],
                                      y[1] if y[1] is not None else then[1], padding=0)

    def show_legend(self, flag: bool) -> None:
        self._legend_visible = flag
        if self._legend is not None:
            self._legend.setVisible(flag)
        if self._legend_right is not None:
            self._legend_right.setVisible(flag)

    def set_downsampling(self, flag: bool) -> None:
        self._downsampling = flag
        try:
            self._plot_item.setDownsampling(auto=flag, mode="peak")
            self._plot_item.setClipToView(flag)
        except Exception:  # noqa: BLE001 - optional optimisation, never fatal
            pass

    def set_theme(self, preset: str) -> None:
        bg, fg, grid_alpha = theme.canvas_colors(preset)
        self._fg = fg
        try:
            pg.setConfigOptions(background=bg, foreground=fg)
        except Exception:  # noqa: BLE001
            pass
        self._widget.setBackground(bg)
        self._widget.showGrid(x=True, y=True, alpha=grid_alpha)
        pen = pg.mkPen(fg, width=1)
        text_pen = pg.mkPen(fg)
        for name in ("left", "bottom", "right", "top"):
            axis = self._plot_item.getAxis(name)
            axis.setPen(pen)
            axis.setTextPen(text_pen)
        try:
            self._plot_item.setTitle(self._title, color=fg)
        except Exception:  # noqa: BLE001
            pass
        for legend in (self._legend, self._legend_right):
            if legend is None:
                continue
            try:
                legend.setLabelTextColor(fg)
            except Exception:  # noqa: BLE001
                pass
        if self._crosshair_v is not None:
            pen = pg.mkPen(fg, width=1, style=Qt.PenStyle.DashLine)
            self._crosshair_v.setPen(pen)
            self._crosshair_h.setPen(pen)
            self._hover_label.setColor(fg)
