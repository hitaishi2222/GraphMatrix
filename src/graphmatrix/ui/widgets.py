"""Small reusable widgets shared by dialogs and views."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox

from graphmatrix.core.model import ColumnType, Project, Worksheet

#: MIME type used when dragging a single column from the Project Explorer onto a graph.
COLUMN_MIME = "application/x-graphmatrix-column"


def contrast_text_color(background: str) -> str:
    """Black or white - whichever stays readable on ``background``.

    Colour buttons paint themselves in the colour they hold, so the label has
    to be legible on that colour instead of the application's text colour.
    """
    color = QColor(background)
    if not color.isValid():
        return "#000000"
    luminance = (
        0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    )
    return "#000000" if luminance > 140 else "#ffffff"


def color_button_style(background: str, text: str) -> str:
    """Style sheet for a button that shows ``background`` as a colour swatch."""
    fg = contrast_text_color(background)
    return (
        f"background-color: {background}; color: {fg};"
        " border: 1px solid palette(mid); border-radius: 6px; padding: 4px 10px;"
    )


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


def fill_column_combo(
    combo: QComboBox,
    sheet: Worksheet | None,
    *,
    types: tuple[ColumnType, ...] | None = None,
    include_none: bool = False,
) -> None:
    combo.clear()
    if include_none:
        combo.addItem("(none)", None)
    if sheet is None:
        return
    for column in sheet.columns:
        if types is not None and column.col_type not in types:
            continue
        combo.addItem(f"{column.name}  ({column.col_type.value})", column.name)
