"""Project Explorer: a tree of project → workbook → sheet → graph."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QStyle, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from respot.core.model import Graph, Project, Workbook, Worksheet

_ROLE_OBJ = Qt.ItemDataRole.UserRole + 1


class ProjectPanel(QWidget):
    """Docked tree view of the project structure."""

    object_activated = Signal(object)  # double-clicked
    selection_changed = Signal(object)  # current selection (may be None)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.tree)

    # -- public API ----------------------------------------------------------
    def set_project(self, project: Project | None) -> None:
        self._project = project
        self.refresh()

    def current_object(self):
        item = self.tree.currentItem()
        return item.data(0, _ROLE_OBJ) if item is not None else None

    def refresh(self) -> None:
        self.tree.clear()
        if self._project is None:
            return

        project_item = QTreeWidgetItem([self._project.name])
        project_item.setData(0, _ROLE_OBJ, self._project)
        self.tree.addTopLevelItem(project_item)

        for book in self._project.workbooks:
            book_item = QTreeWidgetItem([book.name])
            book_item.setData(0, _ROLE_OBJ, book)
            book_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            project_item.addChild(book_item)
            for sheet in book.sheets:
                sheet_item = QTreeWidgetItem([f"{sheet.name}  ({sheet.num_rows}×{sheet.num_columns})"])
                sheet_item.setData(0, _ROLE_OBJ, sheet)
                sheet_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                book_item.addChild(sheet_item)

        for graph in self._project.graphs:
            graph_item = QTreeWidgetItem([graph.name])
            graph_item.setData(0, _ROLE_OBJ, graph)
            graph_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            project_item.addChild(graph_item)

        project_item.setExpanded(True)
        for i in range(project_item.childCount()):
            project_item.child(i).setExpanded(True)

    # -- internals -----------------------------------------------------------
    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        obj = item.data(0, _ROLE_OBJ)
        if obj is not None:
            self.object_activated.emit(obj)

    def _on_selection_changed(self) -> None:
        self.selection_changed.emit(self.current_object())
