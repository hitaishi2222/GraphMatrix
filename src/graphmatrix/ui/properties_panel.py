"""Properties inspector for the currently selected model object."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from graphmatrix.core.model import Column, Graph, Project, Workbook, Worksheet


class PropertiesPanel(QWidget):
    """A property grid with an editable Name field."""

    rename_requested = Signal(object, str)  # (object, new_name)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self._obj = None
        self._loading = False

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Property", "Value"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table)

    def show_object(self, obj) -> None:
        self._obj = obj
        rows = self._describe(obj) if obj is not None else []
        self._loading = True
        try:
            self._table.setRowCount(len(rows))
            for row, (key, value) in enumerate(rows):
                key_item = QTableWidgetItem(key)
                key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                value_item = QTableWidgetItem(str(value))
                if key == "Name" and obj is not None:
                    value_item.setFlags(value_item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, 0, key_item)
                self._table.setItem(row, 1, value_item)
        finally:
            self._loading = False

    # -- internals -----------------------------------------------------------
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or self._obj is None or item.column() != 1:
            return
        key_item = self._table.item(item.row(), 0)
        if key_item is not None and key_item.text() == "Name":
            self.rename_requested.emit(self._obj, item.text())

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
        elif isinstance(obj, Column):
            rows += [
                ("Type", obj.col_type.value),
                ("Units", obj.units),
                ("Comment", obj.comment),
                ("Values", len(obj)),
            ]
        return rows
