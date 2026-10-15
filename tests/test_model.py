"""Core data-model tests (headless, no Qt)."""

from __future__ import annotations

import numpy as np

from respot.core.model import Column, ColumnType, Project, Workbook, Worksheet


def test_column_basics():
    column = Column("Y1", ColumnType.Y, [1, 2, 3], units="V")
    assert len(column) == 3
    assert column.values == [1, 2, 3]
    assert column.col_type is ColumnType.Y
    assert column.units == "V"
    column.append(4)
    assert column.values == [1, 2, 3, 4]


def test_worksheet_row_count_is_longest_column():
    sheet = Worksheet("Sheet1")
    sheet.add_column("X1", ColumnType.X, [1, 2, 3])
    sheet.add_column("Y1", ColumnType.Y, [1, 2])
    assert sheet.num_columns == 2
    assert sheet.num_rows == 3
    assert len(sheet) == 3


def test_worksheet_next_column_name():
    sheet = Worksheet("Sheet1")
    assert sheet.next_column_name(ColumnType.Y) == "Y1"
    sheet.add_column("Y1", ColumnType.Y, [1])
    assert sheet.next_column_name(ColumnType.Y) == "Y2"


def test_workbook_and_project_structure():
    project = Project("Demo")
    book = project.add_workbook(Workbook("Book1"))
    book.add_sheet(Worksheet("Sheet1"))
    assert project.workbook("Book1") is book
    assert book.sheet("Sheet1") is book.sheets[0]
    assert project.unique_name("Graph") == "Graph"
    project.add_graph(__import__("respot.core.model", fromlist=["Graph"]).Graph("Graph"))
    assert project.unique_name("Graph") == "Graph1"


def test_column_roundtrip_preserves_numeric_data():
    x = np.linspace(0, 1, 11)
    column = Column("X1", ColumnType.X, x, units="s", comment="time")
    restored = Column.from_dict(column.to_dict())
    assert restored.name == "X1"
    assert restored.col_type is ColumnType.X
    assert restored.units == "s"
    assert restored.comment == "time"
    np.testing.assert_allclose(restored.data, x)


def test_worksheet_roundtrip():
    sheet = Worksheet("Sheet1")
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0, 2.0])
    sheet.add_column("Y1", ColumnType.Y, [0.0, 1.0, 4.0])
    restored = Worksheet.from_dict(sheet.to_dict())
    assert restored.name == "Sheet1"
    assert restored.column_names == ["X1", "Y1"]
    assert restored.num_rows == 3
    np.testing.assert_allclose(restored.column("Y1").data, [0.0, 1.0, 4.0])
