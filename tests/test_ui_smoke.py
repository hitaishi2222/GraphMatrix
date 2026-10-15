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
