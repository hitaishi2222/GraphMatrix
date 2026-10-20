"""matplotlib implementation of the plot canvas (WYSIWYG).

Because the live canvas and the publication exporter both render through
matplotlib, what you see on screen is exactly what you get on export.

The figure sits on a *workspace* like a sheet of paper on a desk: the
surrounding area belongs to the application, the figure itself is a clearly
bounded surface ("artboard"). That makes it obvious which part of the screen
is the figure, and that part is what the exporter writes out.
"""

from __future__ import annotations

import math
import sys

import numpy as np

sys.setrecursionlimit(10000)

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from .base import PlotCanvas
from .overlay import CanvasOverlay, CanvasTools, watch_container

_LINESTYLES = {
    "solid": "-",
    "dash": "--",
    "dot": ":",
    "dashdot": "-.",
    "longdash": (0, (8, 3)),
}


def _ls(name: str) -> object:
    return _LINESTYLES.get((name or "solid").lower(), "-")


def _shade(color: str, factor: float) -> str:
    """Darken a colour towards black (``factor`` 0 = black, 1 = unchanged)."""
    text = (color or "").lstrip("#")
    if len(text) != 6:
        return color
    try:
        r, g, b = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return color
    return "#%02x%02x%02x" % (
        int(r * factor),
        int(g * factor),
        int(b * factor),
    )


def _make_canvas_class():
    """A matplotlib canvas that reports Ctrl+wheel zooms.

    matplotlib turns the wheel into a "scroll" event, which does nothing when
    no scrollable axes is set - so Ctrl+wheel never zoomed. The zoom is
    handled here instead, on the panel under the pointer.
    """
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

    class ZoomCanvas(FigureCanvasQTAgg):
        ctrl_wheel = Signal(float, QPoint)

        def wheelEvent(self, event):  # noqa: N802 - Qt override
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                steps = event.angleDelta().y() / 120.0
                if not steps:
                    steps = event.pixelDelta().y()
                if steps:
                    self.ctrl_wheel.emit(steps, event.position().toPoint())
                event.accept()
                return
            super().wheelEvent(event)

    return ZoomCanvas


