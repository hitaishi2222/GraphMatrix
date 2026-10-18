"""Workbook: an ordered set of worksheets."""

from __future__ import annotations

from typing import Any, Iterator

from .worksheet import Worksheet


class Workbook:
    """A collection of worksheets, like a multi-sheet data file."""

    def __init__(self, name: str = "Book1") -> None:
        self.name = name
        self.sheets: list[Worksheet] = []

    # -- sheets --------------------------------------------------------------
    def add_sheet(
        self,
        sheet: Worksheet | None = None,
        *,
        name: str | None = None,
        index: int | None = None,
    ) -> Worksheet:
        if sheet is None:
            sheet = Worksheet(name or self.next_sheet_name())
        if index is None:
            self.sheets.append(sheet)
        else:
            self.sheets.insert(index, sheet)
        return sheet

    def remove_sheet(self, sheet: Worksheet) -> int:
        """Remove a sheet, returning the index it occupied."""
        index = self.sheets.index(sheet)
        del self.sheets[index]
        return index

    def sheet(self, name: str) -> Worksheet | None:
        for sheet in self.sheets:
            if sheet.name == name:
                return sheet
        return None

    def next_sheet_name(self) -> str:
        existing = {s.name for s in self.sheets}
        i = 1
        while f"Sheet{i}" in existing:
            i += 1
        return f"Sheet{i}"

    @property
    def num_sheets(self) -> int:
        return len(self.sheets)

    def __len__(self) -> int:
        return len(self.sheets)

    def __iter__(self) -> Iterator[Worksheet]:
        return iter(self.sheets)

    # -- serialization -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "sheets": [s.to_dict() for s in self.sheets]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Workbook":
        book = cls(payload.get("name", "Book1"))
        for sheet_payload in payload.get("sheets", []):
            book.sheets.append(Worksheet.from_dict(sheet_payload))
        return book

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Workbook(name={self.name!r}, sheets={self.num_sheets})"
