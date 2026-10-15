"""Command pattern: undo/redo, and macro recording.

Every mutation of the model goes through a Command. The stack notifies
subscribers on any change (for UI refresh) and can emit each pushed command to a
recorder (for macro generation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from .model import (
    Column,
    ColumnType,
    Graph,
    Layer,
    PlotSpec,
    PlotStyle,
    Project,
    Workbook,
    Worksheet,
)


class Command(ABC):
    """A reversible action against the model."""

    label: str = "Command"

    @abstractmethod
    def execute(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    def undo(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def to_script(self) -> str | None:
        """Return an API call that reproduces this command, or None."""
        return None


class CommandStack:
    """An undo/redo stack with change and push notification."""

    def __init__(self, *, limit: int = 500) -> None:
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._listeners: list[Callable[[], None]] = []
        self._push_listeners: list[Callable[[Command], None]] = []
        self._limit = limit

    # -- notification --------------------------------------------------------
    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback) if callback in self._listeners else None

    def subscribe_push(self, callback: Callable[[Command], None]) -> Callable[[], None]:
        self._push_listeners.append(callback)
        return lambda: self._push_listeners.remove(callback) if callback in self._push_listeners else None

    def _notify(self) -> None:
        for callback in list(self._listeners):
            callback()

    # -- mutation ------------------------------------------------------------
    def push(self, command: Command, *, execute: bool = True) -> Command:
        if execute:
            command.execute()
        self._undo.append(command)
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()
        for callback in list(self._push_listeners):
            callback(command)
        self._notify()
        return command

    def undo(self) -> Command | None:
        if not self._undo:
            return None
        command = self._undo.pop()
        command.undo()
        self._redo.append(command)
        self._notify()
        return command

    def redo(self) -> Command | None:
        if not self._redo:
            return None
        command = self._redo.pop()
        command.execute()
        self._undo.append(command)
        self._notify()
        return command

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._notify()

    # -- state ---------------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_label(self) -> str:
        return self._undo[-1].label if self._undo else ""

    @property
    def redo_label(self) -> str:
        return self._redo[-1].label if self._redo else ""


def _script_array(values: np.ndarray) -> str:
    return repr(np.asarray(values).tolist())


# ---------------------------------------------------------------------------
# Structure commands
# ---------------------------------------------------------------------------


class AddWorkbookCommand(Command):
    label = "Add Workbook"

    def __init__(self, project: Project, workbook: Workbook) -> None:
        self._project, self._workbook = project, workbook

    def execute(self) -> None:
        self._project.add_workbook(self._workbook)

    def undo(self) -> None:
        self._project.remove_workbook(self._workbook)

    def to_script(self) -> str:
        name = self._workbook.name
        lines = [f"api.add_workbook({name!r})"]
        for sheet in self._workbook.sheets:
            lines.append(f"api.add_worksheet({name!r}, {sheet.name!r})")
            for column in sheet.columns:
                lines.append(_column_script(f"{name}/{sheet.name}", sheet.name, column))
        return "\n".join(lines)


class RemoveWorkbookCommand(Command):
    label = "Remove Workbook"

    def __init__(self, project: Project, workbook: Workbook) -> None:
        self._project, self._workbook = project, workbook
        self._index: int | None = None

    def execute(self) -> None:
        self._index = self._project.remove_workbook(self._workbook)

    def undo(self) -> None:
        self._project.add_workbook(self._workbook, index=self._index)


class AddWorksheetCommand(Command):
    label = "Add Worksheet"

    def __init__(self, workbook: Workbook, sheet: Worksheet) -> None:
        self._workbook, self._sheet = workbook, sheet

    def execute(self) -> None:
        self._workbook.add_sheet(self._sheet)

    def undo(self) -> None:
        self._workbook.remove_sheet(self._sheet)

    def to_script(self) -> str:
        return f"api.add_worksheet({self._workbook.name!r}, {self._sheet.name!r})"


class RemoveWorksheetCommand(Command):
    label = "Remove Worksheet"

    def __init__(self, workbook: Workbook, sheet: Worksheet) -> None:
        self._workbook, self._sheet = workbook, sheet
        self._index: int | None = None

    def execute(self) -> None:
        self._index = self._workbook.remove_sheet(self._sheet)

    def undo(self) -> None:
        self._workbook.add_sheet(self._sheet, index=self._index)


class AddColumnCommand(Command):
    label = "Add Column"

    def __init__(self, sheet: Worksheet, column: Column, *, index: int | None = None,
                 source: str | None = None) -> None:
        self._sheet, self._column, self._index = sheet, column, index
        self._source = source or sheet.name

    def execute(self) -> None:
        self._sheet.insert_column(self._column, index=self._index)

    def undo(self) -> None:
        self._sheet.remove_column(self._column)

    def to_script(self) -> str:
        return _column_script(self._source, self._sheet.name, self._column)


class RemoveColumnCommand(Command):
    label = "Remove Column"

    def __init__(self, sheet: Worksheet, column: Column) -> None:
        self._sheet, self._column = sheet, column
        self._index: int | None = None

    def execute(self) -> None:
        self._index = self._sheet.remove_column(self._column)

    def undo(self) -> None:
        self._sheet.insert_column(self._column, index=self._index)


class SetCellValueCommand(Command):
    label = "Edit Cell"

    def __init__(self, sheet: Worksheet, row: int, column_index: int, value: Any) -> None:
        self._sheet, self._row, self._column_index, self._value = sheet, row, column_index, value
        self._old: Any = None

    def execute(self) -> None:
        column = self._sheet.columns[self._column_index]
        self._old = column.get(self._row) if self._row < len(column) else None
        self._sheet.set_value(self._row, self._column_index, self._value)

    def undo(self) -> None:
        column = self._sheet.columns[self._column_index]
        if self._old is None:
            self._sheet.delete_rows(self._row)
        else:
            column.set(self._row, self._old)


class SetColumnInfoCommand(Command):
    label = "Edit Column"

    def __init__(self, sheet: Worksheet, column: Column, **fields: Any) -> None:
        self._sheet, self._column, self._fields = sheet, column, fields
        self._old: dict[str, Any] = {}

    def execute(self) -> None:
        for key, value in self._fields.items():
            self._old[key] = getattr(self._column, key)
            setattr(self._column, key, value)

    def undo(self) -> None:
        for key, value in self._old.items():
            setattr(self._column, key, value)


class SetAttributesCommand(Command):
    """Generic attribute setter for any model object (specs, layers, names)."""

    def __init__(self, target: Any, label: str = "Edit", **fields: Any) -> None:
        self._target, self._fields = target, fields
        self.label = label
        self._old: dict[str, Any] = {}

    def execute(self) -> None:
        for key, value in self._fields.items():
            self._old[key] = getattr(self._target, key)
            setattr(self._target, key, value)

    def undo(self) -> None:
        for key, value in self._old.items():
            setattr(self._target, key, value)


class SetColumnDataCommand(Command):
    label = "Set Column Data"

    def __init__(self, column: Column, data: Sequence[Any], label: str | None = None) -> None:
        self._column = column
        self._new = np.asarray(data)
        self._old = column.data.copy()
        if label:
            self.label = label

    def execute(self) -> None:
        self._column.data = self._new

    def undo(self) -> None:
        self._column.data = self._old


class RenameCommand(Command):
    label = "Rename"

    def __init__(self, target: Any, new_name: str) -> None:
        self._target, self._new = target, new_name
        self._old = getattr(target, "name", None)

    def execute(self) -> None:
        self._target.name = self._new

    def undo(self) -> None:
        self._target.name = self._old


class InsertRowsCommand(Command):
    label = "Insert Rows"

    def __init__(self, sheet: Worksheet, index: int, count: int = 1) -> None:
        self._sheet, self._index, self._count = sheet, index, count

    def execute(self) -> None:
        self._sheet.insert_rows(self._index, self._count)

    def undo(self) -> None:
        self._sheet.delete_rows(self._index, self._count)


class DeleteRowsCommand(Command):
    label = "Delete Rows"

    def __init__(self, sheet: Worksheet, index: int, count: int = 1) -> None:
        self._sheet, self._index, self._count = sheet, index, count
        self._cache: list[np.ndarray] = []

    def execute(self) -> None:
        self._cache = [c.data[self._index:self._index + self._count].copy() for c in self._sheet.columns]
        self._sheet.delete_rows(self._index, self._count)

    def undo(self) -> None:
        for column, saved in zip(self._sheet.columns, self._cache):
            head, tail = column.data[:self._index], column.data[self._index:]
            column.data = np.concatenate([head, saved, tail])


# ---------------------------------------------------------------------------
# Graph commands
# ---------------------------------------------------------------------------


class AddGraphCommand(Command):
    label = "Add Graph"

    def __init__(self, project: Project, graph: Graph) -> None:
        self._project, self._graph = project, graph

    def execute(self) -> None:
        self._project.add_graph(self._graph)

    def undo(self) -> None:
        self._project.remove_graph(self._graph)

    def to_script(self) -> str:
        return f"api.add_graph({self._graph.name!r})"


class RemoveGraphCommand(Command):
    label = "Remove Graph"

    def __init__(self, project: Project, graph: Graph) -> None:
        self._project, self._graph = project, graph
        self._index: int | None = None

    def execute(self) -> None:
        self._index = self._project.remove_graph(self._graph)

    def undo(self) -> None:
        self._project.add_graph(self._graph, index=self._index)


class AddLayerCommand(Command):
    label = "Add Layer"

    def __init__(self, graph: Graph, layer: Layer) -> None:
        self._graph, self._layer = graph, layer

    def execute(self) -> None:
        self._graph.layers.append(self._layer)

    def undo(self) -> None:
        self._graph.remove_layer(self._layer)


class AddPlotCommand(Command):
    label = "Add Plot"

    def __init__(self, graph: Graph, layer: Layer, spec: PlotSpec) -> None:
        self._graph, self._layer, self._spec = graph, layer, spec

    def execute(self) -> None:
        self._layer.add_plot(self._spec)

    def undo(self) -> None:
        self._layer.remove_plot(self._spec)

    def to_script(self) -> str:
        s = self._spec
        return (
            f"api.add_plot({self._graph.name!r}, {s.source!r}, {s.x!r}, {s.y!r}, "
            f"style={PlotStyle(s.style).value!r}, legend={s.legend!r})"
        )


class RemovePlotCommand(Command):
    label = "Remove Plot"

    def __init__(self, graph: Graph, layer: Layer, spec: PlotSpec) -> None:
        self._graph, self._layer, self._spec = graph, layer, spec
        self._index: int | None = None

    def execute(self) -> None:
        self._index = self._layer.remove_plot(self._spec)

    def undo(self) -> None:
        self._layer.plots.insert(self._index if self._index is not None else len(self._layer.plots), self._spec)


class MacroCommand(Command):
    """Groups several commands into a single undoable step."""

    def __init__(self, commands: Iterable[Command], label: str = "Macro") -> None:
        self._commands = list(commands)
        self.label = label

    def execute(self) -> None:
        for command in self._commands:
            command.execute()

    def undo(self) -> None:
        for command in reversed(self._commands):
            command.undo()

    def to_script(self) -> str | None:
        parts = [c.to_script() for c in self._commands]
        if any(p is None for p in parts):
            return None
        return "\n".join(p for p in parts if p)


def _column_script(source: str, sheet_name: str, column: Column) -> str:
    ref = source or sheet_name
    return (
        f"api.add_column({ref!r}, {column.name!r}, {column.col_type.value!r}, "
        f"data={_script_array(column.data)}, units={column.units!r}, comment={column.comment!r})"
    )
