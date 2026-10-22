"""Linked brushing — one shared selection highlighted across every view.

The brush is *view state*, not project data: it is never serialized, never
undoable, and never mutates the model. A :class:`BrushSelection` fronts a single
``source -> rows`` mapping; every open graph view and worksheet subscribes, so a
point clicked on a canvas and a row picked in a sheet highlight each other.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

BRUSH_COLOR = "#ff7f0e"


class BrushSelection(QObject):
    """A shared selection: worksheet source ("Book/Sheet") -> row indices."""

    changed = Signal(str, list)  # (source, sorted rows) — empty list clears

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[str, list[int]] = {}

    def source(self) -> str | None:
        """The one sheet the brush currently points at, else None."""
        return next((k for k, v in self._rows.items() if v), None)

    def get(self, source: str) -> list[int]:
        return list(self._rows.get(source, ()))

    def set(self, source: str, rows: list[int]) -> None:
        rows = sorted({int(r) for r in rows})
        # The brush points at one sheet at a time: moving it clears the rest.
        previous = self.source()
        if rows and previous is not None and previous != source:
            self.clear()
        changed = rows != self._rows.get(source)
        self._rows[source] = rows
        if changed:
            self.changed.emit(source, list(rows))

    def clear(self) -> None:
        sources = [k for k, v in self._rows.items() if v]
        self._rows.clear()
        for source in sources:
            self.changed.emit(source, [])


__all__ = ["BRUSH_COLOR", "BrushSelection"]