class _WorkspaceWatcher(QObject):
    """Keeps the tool strip in the band above the figure."""

    def __init__(self, container: QWidget, tools: CanvasTools) -> None:
        super().__init__(container)
        self._container = container
        self._tools = tools
        container.installEventFilter(self)
        self._place()

    def _place(self) -> None:
        size = self._tools.sizeHint()
        self._tools.resize(size)
        margins = self._container.layout().contentsMargins()
        band = max(margins.top(), size.height())
        y = max(0, (band - size.height()) // 2)
        self._tools.move(
            max(0, self._container.width() - size.width() - 10),
            y,
        )

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.Resize:
            self._place()
        return False


class MatplotlibCanvas(PlotCanvas):
    """A matplotlib FigureCanvasQTAgg-backed 2D canvas."""

    def __init__(self) -> None:
        from matplotlib.figure import Figure

        self._fig = Figure()
        # Constrained layout keeps every panel's tick labels, axis labels and
        # legend in their own space (the exporter uses the same engine, so the
        # preview and the exported file agree).
        try:
            self._fig.set_layout_engine("constrained", wspace=0.0, hspace=0.0)
        except Exception:  # noqa: BLE001 - older matplotlib
            pass
        self._canvas = _make_canvas_class()(self._fig)
        self._canvas.ctrl_wheel.connect(self._on_ctrl_wheel)

        # The workspace holds the figure like a sheet on a desk; the figure
        # itself is the "artboard" and is what gets exported.
        self._container = QWidget()
        self._container.setObjectName("canvasWorkspace")
        lay = QVBoxLayout(self._container)
        lay.setContentsMargins(14, 46, 14, 14)
        lay.setSpacing(0)
        self._frame = QFrame()
        self._frame.setObjectName("canvasArtboard")
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        frame_layout.addWidget(self._canvas)
        lay.addWidget(self._frame)
        # The tool buttons live on the workspace, above the figure, so they
        # never cover the plot and are always clickable.
        self._tools = CanvasTools(self._container)
        self._tools.zoom_in_requested.connect(self.zoom_in)
        self._tools.zoom_out_requested.connect(self.zoom_out)
        self._tools.fit_requested.connect(self.fit)
        self._tools.hover_toggled.connect(self.set_hover)
        self.zoom_changed = self._update_zoom_label
        self._tools_watcher = _WorkspaceWatcher(self._container, self._tools)
        # The panel marker and the hover readout float above
        # the figure as plain widgets, so they can never end up in an export.
        self._overlay = CanvasOverlay(self._canvas)
        self._watcher = watch_container(self._canvas, self._overlay)
        self._grid_rows = 1
        self._grid_cols = 1
        self._gap_x = 0.0
        self._gap_y = 0.0
        self._ax_left = self._fig.add_subplot(111)
        self._axes = [self._ax_left]
        self._current_panel = 0
        self._ax_right = None
        self._right_axes: dict[int, object] = {}
        self._series: list[tuple[np.ndarray, np.ndarray, str]] = []
        self._series_meta: list[dict] = []  # brush/click bookkeeping per series
        self._artists: list[dict] = []  # the drawn artist of every series
        self._selected_series: int | None = None
        self._hover_panel: int | None = None
        self._brush_artists: list = []
        self._hover_enabled = False
        self._hover_cid = None
        self._theme_fg = ""
        self._theme_accent = "#4c8dff"
        self._active_panel = 0
        self._canvas.mpl_connect("button_press_event", self._on_button_press)
        self._canvas.mpl_connect("draw_event", self._on_draw)
        # The panel under the pointer is tracked always (not only while the
        # readout is on), so the zoom tools always act on the right panel.
        self._canvas.mpl_connect("motion_notify_event", self._track_pointer)
        self.label_click_callback = None
        self.set_theme("classic-dark")

    # -- PlotCanvas ---------------------------------------------------------
    def widget(self):
        return self._container

    def artboard(self):
        """The widget that shows the figure itself (the exportable surface)."""
        return self._frame

    def current_limits(self) -> list[tuple[float, float, float, float]]:
        """The limits of every panel, in the order the panels are drawn.

        The exporter uses them so a zoomed or panned view is exported the
        way it is on screen (what you see is what you get).
        """
        limits: list[tuple[float, float, float, float]] = []
        for ax in self._axes:
            try:
                x0, x1 = ax.get_xlim()
                y0, y1 = ax.get_ylim()
            except Exception:  # noqa: BLE001 - the panel may not be scaled yet
                limits.append((0.0, 1.0, 0.0, 1.0))
                continue
            limits.append((float(x0), float(x1), float(y0), float(y1)))
        return limits

    def clear(self) -> None:
        self._fig.clear()
        try:
            self._fig.set_layout_engine("constrained", wspace=self._gap_x, hspace=self._gap_y)
        except Exception:  # noqa: BLE001 - older matplotlib
            pass
        rows = max(1, getattr(self, "_grid_rows", 1))
        cols = max(1, getattr(self, "_grid_cols", 1))
        if rows * cols > 1:
            axes = self._fig.subplots(rows, cols, squeeze=False)
            self._axes = [ax for row in axes for ax in row]
        else:
            self._axes = [self._fig.add_subplot(111)]
        self._ax_left = self._axes[0]
        self._ax_right = None
        self._right_axes = {}
        self._series = []
        self._series_meta = []
        self._artists = []
        self._selected_series = None
        self._hover_panel = None
        self._brush_artists = []
        # re-apply theme colours to the fresh axes
        try:
            self.set_theme(self._last_theme)
        except Exception:
            pass
        self._apply_gaps()
        self._canvas.draw_idle()

    def set_grid(self, rows: int = 1, cols: int = 1) -> None:
        self._grid_rows = max(1, rows)
        self._grid_cols = max(1, cols)
        self.clear()

    def set_panel_gaps(self, h_gap: float = 0.0, v_gap: float = 0.0) -> None:
        """Set the fractional space between panels (0 = flush, 1 = one panel)."""
        self._gap_x = max(0.0, float(h_gap or 0.0))
        self._gap_y = max(0.0, float(v_gap or 0.0))
        self._apply_gaps()
        self._canvas.draw_idle()

    def _apply_gaps(self) -> None:
        # The panel gaps are the spacing between the panels of the constrained
        # layout engine. (Calling subplots_adjust() would switch the engine
        # off, so the gaps go through the engine instead.)
        engine = self._fig.get_layout_engine()
        if engine is None or not hasattr(engine, "set"):
            return
        try:
            engine.set(wspace=self._gap_x, hspace=self._gap_y)
        except Exception:  # noqa: BLE001 - no subplots yet
            pass

    def set_current_panel(self, index: int) -> None:
        if self._axes:
            self._current_panel = index % len(self._axes)
            self._ax_left = self._axes[self._current_panel]
            # Reuse this panel's secondary axis; other panels keep theirs.
            self._ax_right = self._right_axes.get(self._current_panel)

    def plot(
        self,
        x,
        y,
        *,
        style: str = "line",
        color: str = "",
        width: float = 2.0,
        symbol: str = "o",
        symbol_size: float = 7.0,
        name: str | None = None,
        yerr=None,
        xerr=None,
        y_axis: str = "left",
        line_style: str = "solid",
        z=None,
        rows=None,
    ) -> None:
        from types import SimpleNamespace

        from graphmatrix.core.io.export import render_xyz_mpl
        from graphmatrix.core.model import PlotStyle, Z_STYLES

        ax = self._ax_left
        if y_axis == "right":
            ax = self._right_axes.get(self._current_panel)
            if ax is None:
                ax = self._ax_left.twinx()
                self._right_axes[self._current_panel] = ax
            self._ax_right = ax

        xs = np.asarray(x, dtype=float)
        ys = np.asarray(y, dtype=float)
        if rows is None:
            rows = np.arange(xs.size)
        rows = np.asarray(rows, dtype=int)
        n = min(xs.size, ys.size, rows.size)
        xs, ys, rows = xs[:n], ys[:n], rows[:n]
        order = np.argsort(xs)
        xs_s = xs[order]
        ys_s = ys[order]
        rows_s = rows[order]
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
            self._record_series_meta(xs_s, ys_s, rows_s, ax, ms)
            self._series.append((xs_s, ys_s, name or ""))
            render_xyz_mpl(
                ax,
                self._fig,
                plot_style,
                SimpleNamespace(
                    x=xs,
                    y=ys,
                    z=None if z is None else np.asarray(z, float)[:n],
                    legend=lbl,
                ),
                cmap="viridis",
                color=col or "",
                width=width,
                symbol=symbol,
                symbol_size=symbol_size,
                line_style=ls,
                label=lbl,
                z_label="Value",
            )
            # The constrained layout engine handles the spacing here too.
            self._canvas.draw_idle()
            return

        if style == "scatter":
            artist = ax.plot(
                xs,
                ys,
                linestyle="none",
                marker=marker or "o",
                markersize=ms,
                color=col,
                label=lbl,
            )[0]
        elif style == "line":
            artist = ax.plot(
                xs, ys, color=col, linewidth=width, linestyle=ls, label=lbl
            )[0]
        elif style == "line+symbol" or style == "line_symbol":
            artist = ax.plot(
                xs,
                ys,
                color=col,
                linewidth=width,
                marker=marker or "o",
                markersize=ms,
                linestyle=ls,
                label=lbl,
            )[0]
        elif style == "bar":
            artist = ax.bar(xs, ys, color=col, label=lbl)
        elif style == "area":
            ax.fill_between(xs, ys, alpha=0.3, color=col)
            artist = ax.plot(
                xs, ys, color=col, linewidth=width, linestyle=ls, label=lbl
            )[0]
        elif style == "step":
            artist = ax.step(
                xs, ys, where="mid", color=col, linewidth=width, linestyle=ls, label=lbl
            )[0]
        elif style == "errorbar" or style == "error bar":
            artist = ax.errorbar(
                xs,
                ys,
                yerr=yerr,
                xerr=xerr,
                color=col,
                linewidth=width,
                linestyle=ls,
                marker=marker or "o",
                markersize=ms,
                capsize=3,
                label=lbl,
            )[0]
        else:
            artist = ax.plot(
                xs, ys, color=col, linewidth=width, linestyle=ls, label=lbl
            )[0]

        if yerr is not None and style not in ("errorbar", "error bar"):
            ax.errorbar(
                xs,
                ys,
                yerr=yerr,
                color=col,
                linestyle="none",
                marker=marker or "o",
                markersize=ms,
                capsize=3,
                label=None,
            )

        self._record_series_meta(xs_s, ys_s, rows_s, ax, ms)
        self._series.append((xs_s, ys_s, name or ""))
        self._artists.append(
            {"artist": artist, "marker_size": ms, "width": width, "axes": ax}
        )
        self._canvas.draw_idle()

    # -- selection ----------------------------------------------------------
    def set_selected_series(self, index: int | None) -> None:
        """Highlight the series that is selected in the sidebar.

        The chosen curve gets bigger symbols and a halo, so it is obvious
        which line the properties are about.
        """
        self._selected_series = index
        accent = self._theme_accent or "#4c8dff"
        for position, info in enumerate(self._artists):
            artist = info.get("artist")
            if artist is None:
                continue
            chosen = position == index
            try:
                artist.set_markersize(
                    float(info.get("marker_size", 6.0)) * (1.9 if chosen else 1.0)
                )
                artist.set_markeredgecolor(accent if chosen else "none")
                artist.set_markeredgewidth(1.4)
                artist.set_linewidth(
                    float(info.get("width", 1.5)) * (1.7 if chosen else 1.0)
                )
            except Exception:  # noqa: BLE001 - collections have no markers
                continue
        self._canvas.draw_idle()

    # -- overlay (tools, panel marker, readout) -----------------------------
    def overlay(self):
        """The floating chrome drawn on top of the plot."""
        return self._overlay

    def _on_draw(self, event) -> None:
        """Keep the panel marker aligned with the axes after a redraw."""
        axes = self._axes
        if not axes:
            return
        index = min(self._active_panel, len(axes) - 1)
        self._overlay.set_panel(
            self._active_panel,
            len(axes),
            self._panel_rect(axes[index]),
        )
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        """Show the current zoom of the panel in the tool strip."""
        try:
            self._tools.set_zoom_level(self.zoom_factor())
        except Exception:  # noqa: BLE001 - the label must never break a draw
            pass

    def set_active_panel(self, index: int, total: int | None = None) -> None:
        """Mark the panel the user is editing (grid / stack layouts)."""
        self._active_panel = max(0, int(index))
        count = total if total is not None else len(self._axes)
        axes = self._axes
        ax = axes[self._active_panel] if self._active_panel < len(axes) else self._ax_left
        self._overlay.set_panel(self._active_panel, count, self._panel_rect(ax))

    def _display_to_widget(self, x: float, y: float) -> QPoint:
        """Matplotlib display coordinates -> widget pixels.

        Matplotlib measures from the bottom left of the figure, Qt from the
        top left, so the y axis is flipped. The scale is the geometric one:
        the figure's drawing area mapped onto the widget, which is exact
        whatever the dpi and the device pixel ratio happen to be.
        """
        bbox = self._fig.bbox
        fig_w = float(bbox.width) or 1.0
        fig_h = float(bbox.height) or 1.0
        widget_w = float(self._canvas.width()) or 1.0
        widget_h = float(self._canvas.height()) or 1.0
        return QPoint(
            int(round(float(x) / fig_w * widget_w)),
            int(round((fig_h - float(y)) / fig_h * widget_h)),
        )

    def _panel_rect(self, ax) -> object:
        """The axes' area in widget pixels (Qt origin: top left)."""
        from PySide6.QtCore import QRect

        if ax is None:
            return None
        try:
            bbox = ax.get_window_extent()
        except Exception:  # noqa: BLE001 - the figure may not be laid out yet
            return None
        top_left = self._display_to_widget(bbox.x0, bbox.y1)
        bottom_right = self._display_to_widget(bbox.x1, bbox.y0)
        return QRect(
            int(top_left.x()),
            int(top_left.y()),
            max(0, int(bottom_right.x() - top_left.x())),
            max(0, int(bottom_right.y() - top_left.y())),
        )

    def zoom_in(self) -> None:
        """Zoom the current panel in around its centre."""
        self._scale_limits(1 / 1.25)
        self._notify_zoom_changed()

    def zoom_out(self) -> None:
        """Zoom the current panel out around its centre."""
        self._scale_limits(1.25)
        self._notify_zoom_changed()

    def zoom_factor(self) -> float:
        """How much of the data the panel shows (``1.0`` = all of it).

        The ratio is taken from the axes' data limits, so it follows the real
        data instead of counting button presses.
        """
        ax = self._zoom_target()
        if ax is None:
            return 1.0
        try:
            x0, x1 = ax.get_xlim()
            y0, y1 = ax.get_ylim()
            data = ax.dataLim
            dx = float(data.width)
            dy = float(data.height)
        except Exception:  # noqa: BLE001 - the axes may not be scaled yet
            return 1.0
        factors = []
        if dx > 0:
            factors.append(dx / abs(x1 - x0))
        if dy > 0:
            factors.append(dy / abs(y1 - y0))
        if not factors:
            return 1.0
        return max(1.0, min(factors))

    def _zoom_target(self):
        """The panel the tools act on.

        It is the panel the pointer was over last; if the pointer never was
        over the figure, the panel that is being edited is used.
        """
        if self._hover_panel is not None and 0 <= self._hover_panel < len(self._axes):
            return self._axes[self._hover_panel]
        return self._ax_left

    def _target_and_twin(self):
        """The panel the tools act on and its secondary axis."""
        ax = self._zoom_target()
        right = None
        for index, candidate in enumerate(self._axes):
            if candidate is ax:
                right = self._right_axes.get(index)
                break
        return ax, right

    def _scale_limits(self, factor: float) -> None:
        ax, right = self._target_and_twin()
        for target in (ax, right):
            if target is None:
                continue
            try:
                x0, x1 = target.get_xlim()
                y0, y1 = target.get_ylim()
            except Exception:  # noqa: BLE001
                continue
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            target.set_xlim(cx + (x0 - cx) * factor, cx + (x1 - cx) * factor)
            target.set_ylim(cy + (y0 - cy) * factor, cy + (y1 - cy) * factor)
        self._canvas.draw_idle()

    def fit(self) -> None:
        """Reset the panel to the data's own limits."""
        ax, right = self._target_and_twin()
        for target in (ax, right):
            if target is None:
                continue
            try:
                target.autoscale()
            except Exception:  # noqa: BLE001
                continue
        self._canvas.draw_idle()
        self._notify_zoom_changed()

    # -- Ctrl+wheel zoom ----------------------------------------------------
    def _on_ctrl_wheel(self, steps: float, position: QPoint) -> None:
        """Zoom the panel under the pointer (Ctrl+wheel).

        The pointer stays on the same data point, so the zoom reads like
        moving a magnifying glass over the plot.
        """
        from graphmatrix.ui import preferences

        if not preferences.get("canvas/wheel_zoom", True):
            return
        ax = self._axes_at(position)
        if ax is None:
            return
        factor = 1.25 ** (-float(steps))
        try:
            xdata, ydata = ax.transData.inverted().transform(
                (position.x(), position.y())
            )
        except Exception:  # noqa: BLE001 - the axes may not be scaled yet
            return
        self._zoom_axis(ax, "x", xdata, factor)
        self._zoom_axis(ax, "y", ydata, factor)
        self._canvas.draw_idle()
        self._notify_zoom_changed()

    def _axes_at(self, position: QPoint):
        """The panel of the figure under a widget position."""
        for ax in self._axes:
            if ax is None:
                continue
            try:
                bbox = ax.get_window_extent()
            except Exception:  # noqa: BLE001 - the figure may not be laid out
                continue
            if bbox.contains(position.x(), position.y()):
                return ax
        return None

    def _zoom_axis(self, ax, which: str, center: float, factor: float) -> None:
        """Scale one axis around ``center`` (data or log space)."""
        try:
            if which == "x":
                low, high = ax.get_xlim()
                scale = ax.get_xscale()
            else:
                low, high = ax.get_ylim()
                scale = ax.get_yscale()
        except Exception:  # noqa: BLE001
            return
        if scale == "log":
            if center <= 0 or low <= 0 or high <= 0:
                return
            log_center = math.log10(center)
            new_low = 10 ** (log_center + (math.log10(low) - log_center) * factor)
            new_high = 10 ** (log_center + (math.log10(high) - log_center) * factor)
        else:
            new_low = center + (low - center) * factor
            new_high = center + (high - center) * factor
        if new_low == new_high:
            return
        try:
            if which == "x":
                ax.set_xlim(new_low, new_high)
            else:
                ax.set_ylim(new_low, new_high)
        except Exception:  # noqa: BLE001
            return

    def share_y_across_panels(self) -> None:
        """Give every panel the same Y range (the X-Twin layout).

        An X-Twin shows two panels side by side that share their Y axis, so
        both must be scaled to the same data range - otherwise the halves
        cannot be compared by eye.
        """
        low = None
        high = None
        for ax in self._axes:
            if ax is None:
                continue
            try:
                bottom, top = ax.get_ylim()
            except Exception:  # noqa: BLE001 - not scaled yet
                continue
            low = bottom if low is None else min(low, bottom)
            high = top if high is None else max(high, top)
        if low is None or high is None or low == high:
            return
        for ax in self._axes:
            if ax is None:
                continue
            try:
                ax.set_ylim(low, high)
            except Exception:  # noqa: BLE001
                continue
        self._canvas.draw_idle()

    # -- linked brushing ----------------------------------------------------
    def _record_series_meta(self, xs, ys, rows, ax, marker_size: float) -> None:
        """Remember where each point lives so clicks and brush overlays can
        map back to worksheet rows."""
        self._series_meta.append(
            {
                "xs": np.asarray(xs, dtype=float),
                "ys": np.asarray(ys, dtype=float),
                "rows": np.asarray(rows, dtype=int),
                "ax": ax,
                "size": max(8.0, float(marker_size) * 2.0),
            }
        )

    def set_brush(self, selection: dict[int, list[int]] | None) -> None:
        for artist in self._brush_artists:
            try:
                artist.remove()
            except Exception:  # noqa: BLE001 - already gone
                pass
        self._brush_artists = []
        if not selection:
            self._canvas.draw_idle()
            return
        for series_index, series_meta in enumerate(self._series_meta):
            wanted_rows = selection.get(series_index)
            if not wanted_rows:
                continue
            mask = np.isin(series_meta["rows"], list(wanted_rows))
            if not mask.any():
                continue
            artist = series_meta["ax"].plot(
                series_meta["xs"][mask],
                series_meta["ys"][mask],
                linestyle="none",
                marker="o",
                markersize=series_meta["size"],
                markerfacecolor="none",
                markeredgecolor="#ff7f0e",
                markeredgewidth=2.0,
                zorder=10,
            )[0]
            self._brush_artists.append(artist)
        self._canvas.draw_idle()

    def _pick_point(self, event) -> tuple[int, int] | None:
        """Nearest plotted point to a click, as (series_index, worksheet row)."""
        best: tuple[float, int, int] | None = None  # (distance_px, series, row)
        for series_index, series_meta in enumerate(self._series_meta):
            ax = series_meta["ax"]
            transform = ax.transData
            xs, ys = series_meta["xs"], series_meta["ys"]
            display = transform.transform(np.column_stack([xs, ys]))
            try:
                px, py = transform.transform((event.xdata, event.ydata))
            except Exception:  # noqa: BLE001 - outside the data ranges
                continue
            distance = np.hypot(display[:, 0] - px, display[:, 1] - py)
            idx = int(np.argmin(distance))
            if best is None or float(distance[idx]) < best[0]:
                best = (
                    float(distance[idx]),
                    series_index,
                    int(series_meta["rows"][idx]),
                )
        if best is None or best[0] > 12.0:  # within 12 px of a point
            return None
        return best[1], best[2]

    def add_reference_line(
        self,
        orientation,
        position,
        *,
        color="#888888",
        width=1.5,
        line_style="dash",
        label="",
    ) -> None:
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
                ax.text(
                    position,
                    ymax - pad,
                    label,
                    color=color,
                    fontsize=8,
                    ha="left",
                    va="top",
                    rotation=90,
                )
            else:
                ax.text(
                    xmax,
                    position,
                    label,
                    color=color,
                    fontsize=8,
                    ha="right",
                    va="bottom",
                )
        self._canvas.draw_idle()

    def set_hover(self, enabled: bool) -> None:
        enabled = bool(enabled)
        changed = enabled != self._hover_enabled
        self._hover_enabled = enabled
        self._overlay.set_hover_enabled(self._hover_enabled)
        self._tools.set_hover_checked(self._hover_enabled)
        if changed:
            # Tell the owner, so the sidebar button and the menu entry show
            # the same state as the button on the canvas.
            callback = getattr(self, "hover_state_changed", None)
            if callable(callback):
                callback(enabled)
        if enabled and self._hover_cid is None:
            self._hover_cid = self._canvas.mpl_connect(
                "motion_notify_event", self._on_hover
            )
        elif (not enabled) and self._hover_cid is not None:
            self._canvas.mpl_disconnect(self._hover_cid)
            self._hover_cid = None
            self._clear_readout()
            self._canvas.draw_idle()

    def add_annotation(self, text, x, y, *, color="#000000", size=11.0) -> None:
        ax = self._ax_left
        ax.text(
            x,
            y,
            text,
            transform=ax.transAxes,
            color=color,
            fontsize=size,
            ha="left",
            va="top",
        )
        self._canvas.draw_idle()

    def set_title(
        self,
        text: str,
        *,
        fontfamily: str = "",
        fontsize: float = 14.0,
        color: str = "",
    ) -> None:
        kwargs = {"fontsize": fontsize or 14.0}
        if fontfamily:
            kwargs["fontfamily"] = fontfamily
        # Without an explicit colour the title follows the theme, so it stays
        # readable on a dark canvas.
        kwargs["color"] = color or getattr(self, "_theme_fg", "") or "#000000"
        self._fig.suptitle(text, **kwargs)
        # The constrained layout engine reserves the strip the figure title
        # needs, so the title never overlaps the first row of panels.
        self._canvas.draw_idle()

    def set_labels(
        self,
        *,
        bottom=None,
        left=None,
        right=None,
        fontfamily: str = "",
        fontsize: float = 12.0,
        color: str = "",
    ) -> None:
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
                self._right_axes[self._current_panel] = self._ax_right
            self._ax_right.set_ylabel(right, **kwargs)
        self._canvas.draw_idle()

    def set_scales(self, *, x: str = "linear", y: str = "linear") -> None:
        self._ax_left.set_xscale(x)
        self._ax_left.set_yscale(y)
        if self._ax_right is not None:
            self._ax_right.set_yscale(y)
        self._canvas.draw_idle()

    def set_axis_visibility(
        self, *, bottom: bool = True, left: bool = True, right: bool = True
    ) -> None:
        """Show/hide the axis line, ticks, tick labels, and labels for one panel."""
        ax = self._ax_left
        ax.tick_params(
            axis="x", which="both", bottom=bool(bottom), labelbottom=bool(bottom)
        )
        ax.tick_params(axis="y", which="both", left=bool(left), labelleft=bool(left))
        ax.spines["bottom"].set_visible(bool(bottom))
        ax.spines["left"].set_visible(bool(left))
        ax.xaxis.label.set_visible(bool(bottom))
        ax.yaxis.label.set_visible(bool(left))
        if self._ax_right is not None:
            self._ax_right.tick_params(
                axis="y", which="both", right=bool(right), labelright=bool(right)
            )
            self._ax_right.spines["right"].set_visible(bool(right))
            self._ax_right.yaxis.label.set_visible(bool(right))
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
                legend = self._ax_left.legend(
                    handles, labels, loc="best", frameon=False
                )
                # The tool strip floats in the top-right corner of the figure,
                # so a legend that would land there moves out of its way.
                if getattr(legend, "_loc", 0) == 1:  # "upper right"
                    legend.set_loc("lower right")
                # Keep the legend readable on a dark canvas.
                fg = getattr(self, "_theme_fg", "")
                if fg:
                    for text in legend.get_texts():
                        text.set_color(fg)
        self._canvas.draw_idle()

    def set_downsampling(self, flag: bool) -> None:
        self._downsample = bool(flag)

    def set_theme(self, preset: str) -> None:
        self._last_theme = preset
        from graphmatrix.core.plot_themes import resolve_theme
        from graphmatrix.ui import theme

        bg, fg, grid_alpha = resolve_theme(preset, theme.current_preset())
        self._theme_fg = fg
        self._theme_accent = theme.colors().get("accent", "#4c8dff")
        self._fig.patch.set_facecolor(bg)
        self._overlay.set_colors(bg, fg)
        self._tools.refresh_theme()
        self._apply_workspace_colors(bg)
        axes = list(getattr(self, "_axes", []))
        for right in getattr(self, "_right_axes", {}).values():
            if right is not None and right not in axes:
                axes.append(right)
        if self._ax_right is not None and self._ax_right not in axes:
            axes.append(self._ax_right)
        for ax in axes:
            if ax is None:
                continue
            ax.set_facecolor(bg)
            ax.tick_params(colors=fg)
            if ax.xaxis.label is not None:
                ax.xaxis.label.set_color(fg)
            if ax.yaxis.label is not None:
                ax.yaxis.label.set_color(fg)
            if getattr(ax, "title", None) is not None:
                ax.title.set_color(fg)
            for spine in ax.spines.values():
                spine.set_color(fg)
            ax.grid(True, alpha=grid_alpha, color=fg)
        self._canvas.draw_idle()

    # -- hover helpers ------------------------------------------------------
    def _apply_workspace_colors(self, figure_bg: str) -> None:
        """Paint the workspace around the figure and the frame of the artboard.

        The workspace uses the application colours, the artboard the figure's
        own background, so the figure reads as a sheet on a desk.
        """
        from graphmatrix.ui import theme

        palette = theme.colors()
        workspace = _shade(palette.get("window", "#202124"), 0.6)
        border = palette.get("border", "#3a3d42")
        self._container.setStyleSheet(
            f"QWidget#canvasWorkspace {{ background: {workspace}; }}"
        )
        self._frame.setStyleSheet(
            f"QFrame#canvasArtboard {{ background: {figure_bg};"
            f" border: 1px solid {border}; }}"
        )

    def _track_pointer(self, event) -> None:
        """Remember the panel the pointer is over (for the zoom tools)."""
        axes = getattr(event, "inaxes", None)
        if axes is None:
            return
        try:
            self._hover_panel = self._axes.index(axes)
        except ValueError:
            self._hover_panel = None

    def _show_picked_point(self, series_index: int, row: int) -> None:
        """Show the values of the point the user just clicked."""
        if not 0 <= series_index < len(self._series):
            return
        xs, ys, name = self._series[series_index]
        meta = (
            self._series_meta[series_index]
            if series_index < len(self._series_meta)
            else None
        )
        index = None
        if meta is not None and "rows" in meta:
            matches = np.where(np.asarray(meta["rows"]) == int(row))[0]
            if matches.size:
                index = int(matches[0])
        if index is None:
            index = int(np.argmin(np.abs(xs - (xs[0] if xs.size else 0.0))))
        if not xs.size:
            return
        self._overlay.set_readout(
            f"{name}:   x = {float(xs[index]):.4g}    y = {float(ys[index]):.4g}",
            force=True,
        )

    def _on_hover(self, event) -> None:
        from PySide6.QtCore import QPoint

        if not self._hover_enabled:
            return
        axes = getattr(event, "inaxes", None)
        if axes is None:
            return
        # The pointer may be over any panel of the figure, not only the one
        # that is being edited.
        panels = set(self._axes) | {
            ax for ax in self._right_axes.values() if ax is not None
        }
        if axes not in panels:
            return
        # Remember the panel under the pointer: the zoom and the fit work on
        # it, like every other drawing program.
        try:
            self._hover_panel = self._axes.index(axes)
        except ValueError:
            self._hover_panel = None
        # The readout of the point under the pointer. There is deliberately no
        # crosshair: a cross that spans the whole figure would pretend that
        # a stack, a twin or a grid of panels is one single plot.
        best = None
        for index, (xs, ys, name) in enumerate(self._series):
            if xs.size == 0:
                continue
            # Only the series of the panel under the pointer are candidates.
            meta = self._series_meta[index] if index < len(self._series_meta) else None
            if meta is not None and meta.get("ax") is not axes:
                continue
            idx = int(np.searchsorted(xs, event.xdata))
            for cand in (idx - 1, idx):
                if 0 <= cand < xs.size:
                    dist = abs(float(xs[cand]) - float(event.xdata))
                    if best is None or dist < best[0]:
                        best = (dist, float(xs[cand]), float(ys[cand]), name)
        if best is not None:
            self._overlay.set_readout(
                f"{best[3]}:   x = {best[1]:.4g}    y = {best[2]:.4g}"
            )
        else:
            self._overlay.set_readout("")
        self._canvas.draw_idle()

    def _clear_readout(self) -> None:
        """Clear the readout (the overlay owns it)."""
        self._overlay.set_readout("")

    def _on_button_press(self, event) -> None:
        try:
            # Linked brushing: a left click near a plotted point picks its row.
            if (
                not getattr(event, "dblclick", False)
                and getattr(event, "inaxes", None) is not None
                and event.xdata is not None
                and callable(self.point_picked)
            ):
                picked = self._pick_point(event)
                if picked is not None:
                    self._show_picked_point(picked[0], picked[1])
                    self.point_picked(*picked)
                    return
        except Exception:  # noqa: BLE001 - picking must never break plotting
            pass
        try:
            if event.inaxes is not None and callable(self.label_click_callback):
                # Axis area (not a label) -> focus the axes property group.
                for name, artist in (
                    ("title", getattr(self._fig, "_suptitle", None)),
                    ("xlabel", self._ax_left.xaxis.label),
                    ("ylabel", self._ax_left.yaxis.label),
                ):
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
