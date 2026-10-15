"""Worksheet: an ordered set of typed columns."""

from __future__ import annotations

from typing import Any, Iterator, Sequence

from .columns import Column, ColumnType


class Worksheet:
    """A sheet holding typed columns.

    Row count is derived from the longest column (ragged columns are allowed
    during editing, as in Origin).
    """

    def __init__(self, name: str = "Sheet1") -> None:
        self.name = name
        self.columns: list[Column] = []

    # -- columns -------------------------------------------------------------
    def add_column(
        self,
        name: str,
        col_type: ColumnType | str = ColumnType.Y,
        data: Sequence[Any] | None = None,
        *,
        units: str = "",
        comment: str = "",
        dtype: Any = None,
        index: int | None = None,
    ) -> Column:
        column = Column(name, col_type, data, units=units, comment=comment, dtype=dtype)
        self.insert_column(column, index=index)
        return column

    def insert_column(self, column: Column, index: int | None = None) -> Column:
        if index is None:
            self.columns.append(column)
        else:
            self.columns.insert(index, column)
        return column

    def remove_column(self, column: Column) -> int:
        """Remove a column, returning the index it occupied."""
        index = self.columns.index(column)
        del self.columns[index]
        return index

    def column(self, name: str) -> Column | None:
        for column in self.columns:
            if column.name == name:
                return column
        return None

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def next_column_name(self, col_type: ColumnType | str) -> str:
        prefix = ColumnType(col_type).value
        existing = set(self.column_names)
        i = 1
        while f"{prefix}{i}" in existing:
            i += 1
        return f"{prefix}{i}"

    # -- shape ---------------------------------------------------------------
    @property
    def num_columns(self) -> int:
        return len(self.columns)

    @property
    def num_rows(self) -> int:
        return max((len(c) for c in self.columns), default=0)

    def __len__(self) -> int:
        return self.num_rows

    def __iter__(self) -> Iterator[Column]:
        return iter(self.columns)

    # -- serialization -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "columns": [c.to_dict() for c in self.columns]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Worksheet":
        sheet = cls(payload.get("name", "Sheet1"))
        for col_payload in payload.get("columns", []):
            sheet.insert_column(Column.from_dict(col_payload))
        return sheet

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Worksheet(name={self.name!r}, cols={self.num_columns}, rows={self.num_rows})"
