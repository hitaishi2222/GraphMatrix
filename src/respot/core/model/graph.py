"""Graph documents.

M0 only needs the envelope (a graph owns layers); plot specifications and the
rendering model arrive with the M2 canvas work. The shape is defined now so the
project file and the project tree are stable across milestones.
"""

from __future__ import annotations

from typing import Any


class Layer:
    """A single plotting layer within a graph.

    ``plots`` will hold plot specs (data source, style, axis binding) from M2.
    """

    def __init__(self, name: str = "Layer 1") -> None:
        self.name = name
        self.plots: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "plots": list(self.plots)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Layer":
        layer = cls(payload.get("name", "Layer 1"))
        layer.plots = list(payload.get("plots", []))
        return layer

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Layer(name={self.name!r}, plots={len(self.plots)})"


class Graph:
    """A figure: a stack of layers sharing a canvas."""

    def __init__(self, name: str = "Graph1") -> None:
        self.name = name
        self.layers: list[Layer] = [Layer()]

    def add_layer(self, layer: Layer | None = None) -> Layer:
        layer = layer or Layer(f"Layer {len(self.layers) + 1}")
        self.layers.append(layer)
        return layer

    @property
    def num_layers(self) -> int:
        return len(self.layers)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "layers": [l.to_dict() for l in self.layers]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Graph":
        graph = cls(payload.get("name", "Graph1"))
        layers = [Layer.from_dict(l) for l in payload.get("layers", [])]
        if layers:
            graph.layers = layers
        return graph

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Graph(name={self.name!r}, layers={self.num_layers})"
