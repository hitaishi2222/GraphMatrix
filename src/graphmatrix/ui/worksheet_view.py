"""Editable worksheet grid view.

Cell edits and structural changes go through Commands, so every edit is undoable.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from graphmatrix.core.commands import (
    AddColumnCommand,
    CommandStack,
    DeleteRowsCommand,
    InsertRowsCommand,
    RemoveColumnCommand,
    RenameCommand,
    ReorderColumnsCommand,
    SetCellValueCommand,
    SetCellsCommand,
    SetColumnDataCommand,
    SetColumnInfoCommand,
)
from graphmatrix.core.model import Column, ColumnType, FormulaError, Worksheet


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

    plot_column_requested = Signal(str)  # column name to plot against its partner
    #: (source, rows) emitted when the user changes the row selection
    rows_selected = Signal(str, list)

    # Orange tint shared with the graph-canvas brush overlay.
    HIGHLIGHT_COLOR = "#ff7f0e"

    def __init__(self, sheet: Worksheet, commands: CommandStack, source: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sheet = sheet
        self.commands = commands
        self.source = source  # "Book/Sheet", for row labels and commands
        self._loading = False
        self._highlighted_rows: set[int] = set()

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
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().sectionMoved.connect(self._on_section_moved)
        self.table.selectionModel().selectionChanged.connect(self._broadcast_selection)
        layout.addWidget(self.table)

        for keys, slot in (
            (QKeySequence.StandardKey.Copy, self._copy),
            (QKeySequence.StandardKey.Cut, self._cut),
            (QKeySequence.StandardKey.Paste, self._paste),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

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
            header = self.table.horizontalHeader()
            for i in range(self.table.columnCount()):
                header.moveSection(header.visualIndex(i), i)
        finally:
            self._loading = False
        self._apply_row_highlight()
        self.table.resizeColumnsToContents()

    # -- linked brushing -----------------------------------------------------
    def _apply_row_highlight(self) -> None:
        """Tint the brush-selected rows, resetting everything else."""
        from PySide6.QtGui import QColor

        tint = QColor(self.HIGHLIGHT_COLOR)
        tint.setAlpha(40)
        on = self._highlighted_rows
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is not None:
                    item.setBackground(tint if row in on else Qt.GlobalColor.transparent)

    def set_row_highlight(self, rows: list[int]) -> None:
        """Highlight the given worksheet rows (linked brush from graph or sheet)."""
        self._highlighted_rows = {int(r) for r in rows}
        self._apply_row_highlight()

    def selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.table.selectedIndexes()})

    def clear_row_highlight(self) -> None:
        self.set_row_highlight([])

    def _broadcast_selection(self, *_args, **_kwargs) -> None:
        """Emit the user's row selection for linked brushing.

        Guarded so programmatic highlights, table rebuilds (``populate``), and
        the brush itself don't feed back into the shared selection.
        """
        if self._loading or getattr(self, "_broadcasting", False):
            return
        self.rows_selected.emit(self.source, self.selected_rows())

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
        columns = self._selected_column_indices()
        if len(columns) == 1:
            column = self.sheet.columns[columns[0]]
            menu.addAction(f"Plot \u201c{column.name}\u201d", lambda: self._plot_column(column))
            menu.addSeparator()
        menu.addAction("Copy", self._copy)
        menu.addAction("Cut", self._cut)
        menu.addAction("Paste", self._paste)
        menu.addSeparator()
        menu.addAction("Insert Row Above", lambda: self.commands.push(InsertRowsCommand(self.sheet, max(row, 0))))
        menu.addAction("Delete Row", lambda: self.commands.push(DeleteRowsCommand(self.sheet, max(row, 0))))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # -- clipboard -----------------------------------------------------------
    def _selection_bounds(self) -> tuple[int, int, int, int] | None:
        ranges = self.table.selectedRanges()
        if not ranges:
            row = max(self.table.currentRow(), 0)
            col = max(self.table.currentColumn(), 0)
            return row, col, row, col
        top = min(r.topRow() for r in ranges)
        left = min(r.leftColumn() for r in ranges)
        bottom = max(r.bottomRow() for r in ranges)
        right = max(r.rightColumn() for r in ranges)
        return top, left, bottom, right

    def _selected_column_indices(self) -> list[int]:
        bounds = self._selection_bounds()
        if bounds is None:
            return []
        _, left, _, right = bounds
        return [c for c in range(left, right + 1) if c < self.sheet.num_columns]

    def _plot_column(self, column: Column) -> None:
        self.plot_column_requested.emit(column.name)

    def _copy(self) -> None:
        bounds = self._selection_bounds()
        if bounds is None:
            return
        top, left, bottom, right = bounds
        lines = []
        for row in range(top, bottom + 1):
            cells = []
            for col in range(left, right + 1):
                item = self.table.item(row, col)
                cells.append(item.text() if item is not None else "")
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))

    def _cut(self) -> None:
        self._copy()
        bounds = self._selection_bounds()
        if bounds is None:
            return
        top, left, bottom, right = bounds
        for row in range(top, bottom + 1):
            for col in range(left, right + 1):
                if col < self.sheet.num_columns:
                    column = self.sheet.columns[col]
                    self.commands.push(SetCellValueCommand(self.sheet, row, col, self._blank(column)))

    def _cell_from_text(self, column: Column, text: str):
        if column.col_type == ColumnType.TEXT:
            return text
        if text.strip() == "":
            return np.nan
        try:
            return float(text)
        except ValueError:
            return text

    def _blank(self, column: Column):
        return "" if column.col_type == ColumnType.TEXT else np.nan

    def _paste(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return
        rows = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n").split("\n")
        row0 = max(self.table.currentRow(), 0)
        col0 = max(self.table.currentColumn(), 0)
        if col0 >= self.sheet.num_columns:
            return
        values = [
            [self._cell_from_text(self.sheet.columns[col0 + dc], raw)
             for dc, raw in enumerate(line.split("\t"))
             if col0 + dc < self.sheet.num_columns]
            for line in rows
        ]
        self.commands.push(SetCellsCommand(self.sheet, row0, col0, values))

    def _on_section_moved(self, logical: int, old_visual: int, new_visual: int) -> None:
        if self._loading or self.sheet.num_columns == 0:
            return
        header = self.table.horizontalHeader()
        order = [self.sheet.columns[header.logicalIndex(v)] for v in range(self.sheet.num_columns)]
        if [c.name for c in order] == self.sheet.column_names:
            return
        self.commands.push(ReorderColumnsCommand(self.sheet, order))

    def _header_menu(self, pos) -> None:
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        if col < 0 or col >= self.sheet.num_columns:
            return
        column = self.sheet.columns[col]
        menu = QMenu(self)
        menu.addAction(f"Plot \u201c{column.name}\u201d", lambda: self._plot_column(column))
        menu.addSeparator()
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
                __import__("graphmatrix.core.model.formula", fromlist=["evaluate_column_formula"])
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
