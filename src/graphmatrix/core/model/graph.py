"""Graph documents: figures composed of layers, each holding plot specs.

The model stores *references* to worksheet columns (``Book1/Sheet1`` + column
names), not the data. Resolution to arrays happens in ``core.plotting``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..bands import Y_MODES


class PlotStyle(str, Enum):
    LINE = "line"
    SCATTER = "scatter"
    LINE_SYMBOL = "line+symbol"
    BAR = "bar"
    AREA = "area"
    STEP = "step"
    ERRORBAR = "errorbar"
    COLOR_SCATTER = "color-mapped scatter"
    HEATMAP = "heatmap"
    CONTOUR = "contour"
    SCATTER3D = "3d scatter"
    SURFACE3D = "3d surface"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


#: Styles that need a third value (colour or height) flowing with the series.
Z_STYLES = (
    PlotStyle.COLOR_SCATTER,
    PlotStyle.HEATMAP,
    PlotStyle.CONTOUR,
    PlotStyle.SCATTER3D,
    PlotStyle.SURFACE3D,
)


def is_3d_style(style: PlotStyle | str) -> bool:
    """True for styles rendered in a 3D scene (PyVista canvas / 3D export)."""
    return PlotStyle(style) in (PlotStyle.SCATTER3D, PlotStyle.SURFACE3D)


class AxisScale(str, Enum):
    LINEAR = "linear"
    LOG = "log"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class GraphType(str, Enum):
    """Origin-style figure templates: how a graph arranges its layers.

    The type is a *preset* over ``layout_rows`` / ``layout_cols`` and the panel
    spacing: it does not itself create or delete plots, so switching type never
    loses data.
    """

    SIMPLE = "simple"        # one panel, one plot frame
    STACK = "stack"          # panels stacked vertically, sharing X
    STACK_LINE = "stack-line"  # one panel, one band per layer, sharing X
    DOUBLE_Y = "double-y"    # one panel with a secondary (right) Y axis
    X_TWIN = "x-twin"        # panels side by side, sharing Y
    GRID = "grid"            # an R x C grid of panels

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


#: Every graph type, in the order they appear in menus and combos.
GRAPH_TYPES = (
    GraphType.SIMPLE,
    GraphType.STACK,
    GraphType.STACK_LINE,
    GraphType.DOUBLE_Y,
    GraphType.X_TWIN,
    GraphType.GRID,
)

#: Human-readable labels for the graph types.
GRAPH_TYPE_LABELS = {
    GraphType.SIMPLE.value: "Simple",
    GraphType.STACK.value: "Stack (vertical panels)",
    GraphType.STACK_LINE.value: "Stacked line (bands)",
    GraphType.DOUBLE_Y.value: "Double Y (2Y)",
    GraphType.X_TWIN.value: "X-Twin (side-by-side panels)",
    GraphType.GRID.value: "Grid (multi-panel)",
}


def graph_type_label(value: GraphType | str | None) -> str:
    """Return the display label for a graph type value (tolerant of junk)."""
    try:
        key = GraphType(value or GraphType.SIMPLE).value
    except ValueError:
        key = GraphType.SIMPLE.value
    return GRAPH_TYPE_LABELS.get(key, "Simple")


#: Line-dash presets accepted by every backend (canvas + matplotlib export).
LINE_STYLES = ("solid", "dash", "dot", "dashdot", "longdash")

#: Orientation tokens for :class:`ReferenceLine`.
REFERENCE_ORIENTATIONS = ("h", "v")


_PALETTE = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#e377c2",
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
    line_style: str = "solid"  # one of LINE_STYLES
    z: str = ""  # colour/height column for Z_STYLES
    cmap: str = "viridis"  # colormap for colour-mapped / heatmap / contour styles

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "x": self.x,
            "y": self.y,
            "yerr": self.yerr,
            "xerr": self.xerr,
            "style": PlotStyle(self.style).value,
            "color": self.color,
            "line_width": self.line_width,
            "symbol": self.symbol,
            "symbol_size": self.symbol_size,
            "legend": self.legend,
            "y_axis": self.y_axis,
            "line_style": self.line_style,
            "z": self.z,
            "cmap": self.cmap,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlotSpec":
        return cls(
            source=payload["source"],
            x=payload["x"],
            y=payload["y"],
            yerr=payload.get("yerr"),
            xerr=payload.get("xerr"),
            style=PlotStyle(payload.get("style", PlotStyle.LINE_SYMBOL)),
            color=payload.get("color", ""),
            line_width=payload.get("line_width", 2.0),
            symbol=payload.get("symbol", "o"),
            symbol_size=payload.get("symbol_size", 7.0),
            legend=payload.get("legend", ""),
            y_axis=payload.get("y_axis", "left"),
            line_style=payload.get("line_style", "solid"),
            z=payload.get("z", ""),
            cmap=payload.get("cmap", "viridis"),
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
        return {
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "color": self.color,
            "size": self.size,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Annotation":
        return cls(
            text=payload.get("text", ""),
            x=payload.get("x", 0.05),
            y=payload.get("y", 0.95),
            color=payload.get("color", "#000000"),
            size=payload.get("size", 11.0),
        )


@dataclass
class ReferenceLine:
    """A horizontal or vertical guide line drawn across a layer's axes.

    ``orientation`` is ``"h"`` for a line at ``y = position`` or ``"v"`` for a line
    at ``x = position``. Reference lines are *not* data: they are never downsampled,
    never appear in the legend, and carry no worksheet source.
    """

    orientation: str = "h"
    position: float = 0.0
    color: str = "#888888"
    width: float = 1.5
    line_style: str = "dash"
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "orientation": self.orientation,
            "position": self.position,
            "color": self.color,
            "width": self.width,
            "line_style": self.line_style,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReferenceLine":
        return cls(
            orientation=payload.get("orientation", "h"),
            position=payload.get("position", 0.0),
            color=payload.get("color", "#888888"),
            width=payload.get("width", 1.5),
            line_style=payload.get("line_style", "dash"),
            label=payload.get("label", ""),
        )


@dataclass
class Layer:
    """A plotting layer with its own axes configuration."""

    name: str = "Layer 1"
    plots: list[PlotSpec] = field(default_factory=list)
    ref_lines: list[ReferenceLine] = field(default_factory=list)
    x_scale: AxisScale = AxisScale.LINEAR
    y_scale: AxisScale = AxisScale.LINEAR
    x_label: str = ""
    y_label: str = ""
    y2_label: str = ""
    label_font_family: str = ""
    label_font_size: float = 12.0
    label_color: str = ""
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    show_legend: bool = True
    minor_ticks: bool = True
    tick_direction: str = "out"
    show_y_axis: bool = True  # hide ticks/labels/spine for clean stacked panels
    #: How the layer's Y values are drawn: "absolute" or "normalized" (0..1).
    y_mode: str = "absolute"
    z_label: str = "Value"  # colourbar / 3D z-axis label

    def __setattr__(self, name: str, value: Any) -> None:
        """Keep axis scales as :class:`AxisScale` even when set from UI strings.

        Widgets store enum values as plain ``str`` (``"linear"``/``"log"``)
        when the enum subclasses ``str``; normalising here means every consumer
        (export, canvas, code generator) can rely on ``.value``.
        """
        if name in ("x_scale", "y_scale"):
            try:
                value = AxisScale(value)
            except (TypeError, ValueError):
                value = AxisScale.LINEAR
        if name == "y_mode":
            value = str(value or "absolute")
            if value not in Y_MODES:
                value = "absolute"
        super().__setattr__(name, value)

    def add_plot(self, spec: PlotSpec) -> PlotSpec:
        self.plots.append(spec)
        return spec

    def remove_plot(self, spec: PlotSpec) -> int:
        index = self.plots.index(spec)
        del self.plots[index]
        return index

    def add_ref_line(self, line: ReferenceLine) -> ReferenceLine:
        self.ref_lines.append(line)
        return line

    def remove_ref_line(self, line: ReferenceLine) -> int:
        index = self.ref_lines.index(line)
        del self.ref_lines[index]
        return index

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "plots": [p.to_dict() for p in self.plots],
            "ref_lines": [r.to_dict() for r in self.ref_lines],
            "x_scale": AxisScale(self.x_scale).value,
            "y_scale": AxisScale(self.y_scale).value,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "y2_label": self.y2_label,
            "x_min": self.x_min,
            "x_max": self.x_max,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "show_legend": self.show_legend,
            "minor_ticks": self.minor_ticks,
            "tick_direction": self.tick_direction,
            "show_y_axis": self.show_y_axis,
            "y_mode": self.y_mode,
            "z_label": self.z_label,
            "label_font_family": self.label_font_family,
            "label_font_size": self.label_font_size,
            "label_color": self.label_color,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Layer":
        layer = cls(payload.get("name", "Layer 1"))
        layer.plots = [PlotSpec.from_dict(p) for p in payload.get("plots", [])]
        layer.ref_lines = [
            ReferenceLine.from_dict(r) for r in payload.get("ref_lines", [])
        ]
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
        layer.minor_ticks = payload.get("minor_ticks", True)
        layer.show_y_axis = bool(payload.get("show_y_axis", True))
        layer.y_mode = str(payload.get("y_mode", "absolute") or "absolute")
        td = payload.get("tick_direction", "out")
        if td == "both":
            td = "inout"
        layer.tick_direction = td
        layer.z_label = payload.get("z_label", "Value")
        layer.label_font_family = payload.get("label_font_family", "")
        layer.label_font_size = payload.get("label_font_size", 12.0)
        layer.label_color = payload.get("label_color", "")
        return layer

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Layer(name={self.name!r}, plots={len(self.plots)})"


class Graph:
    """A figure: a stack of layers sharing a canvas."""

    def __init__(self, name: str = "Graph1", title: str = "") -> None:
        self.name = name
        self.title = title
        self.title_font_family: str = ""
        self.title_font_size: float = 14.0
        self.title_color: str = ""
        self.graph_type: str = GraphType.SIMPLE.value
        self.layout_rows: int = 1
        self.layout_cols: int = 1
        #: Space between panels, as a percentage of a panel's size (grid/x-twin).
        self.panel_gap_x: float = 12.0
        self.panel_gap_y: float = 12.0
        #: Vertical offset between stacked panels (the "Y delta" of a stack).
        self.y_delta: float = 0.0
        #: Distance between two bands of a stacked-line figure, in band units.
        self.stack_offset: float = 1.2
        self.layers: list[Layer] = [Layer()]
        self.annotations: list[Annotation] = []
        self.journal_preset: str = ""
        self.plot_theme: str = ""

    def add_layer(self, layer: Layer | None = None) -> Layer:
        layer = layer or Layer(f"Layer {len(self.layers) + 1}")
        self.layers.append(layer)
        self.sync_layout()
        return layer

    def remove_layer(self, layer: Layer) -> int:
        index = self.layers.index(layer)
        del self.layers[index]
        self.sync_layout()
        return index

    def sync_layout(self) -> None:
        """Recompute ``layout_rows``/``layout_cols`` from the graph type.

        Simple and Double-Y graphs use a single panel; a Stack lays its layers
        out in one column; an X-Twin lays them out in one row; a Grid keeps the
        user's explicit rows/columns. This keeps the number of panels in step
        with the number of layers as layers are added or removed.
        """
        try:
            gtype = GraphType(getattr(self, "graph_type", GraphType.SIMPLE.value))
        except ValueError:
            gtype = GraphType.SIMPLE
        layers = max(1, len(self.layers))
        if gtype == GraphType.STACK:
            self.layout_rows, self.layout_cols = layers, 1
        elif gtype == GraphType.STACK_LINE:
            # One panel holds every band: the layers are the curves, not the
            # panels.
            self.layout_rows, self.layout_cols = 1, 1
        elif gtype == GraphType.X_TWIN:
            self.layout_rows, self.layout_cols = 1, layers
        elif gtype == GraphType.GRID:
            self.layout_rows = max(1, int(self.layout_rows or 1))
            self.layout_cols = max(1, int(self.layout_cols or 1))
        else:
            self.layout_rows, self.layout_cols = 1, 1

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
            "name": self.name,
            "title": self.title,
            "title_font_family": self.title_font_family,
            "title_font_size": self.title_font_size,
            "title_color": self.title_color,
            "graph_type": self.graph_type,
            "layout_rows": self.layout_rows,
            "layout_cols": self.layout_cols,
            "panel_gap_x": self.panel_gap_x,
            "panel_gap_y": self.panel_gap_y,
            "y_delta": self.y_delta,
            "stack_offset": self.stack_offset,
            "layers": [l.to_dict() for l in self.layers],
            "annotations": [a.to_dict() for a in self.annotations],
            "journal_preset": self.journal_preset,
            "plot_theme": self.plot_theme,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Graph":
        graph = cls(payload.get("name", "Graph1"), payload.get("title", ""))
        graph.title_font_family = payload.get("title_font_family", "")
        graph.title_font_size = payload.get("title_font_size", 14.0)
        graph.title_color = payload.get("title_color", "")
        graph.graph_type = payload.get("graph_type", GraphType.SIMPLE.value)
        graph.layout_rows = int(payload.get("layout_rows", 1) or 1)
        graph.layout_cols = int(payload.get("layout_cols", 1) or 1)
        graph.panel_gap_x = float(payload.get("panel_gap_x", 12.0))
        graph.panel_gap_y = float(payload.get("panel_gap_y", 12.0))
        graph.y_delta = float(payload.get("y_delta", 0.0))
        graph.stack_offset = float(payload.get("stack_offset", 1.2))
        layers = [Layer.from_dict(l) for l in payload.get("layers", [])]
        if layers:
            graph.layers = layers
        graph.annotations = [
            Annotation.from_dict(a) for a in payload.get("annotations", [])
        ]
        graph.journal_preset = payload.get("journal_preset", "")
        graph.plot_theme = payload.get("plot_theme", "")
        return graph

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Graph(name={self.name!r}, layers={self.num_layers})"
