"""Graph style templates.

A template captures the *look* of a graph (plot styles, axis configuration,
annotation styling) without any data references, so it can be saved to a file and
re-applied to a different graph. Plot/annotation counts are matched by position;
extra entries in the graph are left untouched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import AxisScale, Graph, PlotStyle

TEMPLATE_FORMAT = "respot-graph-template"
TEMPLATE_VERSION = 1

_PLOT_FIELDS = ("style", "color", "line_width", "symbol", "symbol_size", "y_axis", "line_style")
_LAYER_FIELDS = ("x_scale", "y_scale", "x_label", "y_label", "y2_label", "show_legend")
_SEGMENT_FIELDS = ("x_min", "x_max", "y_min", "y_max")


def _plot_style(spec) -> dict[str, Any]:
    data: dict[str, Any] = {f: getattr(spec, f) for f in _PLOT_FIELDS}
    data["style"] = PlotStyle(spec.style).value
    return data


def _layer_style(layer) -> dict[str, Any]:
    data: dict[str, Any] = {f: getattr(layer, f) for f in _LAYER_FIELDS}
    data["x_scale"] = AxisScale(layer.x_scale).value
    data["y_scale"] = AxisScale(layer.y_scale).value
    return data


def graph_to_template(graph: Graph, *, name: str = "") -> dict[str, Any]:
    return {
        "format": TEMPLATE_FORMAT,
        "version": TEMPLATE_VERSION,
        "name": name or graph.name,
        "title": graph.title,
        "annotation_style": [{"color": a.color, "size": a.size} for a in graph.annotations],
        "layers": [
            {**_layer_style(layer), "plots": [_plot_style(p) for p in layer.plots]}
            for layer in graph.layers
        ],
    }


def _apply_layer_field(layer, field: str, value: Any) -> None:
    if field in ("x_scale", "y_scale"):
        setattr(layer, field, AxisScale(value))
    else:
        setattr(layer, field, value)


def _apply_plot_field(spec, field: str, value: Any) -> None:
    if field == "style":
        setattr(spec, field, PlotStyle(value))
    else:
        setattr(spec, field, value)


def apply_template(graph: Graph, template: dict[str, Any]) -> None:
    for layer_index, layer_style in enumerate(template.get("layers", [])):
        if layer_index >= len(graph.layers):
            break
        layer = graph.layers[layer_index]
        for field in _LAYER_FIELDS:
            if field in layer_style:
                _apply_layer_field(layer, field, layer_style[field])
        for plot_index, plot_style in enumerate(layer_style.get("plots", [])):
            if plot_index >= len(layer.plots):
                break
            spec = layer.plots[plot_index]
            for field in _PLOT_FIELDS:
                if field in plot_style:
                    _apply_plot_field(spec, field, plot_style[field])

    for index, ann_style in enumerate(template.get("annotation_style", [])):
        if index >= len(graph.annotations):
            break
        if "color" in ann_style:
            graph.annotations[index].color = ann_style["color"]
        if "size" in ann_style:
            graph.annotations[index].size = ann_style["size"]

    if template.get("title") and not graph.title:
        graph.title = template["title"]


def save_template(graph: Graph, path: str | Path, *, name: str = "") -> Path:
    path = Path(path)
    path.write_text(json.dumps(graph_to_template(graph, name=name), indent=2), encoding="utf-8")
    return path


def load_template(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("format") != TEMPLATE_FORMAT:
        raise ValueError(f"not a Respot graph template (format={payload.get('format')!r})")
    return payload


__all__ = [
    "TEMPLATE_FORMAT",
    "TEMPLATE_VERSION",
    "graph_to_template",
    "apply_template",
    "save_template",
    "load_template",
]
