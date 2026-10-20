"""Headless tests for the new UI surfaces: preferences, shortcuts, zoom.

They exercise the real widgets (offscreen), not the model behind them.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setApplicationName("GraphMatrixTests")
    instance.setOrganizationName("GraphMatrixTests")
    yield instance


@pytest.fixture()
def window(app):
    from graphmatrix.ui.main_window import MainWindow

    win = MainWindow()
    win.confirm_on_close = False
    yield win
    win.close()


# -- toolbar and buttons -----------------------------------------------------
def test_toolbar_actions_have_icons_and_shortcut_tooltips(window):
    action_ids = [
        "file.new",
        "file.open",
        "file.save",
        "file.import",
        "edit.undo",
        "data.add_workbook",
        "data.add_worksheet",
        "data.add_graph",
        "data.sample",
        "analyze.fit",
    ]
    for action_id in action_ids:
        action = window.registry.action(action_id)
        assert not action.icon().isNull(), f"{action_id} should have an icon"
        # The shortcut is spelled out in the tooltip, so the user does not
        # have to try the button to find out what it does.
        shortcut = action.shortcut().toString()
        if shortcut:
            assert shortcut in action.toolTip()


def test_toolbar_uses_icons_beside_text(window):
    from PySide6.QtCore import Qt

    assert (
        window.toolbar.toolButtonStyle()
        == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    )


def test_readout_toggle_is_a_compact_switch(window):
    window._action_sample_data()
    window._action_add_graph()
    view = window._active_graph_view
    assert view.hover_check.text() == "Readout"
    assert view.hover_check.isCheckable()
    view.set_hover(False)
    assert view.hover_check.isChecked() is False
    view.set_hover(True)
    assert view.hover_check.isChecked() is True


# -- canvas zoom -------------------------------------------------------------
def test_canvas_reports_the_zoom_level(window):
    window._action_sample_data()
    window._action_add_graph()
    view = window._active_graph_view
    canvas = view.canvas
    assert canvas.zoom_factor() >= 1.0
    # Zooming in makes the panel show less of the data.
    before = canvas.zoom_factor()
    canvas.zoom_in()
    assert canvas.zoom_factor() > before
    canvas.fit()
    assert canvas.zoom_factor() == pytest.approx(1.0, rel=0.05)


def test_zoom_actions_work_on_the_active_graph(window):
    window._action_sample_data()
    window._action_add_graph()
    canvas = window._active_graph_view.canvas
    window._action_zoom_in()
    assert canvas.zoom_factor() > 1.0
    window._action_zoom_fit()
    assert canvas.zoom_factor() == pytest.approx(1.0, rel=0.05)


def test_zoom_shortcuts_are_registered(window):
    expected = {
        "graph.zoom_in": "Ctrl+=",
        "graph.zoom_out": "Ctrl+-",
        "graph.zoom_fit": "Ctrl+0",
    }
    for action_id, shortcut in expected.items():
        action = window.registry.action(action_id)
        assert action.shortcut().toString() == shortcut


# -- keybindings -------------------------------------------------------------
def test_standard_shortcuts_are_present(window):
    expected = {
        "file.new": "Ctrl+N",
        "file.open": "Ctrl+O",
        "file.save": "Ctrl+S",
        "file.close": "Ctrl+W",
        "edit.undo": "Ctrl+Z",
        "export.graph": "Ctrl+E",
        "view.preferences": "Ctrl+,",
        "help.shortcuts": "F1",
        "tools.palette": "Ctrl+Shift+P",
    }
    for action_id, shortcut in expected.items():
        action = window.registry.action(action_id)
        assert action.shortcut().toString() == shortcut, action_id


def test_shortcuts_are_unique(window):
    seen: dict[str, str] = {}
    for spec in window.registry.specs():
        sequence = spec.shortcut
        if not isinstance(sequence, str):
            continue
        if sequence in seen:
            pytest.fail(
                f"{spec.id} and {seen[sequence]} both use {sequence}"
            )
        seen[sequence] = spec.id


def test_shortcuts_dialog_lists_the_shortcuts(window):
    from PySide6.QtWidgets import QTreeWidget

    from graphmatrix.ui.shortcuts_dialog import ShortcutsDialog

    dialog = ShortcutsDialog(window.registry, window)
    try:
        assert isinstance(dialog.tree, QTreeWidget)
        texts = []
        for index in range(dialog.tree.topLevelItemCount()):
            group = dialog.tree.topLevelItem(index)
            for child in range(group.childCount()):
                texts.append(group.child(child).text(0))
        assert "Save Project" in texts
        assert "Add a column at the end" in texts

        # The filter narrows the list down.
        dialog.filter.setText("save")
        shown = []
        for index in range(dialog.tree.topLevelItemCount()):
            group = dialog.tree.topLevelItem(index)
            for child in range(group.childCount()):
                shown.append(group.child(child).text(0))
        assert "Save Project" in shown
        assert all("save" in text.lower() for text in shown)
    finally:
        dialog.close()


def test_close_tab_action_closes_the_current_tab(window):
    window._action_sample_data()
    window._action_add_graph()
    before = window.tabs.count()
    assert before >= 1
    window._action_close_tab()
    assert window.tabs.count() == before - 1


# -- preferences -------------------------------------------------------------
def test_preferences_round_trip(window):
    from graphmatrix.ui import preferences

    preferences.set_value("export/dpi", 600)
    assert preferences.get("export/dpi") == 600
    preferences.reset()
    assert preferences.get("export/dpi") == 300


def test_preferences_dialog_applies_values(window):
    from graphmatrix.ui import preferences
    from graphmatrix.ui.preferences import PreferencesDialog

    dialog = PreferencesDialog(window)
    try:
        dialog.dpi_spin.setValue(450)
        dialog.decimals_combo.setCurrentIndex(
            dialog.decimals_combo.findData(3)
        )
        dialog.wheel_zoom.setChecked(False)
        dialog._apply()
        assert preferences.get("export/dpi") == 450
        assert preferences.new_column_decimals() == 3
        assert preferences.get("canvas/wheel_zoom") is False
    finally:
        preferences.reset()
        dialog.close()


def test_preferences_change_the_export_dialog_defaults(window):
    from graphmatrix.ui import preferences
    from graphmatrix.ui.main_window import ExportGraphDialog

    preferences.set_value("export/dpi", 600)
    preferences.set_value("export/format", "svg")
    try:
        dialog = ExportGraphDialog(window)
        assert dialog.dpi.value() == 600
        assert dialog.format.currentData() == "svg"
    finally:
        preferences.reset()


def test_preferences_decimals_reach_new_columns(window):
    from graphmatrix.ui import preferences

    preferences.set_value("worksheet/new_column_decimals", 2)
    try:
        window._action_sample_data()
        sheet = window.project.workbooks[0].sheets[0]
        window._open_sheet_tab(sheet)
        view = window._views[id(sheet)]
        view.append_column()
        assert sheet.columns[-1].decimal == 2
    finally:
        preferences.reset()


def test_preferences_can_be_restored(window):
    from graphmatrix.ui import preferences
    from graphmatrix.ui.preferences import PreferencesDialog

    preferences.set_value("export/dpi", 1200)
    dialog = PreferencesDialog(window)
    try:
        dialog._restore_defaults()
        assert preferences.get("export/dpi") == 300
    finally:
        preferences.reset()
