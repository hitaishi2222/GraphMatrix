"""Publication export tests (M4)."""

from __future__ import annotations

import numpy as np

from respot.core.io.export import export_graph
from respot.core.model import ColumnType, Graph, PlotSpec, PlotStyle, Project, Workbook, Worksheet


def _project_with_graph():
    project = Project("T")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0, 2 * np.pi, 100)
    sheet.add_column("X1", ColumnType.X, x, units="rad")
    sheet.add_column("Y1", ColumnType.Y, np.sin(x), units="V")
    graph = project.add_graph(Graph("Graph1", title="Sine"))
    graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1", style=PlotStyle.LINE_SYMBOL, legend="sin"))
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
