"""Live / streaming data board (M11) — tail a text file into a worksheet.

A :class:`LiveFileSource` watches one delimited text file: it remembers the
byte offset it last read, and :meth:`poll` returns only the numeric rows that
appeared since the previous call. Truncation (log rotation, re-run of the
writer) resets the source to the beginning. Non-numeric fields and ragged
rows become NaN so a uniform rectangular block is always returned.

The UI (``ui/live_dialog.py``) appends polled rows with ``SetCellsCommand``,
so every tick is one undoable step and the command stack's change
notification refreshes the sheet and every graph bound to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

DELIMITERS: dict[str, str] = {
    "Comma (CSV)": ",",
    "Tab (TSV)": "\t",
    "Semicolon": ";",
    "Space": " ",
    "Pipe": "|",
}


def looks_numeric(text: str) -> bool:
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


@dataclass
class LiveFileSource:
    """Tail one delimited file, exposing numeric rows as they appear."""

    path: Path
    delimiter: str = ","
    _offset: int = field(default=0, init=False, repr=False)
    _width: int | None = field(default=None, init=False, repr=False)

    # -- header --------------------------------------------------------------
    def columns(self) -> list[str]:
        """Column names: the first line if non-numeric, else generic labels.

        Returns ``[]`` for an empty file.
        """
        try:
            with open(self.path, encoding="utf-8", errors="replace") as fh:
                first = fh.readline()
        except OSError:
            return []
        fields = [f.strip() for f in first.rstrip("\r\n").split(self.delimiter)]
        if fields and not any(looks_numeric(f) for f in fields):
            self._width = len(fields)
            return fields
        width = len(fields) if first.strip() else 0
        self._width = width or None
        return [f"C{i + 1}" for i in range(width)]

    # -- ticking -------------------------------------------------------------
    def poll(self) -> list[list[float]]:
        """New numeric rows since the last call (empty list if none)."""
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size < self._offset:  # truncated/rewritten: start over
            self._offset = 0
        try:
            with open(self.path, encoding="utf-8", errors="replace") as fh:
                fh.seek(self._offset)
                chunk = fh.read()
        except OSError:
            return []
        self._offset = self._offset + len(chunk.encode("utf-8"))
        rows: list[list[float]] = []
        for line in chunk.splitlines():
            fields = [f.strip() for f in line.split(self.delimiter)]
            # Skip a (re-appearing) header line entirely.
            if fields and not any(looks_numeric(f) for f in fields):
                if self._width is None or len(fields) != self._width:
                    self.columns()  # re-probe width
                continue
            if not fields or all(f == "" for f in fields):
                continue
            values = [float(f) if looks_numeric(f) else np.nan for f in fields]
            if self._width is not None and self._width > len(values):
                values.extend([np.nan] * (self._width - len(values)))
            if self._width is None:
                self._width = len(values)
            rows.append(values)
        return rows


__all__ = ["LiveFileSource", "DELIMITERS", "looks_numeric"]
