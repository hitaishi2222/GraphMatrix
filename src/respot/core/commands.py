"""Command pattern: undo/redo and (later) macro recording.

Every mutation of the model goes through a Command. The stack notifies
subscribers on any change, and the UI uses that to refresh menus and views.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Iterable

from .model import Column, Project, Workbook, Worksheet


class Command(ABC):
    """A reversible action against the model."""

    label: str = "Command"

    @abstractmethod
    def execute(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    def undo(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class CommandStack:
    """An undo/redo stack with change notification."""

    def __init__(self, *, limit: int = 200) -> None:
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._listeners: list[Callable[[], None]] = []
        self._limit = limit

    # -- notification --------------------------------------------------------
    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a change listener; returns an unsubscribe function."""
        self._listeners.append(callback)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

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


# ---------------------------------------------------------------------------
# Structural commands
# ---------------------------------------------------------------------------


class AddWorkbookCommand(Command):
    label = "Add Workbook"

    def __init__(self, project: Project, workbook: Workbook) -> None:
        self._project = project
        self._workbook = workbook

    def execute(self) -> None:
        self._project.add_workbook(self._workbook)

    def undo(self) -> None:
        self._project.remove_workbook(self._workbook)


class RemoveWorkbookCommand(Command):
    label = "Remove Workbook"

    def __init__(self, project: Project, workbook: Workbook) -> None:
        self._project = project
        self._workbook = workbook
        self._index: int | None = None

    def execute(self) -> None:
        self._index = self._project.remove_workbook(self._workbook)

    def undo(self) -> None:
        self._project.add_workbook(self._workbook, index=self._index)


class AddWorksheetCommand(Command):
    label = "Add Worksheet"

    def __init__(self, workbook: Workbook, sheet: Worksheet) -> None:
        self._workbook = workbook
        self._sheet = sheet

    def execute(self) -> None:
        self._workbook.add_sheet(self._sheet)

    def undo(self) -> None:
        self._workbook.remove_sheet(self._sheet)


class RemoveWorksheetCommand(Command):
    label = "Remove Worksheet"

    def __init__(self, workbook: Workbook, sheet: Worksheet) -> None:
        self._workbook = workbook
        self._sheet = sheet
        self._index: int | None = None

    def execute(self) -> None:
        self._index = self._workbook.remove_sheet(self._sheet)

    def undo(self) -> None:
        self._workbook.add_sheet(self._sheet, index=self._index)


class AddColumnCommand(Command):
    label = "Add Column"

    def __init__(self, sheet: Worksheet, column: Column, *, index: int | None = None) -> None:
        self._sheet = sheet
        self._column = column
        self._index = index

    def execute(self) -> None:
        self._sheet.insert_column(self._column, index=self._index)

    def undo(self) -> None:
        self._sheet.remove_column(self._column)


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
