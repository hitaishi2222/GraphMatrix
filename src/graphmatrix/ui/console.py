"""Embedded Python console (M5).

Executes code against the GraphMatrixAPI namespace. This is the scripting surface that
makes GraphMatrix Python-native rather than a closed GUI.
"""

from __future__ import annotations

import code
import contextlib
import io
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from graphmatrix.core.model import Project
from graphmatrix.core.commands import CommandStack
from graphmatrix.core.scripting.api import GraphMatrixAPI, make_namespace


class _Interpreter(code.InteractiveInterpreter):
    def __init__(self, namespace: dict) -> None:
        super().__init__(namespace)
        self.output = io.StringIO()

    def write(self, text: str) -> None:  # called by showtraceback
        self.output.write(text)


class ConsoleView(QWidget):
    """Output pane + input line, with history and a persistent namespace."""

    def __init__(
        self, project: Project, commands: CommandStack, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._commands = commands
        self._history: list[str] = []
        self._history_index = 0
        self._buffer = ""

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("monospace"))
        self.output.setMaximumBlockCount(5000)

        prompt = QLabel(">>>")
        prompt.setFont(QFont("monospace"))
        self.input = QLineEdit()
        self.input.setFont(QFont("monospace"))
        self.input.returnPressed.connect(self._execute_current)
        self.input.installEventFilter(self)

        row = QHBoxLayout()
        row.addWidget(prompt)
        row.addWidget(self.input)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.output)
        layout.addLayout(row)

        self.set_project(project)
        self._write(
            "GraphMatrix console. `api` and `project` are in scope. Try: api.add_column('Book1/Sheet1','X1','X',data=[0,1,2])"
        )

    # -- namespace -----------------------------------------------------------
    def set_project(self, project: Project) -> None:
        self.api = GraphMatrixAPI(project, self._commands)
        self._interp = _Interpreter(make_namespace(self.api))

    def _write(self, text: str) -> None:
        self.output.appendPlainText(text)
        self.output.verticalScrollBar().setValue(
            self.output.verticalScrollBar().maximum()
        )

    # -- execution -----------------------------------------------------------
    def _execute_current(self) -> None:
        text = self.input.text()
        self.input.clear()
        if text.strip():
            self._history.append(text)
            self._history_index = len(self._history)
        self._buffer += text + "\n"

        source = self._buffer
        try:
            compiled = code.compile_command(source, "<console>", "single")
        except (SyntaxError, OverflowError, ValueError):
            compiled = None
            self._buffer = ""
            self._report_error()
            return
        if compiled is None:
            return  # incomplete; keep buffering

        self._buffer = ""
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                exec(compiled, self._interp.locals, self._interp.locals)
        except SystemExit:
            self._write("(SystemExit ignored)")
        except Exception:  # noqa: BLE001 - show the user what went wrong
            self._write(traceback.format_exc())
        output = stdout.getvalue()
        if output:
            self._write(output.rstrip())

    def _report_error(self) -> None:
        self._write(traceback.format_exc())

    # -- history -------------------------------------------------------------
    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if obj is self.input and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up and self._history:
                self._history_index = max(0, self._history_index - 1)
                self.input.setText(self._history[self._history_index])
                return True
            if key == Qt.Key.Key_Down and self._history:
                self._history_index = min(len(self._history), self._history_index + 1)
                self.input.setText(
                    ""
                    if self._history_index >= len(self._history)
                    else self._history[self._history_index]
                )
                return True
        return super().eventFilter(obj, event)

    def run_script(self, source: str) -> None:
        """Execute a multi-line script and report output/errors."""
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                exec(
                    compile(source, "<macro>", "exec"),
                    self._interp.locals,
                    self._interp.locals,
                )
        except Exception:  # noqa: BLE001
            self._write(traceback.format_exc())
        output = stdout.getvalue()
        if output:
            self._write(output.rstrip())
