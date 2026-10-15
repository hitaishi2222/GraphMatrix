"""Plot resolution / column-pairing tests (core, Qt-free)."""

from __future__ import annotations

from respot.core.model import ColumnType, Project, Workbook, Worksheet
from respot.core.plotting import make_default_graph, make_plot_for_column, resolve_plot


def _project() -> tuple[Project, Worksheet]:
    project = Project("P")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0, 2.0])
    sheet.add_column("Y1", ColumnType.Y, [0.0, 1.0, 4.0])
    sheet.add_column("Y2", ColumnType.Y, [1.0, 2.0, 3.0])
    return project, sheet


def test_make_plot_for_y_column_pairs_with_first_x():
    project, _ = _project()
    spec = make_plot_for_column(project, "Book1/Sheet1", "Y2")
    assert spec is not None
    assert (spec.x, spec.y) == ("X1", "Y2")
    resolved = resolve_plot(project, spec)
    assert resolved is not None and resolved.y.tolist() == [1.0, 2.0, 3.0]


def test_make_plot_for_x_column_pairs_with_first_y():
    project, _ = _project()
    spec = make_plot_for_column(project, "Book1/Sheet1", "X1")
    assert spec is not None
    assert (spec.x, spec.y) == ("X1", "Y1")


def test_make_plot_for_unknown_source_or_column_returns_none():
    project, _ = _project()
    assert make_plot_for_column(project, "Nope/Nope", "Y1") is None
    assert make_plot_for_column(project, "Book1/Sheet1", "ZZ") is None


def test_make_default_graph_seeds_first_xy():
    project, _ = _project()
    graph = make_default_graph(project, "G")
    spec = graph.first_layer.plots[0]
    assert (spec.source, spec.x, spec.y) == ("Book1/Sheet1", "X1", "Y1")
