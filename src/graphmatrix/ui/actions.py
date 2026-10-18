"""Declarative action/menu registry.

Actions are declared once (id, text, shortcut, menu) and reused by both the menu
bar and the toolbar. Keeping them in one place avoids the classic Qt drift where
a menu item and its shortcut get out of sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenuBar, QMenu


@dataclass
class ActionSpec:
    id: str
    text: str
    shortcut: str | None = None
    menu: str | None = None
    checkable: bool = False
    tooltip: str | None = None
    separator_before: bool = False


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
        if spec.shortcut:
            action.setShortcut(QKeySequence(spec.shortcut))
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
