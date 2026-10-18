"""Journal figure preset tests (M8)."""

from __future__ import annotations

from graphmatrix.core.io.export import export_graph
from graphmatrix.core.journals import (
    JOURNAL_PRESETS,
    apply_journal_preset,
    export_rcparams,
    figure_size,
    journal_names,
    preset,
)
from graphmatrix.core.model import ColumnType, Graph, PlotSpec, Project, Workbook, Worksheet


def _graph() -> Graph:
    graph = Graph("Graph1")
    graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1"))
    return graph


def _project_with_graph() -> tuple[Project, Graph]:
    project = Project("J")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    sheet.add_column("X1", ColumnType.X, [1.0, 2.0, 3.0])
    sheet.add_column("Y1", ColumnType.Y, [2.0, 4.0, 6.0])
    graph = project.add_graph(Graph("Graph1"))
    graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1"))
    return project, graph


def test_apply_preset_restyles_plots():
    graph = _graph()
    spec = graph.first_layer.plots[0]
    settings = apply_journal_preset(graph, "Nature (single column)")
    assert graph.journal_preset == "Nature (single column)"
    assert spec.line_width == settings["line_width"] == 1.0
    assert spec.symbol_size == settings["symbol_size"] == 3.5


def test_apply_preset_is_idempotent():
    graph = _graph()
    spec = graph.first_layer.plots[0]
    apply_journal_preset(graph, "Science (double column)")
    apply_journal_preset(graph, "Science (double column)")
    assert spec.line_width == preset("Science (double column)")["line_width"]


def test_unknown_preset_clears_and_falls_back():
    graph = _graph()
    assert preset("Not a Journal") == preset("Default")
    apply_journal_preset(graph, "Not a Journal")
    assert graph.journal_preset == ""


def test_preset_survives_serialization():
    graph = _graph()
    apply_journal_preset(graph, "IEEE (single column)")
    again = Graph.from_dict(graph.to_dict())
    assert again.journal_preset == "IEEE (single column)"


def test_preset_dimensions_and_rcparams():
    width, height = figure_size("Nature (single column)")
    assert (width, height) == (89.0, 70.0)
    rc = export_rcparams("Nature (single column)")
    assert rc["font.size"] == 7.0
    assert rc["lines.linewidth"] == 1.0


def test_journal_names_lead_with_default():
    names = journal_names()
    assert names[0] == "Default"
    assert set(names) == set(JOURNAL_PRESETS)


def test_export_honours_preset_size(tmp_path):
    project, graph = _project_with_graph()
    apply_journal_preset(graph, "APS (single column)")
    out = export_graph(graph, project, tmp_path / "fig.pdf")
    assert out.exists() and out.stat().st_size > 0
