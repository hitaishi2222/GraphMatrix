"""Read-only grid view of a worksheet (editing arrives in M1)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from respot.core.model import Worksheet


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


class WorksheetView(QWidget):
    """Displays a worksheet's columns in a table."""

    def __init__(self, sheet: Worksheet, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sheet = sheet

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.table)

        self.populate()

    def populate(self) -> None:
        sheet = self.sheet
        columns = sheet.columns
        rows = sheet.num_rows

        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(rows)
        self.table.setHorizontalHeaderLabels(
            [f"{c.name}  ({c.col_type.value})" for c in columns]
        )

        for col_index, column in enumerate(columns):
            for row_index in range(rows):
                value = column.get(row_index) if row_index < len(column) else ""
                item = QTableWidgetItem(_fmt(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, col_index, item)

        self.table.resizeColumnsToContents()
