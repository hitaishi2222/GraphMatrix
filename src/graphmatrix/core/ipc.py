"""Direct IPC bridge between a running GraphMatrix GUI and agents/MCP.

The GUI listens on a Unix-domain socket (one per process, path derived from the
pid) and answers newline-delimited JSON requests:

    {"op": "ping"}                                   -> {"ok": true, ...info}
    {"op": "summary"}                                -> {"ok": true, "summary": {...}}
    {"op": "run", "code": "..."}                     -> {"ok": true, "stdout": ..., "stderr": ...}
    {"op": "open", "path": "...", "force": false}    -> {"ok": true, "opened": path}
    {"op": "describe"}                              -> {"ok": true, "description": {...}}
    {"op": "save", "path": "..."}                   -> {"ok": true, "saved": path}
    {"op": "export", "out_dir": "...", ...}         -> {"ok": true, "files": [...]}

``run`` executes Python against the *live* window's project through the same
GraphMatrixAPI / CommandStack the GUI console uses, so changes appear instantly
and are undoable. ``open`` replaces the window's project (refused when the
window has unsaved changes unless ``force`` is set).

Agents talk to the socket with plain ``socket`` calls (see :func:`request`) —
no Qt required on the client side.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import socket
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

#: Ops the bridge answers.
_OPS = ("ping", "summary", "describe", "run", "open", "save", "export", "screenshot")

#: Client-side default timeout in seconds.
DEFAULT_TIMEOUT = 30.0


def _state_dir() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    d = base / "graphmatrix"
    d.mkdir(parents=True, exist_ok=True)
    return d


def socket_path(pid: int | None = None, seq: int | None = None) -> str:
    """Unix-socket path for a GUI instance (default: this process).

    Each bridge in a process gets a unique sequence number so a late-destroyed
    server can never unlink a newer server's socket (QLocalServer unlinks its
    path on destruction).
    """
    pid = pid if pid is not None else os.getpid()
    suffix = "" if seq is None else f"-{seq}"
    return str(_state_dir() / f"ipc-{pid}{suffix}.sock")


#: Strong references: keep every bridge alive while its window lives, so Qt's
#: destructor never unlinks a socket still in use.
_BRIDGES: list["IpcBridge"] = []


def current_window() -> Any | None:
    """The main window of the GUI hosting this process, if any.

    Lets in-process code (the MCP fallback path) reach the window that owns
    the project without importing the UI layer.
    """
    for bridge in reversed(_BRIDGES):
        return bridge.window
    return None


def running_socket_path() -> str | None:
    """Socket path of a running GUI, or None when none is alive.

    Prefers the most recently created bridge socket of the process recorded in
    ``instance.json``; when that file is missing or stale (a GUI started
    without a project file never writes it) every socket in the state
    directory is probed instead, so a live window is always found.
    """
    import glob as _glob

    from graphmatrix.core.instance import get as get_instance

    state = _state_dir()
    candidates: list[str] = []
    running = get_instance()
    if running:
        pattern = str(state / f"ipc-{running['pid']}*.sock")
        candidates = sorted(_glob.glob(pattern), key=os.path.getmtime, reverse=True)
    for cand in sorted(
        _glob.glob(str(state / "ipc-*.sock")), key=os.path.getmtime, reverse=True
    ):
        if cand not in candidates:
            candidates.append(cand)
    for cand in candidates:
        try:
            s = _probe_socket(cand)
            s.close()
            return cand
        except OSError:
            _drop_stale_socket(cand)
            continue
    return None


def _drop_stale_socket(path: str) -> None:
    """Remove a socket file left behind by a GUI that was killed."""
    import errno

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(path)
        s.close()
        return  # someone is listening: not stale
    except OSError as exc:
        if exc.errno not in (errno.ECONNREFUSED, errno.ENOENT):
            return
    try:
        os.unlink(path)
    except OSError:
        pass


def _probe_socket(path: str):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(path)
    return s


class IpcBridge(QObject):
    """Listens on a per-instance Unix socket and mutates the live window."""

    _SEQ = 0

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window = window
        IpcBridge._SEQ += 1
        self._seq = IpcBridge._SEQ
        self._path = socket_path(seq=self._seq)
        self._buffers: dict[QLocalSocket, bytes] = {}

        QLocalServer.removeServer(self._path)  # clear stale socket files
        self.server = QLocalServer(self)
        if not self.server.listen(self._path):
            raise RuntimeError(
                f"IPC bridge failed to listen on {self._path}: "
                f"{self.server.errorString()}"
            )
        try:
            os.chmod(self._path, 0o600)  # same-user only
        except OSError:
            pass
        self.server.newConnection.connect(self._on_connection)
        _BRIDGES.append(self)

    def close(self) -> None:
        """Stop listening and unlink this bridge's own socket path."""
        self.server.close()
        try:
            os.unlink(self._path)
        except OSError:
            pass
        if self in _BRIDGES:
            _BRIDGES.remove(self)

    # -- server side ---------------------------------------------------------
    def _on_connection(self) -> None:
        while self.server.hasPendingConnections():
            conn = self.server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: self._on_ready_read(c))
            conn.disconnected.connect(lambda c=conn: self._drop(c))
            self._buffers[conn] = b""

    def _drop(self, conn: QLocalSocket) -> None:
        self._buffers.pop(conn, None)
        try:
            conn.deleteLater()
        except RuntimeError:
            pass  # underlying C++ object already gone

    def _on_ready_read(self, conn: QLocalSocket) -> None:
        buf = self._buffers.setdefault(conn, b"") + bytes(conn.readAll())
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.strip():
                self._handle(conn, line)
        self._buffers[conn] = buf

    def _handle(self, conn: QLocalSocket, line: bytes) -> None:
        try:
            req = json.loads(line.decode("utf-8"))
            op = req.get("op")
            if op not in _OPS:
                raise ValueError(f"unknown op {op!r} (known: {_OPS})")
            handler = getattr(self, f"_op_{op}")
            result = handler(req)
            response = {"ok": True, **result}
        except Exception as exc:  # noqa: BLE001 - report everything to the agent
            response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        conn.write(json.dumps(response, default=str).encode("utf-8") + b"\n")

    # -- ops -----------------------------------------------------------------
    def _op_ping(self, req: dict) -> dict:
        return {
            "pid": os.getpid(),
            "project": self.window.project.name,
            "path": str(self.window._path) if self.window._path else None,
        }

    def _op_summary(self, req: dict) -> dict:
        from graphmatrix.mcp_server import _summary

        return {"summary": _summary(self.window.project)}

    def _op_describe(self, req: dict) -> dict:
        """A detailed, model-friendly map of the live project."""
        from graphmatrix.core.scripting.graphs import describe_project

        return {"description": describe_project(self.window.project)}

    def _op_save(self, req: dict) -> dict:
        """Save the live project, adopting ``path`` as the window's file."""
        from pathlib import Path

        path = req.get("path")
        if path:
            target = Path(path)
            self.window._path = target
        else:
            target = self.window._path
            if target is None:
                raise ValueError(
                    "op 'save' requires a 'path' (the project has never been saved)"
                )
        self.window.project.save(target)
        self.window._set_dirty(False)
        self.window._update_title()
        return {"saved": str(target)}

    def _op_export(self, req: dict) -> dict:
        """Export graphs of the live project to files."""
        from graphmatrix.core.scripting.graphs import export_graphs
        from graphmatrix.ui import theme

        match_screen = bool(req.get("match_screen"))
        width_mm = float(req.get("width_mm", 100.0))
        screen = self._screen_size_inches() if match_screen else None
        aspect = None
        scale = 1.0
        if screen and screen[0] > 0 and screen[1] > 0:
            aspect = screen[0] / screen[1]
            # Fonts, line widths and markers are absolute (points), so the
            # export is scaled by the page/canvas ratio: that is what keeps a
            # small export looking like the big on-screen canvas.
            scale = max(0.05, min(4.0, (width_mm / 25.4) / screen[0]))
        return export_graphs(
            self.window.project,
            graphs=req.get("graphs"),
            out_dir=req.get("out_dir", "."),
            format=req.get("format", "pdf"),
            dpi=int(req.get("dpi", 300)),
            width_mm=width_mm,
            height_mm=float(req.get("height_mm", 75.0)),
            transparent=bool(req.get("transparent", False)),
            theme=theme.current_preset(),
            aspect=aspect,
            scale=scale,
        )

    def _screen_size_inches(self) -> tuple[float, float] | None:
        """Size of the graph canvas on screen, in inches.

        The matplotlib navigation toolbar is not part of the figure, so it is
        excluded.
        """
        window = self.window
        views = [v for v in window._views.values() if hasattr(v, "canvas")]
        if not views:
            return None
        view = window._active_graph_view
        if view not in views:
            view = views[0]
        try:
            widget = view.canvas.widget()
            figure = getattr(view.canvas, "_fig", None)
            toolbar = getattr(view.canvas, "_toolbar", None)
            width = widget.width()
            height = widget.height()
            if toolbar is not None:
                height -= toolbar.height()
            dpi = float(getattr(figure, "dpi", 0) or 0) or float(
                widget.logicalDpiX() or 96
            )
        except Exception:  # noqa: BLE001 - the view may be closing
            return None
        if width <= 0 or height <= 0:
            return None
        return width / dpi, height / dpi

    def _op_run(self, req: dict) -> dict:
        code = req.get("code")
        if not code or not isinstance(code, str):
            raise ValueError("op 'run' requires a 'code' string")
        from graphmatrix.core.scripting.api import GraphMatrixAPI, make_namespace

        before = {id(g) for g in self.window.project.graphs}
        api = GraphMatrixAPI(self.window.project, self.window.commands)
        ns = make_namespace(api)
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            exec(compile(code, "<ipc>", "exec"), ns)  # noqa: S102 - by design (console parity)
        opened: list[str] = []
        if req.get("open_graphs"):
            for graph in self.window.project.graphs:
                if id(graph) not in before:
                    self.window._open_graph_tab(graph)
                    opened.append(graph.name)
        return {
            "stdout": buf.getvalue(),
            "stderr": err.getvalue(),
            "opened_graphs": opened,
        }

    def _op_open(self, req: dict) -> dict:
        path = req.get("path")
        if not path:
            raise ValueError("op 'open' requires a 'path'")
        if self.window._dirty and not req.get("force"):
            raise RuntimeError(
                "window has unsaved changes; pass force:true to discard them"
            )
        self.window._open_project_path(path)
        return {"opened": str(path)}

    def _op_screenshot(self, req: dict) -> dict:
        path = req.get("path")
        if not path:
            raise ValueError("op 'screenshot' requires a 'path'")
        pm = self.window.grab()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if not pm.save(str(out)):
            raise RuntimeError(f"failed to save screenshot to {out}")
        return {"path": str(out), "width": pm.width(), "height": pm.height()}


# -- client side (no Qt required) -------------------------------------------
def request(
    op: str,
    *,
    sock_path: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    **payload: Any,
) -> dict[str, Any]:
    """Send one request to a running GUI's IPC bridge and return its response."""
    import socket as _socket

    path = sock_path or running_socket_path()
    if not path:
        raise RuntimeError("no running GraphMatrix instance to talk to")
    import time as _time

    sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    sock.settimeout(timeout)
    deadline = _time.monotonic() + timeout
    while True:
        try:
            sock.connect(path)
            break
        except (ConnectionRefusedError, FileNotFoundError):
            # The GUI may still be starting up or busy; retry briefly.
            if _time.monotonic() >= deadline:
                raise
            sock.close()
            sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            sock.settimeout(timeout)
            _time.sleep(0.1)
    try:
        sock.sendall(json.dumps({"op": op, **payload}).encode("utf-8") + b"\n")
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
    finally:
        sock.close()
    if not buf.strip():
        raise RuntimeError(f"no response from {path}")
    return json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))
