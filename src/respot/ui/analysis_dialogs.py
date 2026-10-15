"""Analysis dialogs: choose data + parameters, then show a report.

All heavy lifting lives in ``core.analysis``; these dialogs only gather input and
render :class:`~respot.core.analysis.result.AnalysisResult`.
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from respot.core.analysis import descriptive, fitting, peaks, regression, signal, statistics
from respot.core.commands import AddColumnCommand, CommandStack, MacroCommand
from respot.core.model import Column, ColumnType, Project, Worksheet
from respot.ui.widgets import fill_column_combo, fill_sheet_combo, sheet_label


class AnalysisResultDialog(QDialog):
    """Renders an AnalysisResult and can push its curves back into the project."""

    def __init__(self, result, *, project: Project | None = None, commands: CommandStack | None = None,
                 default_sheet: Worksheet | None = None, add_to_graph=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(result.title)
        self.resize(680, 560)
        self._result = result
        self._project = project
        self._commands = commands
        self._add_to_graph = add_to_graph

        layout = QVBoxLayout(self)
        view = QPlainTextEdit(result.to_text())
        view.setReadOnly(True)
        view.setFont(QFont("monospace"))
        layout.addWidget(view)

        if result.curves and (project is not None and commands is not None):
            row = QHBoxLayout()
            row.addWidget(QLabel("Curves:"))
            self.curve_combo = QComboBox()
            for name in result.curves:
                self.curve_combo.addItem(name, name)
            row.addWidget(self.curve_combo)
            row.addWidget(QLabel("Add to:"))
            self.sheet_combo = QComboBox()
            fill_sheet_combo(self.sheet_combo, project)
            if default_sheet is not None:
                index = self.sheet_combo.findText(sheet_label(project, default_sheet))
                if index >= 0:
                    self.sheet_combo.setCurrentIndex(index)
            row.addWidget(self.sheet_combo)
            add_button = QPushButton("Add as columns")
            add_button.clicked.connect(self._add_curves_as_columns)
            row.addWidget(add_button)
            if add_to_graph is not None:
                plot_button = QPushButton("Plot on active graph")
                plot_button.clicked.connect(self._plot_on_graph)
                row.addWidget(plot_button)
            layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)

    def _selected_curves(self) -> list[tuple[str, object, object]]:
        name = self.curve_combo.currentData()
        x, y = self._result.curves[name]
        return [(name, x, y)]

    def _add_curves_as_columns(self) -> None:
        sheet = self.sheet_combo.currentData()
        if sheet is None or self._commands is None:
            return
        commands = []
        for name, x, y in self._selected_curves():
            xname = sheet.unique_column_name(f"{name}_X")
            yname = sheet.unique_column_name(f"{name}_Y")
            commands.append(AddColumnCommand(sheet, Column(xname, ColumnType.X, x), source=sheet_label(self._project, sheet)))
            commands.append(AddColumnCommand(sheet, Column(yname, ColumnType.Y, y), source=sheet_label(self._project, sheet)))
        self._commands.push(MacroCommand(commands, f"Add {name} columns"))

    def _plot_on_graph(self) -> None:
        if self._add_to_graph is None:
            return
        sheet = self.sheet_combo.currentData()
        for name, x, y in self._selected_curves():
            self._add_to_graph(sheet, name, x, y)


class _TwoColumnDialog(QDialog):
    """Base dialog: a sheet combo plus column combos that refresh on sheet change."""

    def __init__(self, project: Project, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.project = project
        self.form = QFormLayout()
        self.sheet_combo = QComboBox()
        fill_sheet_combo(self.sheet_combo, project)
        self.sheet_combo.currentIndexChanged.connect(self._refresh_columns)
        self.form.addRow("Data source:", self.sheet_combo)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addWidget(self._buttons)

    def _refresh_columns(self) -> None:  # overridden
        pass

    def sheet(self) -> Worksheet | None:
        return self.sheet_combo.currentData()

    def _x_array(self, name: str):
        return self.sheet().column(name).float_data()


class DescriptiveDialog(_TwoColumnDialog):
    def __init__(self, project, parent=None):
        super().__init__(project, "Descriptive Statistics", parent)
        self.columns = QListWidget()
        self.columns.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.form.addRow("Columns:", self.columns)
        self._refresh_columns()

    def _refresh_columns(self):
        self.columns.clear()
        for column in self.sheet().columns:
            item = QListWidgetItem(f"{column.name}  ({column.col_type.value})")
            item.setData(1, column.name)
            self.columns.addItem(item)

    def run(self):
        names = [i.data(1) for i in self.columns.selectedItems()] or [c.name for c in self.sheet().columns]
        return descriptive.summarize_columns(self.sheet(), names)


class RegressionDialog(_TwoColumnDialog):
    def __init__(self, project, parent=None):
        super().__init__(project, "Regression", parent)
        self.mode = QComboBox()
        self.mode.addItems(["Linear", "Polynomial"])
        self.degree = QSpinBox()
        self.degree.setRange(2, 10)
        self.degree.setValue(2)
        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        self.form.addRow("Model:", self.mode)
        self.form.addRow("Degree:", self.degree)
        self.form.addRow("X column:", self.x_combo)
        self.form.addRow("Y column:", self.y_combo)
        self._refresh_columns()

    def _refresh_columns(self):
        fill_column_combo(self.x_combo, self.sheet(), types=(ColumnType.X,))
        fill_column_combo(self.y_combo, self.sheet(), types=(ColumnType.Y,))

    def run(self):
        x = self._x_array(self.x_combo.currentData())
        y = self._x_array(self.y_combo.currentData())
        if self.mode.currentText() == "Linear":
            return regression.linear_fit(x, y)
        return regression.polynomial_fit(x, y, self.degree.value())


class FitDialog(_TwoColumnDialog):
    def __init__(self, project, parent=None):
        super().__init__(project, "Nonlinear Curve Fit", parent)
        self.model_combo = QComboBox()
        self.model_combo.addItems(fitting.available_models())
        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        self.yerr_combo = QComboBox()
        self.form.addRow("Model:", self.model_combo)
        self.form.addRow("X column:", self.x_combo)
        self.form.addRow("Y column:", self.y_combo)
        self.form.addRow("Y error:", self.yerr_combo)
        self._refresh_columns()

    def _refresh_columns(self):
        fill_column_combo(self.x_combo, self.sheet(), types=(ColumnType.X,))
        fill_column_combo(self.y_combo, self.sheet(), types=(ColumnType.Y,))
        fill_column_combo(self.yerr_combo, self.sheet(), types=(ColumnType.YERR,), include_none=True)

    def run(self):
        x = self._x_array(self.x_combo.currentData())
        y = self._x_array(self.y_combo.currentData())
        yerr = self._x_array(self.yerr_combo.currentData()) if self.yerr_combo.currentData() else None
        return fitting.fit_model(self.model_combo.currentText(), x, y, yerr=yerr)


class PeaksDialog(_TwoColumnDialog):
    def __init__(self, project, parent=None):
        super().__init__(project, "Peak Analysis", parent)
        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        self.prominence = QLineEdit()
        self.distance = QLineEdit()
        self.form.addRow("X column:", self.x_combo)
        self.form.addRow("Y column:", self.y_combo)
        self.form.addRow("Min prominence:", self.prominence)
        self.form.addRow("Min distance:", self.distance)
        self._refresh_columns()

    def _refresh_columns(self):
        fill_column_combo(self.x_combo, self.sheet(), types=(ColumnType.X,))
        fill_column_combo(self.y_combo, self.sheet(), types=(ColumnType.Y,))

    def run(self):
        def number(text):
            text = text.strip()
            return float(text) if text else None

        return peaks.find_peaks_result(
            self._x_array(self.x_combo.currentData()),
            self._x_array(self.y_combo.currentData()),
            prominence=number(self.prominence.text()),
            distance=number(self.distance.text()),
        )


class SignalDialog(_TwoColumnDialog):
    OPERATIONS = ["Smooth (Savitzky-Golay)", "Moving Average", "Low-pass Filter",
                  "High-pass Filter", "FFT Spectrum", "Derivative", "Integrate",
                  "Interpolate", "Baseline (polynomial)"]

    def __init__(self, project, parent=None):
        super().__init__(project, "Signal Processing", parent)
        self.operation = QComboBox()
        self.operation.addItems(self.OPERATIONS)
        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        self.window = QSpinBox()
        self.window.setRange(2, 1001)
        self.window.setValue(11)
        self.order = QSpinBox()
        self.order.setRange(1, 9)
        self.order.setValue(3)
        self.cutoff = QDoubleSpinBox()
        self.cutoff.setRange(0.0, 1e9)
        self.cutoff.setValue(1.0)
        self.points = QSpinBox()
        self.points.setRange(2, 100000)
        self.points.setValue(200)
        self.form.addRow("Operation:", self.operation)
        self.form.addRow("X column:", self.x_combo)
        self.form.addRow("Y column:", self.y_combo)
        self.form.addRow("Window / degree:", self.window)
        self.form.addRow("Order:", self.order)
        self.form.addRow("Cutoff:", self.cutoff)
        self.form.addRow("Points:", self.points)
        self._refresh_columns()

    def _refresh_columns(self):
        fill_column_combo(self.x_combo, self.sheet(), types=(ColumnType.X,))
        fill_column_combo(self.y_combo, self.sheet(), types=(ColumnType.Y,))

    def run(self):
        x = self._x_array(self.x_combo.currentData())
        y = self._x_array(self.y_combo.currentData())
        op = self.operation.currentText()
        if op == "Smooth (Savitzky-Golay)":
            return signal.smooth_savgol(x, y, window=self.window.value(), order=self.order.value())
        if op == "Moving Average":
            return signal.smooth_moving_average(x, y, window=self.window.value())
        if op == "Low-pass Filter":
            return signal.butter_filter(x, y, kind="low", cutoff=self.cutoff.value(), order=self.order.value())
        if op == "High-pass Filter":
            return signal.butter_filter(x, y, kind="high", cutoff=self.cutoff.value(), order=self.order.value())
        if op == "FFT Spectrum":
            return signal.fft_spectrum(x, y)
        if op == "Derivative":
            return signal.differentiate(x, y, order=self.order.value())
        if op == "Integrate":
            return signal.integrate_curve(x, y)
        if op == "Interpolate":
            return signal.interpolate(x, y, num=self.points.value())
        return signal.baseline_polynomial(x, y, degree=self.order.value())


class StatisticsDialog(_TwoColumnDialog):
    OPERATIONS = ["Independent t-test", "Paired t-test", "One-sample t-test",
                  "One-way ANOVA", "Correlation (Pearson)", "Correlation (Spearman)",
                  "Correlation matrix", "Histogram"]

    def __init__(self, project, parent=None):
        super().__init__(project, "Statistics", parent)
        self.operation = QComboBox()
        self.operation.addItems(self.OPERATIONS)
        self.a_combo = QComboBox()
        self.b_combo = QComboBox()
        self.popmean = QDoubleSpinBox()
        self.popmean.setRange(-1e12, 1e12)
        self.bins = QSpinBox()
        self.bins.setRange(2, 1000)
        self.bins.setValue(10)
        self.columns = QListWidget()
        self.columns.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.form.addRow("Test:", self.operation)
        self.form.addRow("Column A:", self.a_combo)
        self.form.addRow("Column B:", self.b_combo)
        self.form.addRow("Pop. mean:", self.popmean)
        self.form.addRow("Bins:", self.bins)
        self.form.addRow("Columns (ANOVA / matrix):", self.columns)
        self._refresh_columns()

    def _refresh_columns(self):
        fill_column_combo(self.a_combo, self.sheet(), types=(ColumnType.Y,))
        fill_column_combo(self.b_combo, self.sheet(), types=(ColumnType.Y,))
        self.columns.clear()
        for column in self.sheet().columns:
            if column.col_type == ColumnType.Y:
                item = QListWidgetItem(column.name)
                item.setData(1, column.name)
                self.columns.addItem(item)

    def run(self):
        a = self._x_array(self.a_combo.currentData())
        b = self._x_array(self.b_combo.currentData())
        op = self.operation.currentText()
        if op == "Independent t-test":
            return statistics.ttest_ind(a, b)
        if op == "Paired t-test":
            return statistics.ttest_rel(a, b)
        if op == "One-sample t-test":
            return statistics.ttest_1samp(a, self.popmean.value())
        if op == "One-way ANOVA":
            groups = [self._x_array(i.data(1)) for i in self.columns.selectedItems()]
            return statistics.anova_oneway(groups or [a, b])
        if op == "Correlation (Pearson)":
            return statistics.correlation(a, b, method="pearson")
        if op == "Correlation (Spearman)":
            return statistics.correlation(a, b, method="spearman")
        if op == "Correlation matrix":
            names = [i.data(1) for i in self.columns.selectedItems()] or [c.name for c in self.sheet().columns if c.col_type == ColumnType.Y]
            return statistics.correlation_matrix(names, [self._x_array(n) for n in names])
        return statistics.histogram(a, bins=self.bins.value())
