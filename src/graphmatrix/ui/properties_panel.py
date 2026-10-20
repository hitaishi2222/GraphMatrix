"""Properties inspector for the currently selected model object."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from graphmatrix.core.model import (
    Column,
    Graph,
    GraphType,
    Project,
    Workbook,
    Worksheet,
    graph_type_label,
)

#: Graph layout rows that can be edited directly in the inspector.
_GRAPH_EDITABLE_KEYS = {
    "Graph type",
    "Grid rows",
    "Grid cols",
    "Panel gap X (%)",
    "Panel gap Y (%)",
    "Y delta",
}


class PropertiesPanel(QWidget):
    """A property grid with editable Name and graph-layout fields."""

    rename_requested = Signal(object, str)  # (object, new_name)
    #: (object, displayed property key, raw text) for an edited graph field.
    property_changed = Signal(object, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self._obj = None
        self._loading = False

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Property", "Value"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table)

        # Without a selection the table would be an empty box with a header
        # and nothing in it; this says what to do instead.
        self._hint = QLabel(
            "Select a project, workbook, worksheet, column or graph in the\n"
            "Project Explorer to see its properties here."
        )
        self._hint.setWordWrap(True)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._hint.setContentsMargins(8, 10, 8, 8)
        layout.addWidget(self._hint)
        layout.setStretch(0, 1)
        # A fresh panel shows the hint, not an empty table.
        self._table.setVisible(False)
        self._hint.setVisible(True)

    def show_object(self, obj) -> None:
        self._obj = obj
        rows = self._describe(obj) if obj is not None else []
        self._loading = True
        try:
            self._table.setRowCount(len(rows))
            for row, (key, value) in enumerate(rows):
                key_item = QTableWidgetItem(key)
                key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                value_item = QTableWidgetItem(str(value))
                editable = key == "Name" or (
                    isinstance(obj, Graph) and key in _GRAPH_EDITABLE_KEYS
                )
                if editable:
                    value_item.setFlags(value_item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    value_item.setFlags(
                        value_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                    )
                self._table.setItem(row, 0, key_item)
                self._table.setItem(row, 1, value_item)
        finally:
            self._loading = False
        self._hint.setVisible(obj is None)
        self._table.setVisible(obj is not None)

    # -- internals -----------------------------------------------------------
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or self._obj is None or item.column() != 1:
            return
        key_item = self._table.item(item.row(), 0)
        if key_item is None:
            return
        key = key_item.text()
        if key == "Name":
            self.rename_requested.emit(self._obj, item.text())
        elif isinstance(self._obj, Graph) and key in _GRAPH_EDITABLE_KEYS:
            self.property_changed.emit(self._obj, key, item.text())

    @staticmethod
    def _describe(obj) -> list[tuple[str, object]]:
        rows: list[tuple[str, object]] = [
            ("Type", type(obj).__name__),
            ("Name", getattr(obj, "name", "")),
        ]
        if isinstance(obj, Project):
            rows += [("Workbooks", len(obj.workbooks)), ("Graphs", len(obj.graphs))]
        elif isinstance(obj, Workbook):
            rows += [("Worksheets", obj.num_sheets)]
        elif isinstance(obj, Worksheet):
            rows += [("Columns", obj.num_columns), ("Rows", obj.num_rows)]
        elif isinstance(obj, Graph):
            rows += PropertiesPanel._describe_graph(obj)
        elif isinstance(obj, Column):
            rows += [
                ("Type", obj.col_type.value),
                ("Units", obj.units),
                ("Comment", obj.comment),
                ("Values", len(obj)),
            ]
        return rows

    @staticmethod
    def _describe_graph(obj: Graph) -> list[tuple[str, object]]:
        """Show only the layout properties that the current graph type uses."""
        try:
            gtype = GraphType(getattr(obj, "graph_type", GraphType.SIMPLE.value))
        except ValueError:
            gtype = GraphType.SIMPLE
        plots = sum(len(layer.plots) for layer in obj.layers)
        rows: list[tuple[str, object]] = [
            ("Graph type", graph_type_label(gtype)),
            ("Layers", obj.num_layers),
            ("Plots", plots),
        ]
        if gtype == GraphType.STACK:
            rows.append(("Y delta", f"{obj.y_delta:g}"))
        elif gtype == GraphType.X_TWIN:
            rows += [
                ("Panel gap X (%)", f"{obj.panel_gap_x:g}"),
                ("Y delta", f"{obj.y_delta:g}"),
            ]
        elif gtype == GraphType.GRID:
            rows += [
                ("Grid rows", obj.layout_rows),
                ("Grid cols", obj.layout_cols),
                ("Panel gap X (%)", f"{obj.panel_gap_x:g}"),
                ("Panel gap Y (%)", f"{obj.panel_gap_y:g}"),
            ]
        elif gtype == GraphType.DOUBLE_Y:
            right = sum(
                1
                for layer in obj.layers
                for spec in layer.plots
                if getattr(spec, "y_axis", "left") == "right"
            )
            rows.append(("Right-axis plots", right))
        return rows
