"""matplotlib implementation of the plot canvas (WYSIWYG).

Because the live canvas and the publication exporter both render through
matplotlib, what you see on screen is exactly what you get on export.
"""

from __future__ import annotations

import numpy as np

from .base import PlotCanvas

_LINESTYLES = {
    "solid": "-",
    "dash": "--",
    "dot": ":",
    "dashdot": "-.",
    "longdash": (0, (8, 3)),
}


def _ls(name: str) -> object:
    return _LINESTYLES.get((name or "solid").lower(), "-")


class MatplotlibCanvas(PlotCanvas):
    """A matplotlib FigureCanvasQTAgg-backed 2D canvas."""

    def __init__(self) -> None:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        self._fig = Figure()
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._toolbar = NavigationToolbar2QT(self._canvas, None)
        # Keep the toolbar buttons flat so they sit flush with the themed
        # background instead of showing rounded, bordered boxes with gaps.
        self._toolbar.setStyleSheet(
            "QToolButton, QPushButton { border: none; border-radius: 0; "
            "background: transparent; padding: 2px; }"
            "QToolButton:hover, QPushButton:hover { background: rgba(128,128,128,0.15); }"
        )
        self._container = QWidget()
        lay = QVBoxLayout(self._container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._toolbar)
        lay.addWidget(self._canvas)
        self._grid_rows = 1
        self._grid_cols = 1
        self._ax_left = self._fig.add_subplot(111)
        self._axes = [self._ax_left]
        self._current_panel = 0
        self._ax_right = None
        self._series: list[tuple[np.ndarray, np.ndarray, str]] = []
        self._hover_enabled = False
        self._hover_cid = None
        self._canvas.mpl_connect("button_press_event", self._on_button_press)
        self.label_click_callback = None
        self._cross_v = None
        self._cross_h = None
        self._readout = None
        self.set_theme("classic-dark")

    # -- PlotCanvas ---------------------------------------------------------
    def widget(self):
        return self._container

    def clear(self) -> None:
        self._fig.clear()
        rows = max(1, getattr(self, "_grid_rows", 1))
        cols = max(1, getattr(self, "_grid_cols", 1))
        if rows * cols > 1:
            axes = self._fig.subplots(rows, cols, squeeze=False)
            self._axes = [ax for row in axes for ax in row]
        else:
            self._axes = [self._fig.add_subplot(111)]
        self._ax_left = self._axes[0]
        self._ax_right = None
        self._series = []
        self._cross_v = None
        self._cross_h = None
        self._readout = None
        # re-apply theme colours to the fresh axes
        try:
            self.set_theme(self._last_theme)
        except Exception:
            pass
        self._canvas.draw_idle()

    def set_grid(self, rows: int = 1, cols: int = 1) -> None:
        self._grid_rows = max(1, rows)
        self._grid_cols = max(1, cols)
        self.clear()

    def set_current_panel(self, index: int) -> None:
        if self._axes:
            self._current_panel = index % len(self._axes)
            self._ax_left = self._axes[self._current_panel]
            self._ax_right = None

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
        from types import SimpleNamespace

        from graphmatrix.core.io.export import render_xyz_mpl
        from graphmatrix.core.model import PlotStyle, Z_STYLES

        ax = self._ax_left
        if y_axis == "right":
            if self._ax_right is None:
                self._ax_right = self._ax_left.twinx()
            ax = self._ax_right

        xs = np.asarray(x, dtype=float)
        ys = np.asarray(y, dtype=float)
        order = np.argsort(xs)
        xs_s = xs[order]
        ys_s = ys[order]
        col = color or None
        ls = _ls(line_style)
        lbl = name
        marker = symbol if symbol else None
        ms = symbol_size * 0.6

        plot_style = PlotStyle(style)

        if plot_style in Z_STYLES:
            # The shared renderer keeps the live canvas and the exporter in
            # lockstep. On the flat canvas a 3D style degrades to a colour-mapped
            # 2D scatter; GraphView routes 3D graphs to the PyVista canvas.
            render_xyz_mpl(
                ax, self._fig, plot_style,
                SimpleNamespace(
                    x=np.asarray(x, float), y=np.asarray(y, float),
                    z=None if z is None else np.asarray(z, float), legend=lbl,
                ),
                cmap="viridis", color=col or "",
                width=width, symbol=symbol, symbol_size=symbol_size,
                line_style=ls, label=lbl, z_label="Value",
            )
            try:
                self._fig.tight_layout()
            except Exception:  # noqa: BLE001
                pass
            self._canvas.draw_idle()
            return

        if style == "scatter":
            ax.plot(xs, ys, linestyle="none", marker=marker or "o", markersize=ms,
                    color=col, label=lbl)
        elif style == "line":
            ax.plot(xs, ys, color=col, linewidth=width, linestyle=ls, label=lbl)
        elif style == "line+symbol" or style == "line_symbol":
            ax.plot(xs, ys, color=col, linewidth=width, marker=marker or "o",
                    markersize=ms, linestyle=ls, label=lbl)
        elif style == "bar":
            ax.bar(xs, ys, color=col, label=lbl)
        elif style == "area":
            ax.fill_between(xs, ys, alpha=0.3, color=col)
            ax.plot(xs, ys, color=col, linewidth=width, linestyle=ls, label=lbl)
        elif style == "step":
            ax.step(xs, ys, where="mid", color=col, linewidth=width, linestyle=ls, label=lbl)
        elif style == "errorbar" or style == "error bar":
            ax.errorbar(xs, ys, yerr=yerr, xerr=xerr, color=col,
                        linewidth=width, linestyle=ls, marker=marker or "o",
                        markersize=ms, capsize=3, label=lbl)
        else:
            ax.plot(xs, ys, color=col, linewidth=width, linestyle=ls, label=lbl)

        if yerr is not None and style not in ("errorbar", "error bar"):
            ax.errorbar(xs, ys, yerr=yerr, color=col, linestyle="none", marker=marker or "o",
                        markersize=ms, capsize=3, label=None)

        self._series.append((xs_s, ys_s, name or ""))
        self._canvas.draw_idle()

    def add_reference_line(self, orientation, position, *, color="#888888",
                           width=1.5, line_style="dash", label="") -> None:
        ax = self._ax_left
        ls = _ls(line_style)
        if orientation == "v":
            line = ax.axvline(position, color=color, linewidth=width, linestyle=ls)
        else:
            line = ax.axhline(position, color=color, linewidth=width, linestyle=ls)
        if label:
            try:
                xmin, xmax = ax.get_xlim()
                ymin, ymax = ax.get_ylim()
            except Exception:
                xmin, xmax, ymin, ymax = 0, 1, 0, 1
            pad = 0.01 * (ymax - ymin if ymax != ymin else 1.0)
            if orientation == "v":
                ax.text(position, ymax - pad, label, color=color, fontsize=8,
                        ha="left", va="top", rotation=90)
            else:
                ax.text(xmax, position, label, color=color, fontsize=8,
                        ha="right", va="bottom")
        self._canvas.draw_idle()

    def set_hover(self, enabled: bool) -> None:
        self._hover_enabled = bool(enabled)
        if enabled and self._hover_cid is None:
            self._hover_cid = self._canvas.mpl_connect("motion_notify_event", self._on_hover)
        elif (not enabled) and self._hover_cid is not None:
            self._canvas.mpl_disconnect(self._hover_cid)
            self._hover_cid = None
            self._remove_crosshair()
            self._canvas.draw_idle()

    def add_annotation(self, text, x, y, *, color="#000000", size=11.0) -> None:
        ax = self._ax_left
        ax.text(x, y, text, transform=ax.transAxes, color=color, fontsize=size,
                ha="left", va="top")
        self._canvas.draw_idle()

    def set_title(self, text: str, *, fontfamily: str = "", fontsize: float = 14.0,
                  color: str = "") -> None:
        kwargs = {"fontsize": fontsize or 14.0}
        if fontfamily:
            kwargs["fontfamily"] = fontfamily
        if color:
            kwargs["color"] = color
        self._fig.suptitle(text, **kwargs)
        self._canvas.draw_idle()

    def set_labels(self, *, bottom=None, left=None, right=None,
                   fontfamily: str = "", fontsize: float = 12.0, color: str = "") -> None:
        kwargs = {"fontsize": fontsize or 12.0}
        if fontfamily:
            kwargs["fontfamily"] = fontfamily
        if color:
            kwargs["color"] = color
        if bottom is not None:
            self._ax_left.set_xlabel(bottom, **kwargs)
        if left is not None:
            self._ax_left.set_ylabel(left, **kwargs)
        if right is not None:
            if self._ax_right is None:
                self._ax_right = self._ax_left.twinx()
            self._ax_right.set_ylabel(right, **kwargs)
        self._canvas.draw_idle()

    def set_scales(self, *, x: str = "linear", y: str = "linear") -> None:
        self._ax_left.set_xscale(x)
        self._ax_left.set_yscale(y)
        if self._ax_right is not None:
            self._ax_right.set_yscale(y)
        self._canvas.draw_idle()

    def set_ticks(self, *, minor: bool = True, direction: str = "out") -> None:
        if minor:
            self._ax_left.minorticks_on()
            if self._ax_right is not None:
                self._ax_right.minorticks_on()
        else:
            # turn minor ticks off by clearing minor locators
            from matplotlib.ticker import NullLocator

            self._ax_left.xaxis.set_minor_locator(NullLocator())
            self._ax_left.yaxis.set_minor_locator(NullLocator())
            if self._ax_right is not None:
                self._ax_right.yaxis.set_minor_locator(NullLocator())
        for _ax in (self._ax_left, self._ax_right):
            if _ax is None:
                continue
            _ax.tick_params(which="both", direction=direction or "out")
        self._canvas.draw_idle()

    def set_limits(self, *, x=None, y=None) -> None:
        if x is not None:
            self._ax_left.set_xlim(left=x[0], right=x[1])
        if y is not None:
            self._ax_left.set_ylim(bottom=y[0], top=y[1])
        self._canvas.draw_idle()

    def show_legend(self, flag: bool) -> None:
        # remove existing legend
        leg = self._ax_left.get_legend()
        if leg is not None:
            leg.remove()
        if flag:
            handles, labels = self._ax_left.get_legend_handles_labels()
            if self._ax_right is not None:
                h2, l2 = self._ax_right.get_legend_handles_labels()
                handles = handles + h2
                labels = labels + l2
            if labels:
                self._ax_left.legend(handles, labels, loc="best", frameon=False)
        self._canvas.draw_idle()

    def set_downsampling(self, flag: bool) -> None:
        self._downsample = bool(flag)

    def set_theme(self, preset: str) -> None:
        self._last_theme = preset
        from graphmatrix.ui import theme
        from graphmatrix.ui import plot_themes

        colors = plot_themes.canvas_colors(preset)
        if colors is None:
            bg, fg, grid_alpha = theme.canvas_colors(preset)
        else:
            bg, fg, grid_alpha = colors
        self._fig.patch.set_facecolor(bg)
        self._ax_left.set_facecolor(bg)
        if self._ax_right is not None:
            self._ax_right.set_facecolor(bg)
        for ax in (self._ax_left, self._ax_right):
            if ax is None:
                continue
            ax.tick_params(colors=fg)
            if ax.xaxis.label is not None:
                ax.xaxis.label.set_color(fg)
            if ax.yaxis.label is not None:
                ax.yaxis.label.set_color(fg)
            for spine in ax.spines.values():
                spine.set_color(fg)
            ax.grid(True, alpha=grid_alpha, color=fg)
        self._canvas.draw_idle()

    # -- hover helpers ------------------------------------------------------
    def _on_hover(self, event) -> None:
        if not self._hover_enabled:
            return
        if event.inaxes not in (self._ax_left, self._ax_right):
            return
        ax = self._ax_left
        if self._cross_v is None:
            self._cross_v = ax.axvline(event.xdata, color="gray", linewidth=0.5, alpha=0.5)
            self._cross_h = ax.axhline(event.ydata, color="gray", linewidth=0.5, alpha=0.5)
        else:
            self._cross_v.set_xdata([event.xdata, event.xdata])
            self._cross_h.set_ydata([event.ydata, event.ydata])

        best = None
        for xs, ys, name in self._series:
            if xs.size == 0:
                continue
            idx = int(np.searchsorted(xs, event.xdata))
            for cand in (idx - 1, idx):
                if 0 <= cand < xs.size:
                    dist = abs(float(xs[cand]) - float(event.xdata))
                    if best is None or dist < best[0]:
                        best = (dist, float(xs[cand]), float(ys[cand]), name)
        if best is not None:
            if self._readout is None:
                self._readout = ax.text(0.02, 0.98, "", transform=ax.transAxes,
                                        va="top", ha="left", fontsize=9,
                                        color=ax.xaxis.label.get_color())
            self._readout.set_text(f"{best[3]}: x={best[1]:.4g}, y={best[2]:.4g}")
        self._canvas.draw_idle()

    def _remove_crosshair(self) -> None:
        for attr in ("_cross_v", "_cross_h"):
            obj = getattr(self, attr)
            if obj is not None:
                try:
                    obj.remove()
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._readout is not None:
            try:
                self._readout.remove()
            except Exception:
                pass
            self._readout = None

    def _on_button_press(self, event) -> None:
        try:
            if event.inaxes is not None and callable(self.label_click_callback):
                # Axis area (not a label) -> focus the axes property group.
                for name, artist in (("title", getattr(self._fig, "_suptitle", None)),
                                     ("xlabel", self._ax_left.xaxis.label),
                                     ("ylabel", self._ax_left.yaxis.label)):
                    if artist is not None:
                        contains, _ = artist.contains(event)
                        if contains:
                            self.label_click_callback(name)
                            return
                self.label_click_callback("axes")
        except Exception:  # noqa: BLE001
            pass
        if getattr(event, "dblclick", False):
            try:
                self._ax_left.autoscale()
                if self._ax_right is not None:
                    self._ax_right.autoscale()
            except Exception:
                pass
            self._canvas.draw_idle()
