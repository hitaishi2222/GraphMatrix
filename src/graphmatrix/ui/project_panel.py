"""Project Explorer: a tree of project → workbook → sheet → column / graph.

Columns are draggable: dropping one onto a graph view plots it (X columns pair with
the sheet's first Y, Y columns with the first X).
"""

from __future__ import annotations

import json

from PySide6.QtCore import QByteArray, QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from graphmatrix.core.model import (
    GRAPH_TYPES,
    GRAPH_TYPE_LABELS,
    Column,
    Graph,
    Project,
    Workbook,
    Worksheet,
    graph_type_label,
)
from graphmatrix.ui.icons import lucide_icon
from graphmatrix.ui.widgets import COLUMN_MIME

_ROLE_OBJ = Qt.ItemDataRole.UserRole + 1
_ROLE_DRAG = Qt.ItemDataRole.UserRole + 2


class _ProjectTree(QTreeWidget):
    """A tree that advertises a custom MIME payload for column drags."""

    def mimeTypes(self) -> list[str]:
        return list(super().mimeTypes()) + [COLUMN_MIME]

    def mimeData(self, items):  # type: ignore[override]
        data = super().mimeData(items)
        for item in items:
            payload = item.data(0, _ROLE_DRAG)
            if payload:
                data.setData(
                    COLUMN_MIME, QByteArray(json.dumps(payload).encode("utf-8"))
                )
                break
        return data


