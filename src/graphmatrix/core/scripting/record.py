"""Macro recording: capture pushed commands as replayable Python.

A command's script is snapshotted *when it is pushed*, not when the script is
generated. That matters for structural commands like ``AddWorkbookCommand`` whose
output depends on the workbook's current contents: a workbook added empty must not
later be re-expanded (its sheets and columns are recorded as their own commands).
"""

from __future__ import annotations

from collections.abc import Callable

from ..commands import Command, CommandStack


class MacroRecorder:
    """Records commands pushed onto a CommandStack while active."""

    def __init__(self, stack: CommandStack) -> None:
        self._stack = stack
        self._entries: list[tuple[str, str | None]] = []
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def active(self) -> bool:
        return self._unsubscribe is not None

    @property
    def count(self) -> int:
        return len(self._entries)

    def start(self) -> None:
        if self.active:
            return
        self._entries.clear()
        self._unsubscribe = self._stack.subscribe_push(self._on_push)

    def stop(self) -> list[tuple[str, str | None]]:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        return list(self._entries)

    def _on_push(self, command: Command) -> None:
        self._entries.append((command.label, command.to_script()))

    def script(self) -> str:
        """Render the recorded commands as a runnable GraphMatrix script."""
        lines = [
            "# GraphMatrix macro — generated automatically.",
            "# Run it in the GraphMatrix console, or exec() it with a namespace from",
            "# graphmatrix.core.scripting.api.make_namespace(api).",
            "",
        ]
        for label, snippet in self._entries:
            lines.append(snippet if snippet else f"# (not recordable) {label}")
        return "\n".join(lines)


__all__ = ["MacroRecorder"]
