"""Editable worksheet grid view.

Cell edits and structural changes go through Commands, so every edit is undoable.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from respot.core.commands import (
    AddColumnCommand,
    CommandStack,
    DeleteRowsCommand,
    InsertRowsCommand,
    RemoveColumnCommand,
    RenameCommand,
    SetCellValueCommand,
    SetColumnDataCommand,
    SetColumnInfoCommand,
)
from respot.core.model import Column, ColumnType, FormulaError, Worksheet


def _fmt(value, column: Column | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if np.isnan(value):
            return ""
        if column is not None and column.decimal is not None:
            return f"{value:.{column.decimal}f}"
        return f"{value:g}"
    return str(value)


class WorksheetView(QWidget):
    """Displays and edits a worksheet."""

    def __init__(self, sheet: Worksheet, commands: CommandStack, source: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sheet = sheet
        self.commands = commands
        self.source = source  # "Book/Sheet", for row labels and commands
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self._header_menu)
        layout.addWidget(self.table)

        self.populate()

    # -- rendering -----------------------------------------------------------
    def populate(self) -> None:
        self._loading = True
        try:
            columns = self.sheet.columns
            rows = self.sheet.num_rows
            self.table.clear()
            self.table.setColumnCount(len(columns))
            self.table.setRowCount(max(rows, 1))
            self.table.setHorizontalHeaderLabels(
                [f"{c.name}\n({c.col_type.value})" + (f"\n[{c.units}]" if c.units else "") for c in columns]
            )
            for col_index, column in enumerate(columns):
                for row_index in range(rows):
                    value = column.get(row_index) if row_index < len(column) else ""
                    item = QTableWidgetItem(_fmt(value, column))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(row_index, col_index, item)
        finally:
            self._loading = False
        self.table.resizeColumnsToContents()

    # -- editing -------------------------------------------------------------
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading:
            return
        row, col = item.row(), item.column()
        if col >= self.sheet.num_columns:
            return
        column = self.sheet.columns[col]
        text = item.text().strip()
        if text == "":
            value = np.nan
        else:
            try:
                value = float(text)
            except ValueError:
                value = text
        self.commands.push(SetCellValueCommand(self.sheet, row, col, value))

    def _context_menu(self, pos) -> None:
        menu = QMenu(self)
        row = self.table.currentRow()
        menu.addAction("Insert Row Above", lambda: self.commands.push(InsertRowsCommand(self.sheet, max(row, 0))))
        menu.addAction("Delete Row", lambda: self.commands.push(DeleteRowsCommand(self.sheet, max(row, 0))))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _header_menu(self, pos) -> None:
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        if col < 0 or col >= self.sheet.num_columns:
            return
        column = self.sheet.columns[col]
        menu = QMenu(self)
        menu.addAction("Rename Column…", lambda: self._rename_column(column))
        menu.addAction("Set Units…", lambda: self._edit_field(column, "units", "Units"))
        menu.addAction("Set Comment…", lambda: self._edit_field(column, "comment", "Comment"))
        menu.addAction("Set Type…", lambda: self._set_type(column))
        menu.addAction("Set Decimal Places…", lambda: self._set_decimal(column))
        menu.addSeparator()
        menu.addAction("Set Formula…", lambda: self._set_formula(column))
        menu.addAction("Insert Column", lambda: self._insert_column(col))
        menu.addAction("Delete Column", lambda: self.commands.push(RemoveColumnCommand(self.sheet, column)))
        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def _rename_column(self, column: Column) -> None:
        name, ok = QInputDialog.getText(self, "Rename Column", "Name:", text=column.name)
        if ok and name:
            self.commands.push(RenameCommand(column, name))

    def _edit_field(self, column: Column, field: str, label: str) -> None:
        value, ok = QInputDialog.getText(self, label, f"{label}:", text=getattr(column, field))
        if ok:
            self.commands.push(SetColumnInfoCommand(self.sheet, column, **{field: value}))

    def _set_type(self, column: Column) -> None:
        types = [t.value for t in ColumnType]
        value, ok = QInputDialog.getItem(self, "Column Type", "Type:", types, types.index(column.col_type.value), False)
        if ok:
            self.commands.push(SetColumnInfoCommand(self.sheet, column, col_type=ColumnType(value)))

    def _set_decimal(self, column: Column) -> None:
        value, ok = QInputDialog.getInt(self, "Decimal Places", "Decimals:", column.decimal or 6, 0, 12)
        if ok:
            self.commands.push(SetColumnInfoCommand(self.sheet, column, decimal=value))

    def _set_formula(self, column: Column) -> None:
        text, ok = QInputDialog.getText(
            self, "Set Formula",
            "Formula (use column names, e.g. sin(X1)+2):",
            text="",
        )
        if not ok or not text:
            return
        try:
            values = np.asarray(
                __import__("respot.core.model.formula", fromlist=["evaluate_column_formula"])
                .evaluate_column_formula(self.sheet, text, max(self.sheet.num_rows, 1))
            )
        except FormulaError as exc:
            QMessageBox.warning(self, "Formula error", str(exc))
            return
        self.commands.push(SetColumnDataCommand(column, values, label=f"Formula {column.name}"))

    def _insert_column(self, index: int) -> None:
        name, ok = QInputDialog.getText(self, "Insert Column", "Name:", text=self.sheet.next_column_name(ColumnType.Y))
        if ok and name:
            column = Column(name, ColumnType.Y, [])
            self.commands.push(AddColumnCommand(self.sheet, column, index=index, source=self.source))
