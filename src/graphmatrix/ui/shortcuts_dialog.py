"""A searchable overview of every keyboard shortcut GraphMatrix has.

The action registry already knows every command and its shortcut, so the
dialog is generated from it instead of being a second, hand-written list that
would drift. The worksheet's own shortcuts (copy, paste, rename) are added
explicitly, because they live in the worksheet widget, not in the registry.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from .actions import ActionRegistry, shortcut_text

#: Shortcuts that only exist while a worksheet has the focus.
WORKSHEET_SHORTCUTS = (
    ("Copy the selected cells", "Ctrl+C"),
    ("Cut the selected cells", "Ctrl+X"),
    ("Paste from the clipboard", "Ctrl+V"),
    ("Rename the selected column", "F2"),
    ("Add a row at the end", "Ctrl+Alt+N"),
    ("Add a column at the end", "Ctrl+Alt+C"),
    ("Insert rows above the selection", "Ctrl+Alt+="),
    ("Delete the selected rows", "Ctrl+Alt+-"),
    ("Delete the selected columns", "Ctrl+Alt+Shift+-"),
)


class ShortcutsDialog(QDialog):
    """Lists every command with its shortcut, grouped by menu."""

    def __init__(self, registry: ActionRegistry, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(680, 560)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Every command GraphMatrix offers, with the key that runs it. "
            "On macOS the Ctrl keys are the Command key."
        )
        intro.setWordWrap(True)
        intro.setEnabled(False)
        layout.addWidget(intro)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter shortcuts…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._refresh)
        layout.addWidget(self.filter)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Command", "Shortcut"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 380)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tree, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._entries: list[tuple[str, str, str]] = []
        self._collect(registry)
        self._refresh("")

    # -- construction --------------------------------------------------------
    def _collect(self, registry: ActionRegistry) -> None:
        """Gather (group, command, shortcut) triples from the registry."""
        seen: set[tuple[str, str]] = set()
        for spec in registry.specs():
            shortcut = shortcut_text(spec.shortcut)
            if not shortcut:
                continue
            group = spec.menu or "Other"
            key = (spec.text, shortcut)
            if key in seen:
                continue
            seen.add(key)
            self._entries.append((group, spec.text, shortcut))
        for text, shortcut in WORKSHEET_SHORTCUTS:
            key = (text, shortcut)
            if key in seen:
                continue
            seen.add(key)
            self._entries.append(("Worksheet", text, shortcut))
        self._entries.sort(key=lambda item: (item[0], item[1]))

    # -- filtering -----------------------------------------------------------
    def _refresh(self, query: str) -> None:
        query = query.strip().lower()
        self.tree.clear()
        groups: dict[str, QTreeWidgetItem] = {}
        for group, command, shortcut in self._entries:
            if query and query not in command.lower() and query not in shortcut.lower():
                continue
            parent = groups.get(group)
            if parent is None:
                parent = QTreeWidgetItem(self.tree, [group, ""])
                parent.setFirstColumnSpanned(True)
                parent.setExpanded(True)
                groups[group] = parent
            QTreeWidgetItem(parent, [command, shortcut])
        for index in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(index)
        self.tree.expandAll()


__all__ = ["WORKSHEET_SHORTCUTS", "ShortcutsDialog"]
