"""Declarative action/menu registry.

Actions are declared once (id, text, shortcut, menu) and reused by both the menu
bar and the toolbar. Keeping them in one place avoids the classic Qt drift where
a menu item and its shortcut get out of sync.

Shortcuts are written platform-neutrally: ``"Ctrl+S"`` becomes ``Cmd+S`` on
macOS, and the standard editor keys (new, open, save, undo, redo, close,
preferences, help) use :class:`QKeySequence.StandardKey`, so they follow the
platform's own conventions.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar


@dataclass
class ActionSpec:
    id: str
    text: str
    shortcut: str | QKeySequence.StandardKey | None = None
    menu: str | None = None
    checkable: bool = False
    tooltip: str | None = None
    separator_before: bool = False


def portable_sequence(text: str) -> str:
    """Rewrite ``Ctrl`` as the platform's primary modifier.

    On macOS the primary modifier is ``Meta`` (the Command key); everywhere
    else it is ``Ctrl``. Writing the shortcut once in the action registry is
    therefore enough - no per-platform tables.
    """
    if sys.platform != "darwin":
        return text
    return text.replace("Ctrl+", "Meta+").replace("Ctrl", "Meta")


def key_sequence(
    shortcut: str | QKeySequence.StandardKey | None,
) -> QKeySequence | None:
    """Build a :class:`QKeySequence` from a portable shortcut description."""
    if shortcut is None:
        return None
    if isinstance(shortcut, QKeySequence.StandardKey):
        return QKeySequence(shortcut)
    return QKeySequence(portable_sequence(str(shortcut)))


def shortcut_text(
    shortcut: str | QKeySequence.StandardKey | None,
) -> str:
    """The human-readable form of a shortcut (native to the platform)."""
    sequence = key_sequence(shortcut)
    if sequence is None:
        return ""
    return sequence.toString(QKeySequence.SequenceFormat.NativeText)


class ActionRegistry:
    """Creates and remembers QActions; builds menus from their specs."""

    def __init__(self, parent) -> None:
        self._parent = parent
        self._specs: list[ActionSpec] = []
        self._actions: dict[str, QAction] = {}

    def register(
        self,
        spec: ActionSpec,
        callback: Callable[[], None] | None = None,
        *,
        enabled: bool = True,
    ) -> QAction:
        action = QAction(spec.text, self._parent)
        sequence = key_sequence(spec.shortcut)
        if sequence is not None and not sequence.isEmpty():
            action.setShortcut(sequence)
        action.setCheckable(spec.checkable)
        if spec.tooltip:
            action.setToolTip(spec.tooltip)
            action.setStatusTip(spec.tooltip)
        action.setEnabled(enabled)
        if callback is not None:
            action.triggered.connect(lambda _checked=False, cb=callback: cb())
        self._specs.append(spec)
        self._actions[spec.id] = action
        return action

    def action(self, action_id: str) -> QAction:
        return self._actions[action_id]

    def specs(self) -> list[ActionSpec]:
        return list(self._specs)

    def build_menus(
        self, menubar: QMenuBar, *, order: list[str] | None = None
    ) -> dict[str, QMenu]:
        """Create menus for every spec.menu, in first-seen (or explicit) order."""
        menus: dict[str, QMenu] = {}
        if order:
            for name in order:
                if any(s.menu == name for s in self._specs) and name not in menus:
                    menus[name] = menubar.addMenu(name)
        for spec in self._specs:
            if spec.menu is None:
                continue
            if spec.menu not in menus:
                menus[spec.menu] = menubar.addMenu(spec.menu)
            menu = menus[spec.menu]
            if spec.separator_before and not menu.isEmpty():
                menu.addSeparator()
            menu.addAction(self._actions[spec.id])
        return menus


__all__ = [
    "ActionRegistry",
    "ActionSpec",
    "key_sequence",
    "portable_sequence",
    "shortcut_text",
]
