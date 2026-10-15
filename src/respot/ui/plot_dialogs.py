"""Dialog for adding a plot to a graph."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from respot.core.model import ColumnType, PlotSpec, PlotStyle, Project
from respot.ui.widgets import fill_column_combo, fill_sheet_combo, sheet_label


class AddPlotDialog(QDialog):
    def __init__(self, project: Project, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Plot")
        self._project = project

        self.sheet_combo = QComboBox()
        fill_sheet_combo(self.sheet_combo, project)
        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        self.yerr_combo = QComboBox()
        self.style_combo = QComboBox()
        for style in PlotStyle:
            self.style_combo.addItem(style.value, style)
        self.style_combo.setCurrentText(PlotStyle.LINE_SYMBOL.value)
        self.legend_edit = QLineEdit()

        form = QFormLayout()
        form.addRow("Data source:", self.sheet_combo)
        form.addRow("X column:", self.x_combo)
        form.addRow("Y column:", self.y_combo)
        form.addRow("Y error:", self.yerr_combo)
        form.addRow("Style:", self.style_combo)
        form.addRow("Legend label:", self.legend_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.sheet_combo.currentIndexChanged.connect(self._refresh_columns)
        self._refresh_columns()

    def _refresh_columns(self) -> None:
        sheet = self.sheet_combo.currentData()
        fill_column_combo(self.x_combo, sheet, types=(ColumnType.X,))
        fill_column_combo(self.y_combo, sheet, types=(ColumnType.Y,))
        fill_column_combo(self.yerr_combo, sheet, types=(ColumnType.YERR,), include_none=True)

    def spec(self) -> PlotSpec:
        sheet = self.sheet_combo.currentData()
        return PlotSpec(
            source=sheet_label(self._project, sheet),
            x=self.x_combo.currentData() or "",
            y=self.y_combo.currentData() or "",
            yerr=self.yerr_combo.currentData(),
            style=self.style_combo.currentData(),
            legend=self.legend_edit.text().strip(),
        )
