"""Command stack / undo-redo tests."""

from __future__ import annotations

from respot.core.commands import (
    AddColumnCommand,
    AddWorkbookCommand,
    CommandStack,
    MacroCommand,
    RenameCommand,
    RenameWorkbookCommand,
    RenameWorksheetCommand,
    ReorderColumnsCommand,
    RemoveWorkbookCommand,
    SetCellValueCommand,
    SetCellsCommand,
)
from respot.core.model import (
    Column,
    ColumnType,
    Graph,
    PlotSpec,
    Project,
    Workbook,
    Worksheet,
)


def test_add_workbook_undo_redo():
    project = Project()
    book = Workbook("Book1")
    stack = CommandStack()

    stack.push(AddWorkbookCommand(project, book))
    assert project.workbooks == [book]

    stack.undo()
    assert project.workbooks == []

    stack.redo()
    assert project.workbooks == [book]


def test_remove_workbook_restores_index():
    project = Project()
    a, b, c = Workbook("A"), Workbook("B"), Workbook("C")
    for book in (a, b, c):
        project.add_workbook(book)

    stack = CommandStack()
    stack.push(RemoveWorkbookCommand(project, b))
    assert [w.name for w in project.workbooks] == ["A", "C"]

    stack.undo()
    assert [w.name for w in project.workbooks] == ["A", "B", "C"]


def test_macro_is_a_single_undoable_step():
    sheet = Worksheet("Sheet1")
    stack = CommandStack()
    stack.push(
        MacroCommand(
            [
                AddColumnCommand(sheet, Column("X1", ColumnType.X, [0, 1, 2])),
                AddColumnCommand(sheet, Column("Y1", ColumnType.Y, [0, 1, 4])),
            ],
            label="Add Sample Data",
        )
    )
    assert sheet.column_names == ["X1", "Y1"]
    assert stack.undo_label == "Add Sample Data"

    stack.undo()
    assert sheet.column_names == []

    stack.redo()
    assert sheet.column_names == ["X1", "Y1"]


def test_listeners_fire_and_unsubscribe():
    project = Project()
    stack = CommandStack()
    calls: list[int] = []
    unsubscribe = stack.subscribe(lambda: calls.append(1))

    stack.push(AddWorkbookCommand(project, Workbook("Book1")))
    assert calls == [1]

    unsubscribe()
    stack.push(AddWorkbookCommand(project, Workbook("Book2")))
    assert calls == [1]


def test_push_without_execute():
    project = Project()
    book = Workbook("Book1")
    project.add_workbook(book)
    stack = CommandStack()

    stack.push(AddWorkbookCommand(project, Workbook("Book2")), execute=False)
    # not executed, but recorded so undo is still consistent
    assert len(project.workbooks) == 1
    assert stack.can_undo


def test_set_cell_value_undo_trims_grown_rows():
    sheet = Worksheet("S")
    sheet.add_column("Y1", ColumnType.Y, [1.0])
    stack = CommandStack()

    stack.push(SetCellValueCommand(sheet, 3, 0, 9.0))  # grows the sheet to 4 rows
    assert sheet.num_rows == 4
    assert sheet.column("Y1").data[3] == 9.0

    stack.undo()
    assert sheet.num_rows == 1
    assert sheet.column("Y1").data.tolist() == [1.0]


def test_paste_block_is_one_undoable_step():
    sheet = Worksheet("S")
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0])
    sheet.add_column("Y1", ColumnType.Y, [0.0, 1.0])
    stack = CommandStack()

    stack.push(SetCellsCommand(sheet, 2, 0, [[2.0, 4.0], [3.0, 9.0]]))  # grows to 4 rows
    assert sheet.num_rows == 4
    assert sheet.column("Y1").data[3] == 9.0

    stack.undo()
    assert sheet.num_rows == 2
    assert sheet.column("X1").data.tolist() == [0.0, 1.0]
    assert sheet.column("Y1").data.tolist() == [0.0, 1.0]


def test_reorder_columns_undo_redo():
    sheet = Worksheet("S")
    sheet.add_column("X1", ColumnType.X, [0.0])
    sheet.add_column("Y1", ColumnType.Y, [1.0])
    sheet.add_column("Y2", ColumnType.Y, [2.0])
    stack = CommandStack()

    stack.push(ReorderColumnsCommand(sheet, [sheet.columns[2], sheet.columns[0], sheet.columns[1]]))
    assert sheet.column_names == ["Y2", "X1", "Y1"]

    stack.undo()
    assert sheet.column_names == ["X1", "Y1", "Y2"]

    stack.redo()
    assert sheet.column_names == ["Y2", "X1", "Y1"]


def _project_with_graph():
    project = Project("P")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0])
    sheet.add_column("Y1", ColumnType.Y, [0.0, 1.0])
    graph = project.add_graph(Graph("G"))
    graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1"))
    return project, book, sheet, graph


def test_rename_workbook_rewrites_plot_sources_and_undoes():
    project, book, sheet, graph = _project_with_graph()
    stack = CommandStack()

    stack.push(RenameWorkbookCommand(project, book, "Data"))
    assert book.name == "Data"
    assert graph.first_layer.plots[0].source == "Data/Sheet1"

    stack.undo()
    assert book.name == "Book1"
    assert graph.first_layer.plots[0].source == "Book1/Sheet1"

    stack.redo()
    assert book.name == "Data"
    assert graph.first_layer.plots[0].source == "Data/Sheet1"


def test_rename_worksheet_rewrites_plot_sources_and_undoes():
    project, book, sheet, graph = _project_with_graph()
    stack = CommandStack()

    stack.push(RenameWorksheetCommand(project, book, sheet, "Measurements"))
    assert sheet.name == "Measurements"
    assert graph.first_layer.plots[0].source == "Book1/Measurements"

    stack.undo()
    assert sheet.name == "Sheet1"
    assert graph.first_layer.plots[0].source == "Book1/Sheet1"


def test_rename_does_not_touch_unrelated_sources():
    project, book, sheet, graph = _project_with_graph()
    other = project.add_workbook(Workbook("Book10"))
    other.add_sheet(Worksheet("Sheet1"))
    graph.first_layer.add_plot(PlotSpec("Book10/Sheet1", "X1", "Y1"))

    stack = CommandStack()
    stack.push(RenameWorkbookCommand(project, book, "Renamed"))
    sources = [p.source for layer in graph.layers for p in layer.plots]
    # Only "Book1/Sheet1" changed; "Book10/Sheet1" (a different workbook) did not.
    assert sorted(sources) == ["Book10/Sheet1", "Renamed/Sheet1"]


def test_generic_rename_is_undoable():
    project = Project("Old")
    stack = CommandStack()
    stack.push(RenameCommand(project, "New"))
    assert project.name == "New"
    stack.undo()
    assert project.name == "Old"

