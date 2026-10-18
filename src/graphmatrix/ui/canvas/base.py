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
    ) -> Any:
        """Plot a series and return the backend's plot item.

        ``y_axis`` selects the primary ("left") or secondary ("right") Y axis.
        ``line_style`` is one of :data:`graphmatrix.core.model.graph.LINE_STYLES`.
        ``z`` is the colour/height series for the Z-carrying styles
        (color-mapped scatter, heatmap, contour, 3D scatter/surface).
        """

    @abstractmethod
    def add_reference_line(
        self, orientation: str, position: float, *,
        color: str = "#888888", width: float = 1.5,
        line_style: str = "dash", label: str = "",
    ) -> None:
        """Draw a horizontal (``"h"``) or vertical (``"v"``) guide line."""

    @abstractmethod
    def set_hover(self, enabled: bool) -> None:
        """Turn the hover crosshair + nearest-point readout on or off."""

    @abstractmethod
    def add_annotation(self, text: str, x: float, y: float, *, color: str = "#000000",
                       size: float = 11.0) -> None:
        """Place a text annotation at axes-fraction coordinates (0-1)."""

    @abstractmethod
    def set_title(self, text: str, *, fontfamily: str = "", fontsize: float = 14.0,
                  color: str = "") -> None: ...

    @abstractmethod
    def set_grid(self, rows: int = 1, cols: int = 1) -> None: ...

    @abstractmethod
    def set_current_panel(self, index: int) -> None: ...

    @abstractmethod
    def set_labels(self, *, bottom: str | None = None, left: str | None = None,
                   right: str | None = None, fontfamily: str = "",
                   fontsize: float = 12.0, color: str = "") -> None: ...

    @abstractmethod
    def set_scales(self, *, x: str = "linear", y: str = "linear") -> None: ...

    @abstractmethod
    def set_ticks(self, *, minor: bool = True, direction: str = "out") -> None: ...

    @abstractmethod
    def set_limits(self, *, x: tuple[float | None, float | None] | None = None,
                   y: tuple[float | None, float | None] | None = None) -> None: ...

    @abstractmethod
    def show_legend(self, flag: bool) -> None: ...

    @abstractmethod
    def set_downsampling(self, flag: bool) -> None: ...

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
        + ("" if backend not in BACKEND_EXTRAS else f"; install it with: {BACKEND_EXTRAS[backend]}")
    )
