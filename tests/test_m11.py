"""M11 tests: linked brushing — one shared row selection across sheet and
graph views (BrushSelection state, canvas brush overlay, click-to-pick,
worksheet row highlight, GraphView wiring)."""

from __future__ import annotations

import os

import numpy as np
import pytest

from graphmatrix.core.commands import CommandStack
from graphmatrix.core.model import (
    ColumnType,
    Graph,
    PlotSpec,
    PlotStyle,
    Project,
    Workbook,
    Worksheet,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _ensure_qapp(qapp):
    return qapp


def make_project() -> tuple[Project, Worksheet]:
    project = Project()
    book = Workbook("Book1")
    sheet = Worksheet("Sheet1")
    x = np.arange(10.0)
    y = x * x
    sheet.add_column("X", ColumnType.X, x)
    sheet.add_column("Y", ColumnType.Y, y)
    book.add_sheet(sheet)
    project.add_workbook(book)
    return project, sheet


def make_graph(source: str = "Book1/Sheet1") -> Graph:
    graph = Graph("Graph1")
    graph.first_layer.add_plot(
        PlotSpec(source=source, x="X", y="Y", style=PlotStyle.SCATTER)
    )
    return graph


# -- BrushSelection state -------------------------------------------------------

def test_brush_set_get_and_signal():
    from graphmatrix.ui.brushing import BrushSelection

    events: list[tuple[str, list[int]]] = []
    brush = BrushSelection()
    brush.changed.connect(lambda source, rows: events.append((source, list(rows))))

    brush.set("Book1/Sheet1", [5, 2, 2, 7])
    assert brush.get("Book1/Sheet1") == [2, 5, 7]
    assert brush.source() == "Book1/Sheet1"
    assert events[-1] == ("Book1/Sheet1", [2, 5, 7])

    # Setting the same rows emits nothing; clearing emits an empty payload.
    count = len(events)
    brush.set("Book1/Sheet1", [7, 5, 2])
    assert len(events) == count
    brush.set("Book1/Sheet1", [])
    assert events[-1] == ("Book1/Sheet1", [])
    assert brush.source() is None


def test_brush_moves_between_sheets():
    from graphmatrix.ui.brushing import BrushSelection

    brush = BrushSelection()
    brush.set("B1/S1", [1, 2])
    brush.set("B2/S2", [3])
    # Only the newest sheet is brushed.
    assert brush.get("B1/S1") == []
    assert brush.get("B2/S2") == [3]


# -- matplotlib canvas overlay + click-to-pick ----------------------------------

def test_mpl_canvas_brush_overlay_and_pick():
    pytest.importorskip("matplotlib")
    from types import SimpleNamespace

    from graphmatrix.ui.canvas import create_canvas

    canvas = create_canvas("matplotlib")
    x = np.arange(10.0)
    y = x * x
    rows = np.arange(10)
    canvas.plot(x, y, style="scatter", rows=rows)
    canvas._canvas.draw()  # force a full render so transforms are valid

    canvas.set_brush({0: [2, 4]})
    assert len(canvas._brush_artists) == 1
    positions = canvas._brush_artists[0].get_xydata()
    assert np.allclose(positions, [[2.0, 4.0], [4.0, 16.0]])

    canvas.set_brush({})
    assert canvas._brush_artists == []

    # Simulate a click near the point at x=3 (row 3).
    ax = canvas._ax_left
    px, py = ax.transData.transform((3.0, 9.0))
    inv = ax.transData.inverted()
    # a tiny data-space offset so the click lands within 12 px of the marker
    dx, dy = inv.transform((px + 6, py))
    event = SimpleNamespace(inaxes=ax, xdata=dx, ydata=dy, dblclick=False,
                            button=1, x=px, y=py)
    picked: list[tuple[int, int]] = []
    canvas.point_picked = lambda series_index, row: picked.append((series_index, row))
    canvas._on_button_press(event)
    assert picked == [(0, 3)]

    # A far-away click picks nothing.
    dx, dy = inv.transform((px + 400, py + 400))
    far = SimpleNamespace(inaxes=ax, xdata=dx, ydata=dy, dblclick=False,
                          button=1, x=px + 400, y=py + 400)
    picked.clear()
    canvas._on_button_press(far)
    assert picked == []


def test_mpl_canvas_rows_follow_sort_order():
    """Brush highlights must map back to worksheet rows, not sorted indexes."""
    pytest.importorskip("matplotlib")
    from graphmatrix.ui.canvas import create_canvas

    canvas = create_canvas("matplotlib")
    # Deliberately unsorted x: worksheet row 0 has x = 5.
    x = [5.0, 0.0, 3.0]
    y = [50.0, 0.0, 9.0]
    rows = [0, 1, 2]
    canvas.plot(x, y, style="scatter", rows=rows)
    canvas.set_brush({0: [0]})
    offsets = canvas._brush_artists[0].get_xydata()
    assert np.allclose(offsets, [[5.0, 50.0]])


# -- WorksheetView highlighting --------------------------------------------------

def test_worksheet_row_highlight(qapp):
    from graphmatrix.ui.worksheet_view import WorksheetView

    project, sheet = make_project()
    view = WorksheetView(sheet, CommandStack(), "Book1/Sheet1")
    view.populate()

    view.set_row_highlight([1, 3])
    on = [view.table.item(1, 0).background(), view.table.item(3, 1).background()]
    off = view.table.item(2, 0).background()
    assert on[0].color().alpha() > 0
    assert on[1].color().alpha() > 0
    assert off.color().alpha() == 0

    # Highlight survives a table rebuild.
    view.populate()
    assert view.table.item(1, 0).background().color().alpha() > 0

    view.clear_row_highlight()
    assert view.table.item(1, 0).background().color().alpha() == 0


def test_worksheet_selected_rows_broadcast(qapp):
    from PySide6.QtCore import QItemSelectionModel

    from graphmatrix.ui.worksheet_view import WorksheetView

    project, sheet = make_project()
    view = WorksheetView(sheet, CommandStack(), "Book1/Sheet1")
    view.populate()
    received: list[tuple[str, list[int]]] = []
    view.rows_selected.connect(lambda s, r: received.append((s, list(r))))

    model = view.table.selectionModel()
    model.select(view.table.model().index(2, 0),
                 QItemSelectionModel.SelectionFlag.Select |
                 QItemSelectionModel.SelectionFlag.Rows)
    assert received and received[-1] == ("Book1/Sheet1", [2])


# -- GraphView wiring -------------------------------------------------------------

def test_graphview_brush_roundtrip(qapp):
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QWidget

    from graphmatrix.ui.brushing import BrushSelection
    from graphmatrix.ui.graph_view import GraphView

    project, sheet = make_project()
    graph = make_graph()
    view = GraphView(graph, project, CommandStack())
    view.render()

    # Series bookkeeping matches what the brush needs.
    assert view._series_sources == ["Book1/Sheet1"]

    # The view's brush signal and a shared BrushSelection drive each other.
    hub = BrushSelection()
    view.brush_requested.connect(hub.set)
    hub.changed.connect(view.apply_brush)

    picked: list[tuple[str, list[int]]] = []
    view.brush_requested.connect(lambda s, r: picked.append((s, list(r))))
    view._on_canvas_point_picked(0, 4)
    assert picked == [("Book1/Sheet1", [4])]
    assert hub.get("Book1/Sheet1") == [4]
    # ... and the change broadcast back re-drew the overlay on the canvas.
    assert len(view.canvas._brush_artists) == 1

    # A brush from another sheet clears this graph's overlay.
    hub.set("Book2/Sheet2", [1])
    assert hub.get("Book1/Sheet1") == []
    assert view.canvas._brush_artists == []

    # Re-render keeps the overlay synced (no stale highlights on rebuild).
    hub.set("Book1/Sheet1", [1, 2, 3])
    view.render()
    assert len(view.canvas._brush_artists) == 1


def test_main_window_brush_links_sheet_and_graph(qapp):
    from graphmatrix.ui.main_window import MainWindow
    from graphmatrix.ui.worksheet_view import WorksheetView

    window = MainWindow()
    project = window.project  # __init__ seeds a demo project; use unique names
    book = Workbook("BrushBook")
    sheet = Worksheet("Data")
    x = np.arange(10.0)
    sheet.add_column("X", ColumnType.X, x)
    sheet.add_column("Y", ColumnType.Y, x * x)
    book.add_sheet(sheet)
    project.add_workbook(book)
    graph = make_graph("BrushBook/Data")
    window._open_sheet_tab(sheet)
    window._open_graph_tab(graph)

    sheet_view = window._views[id(sheet)]
    graph_view = window._views[id(graph)]
    assert isinstance(sheet_view, WorksheetView)
    graph_view.render()  # populate series bookkeeping

    # Click a point on the graph -> the sheet row is tinted.
    graph_view._on_canvas_point_picked(0, 5)
    assert window.brush.get("BrushBook/Data") == [5]
    assert sheet_view.table.item(5, 0).background().color().alpha() > 0
    assert len(graph_view.canvas._brush_artists) == 1

    # Select rows in the sheet -> the graph overlay follows.
    from PySide6.QtCore import QItemSelectionModel

    model = sheet_view.table.selectionModel()
    model.select(sheet_view.table.model().index(2, 0),
                 QItemSelectionModel.SelectionFlag.Select |
                 QItemSelectionModel.SelectionFlag.Rows)
    assert window.brush.get("BrushBook/Data") == [2]
    offsets = graph_view.canvas._brush_artists[0].get_xydata()
    assert np.allclose(offsets, [[2.0, 4.0]])
