"""pyqtgraph implementation of the plot canvas."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pyqtgraph as pg

from .base import PlotCanvas

# A small, colour-blind-friendly default cycle.
_COLORS = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf")


class PyQtGraphCanvas(PlotCanvas):
    """A pyqtgraph-backed 2D canvas."""

    def __init__(self) -> None:
        self._widget = pg.PlotWidget()
        self._widget.setBackground("w")
        self._widget.showGrid(x=True, y=True, alpha=0.25)
        self._plot_item = self._widget.getPlotItem()
        self._legend = None
        self._index = 0

    # -- PlotCanvas ----------------------------------------------------------
    def widget(self):
        return self._widget

    def clear(self) -> None:
        self._plot_item.clear()
        if self._legend is not None:
            self._legend.clear()
        self._index = 0

    def plot_xy(self, x: Sequence[float], y: Sequence[float], *, name: str | None = None) -> Any:
        xs = np.asarray(x, dtype=float)
        ys = np.asarray(y, dtype=float)
        n = min(xs.size, ys.size)
        xs, ys = xs[:n], ys[:n]
        pen = pg.mkPen(_COLORS[self._index % len(_COLORS)], width=2)

        kwargs: dict[str, Any] = {}
        if name:
            kwargs["name"] = name
            if self._legend is None:
                self._legend = self._plot_item.addLegend()

        item = self._plot_item.plot(xs, ys, pen=pen, **kwargs)
        self._index += 1
        return item

    def set_title(self, text: str) -> None:
        self._plot_item.setTitle(text)

    def set_labels(self, *, bottom: str | None = None, left: str | None = None) -> None:
        if bottom:
            self._plot_item.setLabel("bottom", bottom)
        if left:
            self._plot_item.setLabel("left", left)
