"""Live / streaming data board (M11): tail a delimited file into a worksheet.

The dialog configures one tail (file, separator, poll interval) and
starts/stops it; the :class:`LiveController` owns the QTimer and appends
rows with ``SetCellsCommand`` — one undoable step per tick, so the command
stack's change notification refreshes the sheet and every graph bound to it.

Live feeds are *session state*: they are not serialized into the project.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from graphmatrix.core.commands import (
    AddColumnCommand,
    AddWorksheetCommand,
    SetCellsCommand,
)
from graphmatrix.core.live import DELIMITERS, LiveFileSource
from graphmatrix.core.model import Column, ColumnType, Worksheet

_LABEL_SAFE = lambda stem: stem.replace(" ", "_") or "Live"  # noqa: E731
_COLUMN_SAFE = lambda stem: stem.replace(" ", "_").replace("-", "_") or "Live"  # noqa: E731


class _Task:
    """One running tail bound to one worksheet."""

    def __init__(self, source: LiveFileSource, sheet: Worksheet) -> None:
        self.source = source
        self.sheet = sheet
        self.appended = 0


class LiveController(QObject):
    """Owns the running tails for a MainWindow; polls on a shared timer."""

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._tasks: list[_Task] = []
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.tick)
        self.enabled = False

    def start(
        self, source: LiveFileSource, book_name: str, interval_ms: int
    ) -> Worksheet:
        """Start tailing ``source`` into a (new or existing) worksheet of the
        workbook named ``book_name``; returns the bound worksheet."""
        project = self._window.project
        book = next((b for b in project.workbooks if b.name == book_name), None)
        if book is None:
            raise ValueError(f"No workbook named {book_name!r}")
        sheet_name = f"Live {_LABEL_SAFE(source.path.stem)}"
        sheet = next((s for s in book.sheets if s.name == sheet_name), None)
        if sheet is None:
            sheet = Worksheet(sheet_name)
            self._window.commands.push(AddWorksheetCommand(book, sheet))
        self._tasks.append(_Task(source, sheet))
        if not self._timer.isActive():
            self._timer.setInterval(max(50, interval_ms))
            self._timer.start()
        self.enabled = True
        return sheet

    def stop_all(self) -> None:
        self._tasks.clear()
        self._timer.stop()
        self.enabled = False

    def has_active(self) -> bool:
        return bool(self._tasks)

    def tick(self) -> None:
        commands = self._window.commands
        for task in list(self._tasks):
            rows = task.source.poll()
            if not rows:
                continue
            # First data on an empty sheet: create the columns the file names.
            if task.sheet.num_columns == 0:
                names = task.source.columns() or [
                    f"C{i + 1}" for i in range(len(rows[0]))
                ]
                for i, name in enumerate(names):
                    col_type = ColumnType.X if i == 0 else ColumnType.Y
                    commands.push(AddColumnCommand(task.sheet, Column(name, col_type)))
            width = min(len(rows[0]), task.sheet.num_columns)
            trimmed = [row[:width] for row in rows]
            commands.push(SetCellsCommand(task.sheet, task.sheet.num_rows, 0, trimmed))
            task.appended += len(trimmed)


class LiveDataDialog(QDialog):
    """Configure and control live tails (Tools → Live Data…)."""

    def __init__(
        self, window, controller: LiveController | None = None, parent=None
    ) -> None:
        super().__init__(parent or window)
        self.setWindowTitle("Live Data")
        self.controller = (
            controller or getattr(window, "live", None) or LiveController(window)
        )
        self._window = window

        layout = QVBoxLayout(self)
        form = QFormLayout()
        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        file_row.addWidget(self.file_edit)
        file_row.addWidget(browse)
        form.addRow("File:", file_row)
        self.delim_combo = QComboBox()
        self.delim_combo.addItems(list(DELIMITERS.keys()))
        self.delim_combo.setEditable(True)  # custom one-character separator
        form.addRow("Separator:", self.delim_combo)
        self.book_combo = QComboBox()
        for book in window.project.workbooks:
            self.book_combo.addItem(book.name)
        form.addRow("Target workbook:", self.book_combo)
        self.interval = QSpinBox()
        self.interval.setRange(50, 60000)
        self.interval.setValue(500)
        self.interval.setSuffix(" ms")
        form.addRow("Poll every:", self.interval)
        layout.addLayout(form)

        self.status = QLabel("No live feeds running.")
        layout.addWidget(self.status)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self._start)
        self.stop_button = QPushButton("Stop All")
        self.stop_button.clicked.connect(self._stop_all)
        self.heads_button = QPushButton("Preview first rows")
        self.heads_button.clicked.connect(self._preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(self.start_button)
        row.addWidget(self.stop_button)
        row.addWidget(self.heads_button)
        row.addStretch(1)
        row.addWidget(buttons)
        layout.addLayout(row)

    # -- helpers -------------------------------------------------------------
    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a data file",
            "",
            "Data (*.csv *.tsv *.txt *.dat *.log);;All Files (*)",
        )
        if path:
            self.file_edit.setText(path)
            stem = Path(path).stem
            if self.book_combo.findText(stem) >= 0:
                self.book_combo.setCurrentText(stem)

    def _build_source(self) -> LiveFileSource | None:
        path = self.file_edit.text().strip()
        if not path:
            QMessageBox.information(self, "Live Data", "Choose a file first.")
            return None
        sep = self.delim_combo.currentText()
        sep = DELIMITERS.get(sep, sep or ",")
        return LiveFileSource(Path(path), delimiter=sep[0] if len(sep) == 1 else sep)

    # -- actions -------------------------------------------------------------
    def _start(self) -> None:
        source = self._build_source()
        if source is None:
            return
        book = self.book_combo.currentText()
        if not book:
            QMessageBox.information(self, "Live Data", "Create a workbook first.")
            return
        sheet = self.controller.start(source, book, self.interval.value())
        window = self._window
        if hasattr(window, "_open_sheet_tab"):
            window._open_sheet_tab(sheet)
        self.status.setText(f"Tailing {source.path.name} → {sheet.name}")

    def _stop_all(self) -> None:
        self.controller.stop_all()
        self.status.setText("No live feeds running.")

    def _preview(self) -> None:
        source = self._build_source()
        if source is None:
            return
        columns = source.columns() or ["(empty file)"]
        rows = source.poll()
        text = (
            ", ".join(columns)
            + "\n"
            + "\n".join(", ".join(f"{v:g}" for v in row) for row in rows[:5])
        )
        QMessageBox.information(self, "Preview", text or "No rows available yet.")
