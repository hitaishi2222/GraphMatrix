"""Graph editor: canvas + plot list + plot/axis properties.

Edits go through Commands (add/remove plot, add layer, property changes) so the
graph is fully part of the undo history.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from graphmatrix.core.commands import (
    AddAnnotationCommand,
    AddLayerCommand,
    AddPlotCommand,
    AddReferenceLineCommand,
    CommandStack,
    RemovePlotCommand,
    RemoveReferenceLineCommand,
    SetAttributesCommand,
)
from graphmatrix.core.model import (
    LINE_STYLES,
    Annotation,
    AxisScale,
    Graph,
    Layer,
    PlotSpec,
    PlotStyle,
    Project,
    ReferenceLine,
)
from graphmatrix.core.plotting import auto_axis_labels, make_plot_for_column, resolve_plot
from graphmatrix.ui import theme
from graphmatrix.ui import plot_themes
from graphmatrix.ui.canvas import create_canvas
from graphmatrix.ui.plot_dialogs import AddPlotDialog, ReferenceLineDialog
from graphmatrix.ui.widgets import COLUMN_MIME

_SYMBOLS = ["o", "s", "^", "v", "d", "+", "x", "*", ""]


class GraphView(QWidget):
    hover_changed = Signal(bool)

    def __init__(self, graph: Graph, project: Project, commands: CommandStack,
                 on_change=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.graph = graph
        self.project = project
        self.commands = commands
        self._on_change = on_change
        self._loading = False
        self.setAcceptDrops(True)

        self.canvas = create_canvas()
        self.canvas.label_click_callback = self._on_label_click
        self.plot_list = QListWidget()
        self.plot_list.currentRowChanged.connect(self._on_plot_selected)
        self.hover_enabled = False

        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.addWidget(self._label("Plots"))
        side.addWidget(self.plot_list)

        buttons = QHBoxLayout()
        for text, slot in (("Add Plot", self.add_plot), ("Remove", self.remove_plot), ("Add Layer", self.add_layer)):
            button = QPushButton(text)
            button.setFlat(True)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        side.addLayout(buttons)

        side.addWidget(self._build_plot_group())
        self.group_axis = self._build_axis_group()
        side.addWidget(self._build_ref_group())
        side.addStretch(1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(self.canvas.widget())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 900])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.refresh()

    # -- construction helpers ------------------------------------------------
    @staticmethod
    def _label(text: str) -> QWidget:
        from PySide6.QtWidgets import QLabel

        label = QLabel(text)
        label.setStyleSheet("font-weight: bold;")
        return label

    def _build_plot_group(self) -> QGroupBox:
        self.group_plot = QGroupBox("Plot Properties")
        form = QFormLayout(self.group_plot)
        self.style_combo = QComboBox()
        for style in PlotStyle:
            self.style_combo.addItem(style.value, style)
        self.linestyle_combo = QComboBox()
        for line_style in LINE_STYLES:
            self.linestyle_combo.addItem(line_style, line_style)
        self.color_button = QPushButton("color")
        self.color_button.clicked.connect(self._pick_color)
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.1, 20.0)
        self.width_spin.setSingleStep(0.5)
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(_SYMBOLS)
        self.symbol_size_spin = QDoubleSpinBox()
        self.symbol_size_spin.setRange(1.0, 40.0)
        self.legend_edit = QLineEdit()
        self.yaxis_combo = QComboBox()
        self.yaxis_combo.addItem("Left", "left")
        self.yaxis_combo.addItem("Right", "right")
        form.addRow("Style:", self.style_combo)
        form.addRow("Line style:", self.linestyle_combo)
        form.addRow("Color:", self.color_button)
        form.addRow("Line width:", self.width_spin)
        form.addRow("Symbol:", self.symbol_combo)
        form.addRow("Symbol size:", self.symbol_size_spin)
        form.addRow("Legend:", self.legend_edit)
        form.addRow("Y axis:", self.yaxis_combo)

        self.style_combo.currentIndexChanged.connect(self._apply_plot_props)
        self.linestyle_combo.currentIndexChanged.connect(self._apply_plot_props)
        self.width_spin.valueChanged.connect(self._apply_plot_props)
        self.symbol_combo.currentIndexChanged.connect(self._apply_plot_props)
        self.symbol_size_spin.valueChanged.connect(self._apply_plot_props)
        self.legend_edit.editingFinished.connect(self._apply_plot_props)
        self.yaxis_combo.currentIndexChanged.connect(self._apply_plot_props)
        self._color = ""
        return self.group_plot

    def _build_axis_group(self) -> QTabWidget:
        self.group_axis = QTabWidget()
        scales_tab = QWidget()
        form = QFormLayout(scales_tab)
        labels_tab = QWidget()
        lform = QFormLayout(labels_tab)
        ticks_tab = QWidget()
        tform = QFormLayout(ticks_tab)
        self.xscale_combo = QComboBox()
        self.yscale_combo = QComboBox()
        for scale in AxisScale:
            self.xscale_combo.addItem(scale.value, scale)
            self.yscale_combo.addItem(scale.value, scale)
        self.title_edit = QLineEdit()
        self.xlabel_edit = QLineEdit()
        self.ylabel_edit = QLineEdit()
        self.y2label_edit = QLineEdit()
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(QFontDatabase.families())
        self.label_font_size_spin = QDoubleSpinBox()
        self.label_font_size_spin.setRange(6.0, 48.0)
        self.label_font_size_spin.setValue(12.0)
        self.title_font_size_spin = QDoubleSpinBox()
        self.title_font_size_spin.setRange(6.0, 48.0)
        self.title_font_size_spin.setValue(14.0)
        self.label_color_button = QPushButton("label color")
        self.title_color_button = QPushButton("title color")
        self.layout_rows_spin = QSpinBox()
        self.layout_rows_spin.setRange(1, 6)
        self.layout_cols_spin = QSpinBox()
        self.layout_cols_spin.setRange(1, 6)
        self.xmin_edit = QLineEdit()
        self.xmax_edit = QLineEdit()
        self.ymin_edit = QLineEdit()
        self.ymax_edit = QLineEdit()
        self.legend_check = QComboBox()
        self.legend_check.addItem("Show", True)
        self.legend_check.addItem("Hide", False)
        self.minor_ticks_check = QComboBox()
        self.minor_ticks_check.addItem("On", True)
        self.minor_ticks_check.addItem("Off", False)
        self.tick_direction_combo = QComboBox()
        self.tick_direction_combo.addItems(["out", "in", "inout"])
        self.plot_theme_combo = QComboBox()
        self.plot_theme_combo.addItem("Follow app theme", "")
        for pt in plot_themes.PLOT_THEMES.values():
            self.plot_theme_combo.addItem(pt.label, pt.id)
        form.addRow("X scale:", self.xscale_combo)
        form.addRow("Y scale:", self.yscale_combo)
        form.addRow("X min:", self.xmin_edit)
        form.addRow("X max:", self.xmax_edit)
        form.addRow("Y min:", self.ymin_edit)
        form.addRow("Y max:", self.ymax_edit)
        form.addRow("Legend:", self.legend_check)
        form.addRow("Plot theme:", self.plot_theme_combo)
        form.addRow("Layout rows:", self.layout_rows_spin)
        form.addRow("Layout cols:", self.layout_cols_spin)

        lform.addRow("Title:", self.title_edit)
        lform.addRow("X label:", self.xlabel_edit)
        lform.addRow("Y label:", self.ylabel_edit)
        lform.addRow("Y2 label:", self.y2label_edit)
        lform.addRow("Font family:", self.font_family_combo)
        lform.addRow("Label size:", self.label_font_size_spin)
        lform.addRow("Title size:", self.title_font_size_spin)
        lform.addRow("Label color:", self.label_color_button)
        lform.addRow("Title color:", self.title_color_button)

        tform.addRow("Minor ticks:", self.minor_ticks_check)
        tform.addRow("Tick direction:", self.tick_direction_combo)

        self.group_axis.addTab(scales_tab, "Scales/Range")
        self.group_axis.addTab(labels_tab, "Labels/Fonts")
        self.group_axis.addTab(ticks_tab, "Ticks")

        for widget in (self.xscale_combo, self.yscale_combo, self.legend_check, self.minor_ticks_check, self.tick_direction_combo):
            widget.currentIndexChanged.connect(self._apply_axis_props)
        self.plot_theme_combo.currentIndexChanged.connect(self._apply_plot_theme)
        for widget in (self.title_edit, self.xlabel_edit, self.ylabel_edit, self.y2label_edit, self.xmin_edit, self.xmax_edit, self.ymin_edit, self.ymax_edit):
            widget.editingFinished.connect(self._apply_axis_props)
        self.font_family_combo.currentIndexChanged.connect(self._apply_axis_props)
        self.label_font_size_spin.valueChanged.connect(self._apply_axis_props)
        self.title_font_size_spin.valueChanged.connect(self._apply_axis_props)
        self.label_color_button.clicked.connect(self._pick_label_color)
        self.title_color_button.clicked.connect(self._pick_title_color)
        self.layout_rows_spin.valueChanged.connect(self._apply_axis_props)
        self.layout_cols_spin.valueChanged.connect(self._apply_axis_props)
        return self.group_axis

    def _build_ref_group(self) -> QGroupBox:
        self.group_ref = QGroupBox("Reference Lines")
        layout = QVBoxLayout(self.group_ref)
        self.ref_list = QListWidget()
        self.ref_list.currentRowChanged.connect(lambda _row: self._update_ref_buttons())
        layout.addWidget(self.ref_list)

        buttons = QHBoxLayout()
        self.add_h_button = QPushButton("Add H-line")
        self.add_h_button.setToolTip("Horizontal guide at y = value")
        self.add_h_button.clicked.connect(lambda: self.add_reference_line("h"))
        self.add_v_button = QPushButton("Add V-line")
        self.add_v_button.setToolTip("Vertical guide at x = value")
        self.add_v_button.clicked.connect(lambda: self.add_reference_line("v"))
        self.remove_ref_button = QPushButton("Remove")
        self.remove_ref_button.clicked.connect(self.remove_reference_line)
        for button in (self.add_h_button, self.add_v_button, self.remove_ref_button):
            button.setFlat(True)
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.hover_check = QPushButton("Data readout: off")
        self.hover_check.setCheckable(True)
        self.hover_check.setToolTip("Show a crosshair and the nearest data point under the mouse")
        self.hover_check.toggled.connect(self.set_hover)
        layout.addWidget(self.hover_check)
        return self.group_ref

    def _update_ref_buttons(self) -> None:
        self.remove_ref_button.setEnabled(self._selected_ref_line() is not None)

    # -- state ---------------------------------------------------------------
    def _selected_spec(self) -> PlotSpec | None:
        item = self.plot_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _layer_for_spec(self, spec: PlotSpec) -> Layer:
        for layer in self.graph.layers:
            if spec in layer.plots:
                return layer
        return self.graph.first_layer

    def _active_layer(self) -> Layer:
        spec = self._selected_spec()
        return self._layer_for_spec(spec) if spec is not None else self.graph.first_layer

    # -- actions -------------------------------------------------------------
    def add_plot(self) -> None:
        if not self.project.workbooks:
            return
        dialog = AddPlotDialog(self.project, self)
        if dialog.exec() and dialog.x_combo.currentData() and dialog.y_combo.currentData():
            spec = dialog.spec()
            self.commands.push(AddPlotCommand(self.graph, self.graph.first_layer, spec))
            self.refresh(select=spec)

    def remove_plot(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            return
        self.commands.push(RemovePlotCommand(self.graph, self._layer_for_spec(spec), spec))
        self.refresh()

    def add_layer(self) -> None:
        layer = Layer(f"Layer {self.graph.num_layers + 1}")
        self.commands.push(AddLayerCommand(self.graph, layer))
        self.refresh()

    def add_annotation(self) -> None:
        text, ok = QInputDialog.getText(self, "Add Annotation", "Text:")
        if not ok or not text:
            return
        self.commands.push(AddAnnotationCommand(self.graph, Annotation(text=text)))
        self.refresh()

    # -- reference lines -----------------------------------------------------
    def _selected_ref_line(self) -> ReferenceLine | None:
        item = self.ref_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _layer_for_ref_line(self, line: ReferenceLine) -> Layer:
        for layer in self.graph.layers:
            if line in layer.ref_lines:
                return layer
        return self.graph.first_layer

    def add_reference_line(self, orientation: str = "h", line: ReferenceLine | None = None) -> None:
        if line is None:
            dialog = ReferenceLineDialog(self, orientation=orientation)
            if not dialog.exec():
                return
            line = dialog.reference_line()
        self.commands.push(AddReferenceLineCommand(self._active_layer(), line))
        self.refresh()

    def remove_reference_line(self) -> None:
        line = self._selected_ref_line()
        if line is None:
            return
        self.commands.push(RemoveReferenceLineCommand(self._layer_for_ref_line(line), line))
        self.refresh()

    def set_hover(self, enabled: bool) -> None:
        self.hover_enabled = bool(enabled)
        if self.hover_check.isChecked() != self.hover_enabled:
            self.hover_check.blockSignals(True)
            self.hover_check.setChecked(self.hover_enabled)
            self.hover_check.blockSignals(False)
        self.hover_check.setText(f"Data readout: {'on' if self.hover_enabled else 'off'}")
        self.canvas.set_hover(self.hover_enabled)
        self.hover_changed.emit(self.hover_enabled)

    def add_column_plot(self, source: str, column_name: str) -> None:
        """Plot a single column (used by drag-and-drop from the Project Explorer)."""
        spec = make_plot_for_column(self.project, source, column_name)
        if spec is None:
            return
        self.commands.push(AddPlotCommand(self.graph, self._active_layer(), spec))
        self.refresh(select=spec)

    # -- drag & drop (column -> layer) ---------------------------------------
    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.mimeData().hasFormat(COLUMN_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.mimeData().hasFormat(COLUMN_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not event.mimeData().hasFormat(COLUMN_MIME):
            return
        payload = json.loads(bytes(event.mimeData().data(COLUMN_MIME)).decode("utf-8"))
        self.add_column_plot(payload.get("source", ""), payload.get("column", ""))
        event.acceptProposedAction()

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color or "#1f77b4"), self, "Plot Color")
        if color.isValid():
            self._color = color.name()
            self._update_color_button()
            self._apply_plot_props()

    def _pick_label_color(self) -> None:
        color = QColorDialog.getColor(QColor(getattr(self, "_label_color", "") or "#000000"), self, "Label Color")
        if color.isValid():
            self._label_color = color.name()
            self._apply_axis_props()

    def _pick_title_color(self) -> None:
        color = QColorDialog.getColor(QColor(getattr(self, "_title_color", "") or "#000000"), self, "Title Color")
        if color.isValid():
            self._title_color = color.name()
            self._apply_axis_props()

    def _update_color_button(self) -> None:
        self.color_button.setStyleSheet(f"background-color: {self._color or '#ffffff'}")

    # -- apply edits ---------------------------------------------------------
    def _apply_plot_props(self) -> None:
        if self._loading:
            return
        spec = self._selected_spec()
        if spec is None:
            return
        self.commands.push(SetAttributesCommand(
            spec, "Edit Plot",
            style=self.style_combo.currentData(),
            line_style=self.linestyle_combo.currentData(),
            color=self._color,
            line_width=self.width_spin.value(),
            symbol=self.symbol_combo.currentText(),
            symbol_size=self.symbol_size_spin.value(),
            legend=self.legend_edit.text().strip(),
            y_axis=self.yaxis_combo.currentData(),
        ))
        self._refresh_list_labels()
        self.render()
        self._changed()

    def _apply_axis_props(self) -> None:
        if self._loading:
            return
        layer = self._active_layer()
        self.commands.push(SetAttributesCommand(
            layer, "Edit Axes",
            x_scale=self.xscale_combo.currentData(),
            y_scale=self.yscale_combo.currentData(),
            x_label=self.xlabel_edit.text(),
            y_label=self.ylabel_edit.text(),
            y2_label=self.y2label_edit.text(),
            x_min=_float_or_none(self.xmin_edit.text()),
            x_max=_float_or_none(self.xmax_edit.text()),
            y_min=_float_or_none(self.ymin_edit.text()),
            y_max=_float_or_none(self.ymax_edit.text()),
            show_legend=self.legend_check.currentData(),
            minor_ticks=self.minor_ticks_check.currentData(),
            tick_direction=self.tick_direction_combo.currentText(),
            label_font_family=self.font_family_combo.currentText(),
            label_font_size=float(self.label_font_size_spin.value()),
            label_color=getattr(self, "_label_color", ""),
        ))
        self.commands.push(SetAttributesCommand(
            self.graph, "Edit Title/Fonts",
            title=self.title_edit.text(),
            title_font_family=self.font_family_combo.currentText(),
            title_font_size=float(self.title_font_size_spin.value()),
            title_color=getattr(self, "_title_color", ""),
            layout_rows=int(self.layout_rows_spin.value()),
            layout_cols=int(self.layout_cols_spin.value()),
        ))
        self.canvas.set_grid(int(self.layout_rows_spin.value()), int(self.layout_cols_spin.value()))
        self.render()
        self._changed()

    def _apply_plot_theme(self) -> None:
        if self._loading:
            return
        self.commands.push(SetAttributesCommand(
            self.graph, "Plot theme",
            plot_theme=self.plot_theme_combo.currentData() or "",
        ))
        self.render()
        self._changed()

    def _changed(self) -> None:
        if self._on_change:
            self._on_change()

    def _on_label_click(self, name: str) -> None:
        self.group_axis.setVisible(True)
        if name == "title":
            self.title_edit.setFocus()
        elif name == "axes":
            self.xmin_edit.setFocus()
        else:
            self.xlabel_edit.setFocus()

    # -- rendering -----------------------------------------------------------
    def refresh(self, select: PlotSpec | None = None) -> None:
        self._refresh_list(select)
        self.render()

    def on_theme_changed(self) -> None:
        """Re-apply the canvas colours after the app theme switched."""
        self.canvas.set_theme(theme.current_preset())
        self.refresh()

    def _refresh_list(self, select: PlotSpec | None) -> None:
        if select is None:
            select = self._selected_spec()
        self.plot_list.blockSignals(True)
        self.plot_list.clear()
        target_row = 0
        for layer in self.graph.layers:
            for spec in layer.plots:
                item = QListWidgetItem(f"{layer.name} · {spec.y} vs {spec.x}")
                item.setData(Qt.ItemDataRole.UserRole, spec)
                self.plot_list.addItem(item)
                if spec is select:
                    target_row = self.plot_list.count() - 1
        self.plot_list.blockSignals(False)
        if self.plot_list.count():
            self.plot_list.setCurrentRow(target_row)
            self._on_plot_selected(target_row)
        else:
            self._clear_forms()
        self._refresh_ref_list()

    def _refresh_ref_list(self, select: ReferenceLine | None = None) -> None:
        if select is None:
            select = self._selected_ref_line()
        self.ref_list.blockSignals(True)
        self.ref_list.clear()
        target_row = -1
        for layer in self.graph.layers:
            for line in layer.ref_lines:
                axis = "y" if line.orientation == "h" else "x"
                label = f"{layer.name} · {axis} = {line.position:g}"
                if line.label:
                    label += f"  ({line.label})"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, line)
                self.ref_list.addItem(item)
                if line is select:
                    target_row = self.ref_list.count() - 1
        self.ref_list.blockSignals(False)
        if target_row >= 0:
            self.ref_list.setCurrentRow(target_row)
        self._update_ref_buttons()

    def _refresh_list_labels(self) -> None:
        for row in range(self.plot_list.count()):
            item = self.plot_list.item(row)
            spec = item.data(Qt.ItemDataRole.UserRole)
            layer = self._layer_for_spec(spec)
            item.setText(f"{layer.name} · {spec.legend or spec.y} vs {spec.x}")

    def _on_plot_selected(self, row: int) -> None:
        spec = self._selected_spec()
        self._loading = True
        try:
            if spec is not None:
                self.style_combo.setCurrentText(PlotStyle(spec.style).value)
                self.linestyle_combo.setCurrentText(spec.line_style)
                self.width_spin.setValue(spec.line_width)
                self.symbol_combo.setCurrentText(spec.symbol)
                self.symbol_size_spin.setValue(spec.symbol_size)
                self.legend_edit.setText(spec.legend)
                self.yaxis_combo.setCurrentText(spec.y_axis)
                self._color = spec.color
            self._load_axis_fields(self._active_layer())
        finally:
            self._loading = False
        self._update_color_button()

    def _load_axis_fields(self, layer: Layer) -> None:
        self.xscale_combo.setCurrentText(AxisScale(layer.x_scale).value)
        self.yscale_combo.setCurrentText(AxisScale(layer.y_scale).value)
        self.title_edit.setText(self.graph.title)
        self.xlabel_edit.setText(layer.x_label)
        self.ylabel_edit.setText(layer.y_label)
        self.y2label_edit.setText(layer.y2_label)
        self.font_family_combo.setCurrentText(layer.label_font_family or self.font_family_combo.itemText(0))
        self.label_font_size_spin.setValue(layer.label_font_size)
        self.title_font_size_spin.setValue(self.graph.title_font_size)
        self._label_color = layer.label_color
        self._title_color = self.graph.title_color
        self.layout_rows_spin.blockSignals(True)
        self.layout_rows_spin.setValue(getattr(self.graph, "layout_rows", 1))
        self.layout_rows_spin.blockSignals(False)
        self.layout_cols_spin.blockSignals(True)
        self.layout_cols_spin.setValue(getattr(self.graph, "layout_cols", 1))
        self.layout_cols_spin.blockSignals(False)
        self.xmin_edit.setText("" if layer.x_min is None else str(layer.x_min))
        self.xmax_edit.setText("" if layer.x_max is None else str(layer.x_max))
        self.ymin_edit.setText("" if layer.y_min is None else str(layer.y_min))
        self.ymax_edit.setText("" if layer.y_max is None else str(layer.y_max))
        self.legend_check.setCurrentIndex(0 if layer.show_legend else 1)
        self.minor_ticks_check.setCurrentIndex(0 if getattr(layer, "minor_ticks", True) else 1)
        idx = self.tick_direction_combo.findText(getattr(layer, "tick_direction", "out"))
        if idx >= 0:
            self.tick_direction_combo.setCurrentIndex(idx)
        # plot theme lives on the graph, not the layer
        theme_idx = self.plot_theme_combo.findData(getattr(self.graph, "plot_theme", ""))
        if theme_idx >= 0:
            self.plot_theme_combo.blockSignals(True)
            self.plot_theme_combo.setCurrentIndex(theme_idx)
            self.plot_theme_combo.blockSignals(False)

    def _clear_forms(self) -> None:
        self._loading = True
        self.legend_edit.clear()
        self._loading = False

    def render(self) -> None:
        self.canvas.set_grid(getattr(self.graph, "layout_rows", 1), getattr(self.graph, "layout_cols", 1))
        self.canvas.set_theme(self.graph.plot_theme or theme.current_preset())
        layer = self._active_layer()
        self.canvas.set_scales(x=AxisScale(layer.x_scale).value, y=AxisScale(layer.y_scale).value)
        self.canvas.show_legend(layer.show_legend)

        for panel_index, each in enumerate(self.graph.layers):
            self.canvas.set_current_panel(panel_index)
            for spec in each.plots:
                data = resolve_plot(self.project, spec)
                if data is None:
                    continue
                self.canvas.plot(
                    data.x, data.y,
                    style=PlotStyle(spec.style).value, color=spec.color,
                    width=spec.line_width, symbol=spec.symbol,
                    symbol_size=spec.symbol_size, name=data.legend,
                    yerr=data.yerr, xerr=data.xerr,
                    y_axis=spec.y_axis, line_style=spec.line_style,
                )

        for each in self.graph.layers:
            for ref in each.ref_lines:
                color = ref.color
                if theme.is_dark() and color.strip().lower() in ("", "#888888", "gray", "grey"):
                    color = theme.canvas_colors()[1]
                self.canvas.add_reference_line(
                    ref.orientation, ref.position, color=color, width=ref.width,
                    line_style=ref.line_style, label=ref.label,
                )

        self.canvas.set_current_panel(0)
        x_label, y_label = auto_axis_labels(self.project, layer)
        self.canvas.set_labels(bottom=x_label or None, left=y_label or None,
                               right=layer.y2_label or None,
                               fontfamily=layer.label_font_family,
                               fontsize=layer.label_font_size,
                               color=layer.label_color)
        self.canvas.set_limits(x=(layer.x_min, layer.x_max), y=(layer.y_min, layer.y_max))
        self.canvas.set_ticks(minor=getattr(layer, "minor_ticks", True),
                             direction=getattr(layer, "tick_direction", "out"))
        if self.graph.title:
            self.canvas.set_title(self.graph.title, fontfamily=self.graph.title_font_family,
                                 fontsize=self.graph.title_font_size, color=self.graph.title_color)
        self.canvas.set_hover(self.hover_enabled)

        for annotation in self.graph.annotations:
            color = annotation.color
            if theme.is_dark() and color.strip().lower() in ("", "#000000", "black"):
                color = theme.canvas_colors()[1]
            self.canvas.add_annotation(annotation.text, annotation.x, annotation.y,
                                       color=color, size=annotation.size)


def _float_or_none(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
