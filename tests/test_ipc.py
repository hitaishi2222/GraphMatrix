"""Direct IPC bridge tests: agent-style client drives a live MainWindow."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from graphmatrix.core.ipc import IpcBridge, request, socket_path  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture()
def bridge(app, monkeypatch):
    """A MainWindow with an IPC bridge on a private test socket path."""
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    bridge = IpcBridge(window)
    # Point the client at this bridge regardless of instance.json state.
    monkeypatch.setattr(
        "graphmatrix.core.ipc.running_socket_path", lambda: bridge._path
    )
    yield bridge
    bridge.close()
    window.close()


def _pump(app, bridge, seconds=1.0):
    """Run the Qt event loop until the bridge answers or time runs out."""
    import time

    from PySide6.QtCore import QDeadlineTimer, QCoreApplication

    deadline = QDeadlineTimer()
    deadline.setRemainingTime(int(seconds * 1000))
    while not deadline.hasExpired():
        QCoreApplication.processEvents()
        time.sleep(0.01)


def _rpc(app, op, timeout=10.0, **payload):
    """Issue an IPC request on a worker thread while pumping the GUI loop.

    The blocking client and the answering Qt event loop share this thread's
    process, so the loop must be pumped for the bridge to respond.
    """
    import threading

    from PySide6.QtCore import QDeadlineTimer, QCoreApplication

    out = {}
    t = threading.Thread(
        target=lambda: out.update(res=request(op, timeout=timeout, **payload))
    )
    t.start()
    deadline = QDeadlineTimer()
    deadline.setRemainingTime(int(timeout * 1000) + 5000)
    while t.is_alive() and not deadline.hasExpired():
        QCoreApplication.processEvents()
    t.join(1.0)
    assert not t.is_alive(), "IPC request never completed"
    return out["res"]


def test_ping_reports_live_window(app, bridge):
    res = _rpc(app, "ping")
    assert res["ok"] is True
    assert res["project"] == bridge.window.project.name
    assert res["pid"] == os.getpid()


def test_summary_reflects_live_project(app, bridge):
    res = _rpc(app, "summary")
    assert res["ok"] is True
    assert res["summary"]["name"] == bridge.window.project.name


def test_run_executes_against_live_project_and_is_undoable(app, bridge):
    window = bridge.window
    before = len(window.project.workbooks)
    undo_before = window.commands.can_undo

    res = _rpc(
        app,
        "run",
        code=(
            "import numpy as np\n"
            "t = np.linspace(0, 1, 10)\n"
            "api.add_workbook('Agent')\n"
            "api.add_worksheet('Agent', 'Sheet1')\n"
            "api.add_column('Agent/Sheet1', 'X', 'X', t)\n"
            "api.add_column('Agent/Sheet1', 'Y', 'Y', np.sin(t))\n"
            "api.add_graph('AgentPlot', source='Agent/Sheet1', x='X', y='Y', style='line')\n"
            "print('hello from agent')"
        ),
    )
    _pump(app, bridge)

    assert res["ok"] is True, res
    assert "hello from agent" in res["stdout"]
    assert len(window.project.workbooks) == before + 1
    assert window.commands.can_undo is not undo_before or undo_before

    # Changes went through the GUI command stack -> undo removes everything.
    while len(window.project.workbooks) > before:
        window.commands.undo()
    assert len(window.project.workbooks) == before


def test_run_reports_errors(app, bridge):
    res = _rpc(app, "run", code="1 / 0")
    assert res["ok"] is False
    assert "ZeroDivisionError" in res["error"]


def test_open_replaces_window_project(app, bridge, tmp_path):
    from graphmatrix.core.model import Project

    other = Project("Other")
    path = tmp_path / "other.gm"
    other.save(path)

    res = _rpc(app, "open", path=str(path))
    _pump(app, bridge)
    assert res["ok"] is True, res
    assert bridge.window.project.name == "Other"


def test_open_refused_when_dirty(app, bridge, tmp_path):
    from graphmatrix.core.model import Project

    path = tmp_path / "x.gm"
    Project("X").save(path)
    bridge.window._set_dirty(True)
    res = _rpc(app, "open", path=str(path))
    assert res["ok"] is False
    assert "unsaved" in res["error"]
    bridge.window._set_dirty(False)
    res = _rpc(app, "open", path=str(path), force=True)
    assert res["ok"] is True


def test_unknown_op_reports_error(app, bridge):
    res = _rpc(app, "explode")
    assert res["ok"] is False
    assert "unknown op" in res["error"]


def test_run_open_graphs_flag_opens_new_tabs(app, bridge):
    res = _rpc(
        app,
        "run",
        open_graphs=True,
        code="""
api.add_workbook('Tabbed')
api.add_worksheet('Tabbed', 'Sheet1')
import numpy as np
api.add_column('Tabbed/Sheet1', 'X', 'X', np.linspace(0, 1, 5))
api.add_column('Tabbed/Sheet1', 'Y', 'Y', np.arange(5.0))
api.add_graph('TabPlot', source='Tabbed/Sheet1', x='X', y='Y', style='line')
""",
    )
    assert res["ok"] is True, res
    assert res["opened_graphs"] == ["TabPlot"]
    # running again without the flag must not re-open or duplicate tabs
    res = _rpc(app, "run", code="api.add_graph('Other')")
    assert res["opened_graphs"] == []
    titles = [bridge.window.tabs.tabText(i) for i in range(bridge.window.tabs.count())]
    assert titles.count("TabPlot") == 1


def test_socket_path_is_per_pid_and_unique():
    p1 = socket_path(123)
    assert p1.endswith("ipc-123.sock")
    assert socket_path().endswith(f"ipc-{os.getpid()}.sock")
    seq_a, seq_b = socket_path(123, 1), socket_path(123, 2)
    assert seq_a != seq_b and "ipc-123-1.sock" in seq_a and "ipc-123-2.sock" in seq_b
