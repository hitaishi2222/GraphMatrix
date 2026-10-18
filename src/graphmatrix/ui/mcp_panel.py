"""In-app control of the GraphMatrix MCP server.

The server runs as a child process (``python -m graphmatrix.mcp_server
--transport http ...``) so the GUI stays responsive and ``fastmcp`` is only
needed when the server is actually started. :class:`McpServerController` is a
small state machine; :class:`McpPanel` renders it and :class:`McpStatusIndicator`
provides the coloured mark shown in the status bar.
"""

from __future__ import annotations

import json
import sys

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Qt, QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtNetwork import QTcpSocket
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

STOPPED = "stopped"
STARTING = "starting"
RUNNING = "running"
ERROR = "error"

STATE_LABELS = {
    STOPPED: "Stopped",
    STARTING: "Starting…",
    RUNNING: "Running",
    ERROR: "Error",
}

STATE_COLORS = {
    STOPPED: "#9aa0a6",
    STARTING: "#e0af68",
    RUNNING: "#3fb950",
    ERROR: "#e5534b",
}

#: Tools advertised by ``graphmatrix.mcp_server`` (kept in sync manually so the
#: panel works even when fastmcp is not installed in the GUI process).
MCP_TOOLS = (
    ("connect", "Open a project file or create an in-memory project session."),
    ("summary", "List workbooks, sheets, columns, graphs, and versions."),
    ("run", "Execute Python against a project session."),
    ("export", "Export selected graphs to PDF/SVG/PNG/… files."),
    ("live_summary", "Summarise the project open in the running GUI."),
    ("live_run", "Run code against the live GUI (instant, undoable)."),
    ("live_open", "Open a project file in the running GUI."),
    ("live_screenshot", "Capture a screenshot of the running GUI window."),
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class McpServerController(QObject):
    """Start/stop ``graphmatrix-mcp`` in a child process and report its state."""

    #: (state, human-readable detail)
    status_changed = Signal(str, str)
    #: Raw child-process output (decoded, chunk by chunk).
    log_output = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = STOPPED
        self._detail = "Not started"
        self._process: QProcess | None = None
        self._host = DEFAULT_HOST
        self._port = DEFAULT_PORT
        self._transport = "http"
        self._stopping = False
        self._probe_attempts = 0
        self._tail: list[str] = []

        self._probe_timer = QTimer(self)
        self._probe_timer.setInterval(250)
        self._probe_timer.timeout.connect(self._probe)

    # -- public API ----------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    @property
    def detail(self) -> str:
        return self._detail

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def transport(self) -> str:
        return self._transport

    def endpoint(self) -> str:
        """URL an MCP client should connect to."""
        path = "sse" if self._transport == "sse" else "mcp"
        return f"http://{self._host}:{self._port}/{path}"

    @staticmethod
    def server_command(
        host: str,
        port: int,
        transport: str = "http",
        *,
        python: str | None = None,
    ) -> list[str]:
        """Command line used to launch the MCP server child process."""
        return [
            python or sys.executable,
            "-m",
            "graphmatrix.mcp_server",
            "--transport",
            transport,
            "--host",
            host,
            "--port",
            str(int(port)),
        ]

    def start(
        self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, transport: str = "http"
    ) -> None:
        if self._state in (STARTING, RUNNING):
            return
        host = (host or DEFAULT_HOST).strip()
        if not host:
            self._set_state(ERROR, "Host must not be empty.")
            return
        if not (1 <= int(port) <= 65535):
            self._set_state(ERROR, "Port must be between 1 and 65535.")
            return
        self._host, self._port, self._transport = host, int(port), transport
        self._stopping = False
        self._probe_attempts = 0
        self._tail = []

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(env)
        process.readyReadStandardOutput.connect(self._read_output)
        process.errorOccurred.connect(self._on_error)
        process.finished.connect(self._on_finished)
        self._process = process

        command = self.server_command(self._host, self._port, transport)
        self._set_state(STARTING, f"Starting on {self.endpoint()}…")
        self._append_log("$ " + " ".join(command) + "\n")
        process.start(command[0], command[1:])
        self._probe_timer.start()

    def stop(self) -> None:
        """Terminate the child process (safe to call when stopped)."""
        self._stopping = True
        self._probe_timer.stop()
        self._terminate_process()
        self._stopping = False
        self._set_state(STOPPED, "Server stopped.")

    # -- internals -----------------------------------------------------------
    def _terminate_process(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            if process.state() != QProcess.ProcessState.NotRunning:
                process.terminate()
                if not process.waitForFinished(2500):
                    process.kill()
                    process.waitForFinished(1000)
        except RuntimeError:
            pass

    def _probe(self) -> None:
        if self._state != STARTING:
            self._probe_timer.stop()
            return
        process = self._process
        if process is None or process.state() == QProcess.ProcessState.NotRunning:
            return
        socket = QTcpSocket(self)
        socket.connectToHost(self._host, self._port)
        connected = socket.waitForConnected(100)
        socket.abort()
        socket.deleteLater()
        if connected:
            self._probe_timer.stop()
            self._set_state(RUNNING, f"Listening on {self.endpoint()}")
            return
        self._probe_attempts += 1
        if self._probe_attempts >= 240:  # ~60 s
            self._probe_timer.stop()
            self._set_state(ERROR, f"Timed out waiting for {self.endpoint()}")
            self._terminate_process()

    def _read_output(self) -> None:
        process = self._process
        if process is None:
            return
        text = bytes(process.readAllStandardOutput()).decode("utf-8", "replace")
        if not text:
            return
        for line in text.splitlines():
            if line.strip():
                self._tail.append(line)
        self._tail = self._tail[-80:]
        self.log_output.emit(text)

    def _on_error(self, error) -> None:
        if error != QProcess.ProcessError.FailedToStart:
            return
        process = self._process
        detail = process.errorString() if process is not None else "failed to start"
        self._probe_timer.stop()
        self._process = None
        self._set_state(ERROR, f"Could not start the server: {detail}")

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        self._probe_timer.stop()
        self._process = None
        if self._stopping:
            self._stopping = False
            self._set_state(STOPPED, "Server stopped.")
            return
        if self._state == ERROR:
            return
        if exit_code == 0:
            self._set_state(STOPPED, "Server exited.")
            return
        tail = self._tail[-1] if self._tail else "no output"
        self._set_state(ERROR, f"Server exited with code {exit_code}: {tail}")

    def _append_log(self, text: str) -> None:
        self.log_output.emit(text)

    def _set_state(self, state: str, detail: str) -> None:
        self._state = state
        self._detail = detail
        self.status_changed.emit(state, detail)


class McpPanel(QWidget):
    """Dock contents: status, host/port, start/stop, tools, logs, bridge state."""

    def __init__(
        self, controller: McpServerController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._build()
        controller.status_changed.connect(self._on_status)
        controller.log_output.connect(self._append_log)

        self._bridge_timer = QTimer(self)
        self._bridge_timer.setInterval(3000)
        self._bridge_timer.timeout.connect(self.refresh_bridge)
        self._on_status(controller.state, controller.detail)
        self.refresh_bridge()

    # -- construction --------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        header = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("font-size: 14pt;")
        self.status_label = QLabel("Stopped")
        self.status_label.setStyleSheet("font-weight: bold;")
        self.detail_label = QLabel("Not started")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: palette(mid);")
        header.addWidget(self.status_dot)
        header.addWidget(self.status_label)
        header.addSpacing(8)
        header.addWidget(self.detail_label, 1)
        layout.addLayout(header)

        form_box = QGroupBox("Server")
        form = QFormLayout(form_box)
        self.transport_combo = QComboBox()
        self.transport_combo.addItem("Streamable HTTP", "http")
        self.transport_combo.addItem("SSE (legacy)", "sse")
        self.host_edit = QLineEdit(DEFAULT_HOST)
        self.host_edit.setToolTip("Bind address; use 127.0.0.1 for local-only access.")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(DEFAULT_PORT)
        self.port_spin.setToolTip("TCP port the MCP server listens on.")
        self.endpoint_label = QLabel(self.controller.endpoint())
        self.endpoint_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Transport:", self.transport_combo)
        form.addRow("Host:", self.host_edit)
        form.addRow("Port:", self.port_spin)
        form.addRow("Endpoint:", self.endpoint_label)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start server")
        self.start_button.clicked.connect(self._toggle)
        self.copy_http_button = QPushButton("Copy HTTP config")
        self.copy_http_button.setToolTip("Copy a JSON client config for this server.")
        self.copy_http_button.clicked.connect(self._copy_http_config)
        self.copy_stdio_button = QPushButton("Copy stdio config")
        self.copy_stdio_button.setToolTip(
            "Copy a config that lets the client launch graphmatrix-mcp itself."
        )
        self.copy_stdio_button.clicked.connect(self._copy_stdio_config)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.copy_http_button)
        buttons.addWidget(self.copy_stdio_button)
        buttons.addStretch(1)
        form.addRow(buttons)
        layout.addWidget(form_box)

        self.host_edit.textChanged.connect(self._update_endpoint)
        self.port_spin.valueChanged.connect(self._update_endpoint)
        self.transport_combo.currentIndexChanged.connect(self._update_endpoint)

        self.bridge_label = QLabel("Live GUI bridge: checking…")
        self.bridge_label.setWordWrap(True)
        self.bridge_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.bridge_label)

        tools_box = QGroupBox("Tools exposed")
        tools_layout = QVBoxLayout(tools_box)
        self.tools_list = QListWidget()
        self.tools_list.setMaximumHeight(130)
        for name, description in MCP_TOOLS:
            self.tools_list.addItem(f"{name} — {description}")
        tools_layout.addWidget(self.tools_list)
        layout.addWidget(tools_box)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setPlaceholderText("Server output appears here.")
        self.log.setMinimumHeight(110)
        layout.addWidget(self.log, 1)

    # -- state ---------------------------------------------------------------
    def _preview_endpoint(self) -> str:
        transport = self.transport_combo.currentData() or "http"
        path = "sse" if transport == "sse" else "mcp"
        host = self.host_edit.text().strip() or DEFAULT_HOST
        return f"http://{host}:{self.port_spin.value()}/{path}"

    def _update_endpoint(self, *_args) -> None:
        self.endpoint_label.setText(self._preview_endpoint())

    def _on_status(self, state: str, detail: str) -> None:
        color = STATE_COLORS.get(state, STATE_COLORS[STOPPED])
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14pt;")
        self.status_label.setText(STATE_LABELS.get(state, state.title()))
        self.detail_label.setText(detail)
        busy = state in (STARTING, RUNNING)
        self.start_button.setText("Stop server" if busy else "Start server")
        for widget in (self.transport_combo, self.host_edit, self.port_spin):
            widget.setEnabled(not busy)
        self.endpoint_label.setText(self._preview_endpoint())

    def _append_log(self, text: str) -> None:
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        self.log.insertPlainText(text if text.endswith("\n") else text + "\n")
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _toggle(self) -> None:
        if self.controller.state in (STARTING, RUNNING):
            self.controller.stop()
            return
        self.controller.start(
            self.host_edit.text().strip() or DEFAULT_HOST,
            self.port_spin.value(),
            self.transport_combo.currentData() or "http",
        )

    # -- clipboard helpers ---------------------------------------------------
    def _copy_http_config(self) -> None:
        payload = {
            "mcpServers": {
                "graphmatrix-live": {
                    "url": self._preview_endpoint(),
                }
            }
        }
        self._copy_json(json.dumps(payload, indent=2))

    def _copy_stdio_config(self) -> None:
        payload = {
            "mcpServers": {
                "graphmatrix": {
                    "command": "graphmatrix-mcp",
                }
            }
        }
        self._copy_json(json.dumps(payload, indent=2))

    def _copy_json(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self._append_log("Copied client config to the clipboard.\n")

    # -- live bridge ---------------------------------------------------------
    def refresh_bridge(self) -> None:
        """Show whether agents can currently reach the running GUI over IPC."""
        try:
            from graphmatrix.core.ipc import running_socket_path
        except ImportError:  # pragma: no cover - IPC is part of the package
            running_socket_path = None
        path = None
        if running_socket_path is not None:
            try:
                path = running_socket_path()
            except OSError:
                path = None
        if path:
            self.bridge_label.setText(f"Live GUI bridge: ● active\n{path}")
            self.bridge_label.setStyleSheet("color: #3fb950;")
        else:
            self.bridge_label.setText(
                "Live GUI bridge: ○ inactive (no registered GUI socket found)"
            )
            self.bridge_label.setStyleSheet("color: palette(mid);")

    # -- Qt events -----------------------------------------------------------
    def showEvent(self, event) -> None:
        self.refresh_bridge()
        self._bridge_timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._bridge_timer.stop()
        super().hideEvent(event)


class McpStatusIndicator(QWidget):
    """Compact status-bar mark: a coloured dot + “MCP”; click opens the panel."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = STOPPED
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(4)
        self._dot = QLabel("●")
        self._text = QLabel("MCP")
        layout.addWidget(self._dot)
        layout.addWidget(self._text)
        self.set_state(STOPPED, "Not started")

    def set_state(self, state: str, detail: str = "") -> None:
        self._state = state
        color = STATE_COLORS.get(state, STATE_COLORS[STOPPED])
        self._dot.setStyleSheet(f"color: {color}; font-size: 12pt;")
        label = STATE_LABELS.get(state, state.title())
        self.setToolTip(
            f"MCP server: {label}\n{detail}\nClick to open the MCP control panel"
        )

    @property
    def state(self) -> str:
        return self._state

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
