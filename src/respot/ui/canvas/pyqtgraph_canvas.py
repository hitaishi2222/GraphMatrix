"""pyqtgraph implementation of the plot canvas."""

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
        self._legend = None
        self._legend_visible = True
        self._index = 0

    # -- PlotCanvas ----------------------------------------------------------
    def widget(self):
        return self._widget

    def clear(self) -> None:
        self._plot_item.clear()
        if self._legend is not None:
            self._legend.clear()
        self._index = 0

    def plot(
        self, x: Sequence[float], y: Sequence[float], *,
        style: str = "line", color: str = "", width: float = 2.0,
        symbol: str = "o", symbol_size: float = 7.0, name: str | None = None,
        yerr: Sequence[float] | None = None, xerr: Sequence[float] | None = None,
    ) -> Any:
        xs = np.asarray(x, dtype=float)
        ys = np.asarray(y, dtype=float)
        n = min(xs.size, ys.size)
        xs, ys = xs[:n], ys[:n]
        pen_color = color or PALETTE[self._index % len(PALETTE)]
        pen = pg.mkPen(pen_color, width=width)
        brush = pg.mkBrush(pen_color)

        kwargs: dict[str, Any] = {}
        if name:
            kwargs["name"] = name
            if self._legend is None:
                self._legend = self._plot_item.addLegend()
                self._legend.setVisible(self._legend_visible)
        symbol_kwargs = dict(symbol=symbol, symbolSize=symbol_size,
                             symbolBrush=brush, symbolPen=pen) if symbol else {}

        if style == "scatter":
            item = self._plot_item.plot(xs, ys, pen=None, **symbol_kwargs, **kwargs)
        elif style == "line":
            item = self._plot_item.plot(xs, ys, pen=pen, **kwargs)
        elif style in ("line+symbol", ""):
            item = self._plot_item.plot(xs, ys, pen=pen, **symbol_kwargs, **kwargs)
        elif style == "step":
            item = self._plot_item.plot(xs, ys, pen=pen, stepMode="center", **kwargs)
        elif style == "area":
            item = self._plot_item.plot(xs, ys, pen=pen, fillLevel=0, brush=pg.mkBrush(pen_color + "55") if len(pen_color) == 7 else brush, **kwargs)
        elif style == "bar":
            width_ = float(np.median(np.diff(xs))) * 0.8 if xs.size > 1 else 0.8
            item = pg.BarGraphItem(x=xs, height=ys, width=width_, brush=brush, pen=pen)
            self._plot_item.addItem(item)
            if name:
                self._legend_note(item, name)
        elif style == "errorbar":
            item = self._plot_item.plot(xs, ys, pen=pen, **symbol_kwargs, **kwargs)
            self._add_error_bars(xs, ys, yerr, xerr, pen)
        else:
            item = self._plot_item.plot(xs, ys, pen=pen, **kwargs)

        self._index += 1
        return item

    def _add_error_bars(self, xs, ys, yerr, xerr, pen) -> None:
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
            self._plot_item.addItem(pg.ErrorBarItem(x=xs, y=ys, **kw))

    def _legend_note(self, item, name: str) -> None:
        if self._legend is None:
            self._legend = self._plot_item.addLegend()
            self._legend.setVisible(self._legend_visible)

    def set_title(self, text: str) -> None:
        self._plot_item.setTitle(text)

    def set_labels(self, *, bottom: str | None = None, left: str | None = None) -> None:
        if bottom:
            self._plot_item.setLabel("bottom", bottom)
        if left:
            self._plot_item.setLabel("left", left)

    def set_scales(self, *, x: str = "linear", y: str = "linear") -> None:
        self._plot_item.setLogMode(x=(x == "log"), y=(y == "log"))

    def set_limits(self, *, x=None, y=None) -> None:
        if x is not None and any(v is not None for v in x):
            self._plot_item.setXRange(x[0] if x[0] is not None else self._plot_item.viewRange()[0][0],
                                      x[1] if x[1] is not None else self._plot_item.viewRange()[0][1], padding=0)
        if y is not None and any(v is not None for v in y):
            self._plot_item.setYRange(y[0] if y[0] is not None else self._plot_item.viewRange()[1][0],
                                      y[1] if y[1] is not None else self._plot_item.viewRange()[1][1], padding=0)

    def show_legend(self, flag: bool) -> None:
        self._legend_visible = flag
        if self._legend is not None:
            self._legend.setVisible(flag)
