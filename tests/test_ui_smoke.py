"""Headless UI smoke test (PySide6 offscreen).

Exercises the real window: sample data, graph tab, plot edit, analysis dialog,
console, export, macro recording, and undo.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from respot.core.commands import AddPlotCommand  # noqa: E402
from respot.core.model import PlotSpec  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_full_workflow(app, tmp_path):
    from respot.core.io.export import export_graph
    from respot.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False  # no modal prompt in headless runs
    try:
        assert window.project.workbooks

        window._action_sample_data()
        sheet = window.project.workbooks[0].sheets[0]
        assert sheet.column_names == ["X1", "Y1"]

        window._action_add_graph()
        graph_view = window._active_graph_view
        assert graph_view is not None
        graph = graph_view.graph
        assert sum(len(layer.plots) for layer in graph.layers) >= 1

        graph_view.commands.push(AddPlotCommand(graph, graph.first_layer, PlotSpec("Book1/Sheet1", "X1", "Y1", legend="extra")))
        graph_view.refresh()
        assert sum(len(layer.plots) for layer in graph.layers) >= 2

        # analysis dialog (construct + run without exec)
        from respot.ui.analysis_dialogs import FitDialog

        fit = FitDialog(window.project)
        result = fit.run()
        assert result.kind == "fit"

        # console executes against the live project
        window.console.run_script("api.add_column('Book1/Sheet1', 'Z1', 'Y', data=[1, 2, 3])")
        assert "Z1" in sheet.column_names

        # export
        out = export_graph(graph, window.project, tmp_path / "fig.pdf")
        assert out.exists()

        # macro recording
        window.registry.action("tools.record").trigger()
        window._action_sample_data()
        window.registry.action("tools.record").trigger()
        assert "api.add_column" in window.recorder.script()

        # undo
        before = len(sheet.columns)
        window.commands.undo()
        assert len(sheet.columns) < before
    finally:
        window.close()


def test_graph_and_sheet_extras(app, tmp_path):
    from PySide6.QtWidgets import QApplication

    from respot.core.commands import AddAnnotationCommand, ReorderColumnsCommand
    from respot.core.model import Annotation
    from respot.core.templates import apply_template, graph_to_template
    from respot.ui.main_window import MainWindow
    from respot.ui.worksheet_view import WorksheetView

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        sheet = window.project.workbooks[0].sheets[0]

        window._action_add_graph()
        graph_view = window._active_graph_view
        graph = graph_view.graph

        # Dual Y axis: mark the plot as right-axis and re-render.
        graph.first_layer.plots[0].y_axis = "right"
        graph_view.refresh()
        assert graph.first_layer.plots[0].y_axis == "right"

        # Annotation add + render.
        window.commands.push(AddAnnotationCommand(graph, Annotation("note", x=0.2, y=0.8)))
        graph_view.refresh()
        assert len(graph.annotations) == 1

        # Template capture/apply should not raise and must not touch data refs.
        apply_template(graph, graph_to_template(graph))
        assert graph.first_layer.plots[0].y == "Y1"

        # Worksheet clipboard paste is one undoable step.
        view = WorksheetView(sheet, window.commands, "Book1/Sheet1")
        QApplication.clipboard().setText("10\t20\n30\t40")
        view.table.setCurrentCell(0, 0)
        view._paste()
        assert sheet.column("X1").data[0] == 10.0
        assert sheet.column("Y1").data[1] == 40.0
        window.commands.undo()
        assert sheet.column("X1").data[0] == 0.0

        # Column reorder is undoable.
        order = list(reversed(sheet.columns))
        window.commands.push(ReorderColumnsCommand(sheet, order))
        assert sheet.column_names[0] == order[0].name
        window.commands.undo()
        assert sheet.column_names[0] == "X1"

        # Project Explorer exposes draggable column items, and a drop adds a plot.
        from PySide6.QtCore import Qt

        from respot.ui.widgets import COLUMN_MIME

        window.project_panel.set_project(window.project)
        tree = window.project_panel.tree
        column_item = tree.topLevelItem(0).child(0).child(0).child(0)
        payload = column_item.data(0, Qt.ItemDataRole.UserRole + 2)
        assert payload == {"source": "Book1/Sheet1", "column": "X1"}
        mime = tree.mimeData([column_item])
        assert mime.hasFormat(COLUMN_MIME)

        before = sum(len(layer.plots) for layer in graph.layers)
        graph_view.add_column_plot(payload["source"], payload["column"])
        assert sum(len(layer.plots) for layer in graph.layers) == before + 1
    finally:
        window.close()
