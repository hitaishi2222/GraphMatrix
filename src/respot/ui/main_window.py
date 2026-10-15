"""The main application window: docks, tabs, menus, and workflow wiring."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from respot.core.commands import (
    AddColumnCommand,
    AddWorkbookCommand,
    AddWorksheetCommand,
    CommandStack,
    MacroCommand,
    RemoveWorkbookCommand,
    RemoveWorksheetCommand,
)
from respot.core.model import Column, ColumnType, Graph, Project, Workbook, Worksheet
from respot.ui.actions import ActionRegistry, ActionSpec
from respot.ui.canvas import create_canvas
from respot.ui.project_panel import ProjectPanel
from respot.ui.properties_panel import PropertiesPanel
from respot.ui.worksheet_view import WorksheetView

APP_TITLE = "Respot"
PROJECT_FILTER = "Respot Project (*.rsproj);;All Files (*)"
# Keep export-only commands even though M0 doesn't use them yet: they document intent.
_ = (RemoveWorkbookCommand, RemoveWorksheetCommand)


class MainWindow(QMainWindow):
    def __init__(self, project: Project | None = None) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 820)

        self.project: Project = project or Project()
        self.commands = CommandStack()
        self.registry = ActionRegistry(self)
        self._path: Path | None = None
        self._dirty = False
        self._views: dict[int, QWidget] = {}  # id(model object) -> tab widget
        self._plugins: list = []

        self._build_docks()
        self._build_central()
        self._register_actions()
        menus = self.registry.build_menus(
            self.menuBar(), order=["File", "Edit", "Data", "Graph", "Help"]
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
        self.project_panel = ProjectPanel()
        self.project_panel.object_activated.connect(self._on_object_activated)
        self.project_panel.selection_changed.connect(self.properties_panel_show)
        dock_project = QDockWidget("Project Explorer", self)
        dock_project.setObjectName("dock.project")
        dock_project.setWidget(self.project_panel)
        dock_project.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_project)
        self.dock_project = dock_project

        self.properties_panel = PropertiesPanel()
        dock_props = QDockWidget("Properties", self)
        dock_props.setObjectName("dock.properties")
        dock_props.setWidget(self.properties_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_props)
        self.dock_properties = dock_props

    def _build_central(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_closed)
        self.setCentralWidget(self.tabs)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("toolbar.main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for action_id in (
            "file.new",
            "file.open",
            "file.save",
            "edit.undo",
            "edit.redo",
            "data.add_workbook",
            "data.add_worksheet",
            "data.add_graph",
            "data.sample",
        ):
            toolbar.addAction(self.registry.action(action_id))
        self.toolbar = toolbar

    def _register_actions(self) -> None:
        r = self.registry
        # File
        r.register(ActionSpec("file.new", "New Project", "Ctrl+N", menu="File"), self._action_new)
        r.register(ActionSpec("file.open", "Open Project...", "Ctrl+O", menu="File"), self._action_open)
        r.register(ActionSpec("file.save", "Save Project", "Ctrl+S", menu="File"), self._action_save)
        r.register(
            ActionSpec("file.save_as", "Save Project As...", "Ctrl+Shift+S", menu="File"),
            self._action_save_as,
        )
        r.register(ActionSpec("file.exit", "Exit", "Ctrl+Q", menu="File", separator_before=True), self.close)
        # Edit
        r.register(ActionSpec("edit.undo", "Undo", "Ctrl+Z", menu="Edit"), self._action_undo, enabled=False)
        r.register(ActionSpec("edit.redo", "Redo", "Ctrl+Shift+Z", menu="Edit"), self._action_redo, enabled=False)
        # Data
        r.register(ActionSpec("data.add_workbook", "Add Workbook", None, menu="Data"), self._action_add_workbook)
        r.register(ActionSpec("data.add_worksheet", "Add Worksheet", None, menu="Data"), self._action_add_worksheet)
        r.register(ActionSpec("data.add_graph", "Add Graph", None, menu="Data"), self._action_add_graph)
        r.register(
            ActionSpec("data.sample", "Add Sample Data", None, menu="Data", separator_before=True),
            self._action_sample_data,
        )
        # Help
        r.register(ActionSpec("help.about", "About Respot", None, menu="Help"), self._action_about)

    # ------------------------------------------------------------ toolbar chips
    def properties_panel_show(self, obj) -> None:
        self.properties_panel.show_object(obj)

    # ------------------------------------------------------------- project ops
    def _set_project(self, project: Project, path: Path | None) -> None:
        self.project = project
        self._path = path
        self.commands.clear()  # a new document starts with a clean history
        self._close_all_tabs()
        self._refresh()
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
        if not path:
            return
        try:
            project = Project.open(path)
        except Exception as exc:  # noqa: BLE001 - surface any load failure to the user
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
        sheet = Worksheet(book.next_sheet_name())
        self.commands.push(AddWorksheetCommand(book, sheet))

    def _action_add_graph(self) -> None:
        graph = Graph(self.project.unique_name("Graph"))
        self.project.add_graph(graph)
        self._set_dirty(True)
        self._refresh()
        self._open_graph_tab(graph)

    def _action_sample_data(self) -> None:
        sheet = self._current_sheet()
        if sheet is None:
            QMessageBox.information(self, "No worksheet", "Create a workbook and worksheet first.")
            return
        x = np.linspace(0.0, 2.0 * np.pi, 200)
        y = np.sin(x)
        self.commands.push(
            MacroCommand(
                [
                    AddColumnCommand(sheet, Column(sheet.next_column_name(ColumnType.X), ColumnType.X, x, units="rad")),
                    AddColumnCommand(sheet, Column(sheet.next_column_name(ColumnType.Y), ColumnType.Y, y, comment="sin(x)")),
                ],
                label="Add Sample Data",
            )
        )
        self._open_sheet_tab(sheet)

    def _action_about(self) -> None:
        from respot import __version__

        QMessageBox.about(
            self,
            "About Respot",
            f"<b>Respot</b> {__version__}<br>"
            "A cross-platform scientific data analysis and graphing GUI.<br><br>"
            "Milestone M0 — application skeleton.",
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
        sel = self.project_panel.current_object()
        if isinstance(sel, Worksheet):
            return sel
        book = self._current_workbook()
        return book.sheets[0] if book and book.sheets else None

    def _first_xy(self):
        """Find the first plottable X/Y pair anywhere in the project."""
        for book in self.project.workbooks:
            for sheet in book.sheets:
                xcol = next((c for c in sheet.columns if c.col_type == ColumnType.X and len(c)), None)
                ycol = next((c for c in sheet.columns if c.col_type == ColumnType.Y and len(c)), None)
                if xcol is not None and ycol is not None:
                    return xcol, ycol
        return None, None

    # ------------------------------------------------------------------- tabs
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
        view = WorksheetView(sheet)
        self._views[id(sheet)] = view
        self.tabs.addTab(view, sheet.name)
        self.tabs.setCurrentWidget(view)

    def _open_graph_tab(self, graph: Graph) -> None:
        view = self._views.get(id(graph))
        if view is not None:
            self.tabs.setCurrentWidget(view)
            return

        canvas = create_canvas()
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(canvas.widget())

        xcol, ycol = self._first_xy()
        if xcol is not None and ycol is not None:
            canvas.set_title(graph.name)
            canvas.plot_xy(list(xcol), list(ycol), name=ycol.name)
            canvas.set_labels(
                bottom=f"{xcol.name}" + (f" ({xcol.units})" if xcol.units else ""),
                left=f"{ycol.name}" + (f" ({ycol.units})" if ycol.units else ""),
            )
        else:
            canvas.set_title(f"{graph.name}  —  no X/Y data yet")

        self._views[id(graph)] = container
        self.tabs.addTab(container, graph.name)
        self.tabs.setCurrentWidget(container)

    def _refresh_open_views(self) -> None:
        for view in self._views.values():
            if isinstance(view, WorksheetView):
                view.populate()

    def _on_tab_closed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        for key, value in list(self._views.items()):
            if value is widget:
                del self._views[key]
                break

    def _close_all_tabs(self) -> None:
        self.tabs.clear()
        self._views.clear()

    # ---------------------------------------------------------------- plugins
    def _load_plugins(self) -> None:
        from respot.plugins.loader import PluginContext, load_plugins

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
                "Plugin errors: " + ", ".join(f"{p.name} ({p.error})" for p in failed), 10000
            )

    # ----------------------------------------------------------------- events
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
