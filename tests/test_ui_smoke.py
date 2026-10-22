"""Headless UI smoke test (PySide6 offscreen).

Exercises the real window: sample data, graph tab, plot edit, analysis dialog,
console, export, macro recording, and undo.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from graphmatrix.core.commands import AddPlotCommand
from graphmatrix.core.model import PlotSpec


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_full_workflow(app, tmp_path):
    from graphmatrix.core.io.export import export_graph
    from graphmatrix.ui.main_window import MainWindow

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

        graph_view.commands.push(
            AddPlotCommand(
                graph,
                graph.first_layer,
                PlotSpec("Book1/Sheet1", "X1", "Y1", legend="extra"),
            )
        )
        graph_view.refresh()
        assert sum(len(layer.plots) for layer in graph.layers) >= 2

        # analysis dialog (construct + run without exec)
        from graphmatrix.ui.analysis_dialogs import FitDialog

        fit = FitDialog(window.project)
        result = fit.run()
        assert result.kind == "fit"

        # console executes against the live project
        window.console.run_script(
            "api.add_column('Book1/Sheet1', 'Z1', 'Y', data=[1, 2, 3])"
        )
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

    from graphmatrix.core.commands import AddAnnotationCommand, ReorderColumnsCommand
    from graphmatrix.core.model import Annotation
    from graphmatrix.core.templates import apply_template, graph_to_template
    from graphmatrix.ui.main_window import MainWindow
    from graphmatrix.ui.worksheet_view import WorksheetView

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
        window.commands.push(
            AddAnnotationCommand(graph, Annotation("note", x=0.2, y=0.8))
        )
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

        from graphmatrix.ui.widgets import COLUMN_MIME

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


def test_theme_preset_switching(app):
    from graphmatrix.ui import theme
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    original = theme.current_preset()
    try:
        window._action_sample_data()
        window._action_add_graph()

        for preset in theme.presets():
            window._action_set_theme(preset.id)
            assert theme.current_preset() == preset.id
            assert theme.is_dark() is preset.dark
            assert window._theme_actions[preset.id].isChecked()

        # The action group stays exclusive: exactly one preset is checked.
        checked = [
            pid for pid, action in window._theme_actions.items() if action.isChecked()
        ]
        assert checked == [theme.current_preset()]
    finally:
        theme.set_preset(original)
        window.close()


def test_rename_project_workbook_and_worksheet(app):
    from graphmatrix.core.model import Graph, PlotSpec
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        sheet = window.project.workbooks[0].sheets[0]
        book = window.project.workbooks[0]

        # A graph sourced from the workbook, to prove renames cascade.
        graph = Graph("G")
        graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1"))
        window.project.add_graph(graph)

        # Rename the project (no cascade), and check the window title updates.
        window._apply_rename(window.project, "My Experiment")
        assert window.project.name == "My Experiment"
        assert "My Experiment" in window.windowTitle()

        # Rename the workbook: the graph's source must follow.
        window._apply_rename(book, "Measure")
        assert book.name == "Measure"
        assert graph.first_layer.plots[0].source == "Measure/Sheet1"

        # Rename the worksheet: the graph's source must follow too.
        window._apply_rename(sheet, "Run1")
        assert sheet.name == "Run1"
        assert graph.first_layer.plots[0].source == "Measure/Run1"

        # Undo unwinds the cascade (one step at a time).
        window.commands.undo()
        assert sheet.name == "Sheet1"
        assert graph.first_layer.plots[0].source == "Measure/Sheet1"
        window.commands.undo()
        assert book.name == "Book1"
        assert graph.first_layer.plots[0].source == "Book1/Sheet1"

        # Validation rejects duplicate names without touching the model.
        from graphmatrix.core.model import Workbook

        window.project.add_workbook(Workbook("Measure"))
        assert window._rename_available(window.project.workbooks[0], "Measure") is False
        assert window._rename_available(window.project.workbooks[0], "Fresh") is True
    finally:
        window.close()


def test_plot_column_from_worksheet(app):
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        sheet = window.project.workbooks[0].sheets[0]
        window._open_sheet_tab(sheet)
        view = window._views[id(sheet)]

        # Selecting the whole column (as the user described) surfaces that column.
        from PySide6.QtWidgets import QTableWidgetSelectionRange

        view.table.setRangeSelected(
            QTableWidgetSelectionRange(0, 1, max(sheet.num_rows - 1, 0), 1), True
        )
        assert view._selected_column_indices() == [1]

        # What the worksheet context menu emits: plot the selected column.
        view.plot_column_requested.emit("Y1")
        assert window.project.graphs, "a graph should be created on demand"
        graph = window.project.graphs[-1]
        plots = [p for layer in graph.layers for p in layer.plots]
        assert any(p.x == "X1" and p.y == "Y1" for p in plots)

        # A second request adds to the now-active graph rather than replacing it.
        before = sum(len(layer.plots) for layer in graph.layers)
        view.plot_column_requested.emit("X1")
        after = sum(len(layer.plots) for layer in graph.layers)
        assert after == before + 1
    finally:
        window.close()


def test_reference_lines_hover_and_slope(app):
    from graphmatrix.core.model import ReferenceLine
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        window._action_add_graph()
        view = window._active_graph_view
        graph = view.graph

        # Add an H-line and a V-line (bypassing the modal dialog), both undoable.
        view.add_reference_line("h", ReferenceLine("h", 0.5, label="zero"))
        view.add_reference_line("v", ReferenceLine("v", 3.0))
        assert len(graph.first_layer.ref_lines) == 2

        assert view.canvas is not None
        # Removing a line is one undo step.
        view.ref_list.setCurrentRow(0)
        view.remove_reference_line()
        assert len(graph.first_layer.ref_lines) == 1
        window.commands.undo()
        assert len(graph.first_layer.ref_lines) == 2

        # Hover readout toggles through the menu action and the sidebar button.
        window.registry.action("graph.hover").setChecked(True)
        window._action_toggle_hover()
        assert view.hover_enabled is True
        view.set_hover(False)
        assert window.registry.action("graph.hover").isChecked() is False

        # Slope dialog runs against the sample data.
        from graphmatrix.ui.analysis_dialogs import SlopeDialog

        dialog = SlopeDialog(window.project)
        dialog.x0_edit.setText("0.5")
        dialog.x1_edit.setText("1.5")
        result = dialog.run()
        assert result.kind == "slope"
        assert "Slope" in result.summary

        # The slope result can annotate the active graph.
        from graphmatrix.ui.analysis_dialogs import AnalysisResultDialog

        before_ann = len(graph.annotations)
        result_dialog = AnalysisResultDialog(
            result,
            project=window.project,
            commands=window.commands,
            add_annotation=window._add_annotation_to_active_graph,
        )
        result_dialog._annotate_on_graph()
        assert len(graph.annotations) == before_ann + 1
        assert "slope" in graph.annotations[-1].text
    finally:
        window.close()


def test_provenance_journal_and_palette(app, tmp_path):
    from PySide6.QtCore import Qt

    from graphmatrix.core.code_export import project_to_script
    from graphmatrix.core.report import export_analysis_bundle
    from graphmatrix.ui.command_palette import CommandPalette
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        window._action_add_graph()
        graph = window._active_graph_view.graph

        # Journal preset restyles the active graph, is recorded, and undoes.
        window._action_apply_journal("Nature (single column)")
        assert graph.journal_preset == "Nature (single column)"
        assert graph.first_layer.plots[0].line_width == 1.0
        assert window._journal_actions["Nature (single column)"].isChecked()
        window.commands.undo()
        assert graph.journal_preset == ""

        # Provenance renders a methods write-up.
        window.provenance.record_import("run.csv", "Book1")
        assert "Imported run.csv" in window.provenance.methods_markdown(window.project)

        # The palette filters the action registry.
        palette = CommandPalette(window.registry)
        palette.search.setText("export active graph")
        assert palette.list.count() >= 1
        assert palette.list.item(0).data(Qt.ItemDataRole.UserRole) == "export.graph"

        # Figure-as-code and bundles write real files.
        assert "api.add_graph" in project_to_script(window.project)
        bundle = export_analysis_bundle(
            window.project, window.provenance, tmp_path / "bundle", figure_formats=()
        )
        assert (bundle.root / "reproduce.py").exists()
        assert (bundle.root / "methods.md").exists()
    finally:
        window.close()


def test_digitize_dialog_extracts(app, tmp_path):
    import numpy as np
    from PIL import Image

    from graphmatrix.ui.digitize_dialog import DigitizeDialog

    image = np.full((120, 160, 3), 255, dtype=np.uint8)
    for col in range(20, 140):
        row = round(100 - 0.5 * (col - 20))
        image[row, col] = 0
    path = tmp_path / "plot.png"
    Image.fromarray(image).save(path)

    dialog = DigitizeDialog()
    try:
        dialog._image_path = path
        dialog._pixel_spins[0].setValue(20)
        dialog._value_spins[0].setValue(0.0)
        dialog._pixel_spins[1].setValue(140)
        dialog._value_spins[1].setValue(12.0)
        dialog._pixel_spins[2].setValue(100)
        dialog._value_spins[2].setValue(0.0)
        dialog._pixel_spins[3].setValue(40)
        dialog._value_spins[3].setValue(6.0)
        result = dialog.run()
        assert result.kind == "digitize"
        x, _y = result.curves["Digitized"]
        assert x.size == 120
    finally:
        dialog.close()


def test_the_graph_editor_appears_with_a_graph(app):
    """The editor panel is useless without a graph, so it starts hidden."""
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        assert window.dock_editor.isHidden()
        window._action_add_graph()
        window._open_graph_tab(window.project.graphs[0])
        assert not window.dock_editor.isHidden()
        assert "panel" in window._status_info.text()
    finally:
        window.close()


def test_the_status_bar_names_the_open_sheet(app):
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        sheet = window.project.workbooks[0].sheets[0]
        assert f"{sheet.num_rows} rows" in window._status_info.text()
    finally:
        window.close()


def test_a_new_project_drops_the_old_selection_and_editor(app):
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        window._action_add_graph()
        window._open_graph_tab(window.project.graphs[0])
        assert not window.dock_editor.isHidden()
        assert window.properties_panel._obj is not None

        window._new_project(confirm=False)
        assert window.dock_editor.isHidden()
        assert window.properties_panel._obj is None
        assert window._status_info.text() == ""
    finally:
        window.close()


def test_tab_navigation_cycles_and_wraps(app):
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        window._action_add_graph()
        window._open_graph_tab(window.project.graphs[0])
        first = window.tabs.currentIndex()
        window._action_next_tab(1)
        second = window.tabs.currentIndex()
        assert second != first
        window._action_next_tab(1)
        window._action_next_tab(1)
        assert window.tabs.currentIndex() in {first, second}
        window._action_next_tab(-1)
        assert 0 <= window.tabs.currentIndex() < window.tabs.count()
    finally:
        window.close()
