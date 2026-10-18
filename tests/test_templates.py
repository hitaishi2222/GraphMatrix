"""Graph style template tests (M2)."""

from __future__ import annotations

import numpy as np
import pytest

from graphmatrix.core.model import Annotation, AxisScale, ColumnType, Graph, PlotSpec, PlotStyle, Project, Workbook, Worksheet
from graphmatrix.core.templates import apply_template, graph_to_template, load_template, save_template


def _graph(style=PlotStyle.SCATTER, color="#112233", x_scale=AxisScale.LINEAR):
    graph = Graph("G", title="T")
    layer = graph.first_layer
    layer.x_scale = x_scale
    layer.plots.append(PlotSpec("B/S", "X1", "Y1", style=style, color=color, legend="d", y_axis="right"))
    graph.annotations.append(Annotation("note", color="#ff0000", size=14))
    return graph


def test_graph_to_template_roundtrips_style():
    template = graph_to_template(_graph())
    assert template["format"] == "graphmatrix-graph-template"
    assert template["layers"][0]["plots"][0]["style"] == "scatter"
    assert template["layers"][0]["x_scale"] == "linear"
    assert template["annotation_style"][0]["size"] == 14


def test_apply_template_changes_style_not_data():
    source = _graph(style=PlotStyle.SCATTER, color="#112233", x_scale=AxisScale.LOG)
    template = graph_to_template(source)

    target = Graph("G2")
    layer = target.first_layer
    layer.plots.append(PlotSpec("B/S", "X2", "Y2", style=PlotStyle.LINE, color="#ffffff"))
    target.annotations.append(Annotation("other"))

    apply_template(target, template)

    spec = target.first_layer.plots[0]
    # Data references are untouched...
    assert (spec.x, spec.y, spec.source) == ("X2", "Y2", "B/S")
    # ...but the look is copied.
    assert spec.style is PlotStyle.SCATTER
    assert spec.color == "#112233"
    assert spec.y_axis == "right"
    assert target.first_layer.x_scale is AxisScale.LOG
    assert target.annotations[0].size == 14


def test_template_file_roundtrip(tmp_path):
    graph = _graph()
    path = save_template(graph, tmp_path / "style.rstpl", name="Pub")
    loaded = load_template(path)
    assert loaded["name"] == "Pub"

    other = Graph("G3")
    other.first_layer.plots.append(PlotSpec("B/S", "X", "Y"))
    apply_template(other, loaded)
    assert other.first_layer.plots[0].style is PlotStyle.SCATTER


def test_load_template_rejects_foreign_file(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"format": "something-else"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_template(path)


def test_graph_annotation_and_y_axis_serialization():
    graph = _graph()
    restored = Graph.from_dict(graph.to_dict())
    assert restored.layers[0].plots[0].y_axis == "right"
    assert len(restored.annotations) == 1
    assert restored.annotations[0].text == "note"
