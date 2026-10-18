"""M11 tests: live / streaming data board — LiveFileSource tailing and the
controller's command-driven sheet append."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from graphmatrix.core.live import LiveFileSource, looks_numeric

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


# -- LiveFileSource --------------------------------------------------------------

def test_header_and_numeric_poll(tmp_path):
    path = tmp_path / "stream.csv"
    write(path, "t,sig\n0.0,1.0\n0.5,2.0\n")
    src = LiveFileSource(path)
    assert src.columns() == ["t", "sig"]
    rows = src.poll()
    assert rows == [[0.0, 1.0], [0.5, 2.0]]
    # No new data → empty
    assert src.poll() == []
    # More data arrives
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("1.0,3.0\n")
    rows = src.poll()
    assert rows == [[1.0, 3.0]]


def test_headerless_file_and_generic_columns(tmp_path):
    path = tmp_path / "raw.dat"
    write(path, "1 10\n2 20\n")
    src = LiveFileSource(path, delimiter=" ")
    assert src.columns() == ["C1", "C2"]
    assert src.poll() == [[1.0, 10.0], [2.0, 20.0]]


def test_ragged_and_non_numeric_fields_become_nan(tmp_path):
    path = tmp_path / "messy.csv"
    write(path, "a,b,c\n5\n1,NA\n")
    src = LiveFileSource(path)
    rows = src.poll()
    assert len(rows) == 2
    a, b = rows
    assert a == [5.0, np.nan, np.nan]        # short row padded to header width
    assert b[0] == 1.0 and np.isnan(b[1])    # non-numeric → NaN
    assert looks_numeric("1e-3") and not looks_numeric("NaN_text")


def test_truncation_restarts(tmp_path):
    path = tmp_path / "rotate.csv"
    write(path, "x\n1\n2\n")
    src = LiveFileSource(path)
    assert src.poll() == [[1.0], [2.0]]
    # Writer restarts (file shorter than the old offset).
    write(path, "x\n7\n")
    rows = src.poll()
    assert rows == [[7.0]]


def test_blank_lines_skipped(tmp_path):
    path = tmp_path / "blanks.csv"
    write(path, "x\n1\n\n\n3\n")
    src = LiveFileSource(path)
    assert src.poll() == [[1.0], [3.0]]


# -- Controller wiring ------------------------------------------------------------

class _WindowStub:
    """Minimal stand-in carrying a real project + command stack."""

    def __init__(self, project, commands) -> None:
        self.project = project
        self.commands = commands


def test_controller_appends_rows_via_commands():
    from graphmatrix.core import commands as cmds
    from graphmatrix.core.model import Project, Workbook, Worksheet
    from graphmatrix.ui.live_dialog import LiveController

    project = Project()
    book = Workbook("StreamBook")
    book.add_sheet(Worksheet("Sheet1"))
    project.add_workbook(book)
    stack = cmds.CommandStack()
    controller = LiveController(_WindowStub(project, stack))

    feed = _make_feed()
    src = LiveFileSource(feed)
    sheet = controller.start(src, "StreamBook", 50)
    assert sheet.name == "Live feed"

    controller.tick()
    assert sheet.num_columns == 2
    assert sheet.column_names == ["t", "sig"]
    assert sheet.column("sig").float_data()[0] == 1.0

    controller.tick()  # nothing new
    assert len(sheet.column("t").float_data()) == 1

    # appended rows widen the sheet, one undoable step per tick
    with open(feed, "a", encoding="utf-8") as fh:
        fh.write("2.0,4.0\n")
    controller.tick()
    assert len(sheet.column("t").float_data()) == 2

    stack.undo()
    assert len(sheet.column("t").float_data()) == 1
    stack.undo()  # back to empty
    assert len(sheet.column("t").float_data()) == 0

    controller.stop_all()
    assert not controller.has_active()


def _make_feed() -> "os.PathLike":
    import tempfile
    from pathlib import Path

    d = Path(tempfile.mkdtemp())
    feed = d / "feed.csv"
    feed.write_text("t,sig\n0.0,1.0\n", encoding="utf-8")
    return feed


# -- MainWindow / dialog smoke -----------------------------------------------------

def test_dialog_smoke(qapp, tmp_path):
    from graphmatrix.ui.main_window import MainWindow
    from graphmatrix.ui.live_dialog import LiveDataDialog

    window = MainWindow()
    window.confirm_on_close = False  # suppress the modal save prompt on close
    path = tmp_path / "feed.csv"
    write(path, "t,val\n0,1\n")

    dialog = LiveDataDialog(window, controller=window.live, parent=window)
    dialog.show()
    dialog.file_edit.setText(str(path))
    assert dialog._build_source() is not None
    book_name = dialog.book_combo.currentText()
    assert book_name, "demo project seeds a workbook"
    dialog._start()
    assert window.live.has_active()
    controller = window.live
    try:
        controller.tick()
        sheet = controller._tasks[0].sheet
        assert sheet.num_columns == 2
        assert sheet.column("val").float_data()[0] == 1.0
    finally:
        controller.stop_all()
    window.close()
