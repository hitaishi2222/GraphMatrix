"""Graph editor: canvas + plot list + plot/axis properties.

Edits go through Commands (add/remove plot, add layer, property changes) so the
graph is fully part of the undo history.
"""

from __future__ import annotations

import json

import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from graphmatrix.core.commands import (
    AddAnnotationCommand,
    AddLayerCommand,
    AddPlotCommand,
    AddReferenceLineCommand,
    CommandStack,
    MacroCommand,
    RemovePlotCommand,
    RemoveReferenceLineCommand,
    SetAttributesCommand,
    SetGraphTypeCommand,
)
from graphmatrix.core.model import (
    LINE_STYLES,
    GRAPH_TYPES,
    GRAPH_TYPE_LABELS,
    Annotation,
    AxisScale,
    Graph,
    GraphType,
    Layer,
    PlotSpec,
    PlotStyle,
    Project,
    ReferenceLine,
    Z_STYLES,
    is_3d_style,
)
from graphmatrix.core.plotting import (
    auto_axis_labels,
    make_plot_for_column,
    resolve_plot,
)
from graphmatrix.core.plot_themes import series_color
from graphmatrix.ui import theme
from graphmatrix.ui import plot_themes
from graphmatrix.ui.canvas import create_canvas
from graphmatrix.ui.icons import ui_icon
from graphmatrix.ui.plot_dialogs import AddPlotDialog, ReferenceLineDialog
from graphmatrix.ui.widgets import COLUMN_MIME, color_button_style, fill_column_combo

_SYMBOLS = ["o", "s", "^", "v", "d", "+", "x", "*", ""]


