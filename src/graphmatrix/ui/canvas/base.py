"""Plot canvas abstraction and backend factory.

The rest of the UI talks to `PlotCanvas`, never to pyqtgraph directly. That keeps
the door open to swap in a GPU (Vispy) backend for large data without touching the
window or the graph model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

BACKENDS = ("pyqtgraph", "matplotlib", "pyvista")
DEFAULT_BACKEND = "matplotlib"

#: Backends that need a GL/EGL context and the ``plot3d`` extra.
BACKEND_EXTRAS = {"pyvista": "pip install pyvista pyvistaqt (the plot3d extra)"}


class PlotCanvas(ABC):
    """A single graph canvas."""

    @abstractmethod
    def widget(self):  # -> QWidget
        """Return the underlying QWidget so callers can embed it."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all plotted data."""

    @abstractmethod
    def plot(
        self,
        x: Sequence[float],
        y: Sequence[float],
        *,
        style: str = "line",
        color: str = "",
        width: float = 2.0,
        symbol: str = "o",
        symbol_size: float = 7.0,
        name: str | None = None,
        yerr: Sequence[float] | None = None,
        xerr: Sequence[float] | None = None,
        y_axis: str = "left",
        line_style: str = "solid",
        z: Sequence[float] | None = None,
        rows: Sequence[int] | None = None,
        raw_y: Sequence[float] | None = None,
    ) -> Any:
        """Plot a series and return the backend's plot item.

        ``y_axis`` selects the primary ("left") or secondary ("right") Y axis.
        ``line_style`` is one of :data:`graphmatrix.core.model.graph.LINE_STYLES`.
        ``z`` is the colour/height series for the Z-carrying styles
        (color-mapped scatter, heatmap, contour, 3D scatter/surface).
        ``rows`` maps each point to its worksheet row for linked brushing.
        ``raw_y`` is the worksheet value of each point when the drawn values
        are scaled or offset (a stacked-line band): the readout then shows the
        real numbers, not the drawn ones.
        """

    def set_brush(self, selection: dict[int, list[int]] | None) -> None:
        """Highlight linked-brush selections per plotted series.

        ``selection`` maps this canvas's series index -> worksheet row indices;
        ``None`` or an empty mapping clears the overlay. Default: no-op —
        backends without brush support degrade silently.
        """

    def clear_brush(self) -> None:
        self.set_brush(None)  # pragma: no cover - trivial delegation

    #: Set to a callable ``(series_index, row) -> None`` to receive clicks on
    #: plotted points (linked brushing: graph -> sheet).
    point_picked = None

    #: Set to a callable ``() -> None`` to be told that the zoom changed, so
    #: the canvas tools can show the current zoom level.
    zoom_changed = None

    @abstractmethod
    def add_reference_line(
        self,
        orientation: str,
        position: float,
        *,
        color: str = "#888888",
        width: float = 1.5,
        line_style: str = "dash",
        label: str = "",
    ) -> None:
        """Draw a horizontal (``"h"``) or vertical (``"v"``) guide line."""

    @abstractmethod
    def set_hover(self, enabled: bool) -> None:
        """Turn the nearest-point readout on or off."""

    @abstractmethod
    def add_annotation(
        self,
        text: str,
        x: float,
        y: float,
        *,
        color: str = "#000000",
        size: float = 11.0,
    ) -> None:
        """Place a text annotation at axes-fraction coordinates (0-1)."""

    @abstractmethod
    def set_title(
        self,
        text: str,
        *,
        fontfamily: str = "",
        fontsize: float = 14.0,
        color: str = "",
    ) -> None: ...

    @abstractmethod
    def set_grid(self, rows: int = 1, cols: int = 1) -> None: ...

    def set_panel_gaps(self, h_gap: float = 0.0, v_gap: float = 0.0) -> None:
        """Set the space between panels, as a fraction of a panel's size.

        Only multi-panel backends (matplotlib) honour this; single-panel
        backends degrade to a no-op.
        """

    def set_axis_visibility(
        self, *, bottom: bool = True, left: bool = True, right: bool = True
    ) -> None:
        """Show/hide axes for the current panel (multi-panel backend only)."""

    def set_y_tick_labels_visible(self, visible: bool = True) -> None:
        """Show/hide the Y tick numbers, keeping the axis line and the ticks.

        Backends without a separate tick-label control degrade to a no-op.
        """

    @abstractmethod
    def set_current_panel(self, index: int) -> None: ...

    @abstractmethod
    def set_labels(
        self,
        *,
        bottom: str | None = None,
        left: str | None = None,
        right: str | None = None,
        fontfamily: str = "",
        fontsize: float = 12.0,
        color: str = "",
    ) -> None: ...

    @abstractmethod
    def set_scales(self, *, x: str = "linear", y: str = "linear") -> None: ...

    @abstractmethod
    def set_ticks(self, *, minor: bool = True, direction: str = "out") -> None: ...

    @abstractmethod
    def set_limits(
        self,
        *,
        x: tuple[float | None, float | None] | None = None,
        y: tuple[float | None, float | None] | None = None,
    ) -> None: ...

    @abstractmethod
    def show_legend(self, flag: bool) -> None: ...

    @abstractmethod
    def set_downsampling(self, flag: bool) -> None: ...

    # -- canvas chrome -------------------------------------------------------
    def overlay(self):
        """The floating chrome drawn on top of the plot, or ``None``.

        The overlay carries the zoom tools, the panel marker and the hover
        readout. It is a plain widget, never a figure artist, so it can not
        end up in an exported file.
        """
        return None

    def set_active_panel(self, index: int, total: int | None = None) -> None:
        """Mark the panel the user is editing (grid / stack layouts)."""

    def zoom_in(self) -> None:
        """Zoom the current panel in."""

    def zoom_out(self) -> None:
        """Zoom the current panel out."""

    def fit(self) -> None:
        """Reset the current panel to the data's own limits."""

    def zoom_factor(self) -> float:
        """How far the current panel is zoomed in.

        ``1.0`` means the panel shows the data's own range; ``2.0`` means it
        shows half of it. Backends that cannot tell report ``1.0``.
        """
        return 1.0

    def _notify_zoom_changed(self) -> None:
        """Tell the UI that the zoom level moved."""
        callback = self.zoom_changed
        if callback is None:
            return
        try:
            callback()
        except Exception:  # noqa: BLE001 - a UI callback must not break the plot
            pass

    @abstractmethod
    def set_theme(self, preset: str) -> None:
        """Match the canvas background/axes to a named theme preset."""


_ALIASES = {
    "mpl": "matplotlib",
    "agg": "matplotlib",
    "wysiwyg": "matplotlib",
    "qt": "matplotlib",
    "figure": "matplotlib",
    "pyqt": "pyqtgraph",
    "pg": "pyqtgraph",
}


def create_canvas(backend: str = DEFAULT_BACKEND) -> PlotCanvas:
    backend = _ALIASES.get(backend, backend)
    if backend == "pyqtgraph":
        from .pyqtgraph_canvas import PyQtGraphCanvas

        return PyQtGraphCanvas()
    if backend == "matplotlib":
        from .matplotlib_canvas import MatplotlibCanvas

        return MatplotlibCanvas()
    if backend == "pyvista":
        from .pyvista_canvas import PyVistaCanvas

        return PyVistaCanvas()
    raise ValueError(
        f"unknown canvas backend: {backend!r} (known: {BACKENDS})"
        + (
            ""
            if backend not in BACKEND_EXTRAS
            else f"; install it with: {BACKEND_EXTRAS[backend]}"
        )
    )
