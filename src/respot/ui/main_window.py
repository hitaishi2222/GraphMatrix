"""The main application window: docks, tabs, menus, and workflow wiring."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from respot.core.commands import (
    AddColumnCommand,
    AddGraphCommand,
    AddPlotCommand,
    AddWorkbookCommand,
    AddWorksheetCommand,
    CommandStack,
    MacroCommand,
)
from respot.core.io import export_delimited, import_file, supported_extensions
from respot.core.io.export import export_graph
from respot.core.model import Column, ColumnType, Graph, PlotSpec, Project, Workbook, Worksheet
from respot.core.plotting import make_default_graph
from respot.core.scripting.record import MacroRecorder
from respot.ui.actions import ActionRegistry, ActionSpec
from respot.ui.analysis_dialogs import (
    AnalysisResultDialog,
    DescriptiveDialog,
    FitDialog,
    PeaksDialog,
    RegressionDialog,
    SignalDialog,
    StatisticsDialog,
)
from respot.ui.console import ConsoleView
from respot.ui.graph_view import GraphView
from respot.ui.project_panel import ProjectPanel
from respot.ui.properties_panel import PropertiesPanel
from respot.ui.widgets import sheet_label
from respot.ui.worksheet_view import WorksheetView

APP_TITLE = "Respot"
PROJECT_FILTER = "Respot Project (*.rsproj);;All Files (*)"
GRAPH_FILTER = "PDF (*.pdf);;SVG (*.svg);;EPS (*.eps);;PNG (*.png);;TIFF (*.tif);;All Files (*)"

_DATA_FILTER = "Data files (" + " ".join(f"*{e}" for e in supported_extensions()) + ");;All Files (*)"


class ExportGraphDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Graph")
        self.width = QDoubleSpinBox(); self.width.setRange(10, 500); self.width.setValue(100.0); self.width.setSuffix(" mm")
        self.height = QDoubleSpinBox(); self.height.setRange(10, 500); self.height.setValue(75.0); self.height.setSuffix(" mm")
        self.dpi = QSpinBox(); self.dpi.setRange(72, 1200); self.dpi.setValue(300)
        form = QFormLayout()
        form.addRow("Width:", self.width)
        form.addRow("Height:", self.height)
        form.addRow("DPI:", self.dpi)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self, project: Project | None = None) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1360, 860)

        self.project: Project = project or Project()
        self.commands = CommandStack()
        self.registry = ActionRegistry(self)
        self.recorder = MacroRecorder(self.commands)
        self._path: Path | None = None
        self._dirty = False
        self.confirm_on_close = True
        self._views: dict[int, QWidget] = {}
        self._active_graph_view: GraphView | None = None
        self._plugins: list = []

        self._build_docks()
        self._build_central()
        self._register_actions()
        menus = self.registry.build_menus(
            self.menuBar(), order=["File", "Edit", "Data", "Graph", "Analyze", "Export", "Tools", "Help"]
        )
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
        dock_props = QDockWidget("Properties", self)
        dock_props.setObjectName("dock.properties")
        dock_props.setWidget(self.properties_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_props)
        self.dock_properties = dock_props

        self.project_panel = ProjectPanel()
        self.project_panel.object_activated.connect(self._on_object_activated)
        self.project_panel.selection_changed.connect(self.properties_panel.show_object)
        dock_project = QDockWidget("Project Explorer", self)
        dock_project.setObjectName("dock.project")
        dock_project.setWidget(self.project_panel)
        dock_project.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_project)
        self.dock_project = dock_project

        self.console = ConsoleView(self.project, self.commands)
        dock_console = QDockWidget("Python Console", self)
        dock_console.setObjectName("dock.console")
        dock_console.setWidget(self.console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock_console)
        dock_console.hide()
        self.dock_console = dock_console

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
        self.addToolBar(toolbar)
        for action_id in (
            "file.new", "file.open", "file.save", "file.import",
            "edit.undo", "edit.redo",
            "data.add_workbook", "data.add_worksheet", "data.add_graph", "data.sample",
            "analyze.fit",
        ):
            toolbar.addAction(self.registry.action(action_id))
        self.toolbar = toolbar

    def _register_actions(self) -> None:
        r = self.registry
        file_actions = [
            ("file.new", "New Project", "Ctrl+N", self._action_new, False),
            ("file.open", "Open Project...", "Ctrl+O", self._action_open, False),
            ("file.save", "Save Project", "Ctrl+S", self._action_save, False),
            ("file.save_as", "Save Project As...", "Ctrl+Shift+S", self._action_save_as, False),
            ("file.import", "Import Data...", "Ctrl+I", self._action_import, True),
            ("file.exit", "Exit", "Ctrl+Q", self.close, True),
        ]
        for action_id, text, shortcut, slot, sep in file_actions:
            r.register(ActionSpec(action_id, text, shortcut, menu="File", separator_before=sep), slot)

        r.register(ActionSpec("edit.undo", "Undo", "Ctrl+Z", menu="Edit"), self._action_undo, enabled=False)
        r.register(ActionSpec("edit.redo", "Redo", "Ctrl+Shift+Z", menu="Edit"), self._action_redo, enabled=False)

        for action_id, text, slot, sep in (
            ("data.add_workbook", "Add Workbook", self._action_add_workbook, False),
            ("data.add_worksheet", "Add Worksheet", self._action_add_worksheet, False),
            ("data.add_graph", "Add Graph", self._action_add_graph, False),
            ("data.sample", "Add Sample Data", self._action_sample_data, True),
        ):
            r.register(ActionSpec(action_id, text, None, menu="Data", separator_before=sep), slot)

        for action_id, text, slot, sep in (
            ("graph.add_plot", "Add Plot to Active Graph", self._action_add_plot, False),
            ("graph.add_layer", "Add Layer", self._action_add_layer, False),
            ("graph.new_from_data", "New Graph From Data", self._action_add_graph, False),
            ("graph.export", "Export Active Graph...", self._action_export_graph, True),
        ):
            r.register(ActionSpec(action_id, text, None, menu="Graph", separator_before=sep), slot)

        for action_id, text, slot, sep in (
            ("analyze.descriptive", "Descriptive Statistics...", self._action_descriptive, False),
            ("analyze.regression", "Regression...", self._action_regression, False),
            ("analyze.fit", "Nonlinear Fit...", self._action_fit, False),
            ("analyze.peaks", "Peak Analysis...", self._action_peaks, True),
            ("analyze.signal", "Signal Processing...", self._action_signal, False),
            ("analyze.statistics", "Statistics / t-test / ANOVA...", self._action_statistics, False),
        ):
            r.register(ActionSpec(action_id, text, None, menu="Analyze", separator_before=sep), slot)

        r.register(ActionSpec("export.graph", "Export Active Graph...", None, menu="Export"), self._action_export_graph)
        r.register(ActionSpec("export.sheet", "Export Worksheet as CSV...", None, menu="Export"), self._action_export_sheet)

        r.register(ActionSpec("tools.console", "Python Console", None, menu="Tools", checkable=True), self._toggle_console)
        r.register(ActionSpec("tools.record", "Record Macro", None, menu="Tools", checkable=True, separator_before=True), self._toggle_record)
        r.register(ActionSpec("tools.save_macro", "Save Recorded Macro...", None, menu="Tools"), self._action_save_macro)
        r.register(ActionSpec("tools.run_macro", "Run Script...", None, menu="Tools"), self._action_run_macro)
        r.register(ActionSpec("tools.batch", "Batch Import...", None, menu="Tools", separator_before=True), self._action_batch_import)

        r.register(ActionSpec("help.about", "About Respot", None, menu="Help"), self._action_about)

    # ------------------------------------------------------------- project ops
    def _set_project(self, project: Project, path: Path | None) -> None:
        self.project = project
        self._path = path
        self.commands.clear()
        self._close_all_tabs()
        self._refresh()
        self.console.set_project(project)
        self._set_dirty(False)

    def _refresh(self) -> None:
        self.project_panel.set_project(self.project)
        self._update_title()

    def _update_title(self) -> None:
        mark = " *" if self._dirty else ""
        location = f"  —  {self._path}" if self._path else ""
        self.setWindowTitle(f"{self.project.name}{mark}{location}  —  {APP_TITLE}")

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
            self, "Unsaved changes",
            "The current project has unsaved changes.\nSave before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
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
        if not path:
            return
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
        path, _ = QFileDialog.getSaveFileName(self, "Save Project As", default, PROJECT_FILTER)
        if not path:
            return False
        if not path.endswith(".rsproj"):
            path += ".rsproj"
        self._path = Path(path)
        return self._action_save()

    def _action_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Data", "", _DATA_FILTER)
        if not path:
            return
        try:
            book = import_file(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import failed", f"Could not import:\n{exc}")
            return
        book.name = self.project.unique_name(book.name)
        self.commands.push(AddWorkbookCommand(self.project, book))
        if book.sheets:
            self._open_sheet_tab(book.sheets[0])
        self.statusBar().showMessage(f"Imported {path}", 4000)

    def _action_batch_import(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Batch Import", "", _DATA_FILTER)
        if not paths:
            return
        commands = []
        for path in paths:
            try:
                book = import_file(path)
            except Exception as exc:  # noqa: BLE001
                self.statusBar().showMessage(f"Skipped {path}: {exc}", 6000)
                continue
            book.name = self.project.unique_name(book.name)
            commands.append(AddWorkbookCommand(self.project, book))
        if commands:
            self.commands.push(MacroCommand(commands, f"Batch Import ({len(commands)})"))
            self.statusBar().showMessage(f"Imported {len(commands)} file(s)", 5000)

    # ---------------------------------------------------------------- edit ops
    def _action_undo(self) -> None:
        self.commands.undo()

    def _action_redo(self) -> None:
        self.commands.redo()

    def _on_stack_changed(self) -> None:
        undo = self.registry.action("edit.undo")
        redo = self.registry.action("edit.redo")
        undo.setEnabled(self.commands.can_undo)
        redo.setEnabled(self.commands.can_redo)
        undo.setText(f"Undo {self.commands.undo_label}".strip())
        redo.setText(f"Redo {self.commands.redo_label}".strip())
        if self.project is not None:
            self.project_panel.set_project(self.project)
            self._refresh_open_views()
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

    def _action_add_graph(self) -> None:
        graph = make_default_graph(self.project, self.project.unique_name("Graph"))
        self.commands.push(AddGraphCommand(self.project, graph))
        self._open_graph_tab(graph)

    def _action_add_plot(self) -> None:
        if self._active_graph_view is None:
            QMessageBox.information(self, "No graph", "Open or create a graph first.")
            return
        self._active_graph_view.add_plot()

    def _action_add_layer(self) -> None:
        if self._active_graph_view is not None:
            self._active_graph_view.add_layer()

    def _action_sample_data(self) -> None:
        sheet = self._current_sheet()
        if sheet is None:
            QMessageBox.information(self, "No worksheet", "Create a workbook and worksheet first.")
            return
        source = sheet_label(self.project, sheet)
        x = np.linspace(0.0, 2.0 * np.pi, 200)
        self.commands.push(MacroCommand(
            [
                AddColumnCommand(sheet, Column(sheet.next_column_name(ColumnType.X), ColumnType.X, x, units="rad"), source=source),
                AddColumnCommand(sheet, Column(sheet.next_column_name(ColumnType.Y), ColumnType.Y, np.sin(x), comment="sin(x)"), source=source),
            ],
            label="Add Sample Data",
        ))
        self._open_sheet_tab(sheet)

    # ------------------------------------------------------------- analyze ops
    def _run_dialog(self, dialog) -> None:
        if dialog.exec():
            result = dialog.run()
            AnalysisResultDialog(
                result, project=self.project, commands=self.commands,
                default_sheet=dialog.sheet(), add_to_graph=self._add_curve_to_active_graph, parent=self,
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

    def _action_signal(self) -> None:
        if self.project.workbooks:
            self._run_dialog(SignalDialog(self.project, self))

    def _action_statistics(self) -> None:
        if self.project.workbooks:
            self._run_dialog(StatisticsDialog(self.project, self))

    def _add_curve_to_active_graph(self, sheet, name, x, y) -> None:
        graph = self._active_graph()
        if graph is None or sheet is None:
            QMessageBox.information(self, "No graph", "Create or open a graph tab first.")
            return
        source = sheet_label(self.project, sheet)
        xname = sheet.unique_column_name(f"{name}_X")
        yname = sheet.unique_column_name(f"{name}_Y")
        self.commands.push(MacroCommand(
            [
                AddColumnCommand(sheet, Column(xname, ColumnType.X, x), source=source),
                AddColumnCommand(sheet, Column(yname, ColumnType.Y, y), source=source),
                AddPlotCommand(graph, graph.first_layer, PlotSpec(source=source, x=xname, y=yname, legend=name)),
            ],
            label=f"Plot {name}",
        ))
        if self._active_graph_view is not None:
            self._active_graph_view.refresh()

    # -------------------------------------------------------------- export ops
    def _action_export_graph(self) -> None:
        graph = self._active_graph()
        if graph is None:
            QMessageBox.information(self, "No graph", "Open a graph first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Graph As", f"{graph.name}.pdf", GRAPH_FILTER)
        if not path:
            return
        options = ExportGraphDialog(self)
        if not options.exec():
            return
        try:
            export_graph(graph, self.project, path, width_mm=options.width.value(),
                         height_mm=options.height.value(), dpi=options.dpi.value())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {path}", 4000)

    def _action_export_sheet(self) -> None:
        sheet = self._current_sheet()
        if sheet is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Worksheet as CSV", f"{sheet.name}.csv", "CSV (*.csv)")
        if not path:
            return
        export_delimited(sheet, path)
        self.statusBar().showMessage(f"Exported {path}", 4000)

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
            self.statusBar().showMessage(f"Stopped recording ({self.recorder.count} steps)", 4000)

    def _action_save_macro(self) -> None:
        if self.recorder.count == 0:
            QMessageBox.information(self, "Nothing recorded", "Enable Record Macro, make some edits, then save.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Macro", "macro.py", "Python (*.py)")
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

    def _action_about(self) -> None:
        from respot import __version__

        QMessageBox.about(
            self, "About Respot",
            f"<b>Respot</b> {__version__}<br>"
            "A cross-platform scientific data analysis and graphing GUI.<br><br>"
            "Milestones M1–M6: worksheets, graphs, analysis, export, scripting, batch.",
        )

    # ---------------------------------------------------------------- helpers
    def _current_workbook(self) -> Workbook | None:
        sel = self.project_panel.current_object()
        if isinstance(sel, Workbook):
            return sel
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
        if isinstance(widget, GraphView):
            self._active_graph_view = widget

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
        self._views[id(sheet)] = view
        self.tabs.addTab(view, sheet.name)
        self.tabs.setCurrentWidget(view)

    def _open_graph_tab(self, graph: Graph) -> None:
        view = self._views.get(id(graph))
        if view is not None:
            self.tabs.setCurrentWidget(view)
            self._active_graph_view = view
            return
        view = GraphView(graph, self.project, self.commands, on_change=self._mark_dirty)
        self._views[id(graph)] = view
        self.tabs.addTab(view, graph.name)
        self.tabs.setCurrentWidget(view)
        self._active_graph_view = view

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
        from respot.plugins.loader import PluginContext, load_plugins

        context = PluginContext(window=self, registry=self.registry, commands=self.commands, plugins_menu=self.plugins_menu)
        self._plugins = load_plugins(context)
        failed = [p for p in self._plugins if not p.ok]
        if failed:
            self.statusBar().showMessage("Plugin errors: " + ", ".join(f"{p.name} ({p.error})" for p in failed), 10000)

    # ----------------------------------------------------------------- events
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self.confirm_on_close or self._confirm_discard():
            event.accept()
        else:
            event.ignore()