class GraphView(QWidget):
    hover_changed = Signal(bool)
    #: (source, rows) emitted when a plotted point is clicked
    brush_requested = Signal(str, list)

    def __init__(
        self,
        graph: Graph,
        project: Project,
        commands: CommandStack,
        on_change=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.graph = graph
        self.project = project
        self.commands = commands
        self._on_change = on_change
        self._loading = False
        self.setAcceptDrops(True)

        self.canvas = create_canvas(self._preferred_backend())
        self.canvas.label_click_callback = self._on_label_click
        self.canvas.point_picked = self._on_canvas_point_picked
        # The canvas tells the sidebar when its readout is switched on or off
        # (the button on the canvas can do it too).
        try:
            self.canvas.hover_state_changed = self._on_canvas_hover_changed
        except Exception:  # noqa: BLE001 - backends without the hook
            pass
        self._series_sources: list[str] = []  # per canvas series, for brushing
        self._series_specs: list[PlotSpec] = []  # the spec behind every series
        self.plot_list = QListWidget()
        self.plot_list.currentRowChanged.connect(self._on_plot_selected)
        # The readout is on by default: the value under the pointer is the
        # most wanted piece of information while looking at a plot.
        self.hover_enabled = True

        # Side panel lives in the main window's Properties dock (swapped per
        # graph view), not inside this tab: the tab shows only the canvas.
        self.plot_panel = self._build_plot_panel()
        self.group_axis = self._build_axis_group()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas.widget())

        self.refresh()

    # -- construction helpers ------------------------------------------------
    def _build_plot_panel(self) -> QWidget:
        """Plots list + plot properties + reference lines (hosted by the dock)."""
        self._plot_group = QGroupBox("Plots")
        plot_layout = QVBoxLayout(self._plot_group)
        plot_layout.addWidget(self.plot_list)
        buttons = QHBoxLayout()
        for text, slot in (
            ("Add Plot", self.add_plot),
            ("Remove", self.remove_plot),
            ("Add Layer", self.add_layer),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        plot_layout.addLayout(buttons)

        panel = QWidget()
        side = QVBoxLayout(panel)
        side.setContentsMargins(4, 4, 4, 4)
        side.setSpacing(6)
        # The readout switch belongs to the figure, not to the reference
        # lines, so it sits on top of the panel. It is a small toggle, not a
        # banner: a full-width blue button reads as "press me", while this is
        # a switch that is simply on.
        self.hover_check = QToolButton()
        self.hover_check.setObjectName("readoutToggle")
        self.hover_check.setText("Readout")
        self.hover_check.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.hover_check.setIcon(ui_icon("crosshair"))
        self.hover_check.setCheckable(True)
        self.hover_check.setToolTip(
            "Show the nearest data point under the mouse "
            "(the values appear in the corner of the figure)"
        )
        self.hover_check.toggled.connect(self.set_hover)
        readout_row = QHBoxLayout()
        readout_row.setContentsMargins(0, 0, 0, 0)
        readout_row.addWidget(self.hover_check)
        readout_row.addStretch(1)
        side.addLayout(readout_row)
        side.addWidget(self._plot_group)
        side.addWidget(self._build_plot_group())
        side.addWidget(self._build_ref_group())
        side.addStretch(1)
        return panel

    def _build_plot_group(self) -> QGroupBox:
        self.group_plot = QGroupBox("Plot Properties")
        form = QFormLayout(self.group_plot)
        self.style_combo = QComboBox()
        for style in PlotStyle:
            self.style_combo.addItem(style.value, style)
        self.linestyle_combo = QComboBox()
        for line_style in LINE_STYLES:
            self.linestyle_combo.addItem(line_style, line_style)
        self.color_button = QPushButton("automatic")
        self.color_button.setToolTip("Colour of this series")
        self.color_button.clicked.connect(self._pick_color)
        self.z_combo = QComboBox()
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
        form.addRow("Colour / Z column:", self.z_combo)
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
        self.zlabel_edit = QLineEdit()
        self.zlabel_edit.setPlaceholderText("colourbar / 3D Z axis")
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
        self.yaxis_visible_check = QComboBox()
        self.yaxis_visible_check.addItem("Show", True)
        self.yaxis_visible_check.addItem("Hide", False)
        self.yaxis_visible_check.setToolTip(
            "Hide the Y axis (line, ticks, labels) for a clean stacked panel."
        )
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

        # -- Layout tab: graph type + type-specific panel spacing ------------
        layout_tab = QWidget()
        plform = QFormLayout(layout_tab)
        self.graphtype_combo = QComboBox()
        self.graphtype_combo.setToolTip(
            "Figure template: simple, vertical stack, double-Y, side-by-side, or grid."
        )
        for gtype in GRAPH_TYPES:
            self.graphtype_combo.addItem(GRAPH_TYPE_LABELS[gtype.value], gtype.value)
        self.panel_gapx_spin = QDoubleSpinBox()
        self.panel_gapx_spin.setRange(0.0, 100.0)
        self.panel_gapx_spin.setSingleStep(1.0)
        self.panel_gapx_spin.setSuffix(" %")
        self.panel_gapx_spin.setToolTip(
            "Horizontal space between panels, as a percentage of a panel's width."
        )
        self.panel_gapy_spin = QDoubleSpinBox()
        self.panel_gapy_spin.setRange(0.0, 100.0)
        self.panel_gapy_spin.setSingleStep(1.0)
        self.panel_gapy_spin.setSuffix(" %")
        self.panel_gapy_spin.setToolTip(
            "Vertical space between panels, as a percentage of a panel's height."
        )
        self.ydelta_spin = QDoubleSpinBox()
        self.ydelta_spin.setRange(-1e6, 1e6)
        self.ydelta_spin.setDecimals(3)
        self.ydelta_spin.setSingleStep(0.1)
        self.ydelta_spin.setToolTip(
            "Vertical offset added to each successive stacked/twin panel's data "
            "(a waterfall-style stack)."
        )
        self.graphtype_hint = QLabel("")
        self.graphtype_hint.setWordWrap(True)
        self.graphtype_hint.setStyleSheet("color: palette(mid);")
        plform.addRow("Graph type:", self.graphtype_combo)
        plform.addRow("Grid columns:", self.layout_cols_spin)
        plform.addRow("Grid rows:", self.layout_rows_spin)
        plform.addRow("Panel gap X:", self.panel_gapx_spin)
        plform.addRow("Panel gap Y:", self.panel_gapy_spin)
        plform.addRow("Y delta:", self.ydelta_spin)
        plform.addRow(self.graphtype_hint)

        self.group_axis.addTab(scales_tab, "Scales/Range")
        self.group_axis.addTab(labels_tab, "Labels/Fonts")
        self.group_axis.addTab(ticks_tab, "Ticks")
        self.group_axis.addTab(layout_tab, "Layout")

        lform.addRow("Title:", self.title_edit)
        lform.addRow("X label:", self.xlabel_edit)
        lform.addRow("Y label:", self.ylabel_edit)
        lform.addRow("Y2 label:", self.y2label_edit)
        lform.addRow("Z label:", self.zlabel_edit)
        lform.addRow("Font family:", self.font_family_combo)
        lform.addRow("Label size:", self.label_font_size_spin)
        lform.addRow("Title size:", self.title_font_size_spin)
        lform.addRow("Label color:", self.label_color_button)
        lform.addRow("Title color:", self.title_color_button)

        tform.addRow("Minor ticks:", self.minor_ticks_check)
        tform.addRow("Tick direction:", self.tick_direction_combo)
        tform.addRow("Y axis:", self.yaxis_visible_check)

        for widget in (
            self.xscale_combo,
            self.yscale_combo,
            self.legend_check,
            self.minor_ticks_check,
            self.tick_direction_combo,
            self.yaxis_visible_check,
        ):
            widget.currentIndexChanged.connect(self._apply_axis_props)
        self.graphtype_combo.currentIndexChanged.connect(self._apply_graph_type)
        for gap_widget in (
            self.panel_gapx_spin,
            self.panel_gapy_spin,
            self.ydelta_spin,
        ):
            gap_widget.valueChanged.connect(self._apply_axis_props)
        self.plot_theme_combo.currentIndexChanged.connect(self._apply_plot_theme)
        for widget in (
            self.title_edit,
            self.xlabel_edit,
            self.ylabel_edit,
            self.y2label_edit,
            self.zlabel_edit,
            self.xmin_edit,
            self.xmax_edit,
            self.ymin_edit,
            self.ymax_edit,
        ):
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
            buttons.addWidget(button)
        layout.addLayout(buttons)
        return self.group_ref

    def _update_ref_buttons(self) -> None:
        self.remove_ref_button.setEnabled(self._selected_ref_line() is not None)

    # -- state ---------------------------------------------------------------
    def _selected_spec(self) -> PlotSpec | None:
        item = self.plot_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _active_panel_index(self) -> int:
        """The index of the panel the user is working on.

        It is the panel that holds the series selected in the plot list, so
        the sidebar, the canvas marker and the tools always talk about the
        same panel.
        """
        spec = self._selected_spec()
        layer = self._layer_for_spec(spec) if spec is not None else self.graph.first_layer
        try:
            return self.graph.layers.index(layer)
        except ValueError:
            return 0

    def _mark_active_panel(self) -> None:
        """Tell the canvas which panel the user is working on.

        In a grid or a stack the canvas highlights that panel and names it
        ("Panel 2 / 4"), so the sidebar and the figure never disagree. The
        canvas also *follows* the selection: the zoom, the fit and the axis
        settings then work on the panel that is being edited, not on the
        first one.
        """
        index = self._active_panel_index()
        self.canvas.set_active_panel(index, len(self.graph.layers))
        self.canvas.set_current_panel(index)

    def _layer_for_spec(self, spec: PlotSpec) -> Layer:
        for layer in self.graph.layers:
            if spec in layer.plots:
                return layer
        return self.graph.first_layer

    def _active_layer(self) -> Layer:
        spec = self._selected_spec()
        return (
            self._layer_for_spec(spec) if spec is not None else self.graph.first_layer
        )

    # -- actions -------------------------------------------------------------
    def add_plot(self) -> None:
        if not self.project.workbooks:
            return
        dialog = AddPlotDialog(self.project, self)
        if (
            dialog.exec()
            and dialog.x_combo.currentData()
            and dialog.y_combo.currentData()
        ):
            spec = dialog.spec()
            self.commands.push(AddPlotCommand(self.graph, self.graph.first_layer, spec))
            self.refresh(select=spec)

    def remove_plot(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            return
        self.commands.push(
            RemovePlotCommand(self.graph, self._layer_for_spec(spec), spec)
        )
        self.refresh()

    def add_layer(self) -> None:
        layer = Layer(f"Layer {self.graph.num_layers + 1}")
        self.commands.push(AddLayerCommand(self.graph, layer))
        self.refresh()

    def set_graph_type(self, graph_type: str) -> None:
        """Apply a graph layout template (undoable) and refresh the tab."""
        if graph_type == getattr(self.graph, "graph_type", ""):
            return
        self.commands.push(SetGraphTypeCommand(self.graph, graph_type))
        self.refresh()
        self._changed()

    def _apply_graph_type(self) -> None:
        if self._loading:
            return
        graph_type = self.graphtype_combo.currentData()
        if not graph_type or graph_type == getattr(self.graph, "graph_type", ""):
            self._sync_type_fields()
            return
        self.commands.push(SetGraphTypeCommand(self.graph, graph_type))
        self.refresh()
        self._changed()

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

    def add_reference_line(
        self, orientation: str = "h", line: ReferenceLine | None = None
    ) -> None:
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
        self.commands.push(
            RemoveReferenceLineCommand(self._layer_for_ref_line(line), line)
        )
        self.refresh()

    def set_hover(self, enabled: bool) -> None:
        self.hover_enabled = bool(enabled)
        if self.hover_check.isChecked() != self.hover_enabled:
            self.hover_check.blockSignals(True)
            self.hover_check.setChecked(self.hover_enabled)
            self.hover_check.blockSignals(False)
        self.hover_check.setText("Readout")
        self.hover_check.setToolTip(
            "Show the nearest data point under the mouse "
            "(the values appear in the corner of the figure)"
            if self.hover_enabled
            else "The data readout is off. Click to switch it on."
        )
        self.canvas.set_hover(self.hover_enabled)
        self.hover_changed.emit(self.hover_enabled)

    def _on_canvas_hover_changed(self, enabled: bool) -> None:
        """The canvas switched its readout on or off: follow it."""
        if bool(enabled) != bool(self.hover_enabled):
            self.set_hover(bool(enabled))

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
        color = QColorDialog.getColor(
            QColor(self._color or "#1f77b4"), self, "Plot Color"
        )
        if color.isValid():
            self._color = color.name()
            self._update_color_button()
            self._apply_plot_props()

    def _pick_label_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(getattr(self, "_label_color", "") or "#000000"), self, "Label Color"
        )
        if color.isValid():
            self._label_color = color.name()
            self._apply_axis_props()

    def _pick_title_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(getattr(self, "_title_color", "") or "#000000"), self, "Title Color"
        )
        if color.isValid():
            self._title_color = color.name()
            self._apply_axis_props()

    def _update_color_button(self) -> None:
        """Show the series colour as a swatch with a readable label."""
        if self._color:
            self.color_button.setText(self._color)
            self.color_button.setStyleSheet(color_button_style(self._color, self._color))
        else:
            # No explicit colour: the palette colour is used, so the button
            # keeps the theme's own look instead of a white slab.
            self.color_button.setText("automatic")
            self.color_button.setStyleSheet(
                "background: palette(window); color: palette(windowText);"
                " border: 1px solid palette(mid); border-radius: 6px; padding: 4px 10px;"
            )

    # -- apply edits ---------------------------------------------------------
    def _populate_z_combo(self, spec: PlotSpec | None) -> None:
        """Fill the Colour/Z column combo from the spec's source sheet."""
        sheet = self.project.sheet(spec.source) if spec is not None else None
        self.z_combo.blockSignals(True)
        fill_column_combo(self.z_combo, sheet, types=None, include_none=True)
        if spec is not None and spec.z:
            index = self.z_combo.findData(spec.z)
            self.z_combo.setCurrentIndex(index if index >= 0 else 0)
        else:
            self.z_combo.setCurrentIndex(0)
        self.z_combo.blockSignals(False)

    def _apply_plot_props(self) -> None:
        if self._loading:
            return
        spec = self._selected_spec()
        if spec is None:
            return
        self.commands.push(
            SetAttributesCommand(
                spec,
                "Edit Plot",
                style=self.style_combo.currentData(),
                line_style=self.linestyle_combo.currentData(),
                color=self._color,
                z=(
                    self.z_combo.currentData() or ""
                    if self.z_combo.count()
                    else getattr(spec, "z", "")
                ),
                line_width=self.width_spin.value(),
                symbol=self.symbol_combo.currentText(),
                symbol_size=self.symbol_size_spin.value(),
                legend=self.legend_edit.text().strip(),
                y_axis=self.yaxis_combo.currentData(),
            )
        )
        self._refresh_list_labels()
        self.render()
        self._changed()

    def _apply_axis_props(self) -> None:
        if self._loading:
            return
        layer = self._active_layer()
        # One undoable step for an axis/property edit (layer + figure fields).
        self.commands.push(
            MacroCommand(
                [
                    SetAttributesCommand(
                        layer,
                        "Edit Axes",
                        x_scale=AxisScale(self.xscale_combo.currentData()),
                        y_scale=AxisScale(self.yscale_combo.currentData()),
                        x_label=self.xlabel_edit.text(),
                        y_label=self.ylabel_edit.text(),
                        y2_label=self.y2label_edit.text(),
                        z_label=self.zlabel_edit.text(),
                        x_min=_float_or_none(self.xmin_edit.text()),
                        x_max=_float_or_none(self.xmax_edit.text()),
                        y_min=_float_or_none(self.ymin_edit.text()),
                        y_max=_float_or_none(self.ymax_edit.text()),
                        show_legend=self.legend_check.currentData(),
                        minor_ticks=self.minor_ticks_check.currentData(),
                        tick_direction=self.tick_direction_combo.currentText(),
                        show_y_axis=self.yaxis_visible_check.currentData(),
                        label_font_family=self.font_family_combo.currentText(),
                        label_font_size=float(self.label_font_size_spin.value()),
                        label_color=getattr(self, "_label_color", ""),
                    ),
                    SetAttributesCommand(
                        self.graph,
                        "Edit Title/Fonts",
                        title=self.title_edit.text(),
                        title_font_family=self.font_family_combo.currentText(),
                        title_font_size=float(self.title_font_size_spin.value()),
                        title_color=getattr(self, "_title_color", ""),
                        layout_rows=int(self.layout_rows_spin.value()),
                        layout_cols=int(self.layout_cols_spin.value()),
                        panel_gap_x=float(self.panel_gapx_spin.value()),
                        panel_gap_y=float(self.panel_gapy_spin.value()),
                        y_delta=float(self.ydelta_spin.value()),
                    ),
                ],
                label="Edit Axes",
            )
        )
        self.canvas.set_grid(
            int(self.layout_rows_spin.value()), int(self.layout_cols_spin.value())
        )
        self.render()
        self._changed()

    def _apply_plot_theme(self) -> None:
        if self._loading:
            return
        self.commands.push(
            SetAttributesCommand(
                self.graph,
                "Plot theme",
                plot_theme=self.plot_theme_combo.currentData() or "",
            )
        )
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
        # The render walks every panel; re-mark the edited one afterwards.
        self._mark_active_panel()
        # The figure was redrawn, so the selected curve needs its highlight
        # again.
        self._highlight_selected_series(self._selected_spec())

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
        self._mark_active_panel()
        self._highlight_selected_series(spec)
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
                self._populate_z_combo(spec)
            self._load_axis_fields(self._active_layer())
        finally:
            self._loading = False
        self._update_color_button()

    def _highlight_selected_series(self, spec: PlotSpec | None) -> None:
        """Mark the selected curve in the figure.

        The sidebar and the plot then show the same series, so it is obvious
        which line the properties and the tools are about.
        """
        setter = getattr(self.canvas, "set_selected_series", None)
        if not callable(setter):
            return
        index = -1
        if spec is not None:
            for position, candidate in enumerate(self._series_specs):
                if candidate is spec:
                    index = position
                    break
        setter(index if index >= 0 else None)

    def select_plot(self, spec: PlotSpec) -> None:
        """Select ``spec`` in the plot list (used when a curve is clicked)."""
        for row in range(self.plot_list.count()):
            item = self.plot_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) is spec:
                self.plot_list.setCurrentRow(row)
                return

    def _load_axis_fields(self, layer: Layer) -> None:
        self.xscale_combo.setCurrentText(AxisScale(layer.x_scale).value)
        self.yscale_combo.setCurrentText(AxisScale(layer.y_scale).value)
        self.title_edit.setText(self.graph.title)
        self.xlabel_edit.setText(layer.x_label)
        self.ylabel_edit.setText(layer.y_label)
        self.y2label_edit.setText(layer.y2_label)
        self.zlabel_edit.setText(getattr(layer, "z_label", ""))
        self.font_family_combo.setCurrentText(
            layer.label_font_family or self.font_family_combo.itemText(0)
        )
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
        gt_index = self.graphtype_combo.findData(
            getattr(self.graph, "graph_type", GraphType.SIMPLE.value)
        )
        self.graphtype_combo.blockSignals(True)
        self.graphtype_combo.setCurrentIndex(gt_index if gt_index >= 0 else 0)
        self.graphtype_combo.blockSignals(False)
        for widget, value in (
            (self.panel_gapx_spin, getattr(self.graph, "panel_gap_x", 12.0)),
            (self.panel_gapy_spin, getattr(self.graph, "panel_gap_y", 12.0)),
            (self.ydelta_spin, getattr(self.graph, "y_delta", 0.0)),
        ):
            widget.blockSignals(True)
            widget.setValue(float(value or 0.0))
            widget.blockSignals(False)
        self._sync_type_fields()
        self.xmin_edit.setText("" if layer.x_min is None else str(layer.x_min))
        self.xmax_edit.setText("" if layer.x_max is None else str(layer.x_max))
        self.ymin_edit.setText("" if layer.y_min is None else str(layer.y_min))
        self.ymax_edit.setText("" if layer.y_max is None else str(layer.y_max))
        self.legend_check.setCurrentIndex(0 if layer.show_legend else 1)
        self.minor_ticks_check.setCurrentIndex(
            0 if getattr(layer, "minor_ticks", True) else 1
        )
        self.yaxis_visible_check.setCurrentIndex(
            0 if getattr(layer, "show_y_axis", True) else 1
        )
        idx = self.tick_direction_combo.findText(
            getattr(layer, "tick_direction", "out")
        )
        if idx >= 0:
            self.tick_direction_combo.setCurrentIndex(idx)
        # plot theme lives on the graph, not the layer
        theme_idx = self.plot_theme_combo.findData(
            getattr(self.graph, "plot_theme", "")
        )
        if theme_idx >= 0:
            self.plot_theme_combo.blockSignals(True)
            self.plot_theme_combo.setCurrentIndex(theme_idx)
            self.plot_theme_combo.blockSignals(False)

    def _clear_forms(self) -> None:
        self._loading = True
        self.legend_edit.clear()
        self._loading = False

    def _sync_type_fields(self) -> None:
        """Enable only the layout fields that apply to the current graph type."""
        try:
            gtype = GraphType(self.graphtype_combo.currentData() or GraphType.SIMPLE.value)
        except ValueError:
            gtype = GraphType.SIMPLE
        show_grid_size = gtype == GraphType.GRID
        show_gaps = gtype in (GraphType.GRID, GraphType.X_TWIN)
        show_delta = gtype in (GraphType.STACK, GraphType.X_TWIN)
        self.layout_rows_spin.setEnabled(show_grid_size)
        self.layout_cols_spin.setEnabled(show_grid_size)
        self.panel_gapx_spin.setEnabled(show_gaps)
        self.panel_gapy_spin.setEnabled(show_gaps)
        self.ydelta_spin.setEnabled(show_delta)
        hints = {
            GraphType.SIMPLE: "One plot frame.",
            GraphType.STACK: (
                "Layers are stacked in a single column (add layers to add panels)."
            ),
            GraphType.DOUBLE_Y: (
                "One frame with a secondary (right) Y axis — set a plot's Y axis to Right."
            ),
            GraphType.X_TWIN: (
                "Layers sit side by side, sharing Y (add layers to add panels)."
            ),
            GraphType.GRID: "An R x C grid of panels — set the rows and columns below.",
        }
        self.graphtype_hint.setText(hints.get(gtype, ""))

    def _preferred_backend(self) -> str:
        """matplotlib by default; the PyVista 3D scene when the graph asks for it."""
        for layer in self.graph.layers:
            for spec in layer.plots:
                if is_3d_style(spec.style):
                    return "pyvista"
        return "matplotlib"

    def _ensure_backend(self) -> None:
        """Swap the canvas when a graph moves between 2D and 3D content.

        The 3D canvas needs the optional plot3d extra; if it is missing the
        (colour-degraded) matplotlib view stays instead of failing the tab.
        """
        wanted = self._preferred_backend()
        klass = type(self.canvas).__name__
        current = (
            "pyvista"
            if klass == "PyVistaCanvas"
            else ("pyqtgraph" if klass == "PyQtGraphCanvas" else "matplotlib")
        )
        if wanted == current:
            return
        try:
            new_canvas = create_canvas(wanted)
        except Exception:  # noqa: BLE001 - optional dep may be absent
            return
        old_widget = self.canvas.widget()
        old_canvas, self.canvas = self.canvas, new_canvas
        self.canvas.label_click_callback = self._on_label_click
        self.canvas.point_picked = self._on_canvas_point_picked
        index = self.splitter.indexOf(old_widget)
        if index < 0:
            index = 1
        self.splitter.replaceWidget(index, self.canvas.widget())
        self.splitter.setStretchFactor(index, 1)
        try:
            old_canvas.close()
        except Exception:  # noqa: BLE001
            pass

    def render(self) -> None:
        self._ensure_backend()
        self._series_sources = []
        self._series_specs = []
        self.canvas.set_grid(
            getattr(self.graph, "layout_rows", 1), getattr(self.graph, "layout_cols", 1)
        )
        self.canvas.set_panel_gaps(
            getattr(self.graph, "panel_gap_x", 0.0) / 100.0,
            getattr(self.graph, "panel_gap_y", 0.0) / 100.0,
        )
        self.canvas.set_theme(self.graph.plot_theme or theme.current_preset())
        three_d = any(
            is_3d_style(spec.style) for each in self.graph.layers for spec in each.plots
        )
        try:
            gtype = GraphType(getattr(self.graph, "graph_type", GraphType.SIMPLE.value))
        except ValueError:
            gtype = GraphType.SIMPLE
        # A stack / x-twin can shift each successive panel vertically, producing
        # the classic waterfall arrangement without changing the worksheet data.
        y_delta = float(getattr(self.graph, "y_delta", 0.0) or 0.0)
        offset_panels = gtype in (GraphType.STACK, GraphType.X_TWIN)

        for panel_index, each in enumerate(self.graph.layers):
            self.canvas.set_current_panel(panel_index)
            offset = panel_index * y_delta if offset_panels else 0.0
            self.canvas.set_scales(
                x=AxisScale(each.x_scale).value, y=AxisScale(each.y_scale).value
            )
            for plot_index, spec in enumerate(each.plots):
                data = resolve_plot(self.project, spec)
                if data is None:
                    continue
                y = data.y if not offset else np.asarray(data.y, dtype=float) + offset
                self._series_sources.append(spec.source)
                self._series_specs.append(spec)
                self.canvas.plot(
                    data.x,
                    y,
                    style=PlotStyle(spec.style).value,
                    # The colour is resolved here so a series on a secondary
                    # axis keeps the palette colour the exporter uses.
                    color=spec.color or series_color(plot_index),
                    width=spec.line_width,
                    symbol=spec.symbol,
                    symbol_size=spec.symbol_size,
                    name=data.legend,
                    yerr=data.yerr,
                    xerr=data.xerr,
                    y_axis=spec.y_axis,
                    line_style=spec.line_style,
                    z=data.z if PlotStyle(spec.style) in Z_STYLES else None,
                    rows=np.arange(0, min(len(data.x), len(data.y))),
                )

            for ref in each.ref_lines:
                color = ref.color
                if theme.is_dark() and color.strip().lower() in (
                    "",
                    "#888888",
                    "gray",
                    "grey",
                ):
                    color = theme.canvas_colors()[1]
                position = (
                    ref.position + offset
                    if ref.orientation == "h" and offset
                    else ref.position
                )
                self.canvas.add_reference_line(
                    ref.orientation,
                    position,
                    color=color,
                    width=ref.width,
                    line_style=ref.line_style,
                    label=ref.label,
                )

            x_label, y_label = auto_axis_labels(self.project, each)
            # Shared axes are only labelled once in a stack / x-twin.
            show_x = not (
                gtype == GraphType.STACK and panel_index != len(self.graph.layers) - 1
            )
            show_y = not (gtype == GraphType.X_TWIN and panel_index != 0)
            self.canvas.set_labels(
                bottom=(x_label if show_x else None) or None,
                left=(y_label if show_y else None) or None,
                right=(each.z_label if three_d else each.y2_label) or None,
                fontfamily=each.label_font_family,
                fontsize=each.label_font_size,
                color=each.label_color,
            )
            self.canvas.set_limits(
                x=(each.x_min, each.x_max), y=(each.y_min, each.y_max)
            )
            self.canvas.set_ticks(
                minor=getattr(each, "minor_ticks", True),
                direction=getattr(each, "tick_direction", "out"),
            )
            self.canvas.set_axis_visibility(
                bottom=show_x,
                left=getattr(each, "show_y_axis", True),
                right=any(
                    getattr(spec, "y_axis", "left") == "right"
                    for spec in each.plots
                ),
            )
            # Add the legend after the plots so its handles exist.
            self.canvas.show_legend(each.show_legend)

        self.canvas.set_current_panel(self._active_panel_index())
        if gtype == GraphType.X_TWIN:
            # The panels of an X-Twin share their Y axis.
            share_y = getattr(self.canvas, "share_y_across_panels", None)
            if callable(share_y):
                share_y()
        if self.graph.title:
            self.canvas.set_title(
                self.graph.title,
                fontfamily=self.graph.title_font_family,
                fontsize=self.graph.title_font_size,
                color=self.graph.title_color,
            )
        # The graph view owns the switch, so the sidebar button, the menu and
        # the canvas always show the same state.
        self.set_hover(self.hover_enabled)

        for annotation in self.graph.annotations:
            color = annotation.color
            if theme.is_dark() and color.strip().lower() in ("", "#000000", "black"):
                color = theme.canvas_colors()[1]
            self.canvas.add_annotation(
                annotation.text,
                annotation.x,
                annotation.y,
                color=color,
                size=annotation.size,
            )

        # Re-apply the linked-brush overlay: rendering rebuilt the canvas.
        self._apply_last_brush()

    # -- linked brushing -----------------------------------------------------
    def current_limits(self) -> dict[int, tuple[float, float, float, float]]:
        """The limits of every panel of the *current view*, per layer.

        The exporter uses them, so a figure that was zoomed or panned on
        screen is written out the way it looks (what you see is what you get).
        """
        getter = getattr(self.canvas, "current_limits", None)
        if not callable(getter):
            return {}
        try:
            values = list(getter())
        except Exception:  # noqa: BLE001 - the canvas may not be ready
            return {}
        if not values:
            return {}
        limits: dict[int, tuple[float, float, float, float]] = {}
        for index in range(len(self.graph.layers)):
            limits[index] = values[index % len(values)]
        return limits

    def _on_canvas_point_picked(self, series_index: int, row: int) -> None:
        """A plotted point was clicked: broadcast the row to the linked views."""
        source = (
            self._series_sources[series_index]
            if 0 <= series_index < len(self._series_sources)
            else ""
        )
        if source:
            self.brush_requested.emit(source, [int(row)])
        # Clicking a curve also selects it, so the properties, the tools and
        # the highlighted line all belong to the same series.
        spec = (
            self._series_specs[series_index]
            if 0 <= series_index < len(self._series_specs)
            else None
        )
        if spec is not None:
            self.select_plot(spec)

    def apply_brush(self, source: str, rows: list[int]) -> None:
        """Highlight this graph's series whose source matches the brush."""
        self._last_brush = (source, list(rows))
        self._apply_last_brush()

    def _apply_last_brush(self) -> None:
        source, rows = getattr(self, "_last_brush", ("", []))
        selection: dict[int, list[int]] = {}
        for series_index, series_source in enumerate(self._series_sources):
            if series_source == source:
                selection[series_index] = list(rows)
        self.canvas.set_brush(selection)


def _float_or_none(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