class ProjectPanel(QWidget):
    """Docked tree view of the project structure."""

    object_activated = Signal(object)  # double-clicked
    selection_changed = Signal(object)  # current selection (may be None)
    rename_requested = Signal(object)  # "Rename…" chosen for an object
    delete_requested = Signal(object)  # "Delete …" chosen for an object
    #: (kind, detail) — kind is "workbook" | "worksheet" | "graph"; for a
    #: graph, detail is the graph-type value ("stack", "grid", …) or "".
    add_requested = Signal(str, str)
    graph_type_requested = Signal(object, str)  # (graph, graph-type value)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        #: True while the tree rebuilds itself, so the restored selection does
        #: not look like a user click (which would switch the active tab).
        self._restoring = False
        #: Keep Python references to context-menu submenus; PySide otherwise
        #: deletes them when the local wrapper is garbage-collected.
        self._menu_refs: list[QMenu] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self.tree = _ProjectTree()
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setDragEnabled(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.installEventFilter(self)
        self.tree.viewport().installEventFilter(self)
        layout.addWidget(self.tree)

    # -- public API ----------------------------------------------------------
    def set_project(self, project: Project | None) -> None:
        self._project = project
        self.refresh()

    def current_object(self):
        item = self.tree.currentItem()
        return item.data(0, _ROLE_OBJ) if item is not None else None

    def refresh(self) -> None:
        # Keep the selection across a rebuild: the tree is rebuilt after
        # every edit, and losing the selection would empty the Properties
        # panel and switch the canvas away from the object being edited.
        selected = self.current_object()
        self._restoring = True
        self.tree.clear()
        if self._project is None:
            self._restoring = False
            return

        project_item = QTreeWidgetItem([self._project.name])
        project_item.setData(0, _ROLE_OBJ, self._project)
        project_item.setIcon(0, lucide_icon("database", "project"))
        self.tree.addTopLevelItem(project_item)

        for book in self._project.workbooks:
            book_item = QTreeWidgetItem([book.name])
            book_item.setData(0, _ROLE_OBJ, book)
            book_item.setIcon(0, lucide_icon("folder", "workbook"))
            project_item.addChild(book_item)
            for sheet in book.sheets:
                sheet_item = QTreeWidgetItem(
                    [f"{sheet.name}  ({sheet.num_rows}×{sheet.num_columns})"]
                )
                sheet_item.setData(0, _ROLE_OBJ, sheet)
                sheet_item.setIcon(0, lucide_icon("file-text", "sheet"))
                book_item.addChild(sheet_item)
                for column in sheet.columns:
                    col_item = QTreeWidgetItem(
                        [f"{column.name}  [{column.col_type.value}]"]
                    )
                    col_item.setData(0, _ROLE_OBJ, column)
                    col_item.setIcon(0, lucide_icon("columns", "column"))
                    col_item.setData(
                        0,
                        _ROLE_DRAG,
                        {
                            "source": f"{book.name}/{sheet.name}",
                            "column": column.name,
                        },
                    )
                    sheet_item.addChild(col_item)

        for graph in self._project.graphs:
            graph_item = QTreeWidgetItem(
                [f"{graph.name}  [{graph_type_label(graph.graph_type)}]"]
            )
            graph_item.setData(0, _ROLE_OBJ, graph)
            graph_item.setIcon(0, lucide_icon("line-chart", "graph"))
            project_item.addChild(graph_item)

        project_item.setExpanded(True)
        for i in range(project_item.childCount()):
            child = project_item.child(i)
            child.setExpanded(True)
            for j in range(child.childCount()):
                child.child(j).setExpanded(True)

        if selected is not None:
            item = self._find_item(selected)
            if item is not None:
                self.tree.setCurrentItem(item)
        self._restoring = False

    def select_object(self, obj) -> None:
        """Select ``obj`` in the tree without reacting to the selection.

        Used to keep the tree in step with the active tab, so the tree, the
        Properties panel and the canvas always talk about the same object.
        """
        if obj is None:
            return
        item = self._find_item(obj)
        if item is None:
            return
        self._restoring = True
        try:
            self.tree.setCurrentItem(item)
        finally:
            self._restoring = False

    def _find_item(self, obj) -> QTreeWidgetItem | None:
        """The tree item that stands for ``obj`` (by identity)."""
        root = self.tree.invisibleRootItem()
        for index in range(root.childCount()):
            item = root.child(index)
            found = self._find_item_in(item, obj)
            if found is not None:
                return found
        return None

    @staticmethod
    def _find_item_in(item: QTreeWidgetItem, obj) -> QTreeWidgetItem | None:
        if item.data(0, _ROLE_OBJ) is obj:
            return item
        for index in range(item.childCount()):
            found = ProjectPanel._find_item_in(item.child(index), obj)
            if found is not None:
                return found
        return None

    # -- internals -----------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        """Catch F2 in the tree.

        The tree view swallows the key (it tries to edit the item), so the
        application-wide "Rename…" action never sees it. Renaming is handled
        right here instead.
        """
        if (
            obj in (self.tree, self.tree.viewport())
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_F2
        ):
            self.rename_requested.emit(self.current_object())
            return True
        return False

    def build_context_menu(self, obj) -> QMenu:
        """Build the right-click menu for ``obj`` (also used by the tests)."""
        menu = QMenu(self.tree)
        if obj is None:
            return menu
        if isinstance(obj, (Graph, Worksheet)):
            menu.addAction("Open", lambda: self.object_activated.emit(obj))
        if getattr(obj, "name", None) is not None:
            menu.addAction("Rename…", lambda: self.rename_requested.emit(obj))

        type_menu = None
        if isinstance(obj, Graph):
            type_menu = menu.addMenu("Graph Type")
            for gtype in GRAPH_TYPES:
                action = type_menu.addAction(
                    GRAPH_TYPE_LABELS[gtype.value],
                    lambda _checked=False, value=gtype.value: (
                        self.graph_type_requested.emit(obj, value)
                    ),
                )
                action.setCheckable(True)
                action.setChecked(gtype.value == obj.graph_type)

        add_menu = menu.addMenu("Add")
        add_menu.addAction(
            "New Workbook", lambda: self.add_requested.emit("workbook", "")
        )
        add_menu.addAction(
            "New Worksheet", lambda: self.add_requested.emit("worksheet", "")
        )
        graph_menu = add_menu.addMenu("New Graph")
        for gtype in GRAPH_TYPES:
            graph_menu.addAction(
                GRAPH_TYPE_LABELS[gtype.value],
                lambda _checked=False, value=gtype.value: self.add_requested.emit(
                    "graph", value
                ),
            )

        delete_label = self._delete_label(obj)
        if delete_label:
            menu.addSeparator()
            menu.addAction(delete_label, lambda: self.delete_requested.emit(obj))
        self._menu_refs = [menu, add_menu, graph_menu] + (
            [type_menu] if type_menu is not None else []
        )
        #: Direct references for callers/tests that inspect the submenus.
        self.context_add_menu = add_menu
        self.context_graph_menu = graph_menu
        self.context_type_menu = type_menu
        return menu

    def _on_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is not None:
            self.tree.setCurrentItem(item)
        # Right-clicking empty space still offers "Add …" at project level.
        obj = item.data(0, _ROLE_OBJ) if item is not None else self._project
        if obj is None:
            return
        menu = self.build_context_menu(obj)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    @staticmethod
    def _delete_label(obj) -> str:
        if isinstance(obj, Graph):
            return "Delete Graph"
        if isinstance(obj, Workbook):
            return "Delete Workbook"
        if isinstance(obj, Worksheet):
            return "Delete Worksheet"
        if isinstance(obj, Column):
            return "Delete Column"
        return ""  # the project itself cannot be deleted

    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        obj = item.data(0, _ROLE_OBJ)
        if obj is not None:
            self.object_activated.emit(obj)

    def _on_selection_changed(self) -> None:
        if self._restoring:
            # The tree rebuilt itself and restored the selection; that is
            # not a user click, so nothing else may react to it.
            return
        self.selection_changed.emit(self.current_object())
