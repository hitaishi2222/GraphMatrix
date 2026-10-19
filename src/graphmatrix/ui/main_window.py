"""The main application window: docks, tabs, menus, and workflow wiring."""

from __future__ import annotations

import copy
import traceback
from pathlib import Path

import numpy as np
from PySide6.QtCore import QFileSystemWatcher, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from graphmatrix.core.code_export import project_to_script
from graphmatrix.core.analysis.descriptive import batch_summary
from graphmatrix.core.commands import (
    AddAnnotationCommand,
    AddColumnCommand,
    AddGraphCommand,
    AddPlotCommand,
    AddWorkbookCommand,
    AddWorksheetCommand,
    CommandStack,
    MacroCommand,
    RemoveColumnCommand,
    RemoveGraphCommand,
    RemoveWorkbookCommand,
    RemoveWorksheetCommand,
    RenameCommand,
    RenameWorkbookCommand,
    RenameWorksheetCommand,
    SetAttributesCommand,
    SetGraphTypeCommand,
)
from graphmatrix.core.io import export_delimited, import_file, supported_extensions
from graphmatrix.core.io.export import export_graph
from graphmatrix.core.journals import journal_names, preset as journal_preset_settings
from graphmatrix.core.instance import (
    register as register_instance,
    unregister as unregister_instance,
)
from graphmatrix.core.model import (
    Annotation,
    Column,
    ColumnType,
    GRAPH_TYPES,
    GRAPH_TYPE_LABELS,
    Graph,
    GraphType,
    Layer,
    PlotSpec,
    Project,
    Workbook,
    Worksheet,
    graph_type_label,
)
from graphmatrix.core.plotting import make_default_graph, make_plot_for_column
from graphmatrix.core.provenance import ProvenanceLog
from graphmatrix.core.report import export_analysis_bundle
from graphmatrix.core.scripting.record import MacroRecorder
from graphmatrix.core.templates import apply_template, load_template, save_template
from graphmatrix.ui.theme import (
    apply_theme,
    current_preset,
    load_saved_preset,
    presets,
    save_preset,
)
from graphmatrix.ui.actions import ActionRegistry, ActionSpec
from graphmatrix.ui.analysis_dialogs import (
    AnalysisResultDialog,
    DeconvolutionDialog,
    DescriptiveDialog,
    FitDialog,
    PeaksDialog,
    RegressionDialog,
    SignalDialog,
    SlopeDialog,
    StatisticsDialog,
)
from graphmatrix.ui.command_palette import CommandPalette
from graphmatrix.ui.console import ConsoleView
from graphmatrix.ui.digitize_dialog import DigitizeDialog
from graphmatrix.ui.brushing import BrushSelection
from graphmatrix.ui.graph_view import GraphView
from graphmatrix.ui.live_dialog import LiveController
from graphmatrix.ui.project_panel import ProjectPanel
from graphmatrix.ui.properties_panel import PropertiesPanel
from graphmatrix.ui.widgets import sheet_label
from graphmatrix.ui.worksheet_view import WorksheetView

APP_TITLE = "GraphMatrix"
PROJECT_FILTER = "GraphMatrix Project (*.rsproj);;All Files (*)"
GRAPH_FILTER = (
    "PDF (*.pdf);;SVG (*.svg);;EPS (*.eps);;PNG (*.png);;TIFF (*.tif);;All Files (*)"
)

_DATA_FILTER = (
    "Data files ("
    + " ".join(f"*{e}" for e in supported_extensions())
    + ");;All Files (*)"
)

_EXPORT_SUFFIXES = {".pdf", ".svg", ".eps", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}

#: Editable graph layout rows in the Properties inspector: displayed key ->
#: (Graph attribute, value caster).
_GRAPH_PROPERTY_CASTS = {
    "Grid rows": ("layout_rows", int),
    "Grid cols": ("layout_cols", int),
    "Panel gap X (%)": ("panel_gap_x", float),
    "Panel gap Y (%)": ("panel_gap_y", float),
    "Y delta": ("y_delta", float),
}


def _slug(text: str) -> str:
    """A stable action-id fragment for free-form labels (journal preset names)."""
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")


def _normalized_export_path(path: str) -> str:
    """Give ``path`` a supported export extension, defaulting to ``.pdf``.

    Guards against a stray extension typed under the "All Files" filter (e.g.
    ``figure.bmp``), which would otherwise make matplotlib raise.
    """
    suffix = Path(path).suffix.lower()
    if suffix in _EXPORT_SUFFIXES:
        return path
    if suffix:
        return str(Path(path).with_suffix(".pdf"))
    return path + ".pdf"


class ExportGraphDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Graph")
        self.width = QDoubleSpinBox()
        self.width.setRange(10, 500)
        self.width.setValue(100.0)
        self.width.setSuffix(" mm")
        self.height = QDoubleSpinBox()
        self.height.setRange(10, 500)
        self.height.setValue(75.0)
        self.height.setSuffix(" mm")
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 1200)
        self.dpi.setValue(300)
        self.transparent = QCheckBox("Transparent background")
        self.match_screen = QCheckBox("Match on-screen proportions")
        self.match_screen.setChecked(True)
        self.match_screen.setToolTip(
            "Use the proportions of the figure on screen and scale the "
            "typography, line widths and markers accordingly, so the file "
            "looks exactly like the preview. Turn it off for print-sized "
            "figures with standard (point-sized) typography."
        )
        form = QFormLayout()
        form.addRow("Width:", self.width)
        form.addRow("Height:", self.height)
        form.addRow("DPI:", self.dpi)
        form.addRow(self.transparent)
        form.addRow(self.match_screen)

        # One-click aspect-ratio presets.
        ratio_row = QHBoxLayout()
        ratio_row.addWidget(QLabel("Ratio:"))
        for label, ratio in (
            ("1:1", 1.0),
            ("4:3", 4 / 3),
            ("3:2", 1.5),
            ("16:9", 16 / 9),
            ("Golden", 1.618),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked=False, r=ratio: self._apply_ratio(r))
            ratio_row.addWidget(btn)
        ratio_row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(ratio_row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_ratio(self, ratio: float) -> None:
        width = self.width.value()
        self.height.setValue(round(width / ratio, 2))

class MainWindow(QMainWindow):
    def __init__(self, project: Project | None = None) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1440, 900)
        self.setMinimumSize(1024, 640)
        self.setAcceptDrops(True)

        app = QApplication.instance()
        if app is not None and not app.styleSheet():
            apply_theme(app, preset=load_saved_preset())

        self.project: Project = project or Project()
        self.commands = CommandStack()
        self.registry = ActionRegistry(self)
        self.recorder = MacroRecorder(self.commands)
        self.provenance = ProvenanceLog()
        self.provenance.attach(self.commands)
        self._path: Path | None = None
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.fileChanged.connect(self._on_project_file_changed)
        self._reloading_from_disk = False

        # Linked brushing: one shared row selection across sheet + graph tabs.
        self.brush = BrushSelection(self)
        self.brush.changed.connect(self._apply_brush)

        # Live / streaming data board (Tools → Live Data…).
        self.live = LiveController(self)
        self._dirty = False
        self.confirm_on_close = True
        self._views: dict[int, QWidget] = {}
        self._active_graph_view: GraphView | None = None
        self._plugins: list = []

        self._build_docks()
        self._build_central()
        self._register_actions()
        menus = self.registry.build_menus(
            self.menuBar(),
            order=[
                "File",
                "Edit",
                "Data",
                "Graph",
                "Analyze",
                "Export",
                "View",
                "Tools",
                "Help",
            ],
        )
        view_menu = menus.get("View")
        if view_menu is not None:
            view_menu.addSeparator()
            for dock, label in (
                (self.dock_project, "Project Explorer"),
                (self.dock_properties, "Properties"),
                (self.dock_console, "Python Console"),
            ):
                action = dock.toggleViewAction()
                action.setText(label)
                view_menu.addAction(action)
        self.plugins_menu = QMenu("Plugins", self)
        help_menu = menus.get("Help")
        if help_menu is not None:
            self.menuBar().insertMenu(help_menu.menuAction(), self.plugins_menu)
        else:
            self.menuBar().addMenu(self.plugins_menu)
        self._build_toolbar()
        self.statusBar().showMessage("Ready")

        self.commands.subscribe(self._on_stack_changed)
        self._on_stack_changed()
        self._new_project(confirm=False)
        self._load_plugins()

    # ------------------------------------------------------------------ build
    def _build_docks(self) -> None:
        self.properties_panel = PropertiesPanel()
        self.properties_panel.rename_requested.connect(self._apply_rename)
        self.properties_panel.property_changed.connect(self._apply_property)

        # Right dock: object properties on top; below, tabs for the active
        # graph view's Plot panel and Axes editor (swapped per graph tab).
        self._plot_host = QWidget()
        self._plot_host_layout = QVBoxLayout(self._plot_host)
        self._plot_host_layout.setContentsMargins(2, 2, 2, 2)
        self.axes_container = QWidget()
        self.axes_layout = QVBoxLayout(self.axes_container)
        self.axes_layout.setContentsMargins(2, 2, 2, 2)
        self.axes_layout.setSpacing(4)

        self._graph_tabs = QTabWidget()
        self._graph_tabs.setDocumentMode(True)
        self._graph_tabs.addTab(self._plot_host, "Plot")
        self._graph_tabs.addTab(self.axes_container, "Axes")

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setObjectName("splitter.properties")
        right_splitter.addWidget(self.properties_panel)
        right_splitter.addWidget(self._graph_tabs)
        right_splitter.setStretchFactor(0, 0)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setSizes([200, 600])

        dock_props = QDockWidget("Properties", self)
        dock_props.setObjectName("dock.properties")
        dock_props.setWidget(right_splitter)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_props)
        self.dock_properties = dock_props

        self.project_panel = ProjectPanel()
        self.project_panel.object_activated.connect(self._on_object_activated)
        self.project_panel.selection_changed.connect(self.properties_panel.show_object)
        self.project_panel.rename_requested.connect(self._action_rename_for)
        self.project_panel.delete_requested.connect(self._action_delete_object)
        self.project_panel.add_requested.connect(self._on_tree_add_requested)
        self.project_panel.graph_type_requested.connect(
            self._on_tree_graph_type_requested
        )
        dock_project = QDockWidget("Project Explorer", self)
        dock_project.setObjectName("dock.project")
        dock_project.setWidget(self.project_panel)
        dock_project.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_project)
        self.dock_project = dock_project

        self.console = ConsoleView(self.project, self.commands)
        dock_console = QDockWidget("Python Console", self)
        dock_console.setObjectName("dock.console")
        dock_console.setWidget(self.console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock_console)
        dock_console.hide()
        self.dock_console = dock_console

        # Versions are exposed via a toolbar dropdown (see _build_toolbar).

    def _build_central(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_closed)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("toolbar.main")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(toolbar)
        groups = (
            ("file.new", "file.open", "file.save", "file.import"),
            ("edit.undo", "edit.redo"),
            (
                "data.add_workbook",
                "data.add_worksheet",
                "data.add_graph",
                "data.sample",
            ),
            ("analyze.fit",),
        )
        for index, group in enumerate(groups):
            if index:
                toolbar.addSeparator()
            for action_id in group:
                toolbar.addAction(self.registry.action(action_id))
        toolbar.addSeparator()
        type_label = QLabel("Graph type:")
        type_label.setContentsMargins(6, 0, 4, 0)
        toolbar.addWidget(type_label)
        self.graph_type_combo = QComboBox()
        self.graph_type_combo.setToolTip(
            "Layout template for the active graph "
            "(simple, stack, double-Y, x-twin, grid)"
        )
        for gtype in GRAPH_TYPES:
            self.graph_type_combo.addItem(
                GRAPH_TYPE_LABELS[gtype.value], gtype.value
            )
        self.graph_type_combo.setEnabled(False)
        self.graph_type_combo.currentIndexChanged.connect(
            self._on_toolbar_graph_type
        )
        toolbar.addWidget(self.graph_type_combo)

        toolbar.addSeparator()
        theme_button = QToolButton()
        theme_button.setText("Theme")
        theme_button.setToolTip("Switch the colour scheme")
        theme_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        theme_button.setMenu(self._theme_menu)
        toolbar.addWidget(theme_button)

        self._version_menu = QMenu("Version", self)
        version_button = QToolButton()
        version_button.setText("Version")
        version_button.setToolTip("Manage project versions")
        version_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        version_button.setMenu(self._version_menu)
        toolbar.addWidget(version_button)
        self._version_button = version_button
        self.toolbar = toolbar

    def _register_actions(self) -> None:
        r = self.registry
        file_actions = [
            ("file.new", "New Project", "Ctrl+N", self._action_new, False),
            ("file.open", "Open Project...", "Ctrl+O", self._action_open, False),
            ("file.save", "Save Project", "Ctrl+S", self._action_save, False),
            (
                "file.save_as",
                "Save Project As...",
                "Ctrl+Shift+S",
                self._action_save_as,
                False,
            ),
            ("file.import", "Import Data...", "Ctrl+I", self._action_import, True),
            ("file.exit", "Exit", "Ctrl+Q", self.close, True),
        ]
        for action_id, text, shortcut, slot, sep in file_actions:
            r.register(
                ActionSpec(
                    action_id, text, shortcut, menu="File", separator_before=sep
                ),
                slot,
            )

        r.register(
            ActionSpec("edit.undo", "Undo", "Ctrl+Z", menu="Edit"),
            self._action_undo,
            enabled=False,
        )
        r.register(
            ActionSpec("edit.redo", "Redo", "Ctrl+Shift+Z", menu="Edit"),
            self._action_redo,
            enabled=False,
        )
        r.register(
            ActionSpec(
                "edit.rename", "Rename…", "F2", menu="Edit", separator_before=True
            ),
            self._action_rename,
        )

        # Theme presets: one checkable action each, grouped into a View submenu
        # that the toolbar also exposes as a dropdown.
        self._theme_menu = QMenu("Theme", self)
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_actions: dict[str, QAction] = {}
        for theme_preset in presets():
            action = r.register(
                ActionSpec(
                    f"view.theme.{theme_preset.id}",
                    theme_preset.label,
                    None,
                    checkable=True,
                    tooltip=theme_preset.description,
                ),
                lambda _checked=False, pid=theme_preset.id: self._action_set_theme(pid),
            )
            action.setActionGroup(self._theme_group)
            action.setChecked(theme_preset.id == current_preset())
            self._theme_actions[theme_preset.id] = action
            self._theme_menu.addAction(action)
        theme_menu_action = r.register(
            ActionSpec("view.theme", "Theme", menu="View"), None
        )
        theme_menu_action.setMenu(self._theme_menu)

        for action_id, text, slot, sep in (
            ("data.add_workbook", "Add Workbook", self._action_add_workbook, False),
            ("data.add_worksheet", "Add Worksheet", self._action_add_worksheet, False),
            ("data.add_graph", "Add Graph", self._action_add_graph, False),
            ("data.sample", "Add Sample Data", self._action_sample_data, True),
        ):
            r.register(
                ActionSpec(action_id, text, None, menu="Data", separator_before=sep),
                slot,
            )

        # Worksheet row/column edits, with spreadsheet-style keyboard shortcuts.
        # The menu keeps them discoverable; the shortcuts work from any sheet.
        self._rows_cols_menu = QMenu("Rows and Columns", self)
        for action_id, text, shortcut, slot, tooltip in (
            (
                "data.add_row",
                "Add Row at End",
                "Ctrl+Alt+N",
                self._action_add_row,
                "Append a row to the active worksheet",
            ),
            (
                "data.add_column",
                "Add Column at End",
                "Ctrl+Alt+C",
                self._action_add_column,
                "Append a Y column to the active worksheet",
            ),
            (
                "data.insert_row",
                "Insert Row Above Selection",
                "Ctrl+Alt+=",
                self._action_insert_row_above,
                "Insert as many rows as are selected, above them",
            ),
            (
                "data.insert_row_below",
                "Insert Row Below Selection",
                None,
                self._action_insert_row_below,
                "Insert as many rows as are selected, below them",
            ),
            (
                "data.delete_rows",
                "Delete Selected Rows",
                "Ctrl+Alt+-",
                self._action_delete_rows,
                "Delete the selected worksheet rows (undoable)",
            ),
            (
                "data.delete_columns",
                "Delete Selected Columns",
                "Ctrl+Alt+Shift+-",
                self._action_delete_columns,
                "Delete the selected worksheet columns (undoable)",
            ),
        ):
            action = r.register(
                ActionSpec(action_id, text, shortcut, tooltip=tooltip), slot
            )
            self._rows_cols_menu.addAction(action)
        rows_cols_action = r.register(
            ActionSpec(
                "data.rows_cols",
                "Rows and Columns",
                None,
                menu="Data",
                separator_before=True,
            ),
            None,
        )
        rows_cols_action.setMenu(self._rows_cols_menu)

        # Graph layout templates (simple/stack/2Y/x-twin/grid): checkable
        # actions so the current type is visible from the menu bar.
        self._graph_type_menu = QMenu("Graph Type", self)
        self._graph_type_group = QActionGroup(self)
        self._graph_type_group.setExclusive(True)
        self._graph_type_actions: dict[str, QAction] = {}
        for gtype in GRAPH_TYPES:
            action = r.register(
                ActionSpec(
                    f"graph.type.{_slug(gtype.value)}",
                    GRAPH_TYPE_LABELS[gtype.value],
                    None,
                    checkable=True,
                    tooltip=f"Lay the graph out as {graph_type_label(gtype)}",
                ),
                lambda _checked=False, value=gtype.value: self._action_set_graph_type(
                    value
                ),
            )
            action.setActionGroup(self._graph_type_group)
            self._graph_type_actions[gtype.value] = action
            self._graph_type_menu.addAction(action)
        graph_type_menu_action = r.register(
            ActionSpec("graph.type", "Graph Type", None, menu="Graph"), None
        )
        graph_type_menu_action.setMenu(self._graph_type_menu)

        # Journal presets: checkable actions mirroring the theme submenu.
        self._journal_menu = QMenu("Journal Preset", self)
        self._journal_group = QActionGroup(self)
        self._journal_group.setExclusive(True)
        self._journal_actions: dict[str, QAction] = {}
        for preset_name in journal_names():
            action = r.register(
                ActionSpec(
                    f"graph.journal.{_slug(preset_name)}",
                    preset_name,
                    None,
                    checkable=True,
                    tooltip=f"Restyle plots and export typography for {preset_name}",
                ),
                lambda _checked=False, name=preset_name: self._action_apply_journal(
                    name
                ),
            )
            action.setActionGroup(self._journal_group)
            self._journal_actions[preset_name] = action
            self._journal_menu.addAction(action)
        journal_menu_action = r.register(
            ActionSpec("graph.journal", "Journal Preset", None, menu="Graph"), None
        )
        journal_menu_action.setMenu(self._journal_menu)

        for action_id, text, slot, sep in (
            (
                "graph.add_plot",
                "Add Plot to Active Graph",
                self._action_add_plot,
                False,
            ),
            ("graph.add_layer", "Add Layer", self._action_add_layer, False),
            (
                "graph.new_from_data",
                "New Graph From Data",
                self._action_add_graph,
                False,
            ),
            (
                "graph.add_ref_line",
                "Add Reference Line…",
                self._action_add_reference_line,
                True,
            ),
            ("graph.hover", "Data Readout (Hover)", self._action_toggle_hover, False),
            (
                "graph.add_annotation",
                "Add Annotation...",
                self._action_add_annotation,
                True,
            ),
            (
                "graph.save_template",
                "Save Style Template...",
                self._action_save_template,
                True,
            ),
            (
                "graph.apply_template",
                "Apply Style Template...",
                self._action_apply_template,
                False,
            ),
            ("graph.export", "Export Active Graph...", self._action_export_graph, True),
        ):
            r.register(
                ActionSpec(action_id, text, None, menu="Graph", separator_before=sep),
                slot,
            )
        self.registry.action("graph.hover").setCheckable(True)

        for action_id, text, slot, sep in (
            (
                "analyze.descriptive",
                "Descriptive Statistics...",
                self._action_descriptive,
                False,
            ),
            ("analyze.regression", "Regression...", self._action_regression, False),
            ("analyze.fit", "Nonlinear Fit...", self._action_fit, False),
            ("analyze.slope", "Slope / Range Fit...", self._action_slope, False),
            ("analyze.peaks", "Peak Analysis...", self._action_peaks, True),
            (
                "analyze.deconvolution",
                "Peak Deconvolution...",
                self._action_deconvolution,
                False,
            ),
            ("analyze.signal", "Signal Processing...", self._action_signal, False),
            (
                "analyze.statistics",
                "Statistics / t-test / ANOVA...",
                self._action_statistics,
                False,
            ),
            (
                "analyze.batch_stats",
                "Batch Statistics...",
                self._action_batch_stats,
                False,
            ),
            (
                "analyze.digitize",
                "Digitize Curve from Image...",
                self._action_digitize,
                True,
            ),
        ):
            r.register(
                ActionSpec(action_id, text, None, menu="Analyze", separator_before=sep),
                slot,
            )

        r.register(
            ActionSpec("export.graph", "Export Active Graph...", None, menu="Export"),
            self._action_export_graph,
        )
        r.register(
            ActionSpec(
                "export.all_graphs", "Export All Graphs...", None, menu="Export"
            ),
            self._action_export_all_graphs,
        )
        r.register(
            ActionSpec(
                "export.sheet", "Export Worksheet as CSV...", None, menu="Export"
            ),
            self._action_export_sheet,
        )
        r.register(
            ActionSpec(
                "export.script",
                "Export Project as Python Script...",
                None,
                menu="Export",
                separator_before=True,
            ),
            self._action_export_script,
        )
        r.register(
            ActionSpec(
                "export.bundle", "Export Analysis Bundle...", None, menu="Export"
            ),
            self._action_export_bundle,
        )

        r.register(
            ActionSpec(
                "tools.palette", "Command Palette...", "Ctrl+Shift+P", menu="Tools"
            ),
            self._action_command_palette,
        )
        r.register(
            ActionSpec("tools.methods", "Analysis Methods...", None, menu="Tools"),
            self._action_show_methods,
        )
        r.register(
            ActionSpec(
                "tools.console",
                "Python Console",
                None,
                menu="Tools",
                checkable=True,
                separator_before=True,
            ),
            self._toggle_console,
        )
        r.register(
            ActionSpec(
                "tools.record",
                "Record Macro",
                None,
                menu="Tools",
                checkable=True,
                separator_before=True,
            ),
            self._toggle_record,
        )
        r.register(
            ActionSpec(
                "tools.save_macro", "Save Recorded Macro...", None, menu="Tools"
            ),
            self._action_save_macro,
        )
        r.register(
            ActionSpec("tools.run_macro", "Run Script...", None, menu="Tools"),
            self._action_run_macro,
        )
        r.register(
            ActionSpec(
                "tools.batch",
                "Batch Import...",
                None,
                menu="Tools",
                separator_before=True,
            ),
            self._action_batch_import,
        )
        r.register(
            ActionSpec(
                "tools.batch_analysis", "Batch Analysis (Recipe)...", None, menu="Tools"
            ),
            self._action_batch_analysis,
        )
        r.register(
            ActionSpec(
                "tools.live", "Live Data...", None, menu="Tools", separator_before=True
            ),
            self._action_live_data,
        )
        r.register(
            ActionSpec("help.about", "About GraphMatrix", None, menu="Help"),
            self._action_about,
        )

    # ------------------------------------------------------------- project ops
    def _set_project(self, project: Project, path: Path | None) -> None:
        # Stop watching the previous file.
        if self._path is not None and self._path.exists():
            try:
                self._file_watcher.removePath(str(self._path))
            except Exception:  # noqa: BLE001
                pass
        self.project = project
        self._path = path
        if path is not None and path.exists():
            self._file_watcher.addPath(str(path))
        register_instance(path)
        self.commands.clear()
        self.provenance.clear()
        self._close_all_tabs()
        self._refresh()
        self.console.set_project(project)
        self._set_dirty(False)

    def _on_project_file_changed(self, path: str) -> None:
        if self._reloading_from_disk:
            return
        if self._path is None or str(self._path) != path:
            return
        if self._dirty:
            # Don't clobber unsaved work; warn once.
            self.statusBar().showMessage(
                "Project file changed on disk (unsaved changes kept)", 4000
            )
            return
        if not Path(path).exists():
            return
        self._reloading_from_disk = True
        try:
            project = Project.open(path)
            self._set_project(project, Path(path))
            self.statusBar().showMessage("Project reloaded from disk", 3000)
        except Exception as exc:  # noqa: BLE001
            self.statusBar().showMessage(f"Reload failed: {exc}", 4000)
        finally:
            self._reloading_from_disk = False
            # Re-arm watcher (some platforms drop the path after a change).
            if self._path is not None and self._path.exists():
                try:
                    self._file_watcher.addPath(str(self._path))
                except Exception:  # noqa: BLE001
                    pass

    def _refresh(self) -> None:
        self.project_panel.set_project(self.project)
        self._update_title()
        self._refresh_versions()

    def _update_title(self) -> None:
        mark = " *" if self._dirty else ""
        location = f"  —  {self._path}" if self._path else ""
        self.setWindowTitle(f"{self.project.name}{mark}{location}  —  {APP_TITLE}")

    def _refresh_versions(self) -> None:
        self._version_menu.clear()
        for version in getattr(self.project, "versions", []):
            name = version.get("name", "")
            action = self._version_menu.addAction(
                name,
                lambda _checked=False, n=name: self._action_restore_version_name(n),
            )
            action.setCheckable(False)
        self._version_menu.addSeparator()
        self._version_menu.addAction("New Version…", self._action_create_version)
        # Delete submenu
        delete_menu = self._version_menu.addMenu("Delete Version")
        for version in getattr(self.project, "versions", []):
            name = version.get("name", "")
            delete_menu.addAction(
                name, lambda _checked=False, n=name: self._action_delete_version_name(n)
            )

    def _action_create_version(self) -> None:
        name, ok = QInputDialog.getText(self, "New Version", "Version name:")
        if not ok or not name.strip():
            return
        note, _ = QInputDialog.getText(self, "New Version", "Note (optional):")
        try:
            self.project.create_version(name.strip(), note.strip())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Version", str(exc))
            return
        self._refresh_versions()
        self._mark_dirty()

    def _action_restore_version_name(self, name: str) -> None:
        if (
            QMessageBox.question(
                self,
                "Restore Version",
                f"Restore version {name!r}? Current changes will be replaced.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.project.restore_version(name)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Version", str(exc))
            return
        self._refresh()
        self._mark_dirty()

    def _action_delete_version_name(self, name: str) -> None:
        if (
            QMessageBox.question(self, "Delete Version", f"Delete version {name!r}?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.project.delete_version(name)
        self._refresh_versions()
        self._mark_dirty()

    def _set_dirty(self, flag: bool) -> None:
        if flag != self._dirty:
            self._dirty = flag
            self._update_title()

    def _mark_dirty(self) -> None:
        self._set_dirty(True)

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        result = QMessageBox.warning(
            self,
            "Unsaved changes",
            "The current project has unsaved changes.\nSave before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if result == QMessageBox.StandardButton.Save:
            return self._action_save()
        return result == QMessageBox.StandardButton.Discard

    def _new_project(self, *, confirm: bool = True) -> bool:
        if confirm and not self._confirm_discard():
            return False
        project = Project()
        book = project.add_workbook(Workbook("Book1"))
        book.add_sheet(Worksheet("Sheet1"))
        self._set_project(project, path=None)
        return True

    def _action_new(self) -> None:
        self._new_project(confirm=True)

    def _action_open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", PROJECT_FILTER)
        if path:
            self._open_project_path(path)

    def _open_project_path(self, path) -> None:
        try:
            project = Project.open(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open failed", f"Could not open project:\n{exc}")
            return
        self._set_project(project, path=Path(path))
        self.statusBar().showMessage(f"Opened {path}", 4000)

    def _action_save(self) -> bool:
        if self._path is None:
            return self._action_save_as()
        try:
            self.project.save(self._path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", f"Could not save project:\n{exc}")
            return False
        self._set_dirty(False)
        self.statusBar().showMessage(f"Saved {self._path}", 4000)
        return True

    def _action_save_as(self) -> bool:
        default = str(self._path) if self._path else f"{self.project.name}.rsproj"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", default, PROJECT_FILTER
        )
        if not path:
            return False
        if not path.endswith(".rsproj"):
            path += ".rsproj"
        self._path = Path(path)
        return self._action_save()

    def _action_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Data", "", _DATA_FILTER)
        if path:
            self._import_paths([path])

    def _import_paths(self, paths, *, interactive: bool = True) -> None:
        """Import one or more data files, each as its own undoable step."""
        paths = [str(p) for p in paths]
        commands: list = []
        first_book = None
        for path in paths:
            try:
                book = import_file(path)
            except Exception as exc:  # noqa: BLE001
                if interactive and len(paths) == 1:
                    QMessageBox.critical(
                        self, "Import failed", f"Could not import:\n{exc}"
                    )
                else:
                    self.statusBar().showMessage(
                        f"Skipped {Path(path).name}: {exc}", 6000
                    )
                continue
            book.name = self.project.unique_name(book.name)
            commands.append(AddWorkbookCommand(self.project, book))
            self.provenance.record_import(path, book.name)
            if first_book is None:
                first_book = book
        if not commands:
            return
        if len(commands) == 1:
            self.commands.push(commands[0])
        else:
            self.commands.push(
                MacroCommand(commands, f"Import ({len(commands)} files)")
            )
        if first_book is not None and first_book.sheets and len(paths) == 1:
            self._open_sheet_tab(first_book.sheets[0])
        self.statusBar().showMessage(f"Imported {len(commands)} file(s)", 4000)

    def _action_batch_import(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Batch Import", "", _DATA_FILTER)
        if paths:
            self._import_paths(paths, interactive=False)

    def _action_live_data(self) -> None:
        from graphmatrix.ui.live_dialog import LiveDataDialog

        LiveDataDialog(self, controller=self.live, parent=self).show()

    def _action_batch_analysis(self) -> None:
        from graphmatrix.core.batch import run_recipe_over_files
        from graphmatrix.core.recipes import load_recipe

        recipe_path, _ = QFileDialog.getOpenFileName(
            self, "Open Analysis Recipe", "", "GraphMatrix Recipe (*.json *.rsr)"
        )
        if not recipe_path:
            return
        try:
            recipe = load_recipe(recipe_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Recipe failed", str(exc))
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Data Files", "", _DATA_FILTER
        )
        if not paths:
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "Report / Figure Output Folder"
        )
        items = run_recipe_over_files(
            paths, recipe, report_dir=out_dir or None, export_dir=out_dir or None
        )
        ok = sum(1 for item in items if item.ok)
        self.statusBar().showMessage(
            f"Batch analysis: {ok}/{len(items)} succeeded", 6000
        )
        failures = [item for item in items if not item.ok]
        if failures:
            QMessageBox.warning(
                self,
                "Batch failures",
                "\n".join(f"{item.path.name}: {item.error}" for item in failures[:10]),
            )

    # ------------------------------------------------------------ drag & drop
    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths:
            return
        projects = [p for p in paths if p.lower().endswith(".rsproj")]
        data = [p for p in paths if not p.lower().endswith(".rsproj")]
        if projects:
            self._open_project_path(projects[0])
        if data:
            self._import_paths(data, interactive=False)
        event.acceptProposedAction()

    # ---------------------------------------------------------------- edit ops
    def _action_undo(self) -> None:
        self.commands.undo()

    def _action_redo(self) -> None:
        self.commands.redo()

    # ------------------------------------------------------------------ rename
    def _action_rename(self) -> None:
        self._action_rename_for(self.project_panel.current_object())

    def _action_delete_object(self, obj) -> None:
        """Delete the selected object as one undoable step.

        Open tabs for the deleted graph/worksheet are closed first; Ctrl+Z
        restores the model object (tabs can be re-opened from the tree).
        """
        if isinstance(obj, Graph):
            # close any open tab
            view = self._views.get(id(obj))
            if view is not None:
                idx = self.tabs.indexOf(view)
                if idx >= 0:
                    self.tabs.removeTab(idx)
                del self._views[id(obj)]
                if self._active_graph_view is view:
                    self._active_graph_view = None
            self.commands.push(RemoveGraphCommand(self.project, obj))
        elif isinstance(obj, Workbook):
            self.commands.push(RemoveWorkbookCommand(self.project, obj))
        elif isinstance(obj, Worksheet):
            view = self._views.get(id(obj))
            if view is not None:
                idx = self.tabs.indexOf(view)
                if idx >= 0:
                    self.tabs.removeTab(idx)
                del self._views[id(obj)]
            self.commands.push(RemoveWorksheetCommand(obj.workbook, obj))
        elif isinstance(obj, Column):
            self.commands.push(RemoveColumnCommand(obj.worksheet, obj))
        else:
            return
        self.project_panel.set_project(self.project)
        self.properties_panel.show_object(None)

    # -- graph layout types --------------------------------------------------
    def _resolve_graph_type(self, text: str) -> str | None:
        """Map a value, full label, or short label to a graph-type value."""
        raw = (text or "").strip().lower()
        if not raw:
            return None
        for gtype in GRAPH_TYPES:
            label = GRAPH_TYPE_LABELS[gtype.value]
            short = label.split(" (")[0].lower()
            if raw in (gtype.value.lower(), label.lower(), short):
                return gtype.value
        return None

    def _sync_graph_type_actions(self, graph: Graph | None) -> None:
        """Mirror the active graph's type in the menu checks and toolbar combo."""
        current = getattr(graph, "graph_type", "") if graph is not None else ""
        if hasattr(self, "_graph_type_actions"):
            self._graph_type_group.setExclusive(False)
            for value, action in self._graph_type_actions.items():
                action.blockSignals(True)
                action.setChecked(value == current)
                action.blockSignals(False)
            self._graph_type_group.setExclusive(True)
        combo = getattr(self, "graph_type_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            index = combo.findData(current)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.setEnabled(graph is not None)
            combo.blockSignals(False)

    def _action_set_graph_type(self, graph_type: str) -> None:
        """Apply a layout template to the active (or selected) graph."""
        view = self._active_graph_view
        if view is None:
            selected = self.project_panel.current_object()
            if isinstance(selected, Graph):
                self._open_graph_tab(selected)
                view = self._active_graph_view
        label = graph_type_label(graph_type)
        if view is None:
            self.statusBar().showMessage(
                f"Open a graph to switch it to {label}", 4000
            )
            self._sync_graph_type_actions(None)
            return
        view.set_graph_type(graph_type)
        self._sync_graph_type_actions(view.graph)
        if (
            getattr(view.graph, "graph_type", "")
            in (GraphType.STACK.value, GraphType.X_TWIN.value)
            and view.graph.num_layers < 2
        ):
            self.statusBar().showMessage(
                f"Graph type: {label} — add layers (Graph → Add Layer) to show panels",
                6000,
            )
        else:
            self.statusBar().showMessage(f"Graph type: {label}", 3000)

    def _on_toolbar_graph_type(self, index: int) -> None:
        if not hasattr(self, "graph_type_combo"):
            return
        value = self.graph_type_combo.itemData(index)
        if value:
            self._action_set_graph_type(value)

    def _apply_property(self, obj, key: str, text: str) -> None:
        """Apply a value edited in the Properties inspector."""
        if not isinstance(obj, Graph):
            return
        if key == "Graph type":
            value = self._resolve_graph_type(text)
            if value is None:
                QMessageBox.warning(
                    self,
                    "Unknown graph type",
                    f"\u201c{text}\u201d is not one of the graph layout types.",
                )
                self.properties_panel.show_object(obj)
                return
            if value != obj.graph_type:
                self.commands.push(SetGraphTypeCommand(obj, value))
                self.statusBar().showMessage(
                    f"Graph type: {graph_type_label(value)}", 3000
                )
            self.properties_panel.show_object(obj)
            return

        field, caster = _GRAPH_PROPERTY_CASTS.get(key, (None, None))
        if field is None:
            return
        try:
            value = caster(str(text).strip())
        except (TypeError, ValueError):
            QMessageBox.warning(
                self, "Invalid value", f"\u201c{text}\u201d is not a valid {key}."
            )
            self.properties_panel.show_object(obj)
            return
        if field in ("layout_rows", "layout_cols"):
            value = max(1, min(12, int(value)))
        elif field == "y_delta":
            value = max(-1e6, min(1e6, float(value)))
        else:
            value = max(0.0, min(100.0, float(value)))
        self.commands.push(
            SetAttributesCommand(obj, "Edit Layout", **{field: value})
        )
        self.properties_panel.show_object(obj)

    def _action_rename_for(self, obj) -> None:
        if obj is None:
            self.statusBar().showMessage(
                "Select a project, workbook, worksheet, or graph to rename", 3000
            )
            return
        old = getattr(obj, "name", "") or ""
        new_name, ok = QInputDialog.getText(self, "Rename", "Name:", text=old)
        if not ok:
            self.properties_panel.show_object(obj)
            return
        self._apply_rename(obj, new_name)

    def _apply_rename(self, obj, new_name: str | None = None) -> None:
        """Apply a rename (with validation and source-rewriting) as one undo step."""
        if obj is None:
            return
        if new_name is None:
            self._action_rename_for(obj)
            return
        old = getattr(obj, "name", "") or ""
        new_name = (new_name or "").strip()
        if not new_name or new_name == old:
            self._resync_after_rename(obj)
            return
        if not self._rename_available(obj, new_name):
            QMessageBox.warning(
                self, "Name in use", f"\u201c{new_name}\u201d is already used."
            )
            self._resync_after_rename(obj)
            return
        command = self._rename_command(obj, new_name)
        if command is None:
            self._resync_after_rename(obj)
            return
        self.commands.push(command)
        self._resync_after_rename(obj)
        self._sync_tab_titles()
        self.statusBar().showMessage(f"Renamed to \u201c{new_name}\u201d", 3000)

    def _rename_available(self, obj, name: str) -> bool:
        if isinstance(obj, Project):
            return True
        if isinstance(obj, Workbook):
            return all(b is obj or b.name != name for b in self.project.workbooks)
        if isinstance(obj, Worksheet):
            book = self._workbook_for(obj)
            return book is None or all(s is obj or s.name != name for s in book.sheets)
        if isinstance(obj, Graph):
            return all(g is obj or g.name != name for g in self.project.graphs)
        if isinstance(obj, Column):
            sheet = self._sheet_for_column(obj)
            return sheet is None or all(
                c is obj or c.name != name for c in sheet.columns
            )
        return True

    def _rename_command(self, obj, name: str):
        if isinstance(obj, Workbook):
            return RenameWorkbookCommand(self.project, obj, name)
        if isinstance(obj, Worksheet):
            book = self._workbook_for(obj)
            return (
                RenameWorksheetCommand(self.project, book, obj, name) if book else None
            )
        if isinstance(obj, (Project, Graph, Column)):
            return RenameCommand(obj, name)
        return None

    def _workbook_for(self, sheet: Worksheet) -> Workbook | None:
        for book in self.project.workbooks:
            if sheet in book.sheets:
                return book
        return None

    def _sheet_for_column(self, column: Column) -> Worksheet | None:
        for book in self.project.workbooks:
            for sheet in book.sheets:
                if column in sheet.columns:
                    return sheet
        return None

    def _resync_after_rename(self, obj) -> None:
        self.project_panel.set_project(self.project)
        self._update_title()
        self.properties_panel.show_object(obj)

    def _sync_tab_titles(self) -> None:
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, WorksheetView):
                self.tabs.setTabText(index, widget.sheet.name)
            elif isinstance(widget, GraphView):
                self.tabs.setTabText(index, widget.graph.name)

    def _action_set_theme(self, preset_id: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        applied = apply_theme(app, preset=preset_id)
        save_preset(applied)
        action = self._theme_actions.get(applied)
        if action is not None and not action.isChecked():
            action.setChecked(True)
        for view in self._views.values():
            if hasattr(view, "on_theme_changed"):
                view.on_theme_changed()
        label = next((p.label for p in presets() if p.id == applied), applied)
        self.statusBar().showMessage(f"{label} theme applied", 2500)

    def _on_stack_changed(self) -> None:
        undo = self.registry.action("edit.undo")
        redo = self.registry.action("edit.redo")
        undo.setEnabled(self.commands.can_undo)
        redo.setEnabled(self.commands.can_redo)
        undo.setText("Undo")
        redo.setText("Redo")
        undo.setToolTip(f"Undo {self.commands.undo_label}".strip())
        redo.setToolTip(f"Redo {self.commands.redo_label}".strip())
        if self.project is not None:
            self.project_panel.set_project(self.project)
            self._refresh_open_views()
            self._sync_journal_actions(self._active_graph())
            self._sync_graph_type_actions(
                self._active_graph_view.graph if self._active_graph_view else None
            )
            selected = self.project_panel.current_object()
            if isinstance(selected, Graph):
                self.properties_panel.show_object(selected)
        self._set_dirty(True)

    # ---------------------------------------------------------------- data ops
    def _action_add_workbook(self) -> None:
        book = Workbook(self.project.unique_name("Book"))
        book.add_sheet(Worksheet("Sheet1"))
        self.commands.push(AddWorkbookCommand(self.project, book))

    def _action_add_worksheet(self) -> None:
        book = self._current_workbook()
        if book is None:
            self._action_add_workbook()
            book = self.project.workbooks[-1]
        self.commands.push(AddWorksheetCommand(book, Worksheet(book.next_sheet_name())))

    # -- worksheet row/column keyboard commands ------------------------------
    def _active_sheet_view(self) -> WorksheetView | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, WorksheetView) else None

    def _on_active_sheet(self, message: str, callback) -> None:
        view = self._active_sheet_view()
        if view is None:
            self.statusBar().showMessage(f"Open a worksheet to {message}", 3000)
            return
        callback(view)

    def _action_add_row(self) -> None:
        self._on_active_sheet("add a row", lambda view: view.append_row())

    def _action_add_column(self) -> None:
        self._on_active_sheet("add a column", lambda view: view.append_column())

    def _action_insert_row_above(self) -> None:
        self._on_active_sheet(
            "insert rows", lambda view: view.insert_rows_above()
        )

    def _action_insert_row_below(self) -> None:
        self._on_active_sheet(
            "insert rows", lambda view: view.insert_rows_below()
        )

    def _action_delete_rows(self) -> None:
        self._on_active_sheet(
            "delete rows", lambda view: view.delete_selected_rows()
        )

    def _action_delete_columns(self) -> None:
        self._on_active_sheet(
            "delete columns", lambda view: view.delete_selected_columns()
        )

    def _on_tree_graph_type_requested(self, graph: Graph, graph_type: str) -> None:
        """Apply a layout type chosen from a graph's tree context menu."""
        view = self._views.get(id(graph))
        if view is None:
            self._open_graph_tab(graph)
        else:
            self.tabs.setCurrentWidget(view)
            self._active_graph_view = view
        self._action_set_graph_type(graph_type)

    def _on_tree_add_requested(self, kind: str, detail: str = "") -> None:
        """Create an object from the Project Explorer's “Add” submenu."""
        if kind == "workbook":
            self._action_add_workbook()
        elif kind == "worksheet":
            self._action_add_worksheet()
        elif kind == "graph":
            self._action_add_graph(detail or None)

    def _action_add_graph(self, graph_type: str | None = None) -> None:
        graph = make_default_graph(self.project, self.project.unique_name("Graph"))
        if graph_type:
            try:
                gtype = GraphType(graph_type)
            except ValueError:
                gtype = GraphType.SIMPLE
            graph.graph_type = gtype.value
            # A stack / x-twin template starts with two panels so the layout is
            # visible immediately; the second panel copies the first plot spec
            # (data references are shared, nothing is duplicated on disk).
            if gtype in (GraphType.STACK, GraphType.X_TWIN) and graph.layers:
                source = graph.first_layer
                if source.plots:
                    extra = Layer("Layer 2")
                    extra.plots = [copy.deepcopy(spec) for spec in source.plots]
                    graph.layers.append(extra)
            graph.sync_layout()
        self.commands.push(AddGraphCommand(self.project, graph))
        self._open_graph_tab(graph)
        self._sync_graph_type_actions(
            self._active_graph_view.graph if self._active_graph_view else None
        )

    def _action_add_plot(self) -> None:
        if self._active_graph_view is None:
            QMessageBox.information(self, "No graph", "Open or create a graph first.")
            return
        self._active_graph_view.add_plot()

    def _plot_column(self, source: str, column_name: str) -> None:
        """Plot one column against its partner X/Y (worksheet context menu)."""
        if make_plot_for_column(self.project, source, column_name) is None:
            QMessageBox.information(
                self,
                "Cannot plot",
                f"\u201c{column_name}\u201d needs a matching X and Y column to plot against.",
            )
            return
        view = self._active_graph_view
        if view is None:
            graph = Graph(self.project.unique_name("Graph"))
            self.commands.push(AddGraphCommand(self.project, graph))
            self._open_graph_tab(graph)
            view = self._active_graph_view
        if view is None:
            return
        view.add_column_plot(source, column_name)
        self.statusBar().showMessage(f"Plotted \u201c{column_name}\u201d", 3000)

    def _action_add_layer(self) -> None:
        if self._active_graph_view is not None:
            self._active_graph_view.add_layer()

    def _action_add_annotation(self) -> None:
        if self._active_graph_view is None:
            QMessageBox.information(self, "No graph", "Open or create a graph first.")
            return
        self._active_graph_view.add_annotation()

    def _action_add_reference_line(self) -> None:
        if self._active_graph_view is None:
            QMessageBox.information(self, "No graph", "Open or create a graph first.")
            return
        self._active_graph_view.add_reference_line()

    def _action_toggle_hover(self) -> None:
        action = self.registry.action("graph.hover")
        if self._active_graph_view is None:
            action.setChecked(False)
            QMessageBox.information(self, "No graph", "Open or create a graph first.")
            return
        self._active_graph_view.set_hover(action.isChecked())

    def _add_annotation_to_active_graph(self, text: str) -> None:
        graph = self._active_graph()
        if graph is None:
            QMessageBox.information(
                self, "No graph", "Create or open a graph tab first."
            )
            return
        self.commands.push(AddAnnotationCommand(graph, Annotation(text=text)))
        if self._active_graph_view is not None:
            self._active_graph_view.refresh()

    def _action_save_template(self) -> None:
        graph = self._active_graph()
        if graph is None:
            QMessageBox.information(self, "No graph", "Open a graph first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Style Template",
            f"{graph.name}.rstpl",
            "GraphMatrix Template (*.rstpl *.json)",
        )
        if not path:
            return
        save_template(graph, path)
        self.statusBar().showMessage(f"Saved template {path}", 4000)

    def _action_apply_template(self) -> None:
        graph = self._active_graph()
        if graph is None:
            QMessageBox.information(self, "No graph", "Open a graph first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Apply Style Template", "", "GraphMatrix Template (*.rstpl *.json)"
        )
        if not path:
            return
        try:
            template = load_template(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Template failed", str(exc))
            return
        apply_template(graph, template)
        if self._active_graph_view is not None:
            self._active_graph_view.refresh()
        self._mark_dirty()
        self.statusBar().showMessage(f"Applied template {path}", 4000)

    def _action_apply_journal(self, name: str) -> None:
        graph = self._active_graph()
        if graph is None:
            QMessageBox.information(self, "No graph", "Open a graph first.")
            return
        settings = journal_preset_settings(name)
        target_preset = name if name in journal_names() else ""
        commands: list = [
            SetAttributesCommand(graph, "Journal Preset", journal_preset=target_preset)
        ]
        for layer in graph.layers:
            for spec in layer.plots:
                commands.append(
                    SetAttributesCommand(
                        spec,
                        "Journal Preset",
                        line_width=float(settings["line_width"]),
                        symbol_size=float(settings["symbol_size"]),
                    )
                )
        self.commands.push(MacroCommand(commands, f"Apply Journal Preset: {name}"))
        if self._active_graph_view is not None:
            self._active_graph_view.refresh()
        self._mark_dirty()
        self.statusBar().showMessage(f"Applied journal preset: {name}", 4000)

    def _action_sample_data(self) -> None:
        sheet = self._current_sheet()
        if sheet is None:
            QMessageBox.information(
                self, "No worksheet", "Create a workbook and worksheet first."
            )
            return
        source = sheet_label(self.project, sheet)
        x = np.linspace(0.0, 2.0 * np.pi, 200)
        self.commands.push(
            MacroCommand(
                [
                    AddColumnCommand(
                        sheet,
                        Column(
                            sheet.next_column_name(ColumnType.X),
                            ColumnType.X,
                            x,
                            units="rad",
                        ),
                        source=source,
                    ),
                    AddColumnCommand(
                        sheet,
                        Column(
                            sheet.next_column_name(ColumnType.Y),
                            ColumnType.Y,
                            np.sin(x),
                            comment="sin(x)",
                        ),
                        source=source,
                    ),
                ],
                label="Add Sample Data",
            )
        )
        self._open_sheet_tab(sheet)

    # ------------------------------------------------------------- analyze ops
    def _run_dialog(self, dialog) -> None:
        if dialog.exec():
            result = dialog.run()
            sheet = dialog.sheet()
            source = sheet_label(self.project, sheet) if sheet is not None else ""
            self.provenance.record_analysis(result, source=source)
            AnalysisResultDialog(
                result,
                project=self.project,
                commands=self.commands,
                default_sheet=dialog.sheet(),
                add_to_graph=self._add_curve_to_active_graph,
                add_annotation=self._add_annotation_to_active_graph,
                parent=self,
            ).exec()

    def _action_descriptive(self) -> None:
        if self.project.workbooks:
            self._run_dialog(DescriptiveDialog(self.project, self))

    def _action_regression(self) -> None:
        if self.project.workbooks:
            self._run_dialog(RegressionDialog(self.project, self))

    def _action_fit(self) -> None:
        if self.project.workbooks:
            self._run_dialog(FitDialog(self.project, self))

    def _action_peaks(self) -> None:
        if self.project.workbooks:
            self._run_dialog(PeaksDialog(self.project, self))

    def _action_deconvolution(self) -> None:
        if self.project.workbooks:
            self._run_dialog(DeconvolutionDialog(self.project, self))

    def _action_signal(self) -> None:
        if self.project.workbooks:
            self._run_dialog(SignalDialog(self.project, self))

    def _action_slope(self) -> None:
        if self.project.workbooks:
            self._run_dialog(SlopeDialog(self.project, self))

    def _action_statistics(self) -> None:
        if self.project.workbooks:
            self._run_dialog(StatisticsDialog(self.project, self))

    def _action_batch_stats(self) -> None:
        result = batch_summary(self.project)
        self.provenance.record_analysis(result, source="")
        AnalysisResultDialog(result, parent=self).exec()

    def _action_digitize(self) -> None:
        dialog = DigitizeDialog(self)
        if not dialog.exec():
            return
        try:
            result = dialog.run()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Digitizing failed", f"{type(exc).__name__}: {exc}"
            )
            return
        sheet = self._current_sheet()
        source = sheet_label(self.project, sheet) if sheet is not None else ""
        self.provenance.record_analysis(result, source=source)
        AnalysisResultDialog(
            result,
            project=self.project,
            commands=self.commands,
            default_sheet=sheet,
            add_to_graph=self._add_curve_to_active_graph,
            add_annotation=self._add_annotation_to_active_graph,
            parent=self,
        ).exec()

    def _add_curve_to_active_graph(self, sheet, name, x, y) -> None:
        graph = self._active_graph()
        if graph is None or sheet is None:
            QMessageBox.information(
                self, "No graph", "Create or open a graph tab first."
            )
            return
        source = sheet_label(self.project, sheet)
        xname = sheet.unique_column_name(f"{name}_X")
        yname = sheet.unique_column_name(f"{name}_Y")
        self.commands.push(
            MacroCommand(
                [
                    AddColumnCommand(
                        sheet, Column(xname, ColumnType.X, x), source=source
                    ),
                    AddColumnCommand(
                        sheet, Column(yname, ColumnType.Y, y), source=source
                    ),
                    AddPlotCommand(
                        graph,
                        graph.first_layer,
                        PlotSpec(source=source, x=xname, y=yname, legend=name),
                    ),
                ],
                label=f"Plot {name}",
            )
        )
        if self._active_graph_view is not None:
            self._active_graph_view.refresh()

    # -------------------------------------------------------------- export ops
    def _action_export_graph(self) -> None:
        graph = self._active_graph()
        if graph is None:
            QMessageBox.information(self, "No graph", "Open a graph first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Graph As", f"{graph.name}.pdf", GRAPH_FILTER
        )
        if not path:
            return
        path = _normalized_export_path(path)
        options = ExportGraphDialog(self)
        if not options.exec():
            return
        aspect, scale = self._export_geometry(options)
        try:
            export_graph(
                graph,
                self.project,
                path,
                width_mm=options.width.value(),
                height_mm=options.height.value(),
                dpi=options.dpi.value(),
                transparent=options.transparent.isChecked(),
                theme=current_preset(),
                aspect=aspect,
                scale=scale,
            )
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            QMessageBox.critical(self, "Export failed", f"{type(exc).__name__}: {exc}")
            return
        self.statusBar().showMessage(f"Exported {path}", 4000)

    def _action_export_all_graphs(self) -> None:
        if not self.project.graphs:
            QMessageBox.information(self, "No graphs", "This project has no graphs.")
            return
        directory = QFileDialog.getExistingDirectory(
            self, "Export All Graphs To Folder"
        )
        if not directory:
            return
        options = ExportGraphDialog(self)
        if not options.exec():
            return
        out_dir = Path(directory)
        exported = 0
        aspect, scale = self._export_geometry(options)
        for graph in self.project.graphs:
            target = out_dir / f"{graph.name}.pdf"
            try:
                export_graph(
                    graph,
                    self.project,
                    target,
                    width_mm=options.width.value(),
                    height_mm=options.height.value(),
                    dpi=options.dpi.value(),
                    transparent=options.transparent.isChecked(),
                    theme=current_preset(),
                    aspect=aspect,
                    scale=scale,
                )
                exported += 1
            except Exception as exc:  # noqa: BLE001
                self.statusBar().showMessage(f"Failed {graph.name}: {exc}", 6000)
        self.statusBar().showMessage(f"Exported {exported} graph(s) to {out_dir}", 5000)

    def _export_geometry(self, options) -> tuple[float | None, float]:
        """Aspect ratio and typography scale for an export.

        With "Match on-screen proportions" the file keeps the shape of the
        figure on screen and its typography, line widths and markers are
        scaled by the page/canvas ratio — that is what makes the export look
        like the preview instead of a differently sized page.
        """
        if not options.match_screen.isChecked():
            return None, 1.0
        view = self._active_graph_view
        if view is None or not hasattr(view, "canvas"):
            return None, 1.0
        try:
            widget = view.canvas.widget()
            figure = getattr(view.canvas, "_fig", None)
            toolbar = getattr(view.canvas, "_toolbar", None)
            width = widget.width()
            height = widget.height()
            if toolbar is not None:
                height -= toolbar.height()
            dpi = float(getattr(figure, "dpi", 0) or 0) or float(
                widget.logicalDpiX() or 96
            )
        except Exception:  # noqa: BLE001 - the view may be closing
            return None, 1.0
        if width <= 0 or height <= 0:
            return None, 1.0
        screen_w, screen_h = width / dpi, height / dpi
        aspect = screen_w / screen_h
        options.height.setValue(round(options.width.value() / aspect, 2))
        scale = (options.width.value() / 25.4) / screen_w
        return aspect, max(0.05, min(4.0, scale))

    def _action_export_sheet(self) -> None:
        sheet = self._current_sheet()
        if sheet is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Worksheet as CSV", f"{sheet.name}.csv", "CSV (*.csv)"
        )
        if not path:
            return
        export_delimited(sheet, path)
        self.statusBar().showMessage(f"Exported {path}", 4000)

    def _action_export_script(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Project as Python Script",
            f"{self.project.name}.py",
            "Python (*.py)",
        )
        if not path:
            return
        Path(path).write_text(project_to_script(self.project), encoding="utf-8")
        self.statusBar().showMessage(f"Exported script {path}", 4000)

    def _action_export_bundle(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Export Analysis Bundle To Folder"
        )
        if not directory:
            return
        try:
            bundle = export_analysis_bundle(self.project, self.provenance, directory)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            QMessageBox.critical(self, "Bundle failed", f"{type(exc).__name__}: {exc}")
            return
        counts = ", ".join(f"{len(v)} {k}" for k, v in bundle.files.items() if v)
        QMessageBox.information(
            self,
            "Analysis bundle",
            f"Wrote a reproducible bundle to:\n{bundle.root}\n\n{counts}",
        )
        self.statusBar().showMessage(f"Exported bundle to {bundle.root}", 6000)

    # --------------------------------------------------------------- tool ops
    def _toggle_console(self, *_args) -> None:
        self.dock_console.setVisible(self.registry.action("tools.console").isChecked())

    def _toggle_record(self, *_args) -> None:
        action = self.registry.action("tools.record")
        if action.isChecked():
            self.recorder.start()
            self.statusBar().showMessage("Recording macro…")
        else:
            self.recorder.stop()
            self.statusBar().showMessage(
                f"Stopped recording ({self.recorder.count} steps)", 4000
            )

    def _action_save_macro(self) -> None:
        if self.recorder.count == 0:
            QMessageBox.information(
                self,
                "Nothing recorded",
                "Enable Record Macro, make some edits, then save.",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Macro", "macro.py", "Python (*.py)"
        )
        if path:
            Path(path).write_text(self.recorder.script(), encoding="utf-8")
            self.statusBar().showMessage(f"Saved macro {path}", 4000)

    def _action_run_macro(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Run Script", "", "Python (*.py)")
        if not path:
            return
        self.console.set_project(self.project)
        self.dock_console.show()
        self.registry.action("tools.console").setChecked(True)
        self.console.run_script(Path(path).read_text(encoding="utf-8"))
        self.console.set_project(self.project)

    def _action_command_palette(self) -> None:
        palette = CommandPalette(self.registry, self)
        if palette.exec() and palette.selected_action:
            action = self.registry.action(palette.selected_action)
            if action.isEnabled():
                action.trigger()

    def _action_show_methods(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Analysis Methods")
        dialog.resize(640, 560)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit(self.provenance.methods_markdown(self.project))
        view.setReadOnly(True)
        view.setFont(QFont("monospace"))
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _action_about(self) -> None:
        from graphmatrix import __version__

        QMessageBox.about(
            self,
            "About GraphMatrix",
            f"<b>GraphMatrix</b> {__version__}<br>"
            "A cross-platform scientific data analysis and graphing GUI.<br><br>"
            "Milestones M1–M6: worksheets, graphs, analysis, export, scripting, batch.",
        )

    # ---------------------------------------------------------------- helpers
    def _current_workbook(self) -> Workbook | None:
        sel = self.project_panel.current_object()
        if isinstance(sel, Workbook):
            return sel
        if isinstance(sel, Column):
            sel = self._sheet_for_column(sel)
        if isinstance(sel, Worksheet):
            for book in self.project.workbooks:
                if sel in book.sheets:
                    return book
        return self.project.workbooks[0] if self.project.workbooks else None

    def _current_sheet(self) -> Worksheet | None:
        view = self.tabs.currentWidget()
        if isinstance(view, WorksheetView):
            return view.sheet
        sel = self.project_panel.current_object()
        if isinstance(sel, Column):
            sel = self._sheet_for_column(sel)
        if isinstance(sel, Worksheet):
            return sel
        book = self._current_workbook()
        return book.sheets[0] if book and book.sheets else None

    def _active_graph(self) -> Graph | None:
        if self._active_graph_view is not None:
            return self._active_graph_view.graph
        return self.project.graphs[0] if self.project.graphs else None

    # ------------------------------------------------------------------- tabs
    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        # Swap the graph side panels (Plot + Axes) to the active graph view.
        while self.axes_layout.count():
            item = self.axes_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        while self._plot_host_layout.count():
            item = self._plot_host_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        if isinstance(widget, GraphView):
            self._plot_host_layout.addWidget(widget.plot_panel)
            self.axes_layout.addWidget(widget.group_axis)
        if isinstance(widget, GraphView):
            self._active_graph_view = widget
            action = self.registry.action("graph.hover")
            action.blockSignals(True)
            action.setChecked(widget.hover_enabled)
            action.blockSignals(False)
            self._sync_journal_actions(widget.graph)
            self._sync_graph_type_actions(widget.graph)
        else:
            self._sync_graph_type_actions(
                self._active_graph_view.graph if self._active_graph_view else None
            )

    def _sync_journal_actions(self, graph: Graph | None) -> None:
        current = getattr(graph, "journal_preset", "") if graph is not None else ""
        for name, action in self._journal_actions.items():
            action.blockSignals(True)
            action.setChecked(name == current)
            action.blockSignals(False)

    def _on_graph_hover_changed(self, enabled: bool) -> None:
        action = self.registry.action("graph.hover")
        if action.isChecked() != enabled:
            action.blockSignals(True)
            action.setChecked(enabled)
            action.blockSignals(False)

    # -- linked brushing -----------------------------------------------------
    def _on_brush_requested(self, source: str, rows: list) -> None:
        """Graph clicks and sheet selections both funnel through the brush."""
        self.brush.set(source, rows)

    def _apply_brush(self, source: str, rows: list) -> None:
        """Broadcast the shared selection to every open sheet and graph tab."""
        for view in self._views.values():
            if isinstance(view, WorksheetView):
                view.set_row_highlight(rows if view.source == source else [])
            elif isinstance(view, GraphView):
                view.apply_brush(source, rows)

    def _on_object_activated(self, obj) -> None:
        if isinstance(obj, Worksheet):
            self._open_sheet_tab(obj)
        elif isinstance(obj, Graph):
            self._open_graph_tab(obj)
        elif isinstance(obj, Workbook) and obj.sheets:
            self._open_sheet_tab(obj.sheets[0])

    def _open_sheet_tab(self, sheet: Worksheet) -> None:
        view = self._views.get(id(sheet))
        if view is not None:
            self.tabs.setCurrentWidget(view)
            return
        view = WorksheetView(sheet, self.commands, sheet_label(self.project, sheet))
        view.plot_column_requested.connect(
            lambda name, s=sheet: self._plot_column(sheet_label(self.project, s), name)
        )
        view.rows_selected.connect(self._on_brush_requested)
        self._views[id(sheet)] = view
        self.tabs.addTab(view, sheet.name)
        # If the brush already points at this sheet, tint it on arrival.
        view.set_row_highlight(self.brush.get(view.source))
        self.tabs.setCurrentWidget(view)

    def _open_graph_tab(self, graph: Graph) -> None:
        view = self._views.get(id(graph))
        if view is not None:
            self.tabs.setCurrentWidget(view)
            self._active_graph_view = view
            return
        view = GraphView(graph, self.project, self.commands, on_change=self._mark_dirty)
        view.hover_changed.connect(self._on_graph_hover_changed)
        view.brush_requested.connect(self._on_brush_requested)
        self._views[id(graph)] = view
        self.tabs.addTab(view, graph.name)
        self.tabs.setCurrentWidget(view)
        self._active_graph_view = view
        self._sync_journal_actions(graph)

    def _refresh_open_views(self) -> None:
        for view in self._views.values():
            if isinstance(view, WorksheetView):
                view.populate()
            elif isinstance(view, GraphView):
                view.refresh()

    def _on_tab_closed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        for key, value in list(self._views.items()):
            if value is widget:
                del self._views[key]
                if value is self._active_graph_view:
                    self._active_graph_view = None
                break

    def _close_all_tabs(self) -> None:
        self.tabs.clear()
        self._views.clear()
        self._active_graph_view = None

    # ---------------------------------------------------------------- plugins
    def _load_plugins(self) -> None:
        from graphmatrix.plugins.loader import PluginContext, load_plugins

        context = PluginContext(
            window=self,
            registry=self.registry,
            commands=self.commands,
            plugins_menu=self.plugins_menu,
        )
        self._plugins = load_plugins(context)
        failed = [p for p in self._plugins if not p.ok]
        if failed:
            self.statusBar().showMessage(
                "Plugin errors: " + ", ".join(f"{p.name} ({p.error})" for p in failed),
                10000,
            )

    # ----------------------------------------------------------------- events
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self.confirm_on_close or self._confirm_discard():
            unregister_instance()
            event.accept()
        else:
            event.ignore()
