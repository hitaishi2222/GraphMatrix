"""Dialog for adding a plot to a graph."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from respot.core.model import LINE_STYLES, ColumnType, PlotSpec, PlotStyle, Project, ReferenceLine
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


class ReferenceLineDialog(QDialog):
    """Choose an H-line or V-line: position, colour, width, dash, and label."""

    def __init__(self, parent=None, *, orientation: str = "h") -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Reference Line")
        self._color = "#888888"

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("Horizontal (y = …)", "h")
        self.orientation_combo.addItem("Vertical (x = …)", "v")
        self.orientation_combo.setCurrentIndex(0 if orientation == "h" else 1)
        self.position = QDoubleSpinBox()
        self.position.setRange(-1e12, 1e12)
        self.position.setDecimals(4)
        self.position.setValue(0.0)
        self.color_button = QPushButton("colour")
        self.color_button.clicked.connect(self._pick_color)
        self.width = QDoubleSpinBox()
        self.width.setRange(0.5, 10.0)
        self.width.setSingleStep(0.5)
        self.width.setValue(1.5)
        self.style_combo = QComboBox()
        for style in LINE_STYLES:
            self.style_combo.addItem(style, style)
        self.style_combo.setCurrentText("dash")
        self.label_edit = QLineEdit()

        form = QFormLayout()
        form.addRow("Orientation:", self.orientation_combo)
        form.addRow("Position:", self.position)
        form.addRow("Colour:", self.color_button)
        form.addRow("Width:", self.width)
        form.addRow("Line style:", self.style_combo)
        form.addRow("Label:", self.label_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._update_color_button()

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Reference Line Colour")
        if color.isValid():
            self._color = color.name()
            self._update_color_button()

    def _update_color_button(self) -> None:
        self.color_button.setStyleSheet(f"background-color: {self._color}")

    def reference_line(self) -> ReferenceLine:
        return ReferenceLine(
            orientation=self.orientation_combo.currentData(),
            position=self.position.value(),
            color=self._color,
            width=self.width.value(),
            line_style=self.style_combo.currentData(),
            label=self.label_edit.text().strip(),
        )
