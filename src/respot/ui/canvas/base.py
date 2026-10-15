"""Plot canvas abstraction and backend factory.

The rest of the UI talks to `PlotCanvas`, never to pyqtgraph directly. That keeps
the door open to swap in a GPU (Vispy) backend for large data without touching the
window or the graph model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

BACKENDS = ("pyqtgraph",)
DEFAULT_BACKEND = "pyqtgraph"


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
    ) -> Any:
        """Plot a series and return the backend's plot item.

        ``y_axis`` selects the primary ("left") or secondary ("right") Y axis.
        """

    @abstractmethod
    def add_annotation(self, text: str, x: float, y: float, *, color: str = "#000000",
                       size: float = 11.0) -> None:
        """Place a text annotation at axes-fraction coordinates (0-1)."""

    @abstractmethod
    def set_title(self, text: str) -> None: ...

    @abstractmethod
    def set_labels(self, *, bottom: str | None = None, left: str | None = None,
                   right: str | None = None) -> None: ...

    @abstractmethod
    def set_scales(self, *, x: str = "linear", y: str = "linear") -> None: ...

    @abstractmethod
    def set_limits(self, *, x: tuple[float | None, float | None] | None = None,
                   y: tuple[float | None, float | None] | None = None) -> None: ...

    @abstractmethod
    def show_legend(self, flag: bool) -> None: ...

    @abstractmethod
    def set_downsampling(self, flag: bool) -> None: ...


def create_canvas(backend: str = DEFAULT_BACKEND) -> PlotCanvas:
    if backend == "pyqtgraph":
        from .pyqtgraph_canvas import PyQtGraphCanvas

        return PyQtGraphCanvas()
    raise ValueError(f"unknown canvas backend: {backend!r} (known: {BACKENDS})")
