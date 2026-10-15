"""Scripting / API / macro tests (M5) and batch processing."""

from __future__ import annotations

import numpy as np

from respot.core.commands import CommandStack
from respot.core.model import Project
from respot.core.scripting.api import RespotAPI
from respot.core.scripting.record import MacroRecorder


def test_api_builds_project():
    project = Project()
    stack = CommandStack()
    api = RespotAPI(project, stack)

    api.add_workbook("Book1")
    api.add_worksheet("Book1", "Sheet1")
    api.add_column("Book1/Sheet1", "X1", "X", data=[0.0, 1.0, 2.0])
    api.add_column("Book1/Sheet1", "Y1", "Y", data=[0.0, 1.0, 4.0])
    graph = api.add_graph("Graph1", "Book1/Sheet1", "X1", "Y1")

    assert project.workbook("Book1") is not None
    assert project.sheet("Book1/Sheet1").column("Y1") is not None
    assert graph.num_layers == 1
    assert len(graph.first_layer.plots) == 1
    # API changes went through the command stack, so they are undoable.
    assert stack.can_undo


def test_api_analysis_delegates():
    project = Project()
    api = RespotAPI(project)
    api.add_workbook("B")
    api.add_worksheet("B", "S")
    x = np.linspace(0, 10, 100)
    api.add_column("B/S", "X1", "X", data=x)
    api.add_column("B/S", "Y1", "Y", data=3 * np.exp(-x / 2.0) + 0.1)
    result = api.fit("Exponential Decay", "B/S", "X1", "Y1")
    assert result.summary["R²"] > 0.99


def test_macro_recorder_generates_runnable_script():
    project = Project()
    stack = CommandStack()
    api = RespotAPI(project, stack)

    recorder = MacroRecorder(stack)
    recorder.start()
    api.add_workbook("B")
    api.add_worksheet("B", "S")
    api.add_column("B/S", "X1", "X", data=[0.0, 1.0, 2.0])
    api.add_column("B/S", "Y1", "Y", data=[0.0, 1.0, 4.0])
    recorder.stop()

    script = recorder.script()
    assert "api.add_column" in script
    assert "api.add_workbook" in script

    # Replay into a fresh project via a fresh API.
    fresh = Project()
    fresh_api = RespotAPI(fresh)
    namespace = {"api": fresh_api}
    exec(compile(script, "<macro>", "exec"), namespace)  # noqa: S102 - test of generated code
    assert fresh.sheet("B/S").column("Y1") is not None
    np.testing.assert_allclose(fresh.sheet("B/S").column("Y1").data, [0.0, 1.0, 4.0])


def test_macro_replays_populated_workbook():
    from respot.core.commands import AddWorkbookCommand
    from respot.core.model import ColumnType, Workbook, Worksheet

    project = Project()
    stack = CommandStack()
    book = Workbook("Imported")
    sheet = book.add_sheet(Worksheet("Sheet1"))
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0])
    sheet.add_column("Y1", ColumnType.Y, [2.0, 3.0])

    recorder = MacroRecorder(stack)
    recorder.start()
    stack.push(AddWorkbookCommand(project, book))  # populated workbook, single command
    recorder.stop()

    fresh = Project()
    namespace = {"api": RespotAPI(fresh)}
    exec(compile(recorder.script(), "<macro>", "exec"), namespace)  # noqa: S102
    assert fresh.sheet("Imported/Sheet1").column("Y1") is not None
    np.testing.assert_allclose(fresh.sheet("Imported/Sheet1").column("Y1").data, [2.0, 3.0])


def test_batch_processing(tmp_path):
    from respot.core.batch import process_files
    from respot.core.io import importer
    from respot.core.model import ColumnType, Worksheet

    paths = []
    for i in range(3):
        sheet = Worksheet("S")
        sheet.add_column("X1", ColumnType.X, [0.0, 1.0, 2.0])
        sheet.add_column("Y1", ColumnType.Y, [float(i), float(i) + 1, float(i) + 2])
        path = tmp_path / f"f{i}.csv"
        importer.export_delimited(sheet, path)
        paths.append(path)

    items = process_files(paths, lambda book, path: book.sheets[0].num_rows)
    assert all(item.ok for item in items)
    assert [item.result for item in items] == [3, 3, 3]
