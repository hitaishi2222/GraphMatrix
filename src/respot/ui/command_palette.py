"""Command palette: fuzzy-search every registered action and run it.

This is the low-risk half of "Ask Respot": instead of guessing a command grammar, it
surfaces the actions Respot already has (with their shortcuts) and ranks them by a
subsequence match, so ``exag`` finds "Export Active Graph" and ``als`` finds nothing
until such an action exists. Type, arrow, Enter.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from .actions import ActionRegistry


def _score(query: str, text: str) -> int | None:
    """Subsequence score: lower is better, ``None`` means no match.

    Exact and prefix matches are rewarded, as is matching near word starts, so
    ``ap`` prefers "Add Plot" over "Apply Template".
    """
    if not query:
        return 0
    lowered = text.lower()
    if query in lowered:
        return lowered.index(query)
    position = 0
    score = 0
    last = -1
    for char in query:
        found = lowered.find(char, position)
        if found == -1:
            return None
        gap = found - last
        score += gap
        if found == 0 or lowered[found - 1] in " ._/":
            score -= 1
        last = found
        position = found + 1
    return score + len(lowered)


class CommandPalette(QDialog):
    """A searchable list of actions. ``selected_action`` is set on accept."""

    def __init__(self, registry: ActionRegistry, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.resize(560, 420)
        self.selected_action: str | None = None
        self._entries: list[tuple[str, str]] = []

        for spec in registry.specs():
            label = spec.text
            if spec.shortcut:
                label = f"{label}  ({spec.shortcut})"
            if spec.menu:
                label = f"{label}  ·  {spec.menu}"
            self._entries.append((label, spec.id))

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command…")
        self.search.textChanged.connect(self._refresh)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _item: self._accept_current())
        layout.addWidget(self.list, 1)

        hint = QLabel("↑ ↓ to choose · Enter to run · Esc to close")
        hint.setEnabled(False)
        layout.addWidget(hint)

        self._refresh("")
        self.search.setFocus()

    # -- filtering -----------------------------------------------------------
    def _refresh(self, query: str) -> None:
        query = query.strip().lower()
        scored: list[tuple[int, str, str]] = []
        for label, action_id in self._entries:
            score = _score(query, label.lower())
            if score is not None:
                scored.append((score, label, action_id))
        scored.sort(key=lambda item: (item[0], item[1]))
        self.list.clear()
        for _score_value, label, action_id in scored:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, action_id)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _accept_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        self.selected_action = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    # -- events --------------------------------------------------------------
    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        if watched is self.search and isinstance(event, QKeyEvent):
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self.list.keyPressEvent(event)
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._accept_current()
            return
        super().keyPressEvent(event)


__all__ = ["CommandPalette"]
