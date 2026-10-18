"""Worksheet row/column controls: header “+”, insert/delete, undo."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QTableWidgetSelectionRange  # noqa: E402

from graphmatrix.core.commands import CommandStack  # noqa: E402
from graphmatrix.core.model import ColumnType, Worksheet  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def make_view():
    from graphmatrix.ui.worksheet_view import WorksheetView

    sheet = Worksheet("Sheet1")
    sheet.add_column("X1", ColumnType.X, np.array([0, 1, 2]))
    sheet.add_column("Y1", ColumnType.Y, np.array([10.0, 20.0, 30.0]))
    commands = CommandStack()
    view = WorksheetView(sheet, commands, "Book1/Sheet1")
    return sheet, commands, view


# -- model: inserting blanks must not corrupt integer columns ----------------


def test_insert_blanks_promotes_integers_to_nan():
    sheet = Worksheet("S")
    sheet.add_column("X1", ColumnType.X, np.array([0, 1, 2]))
    sheet.add_column("T", ColumnType.TEXT, ["a", "b", "c"])

    sheet.insert_rows(1, 2)
    x = sheet.column("X1")
    assert x.dtype == np.float64
    assert np.isnan(x.data[1]) and np.isnan(x.data[2])
    assert sheet.column("T").values == ["a", "", "", "b", "c"]

    sheet.delete_rows(1, 2)
    assert sheet.column("X1").values == [0.0, 1.0, 2.0]
    assert sheet.column("T").values == ["a", "b", "c"]


def test_ensure_rows_uses_real_blanks():
    sheet = Worksheet("S")
    sheet.add_column("Y1", ColumnType.Y, np.array([1, 2]))
    sheet.ensure_rows(4)
    assert sheet.num_rows == 4
    assert np.isnan(sheet.column("Y1").data[2])
    assert np.isnan(sheet.column("Y1").data[3])


# -- header “+” --------------------------------------------------------------


def test_header_plus_appends_a_column(qapp):
    sheet, commands, view = make_view()
    assert view.add_column_button.text() == "+"
    assert "column" in view.add_column_button.toolTip().lower()

    view.add_column_button.click()
    assert sheet.column_names == ["X1", "Y1", "Y2"]
    commands.undo()
    assert sheet.column_names == ["X1", "Y1"]
    view.deleteLater()


def test_header_plus_sits_after_the_last_header(qapp):
    _sheet, _commands, view = make_view()
    view.resize(700, 400)
    view.show()
    qapp.processEvents()
    view._position_add_column_button()
    first_x = view.add_column_button.x()
    assert first_x > 0
    assert view.add_column_button.isVisible()

    view.append_column()
    view.populate()
    qapp.processEvents()
    view._position_add_column_button()
    assert view.add_column_button.x() > first_x
    view.close()
    view.deleteLater()


# -- rows --------------------------------------------------------------------


def test_row_append_insert_delete_and_undo(qapp):
    sheet, commands, view = make_view()

    view.append_row()
    assert sheet.num_rows == 4
    assert np.isnan(sheet.column("X1").data[3])
    commands.undo()
    assert sheet.num_rows == 3

    view.table.selectRow(1)
    view.insert_rows_below()
    assert sheet.num_rows == 4
    assert np.isnan(sheet.column("X1").data[2])
    commands.undo()
    assert sheet.num_rows == 3

    view.table.selectRow(1)
    view.delete_selected_rows()
    assert sheet.num_rows == 2
    commands.undo()
    assert sheet.num_rows == 3
    view.populate()
    assert view.table.rowCount() == 3
    view.deleteLater()


# -- columns -----------------------------------------------------------------


def test_main_window_sheet_actions_and_shortcuts(qapp):
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        sheet = window.project.workbooks[0].sheets[0]
        window._open_sheet_tab(sheet)
        view = window._active_sheet_view()
        assert view is not None

        rows, columns = sheet.num_rows, sheet.num_columns
        window._action_add_row()
        assert sheet.num_rows == rows + 1
        window.commands.undo()

        window._action_add_column()
        assert sheet.num_columns == columns + 1
        window.commands.undo()

        view.table.selectRow(1)
        window._action_insert_row_above()
        assert sheet.num_rows == rows + 1
        window.commands.undo()

        view.table.selectRow(1)
        window._action_delete_rows()
        assert sheet.num_rows == rows - 1
        window.commands.undo()

        view.table.clearSelection()
        view.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 2, 1), True)
        window._action_delete_columns()
        assert sheet.num_columns == 0
        window.commands.undo()
        assert sheet.column_names == ["X1", "Y1"]

        assert (
            window.registry.action("data.add_row").shortcut().toString()
            == "Ctrl+Alt+N"
        )
        assert (
            window.registry.action("data.delete_columns").shortcut().toString()
            == "Ctrl+Alt+Shift+-"
        )
        menu = window._rows_cols_menu
        assert [a.text() for a in menu.actions()][:2] == [
            "Add Row at End",
            "Add Column at End",
        ]
    finally:
        window.close()


def test_column_insert_left_right_and_delete(qapp):
    sheet, commands, view = make_view()

    view.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 2, 0), True)
    view.insert_column_left()
    assert sheet.column_names == ["Y2", "X1", "Y1"]
    commands.undo()
    assert sheet.column_names == ["X1", "Y1"]

    view.table.clearSelection()
    view.table.setRangeSelected(QTableWidgetSelectionRange(0, 1, 2, 1), True)
    view.insert_column_right()
    assert sheet.column_names == ["X1", "Y1", "Y2"]
    commands.undo()
    assert sheet.column_names == ["X1", "Y1"]

    # Deleting two selected columns is one undoable step.
    view.table.clearSelection()
    view.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 2, 1), True)
    view.delete_selected_columns()
    assert sheet.column_names == []
    commands.undo()
    assert sheet.column_names == ["X1", "Y1"]
    view.deleteLater()
