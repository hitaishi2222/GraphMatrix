"""pyqtgraph implementation of the plot canvas.

Supports a secondary Y axis (a second :class:`pyqtgraph.ViewBox` linked on X),
text annotations in axes-fraction coordinates, and automatic level-of-detail
downsampling for large series.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pyqtgraph as pg

from .base import PlotCanvas

PALETTE = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd",
           "#ff7f0e", "#17becf", "#8c564b", "#e377c2")


class PyQtGraphCanvas(PlotCanvas):
    """A pyqtgraph-backed 2D canvas."""

    def __init__(self) -> None:
        pg.setConfigOptions(antialias=True)
        self._widget = pg.PlotWidget()
        self._widget.setBackground("w")
        self._widget.showGrid(x=True, y=True, alpha=0.25)
        self._plot_item = self._widget.getPlotItem()
        self._main_view = self._plot_item.getViewBox()
        self._legend = None
        self._legend_right = None
        self._legend_visible = True
        self._index = 0
        self._annotations: list[Any] = []
        self._downsampling = True

        # Secondary Y axis: a parallax ViewBox sharing the X range.
        self._view_right = pg.ViewBox()
        self._plot_item.showAxis("right")
        self._plot_item.scene().addItem(self._view_right)
        self._plot_item.getAxis("right").linkToView(self._view_right)
        self._view_right.setXLink(self._plot_item)
        self._main_view.sigResized.connect(self._sync_right_view)
        self._sync_right_view()
        self.set_downsampling(True)

    def _sync_right_view(self) -> None:
        self._view_right.setGeometry(self._main_view.sceneBoundingRect())
        self._view_right.linkedViewChanged(self._main_view, self._view_right.XAxis)

    def _container(self, right: bool):
        return self._view_right if right else self._plot_item

    # -- PlotCanvas ----------------------------------------------------------
    def widget(self):
        return self._widget

    def clear(self) -> None:
        self._plot_item.clear()
        for item in list(self._annotations):
            try:
                self._main_view.removeItem(item)
            except Exception:  # noqa: BLE001
                pass
        self._annotations.clear()
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
        y_axis: str = "left",
    ) -> Any:
        xs = np.asarray(x, dtype=float)
        ys = np.asarray(y, dtype=float)
        n = min(xs.size, ys.size)
        xs, ys = xs[:n], ys[:n]
        right = y_axis == "right"
        pen_color = color or PALETTE[self._index % len(PALETTE)]
        pen = pg.mkPen(pen_color, width=width)
        brush = pg.mkBrush(pen_color)

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

    def set_title(self, text: str) -> None:
        self._plot_item.setTitle(text)

    def set_labels(self, *, bottom: str | None = None, left: str | None = None,
                   right: str | None = None) -> None:
        if bottom:
            self._plot_item.setLabel("bottom", bottom)
        if left:
            self._plot_item.setLabel("left", left)
        if right:
            self._plot_item.setLabel("right", right)

    def set_scales(self, *, x: str = "linear", y: str = "linear") -> None:
        self._plot_item.setLogMode(x=(x == "log"), y=(y == "log"))

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
