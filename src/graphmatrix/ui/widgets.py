"""Small reusable widgets shared by dialogs and views."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from graphmatrix.core.model import ColumnType, Project, Worksheet

#: MIME type used when dragging a single column from the Project Explorer onto a graph.
COLUMN_MIME = "application/x-graphmatrix-column"


def sheet_label(project: Project, sheet: Worksheet) -> str:
    for book in project.workbooks:
        if sheet in book.sheets:
            return f"{book.name}/{sheet.name}"
    return sheet.name


def fill_sheet_combo(combo: QComboBox, project: Project) -> None:
    combo.clear()
    for book in project.workbooks:
        for sheet in book.sheets:
            combo.addItem(f"{book.name}/{sheet.name}", sheet)


def fill_column_combo(combo: QComboBox, sheet: Worksheet | None,
                      *, types: tuple[ColumnType, ...] | None = None,
                      include_none: bool = False) -> None:
    combo.clear()
    if include_none:
        combo.addItem("(none)", None)
    if sheet is None:
        return
    for column in sheet.columns:
        if types is not None and column.col_type not in types:
            continue
        combo.addItem(f"{column.name}  ({column.col_type.value})", column.name)
