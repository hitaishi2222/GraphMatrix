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
        """Remove all plotted data from the canvas."""

    @abstractmethod
    def plot_xy(self, x: Sequence[float], y: Sequence[float], *, name: str | None = None) -> Any:
        """Plot a data series and return the backend's plot item."""

    @abstractmethod
    def set_title(self, text: str) -> None:
        ...

    @abstractmethod
    def set_labels(self, *, bottom: str | None = None, left: str | None = None) -> None:
        ...


def create_canvas(backend: str = DEFAULT_BACKEND) -> PlotCanvas:
    if backend == "pyqtgraph":
        from .pyqtgraph_canvas import PyQtGraphCanvas

        return PyQtGraphCanvas()
    raise ValueError(f"unknown canvas backend: {backend!r} (known: {BACKENDS})")
