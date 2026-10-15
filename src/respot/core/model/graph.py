"""Graph documents: figures composed of layers, each holding plot specs.

The model stores *references* to worksheet columns (``Book1/Sheet1`` + column
names), not the data. Resolution to arrays happens in ``core.plotting``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlotStyle(str, Enum):
    LINE = "line"
    SCATTER = "scatter"
    LINE_SYMBOL = "line+symbol"
    BAR = "bar"
    AREA = "area"
    STEP = "step"
    ERRORBAR = "errorbar"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class AxisScale(str, Enum):
    LINEAR = "linear"
    LOG = "log"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


_PALETTE = (
    "#1f77b4", "#d62728", "#2ca02c", "#9467bd",
    "#ff7f0e", "#17becf", "#8c564b", "#e377c2",
)


@dataclass
class PlotSpec:
    """One plotted series: a data source plus style."""

    source: str  # "Book1/Sheet1"
    x: str
    y: str
    yerr: str | None = None
    xerr: str | None = None
    style: PlotStyle = PlotStyle.LINE_SYMBOL
    color: str = ""
    line_width: float = 2.0
    symbol: str = "o"
    symbol_size: float = 7.0
    legend: str = ""
    y_axis: str = "left"  # "left" | "right" (secondary Y axis)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source, "x": self.x, "y": self.y,
            "yerr": self.yerr, "xerr": self.xerr,
            "style": PlotStyle(self.style).value, "color": self.color,
            "line_width": self.line_width, "symbol": self.symbol,
            "symbol_size": self.symbol_size, "legend": self.legend,
            "y_axis": self.y_axis,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlotSpec":
        return cls(
            source=payload["source"], x=payload["x"], y=payload["y"],
            yerr=payload.get("yerr"), xerr=payload.get("xerr"),
            style=PlotStyle(payload.get("style", PlotStyle.LINE_SYMBOL)),
            color=payload.get("color", ""), line_width=payload.get("line_width", 2.0),
            symbol=payload.get("symbol", "o"), symbol_size=payload.get("symbol_size", 7.0),
            legend=payload.get("legend", ""),
            y_axis=payload.get("y_axis", "left"),
        )


@dataclass
class Annotation:
    """A text label placed on the figure at axes-fraction coordinates."""

    text: str = ""
    x: float = 0.05
    y: float = 0.95
    color: str = "#000000"
    size: float = 11.0

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "x": self.x, "y": self.y, "color": self.color, "size": self.size}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Annotation":
        return cls(
            text=payload.get("text", ""), x=payload.get("x", 0.05), y=payload.get("y", 0.95),
            color=payload.get("color", "#000000"), size=payload.get("size", 11.0),
        )


@dataclass
class Layer:
    """A plotting layer with its own axes configuration."""

    name: str = "Layer 1"
    plots: list[PlotSpec] = field(default_factory=list)
    x_scale: AxisScale = AxisScale.LINEAR
    y_scale: AxisScale = AxisScale.LINEAR
    x_label: str = ""
    y_label: str = ""
    y2_label: str = ""
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    show_legend: bool = True

    def add_plot(self, spec: PlotSpec) -> PlotSpec:
        self.plots.append(spec)
        return spec

    def remove_plot(self, spec: PlotSpec) -> int:
        index = self.plots.index(spec)
        del self.plots[index]
        return index

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "plots": [p.to_dict() for p in self.plots],
            "x_scale": AxisScale(self.x_scale).value,
            "y_scale": AxisScale(self.y_scale).value,
            "x_label": self.x_label, "y_label": self.y_label, "y2_label": self.y2_label,
            "x_min": self.x_min, "x_max": self.x_max,
            "y_min": self.y_min, "y_max": self.y_max,
            "show_legend": self.show_legend,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Layer":
        layer = cls(payload.get("name", "Layer 1"))
        layer.plots = [PlotSpec.from_dict(p) for p in payload.get("plots", [])]
        layer.x_scale = AxisScale(payload.get("x_scale", "linear"))
        layer.y_scale = AxisScale(payload.get("y_scale", "linear"))
        layer.x_label = payload.get("x_label", "")
        layer.y_label = payload.get("y_label", "")
        layer.y2_label = payload.get("y2_label", "")
        layer.x_min = payload.get("x_min")
        layer.x_max = payload.get("x_max")
        layer.y_min = payload.get("y_min")
        layer.y_max = payload.get("y_max")
        layer.show_legend = payload.get("show_legend", True)
        return layer

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Layer(name={self.name!r}, plots={len(self.plots)})"


class Graph:
    """A figure: a stack of layers sharing a canvas."""

    def __init__(self, name: str = "Graph1", title: str = "") -> None:
        self.name = name
        self.title = title
        self.layers: list[Layer] = [Layer()]
        self.annotations: list[Annotation] = []

    def add_layer(self, layer: Layer | None = None) -> Layer:
        layer = layer or Layer(f"Layer {len(self.layers) + 1}")
        self.layers.append(layer)
        return layer

    def remove_layer(self, layer: Layer) -> int:
        index = self.layers.index(layer)
        del self.layers[index]
        return index

    @property
    def first_layer(self) -> Layer:
        if not self.layers:
            self.layers.append(Layer())
        return self.layers[0]

    @property
    def num_layers(self) -> int:
        return len(self.layers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "title": self.title,
            "layers": [l.to_dict() for l in self.layers],
            "annotations": [a.to_dict() for a in self.annotations],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Graph":
        graph = cls(payload.get("name", "Graph1"), payload.get("title", ""))
        layers = [Layer.from_dict(l) for l in payload.get("layers", [])]
        if layers:
            graph.layers = layers
        graph.annotations = [Annotation.from_dict(a) for a in payload.get("annotations", [])]
        return graph

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Graph(name={self.name!r}, layers={self.num_layers})"
