"""Command stack / undo-redo tests."""

from __future__ import annotations

from respot.core.commands import (
    AddColumnCommand,
    AddWorkbookCommand,
    CommandStack,
    MacroCommand,
    RemoveWorkbookCommand,
)
from respot.core.model import Column, ColumnType, Project, Workbook, Worksheet


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
