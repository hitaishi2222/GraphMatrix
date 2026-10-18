"""Publication export tests (M4)."""

from __future__ import annotations

import numpy as np
import pytest

from graphmatrix.core.io.export import export_graph
from graphmatrix.core.model import (
    Annotation,
    ColumnType,
    Graph,
    PlotSpec,
    PlotStyle,
    Project,
    Workbook,
    Worksheet,
)


def _project_with_graph():
    project = Project("T")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0, 2 * np.pi, 100)
    sheet.add_column("X1", ColumnType.X, x, units="rad")
    sheet.add_column("Y1", ColumnType.Y, np.sin(x), units="V")
    graph = project.add_graph(Graph("Graph1", title="Sine"))
    graph.first_layer.add_plot(
        PlotSpec("Book1/Sheet1", "X1", "Y1", style=PlotStyle.LINE_SYMBOL, legend="sin")
    )
    return project, graph


def test_export_vector_and_raster(tmp_path):
    project, graph = _project_with_graph()
    for ext in ("pdf", "svg", "eps", "png"):
        out = export_graph(graph, project, tmp_path / f"fig.{ext}")
        assert out.exists() and out.stat().st_size > 0


def test_export_all_styles(tmp_path):
    project, graph = _project_with_graph()
    layer = graph.first_layer
    for style in PlotStyle:
        layer.plots[0].style = style
        out = export_graph(graph, project, tmp_path / f"fig_{style.name}.png")
        assert out.exists() and out.stat().st_size > 0


def test_export_dual_axis_and_annotation(tmp_path):
    project = Project("T")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0, 10, 120)
    sheet.add_column("X1", ColumnType.X, x)
    sheet.add_column("Y1", ColumnType.Y, np.sin(x))
    sheet.add_column("Y2", ColumnType.Y, 100 * np.cos(x))
    graph = project.add_graph(Graph("Graph1", title="Dual"))
    layer = graph.first_layer
    layer.y2_label = "Second"
    layer.plots.append(PlotSpec("Book1/Sheet1", "X1", "Y1", legend="sin"))
    layer.plots.append(
        PlotSpec("Book1/Sheet1", "X1", "Y2", legend="cos", y_axis="right")
    )
    graph.annotations.append(Annotation("peak", x=0.6, y=0.2))

    out = export_graph(graph, project, tmp_path / "dual.pdf")
    assert out.exists() and out.stat().st_size > 0


def test_export_grid_and_stack_layouts(tmp_path):
    from graphmatrix.core.model import Layer

    project, graph = _project_with_graph()
    second = Layer("Layer 2")
    second.plots.append(PlotSpec("Book1/Sheet1", "X1", "Y1", legend="sin2"))
    graph.layers.append(second)

    graph.graph_type = "grid"
    graph.layout_rows, graph.layout_cols = 2, 2
    graph.sync_layout()
    grid_out = export_graph(graph, project, tmp_path / "grid.png")
    assert grid_out.exists() and grid_out.stat().st_size > 0

    graph.graph_type = "stack"
    graph.y_delta = 1.0
    graph.sync_layout()
    stack_out = export_graph(graph, project, tmp_path / "stack.pdf")
    assert stack_out.exists() and stack_out.stat().st_size > 0


def test_unsupported_format_raises_a_clear_error(tmp_path):
    project, graph = _project_with_graph()
    with pytest.raises(ValueError, match="Unsupported export format"):
        export_graph(graph, project, tmp_path / "fig.bmp")


def test_jpeg_suffix_maps_to_jpg(tmp_path):
    project, graph = _project_with_graph()
    out = export_graph(graph, project, tmp_path / "fig.jpeg")
    assert out.exists() and out.stat().st_size > 0
