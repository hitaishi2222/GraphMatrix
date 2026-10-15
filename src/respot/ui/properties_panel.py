"""Properties inspector for the currently selected model object."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from respot.core.model import Graph, Project, Workbook, Worksheet


class PropertiesPanel(QWidget):
    """A read-only property grid. Grows into a real inspector in M1/M2."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Property", "Value"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

    def show_object(self, obj) -> None:
        rows = self._describe(obj) if obj is not None else []
        self._table.setRowCount(len(rows))
        for row, (key, value) in enumerate(rows):
            self._table.setItem(row, 0, QTableWidgetItem(key))
            self._table.setItem(row, 1, QTableWidgetItem(str(value)))

    # -- internals -----------------------------------------------------------
    @staticmethod
    def _describe(obj) -> list[tuple[str, object]]:
        rows: list[tuple[str, object]] = [
            ("Type", type(obj).__name__),
            ("Name", getattr(obj, "name", "")),
        ]
        if isinstance(obj, Project):
            rows += [("Workbooks", len(obj.workbooks)), ("Graphs", len(obj.graphs))]
        elif isinstance(obj, Workbook):
            rows += [("Worksheets", obj.num_sheets)]
        elif isinstance(obj, Worksheet):
            rows += [("Columns", obj.num_columns), ("Rows", obj.num_rows)]
        elif isinstance(obj, Graph):
            rows += [("Layers", obj.num_layers)]
        return rows
