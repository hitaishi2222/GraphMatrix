"""Worksheet: an ordered set of typed columns."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import numpy as np

from .columns import Column, ColumnType
from .formula import evaluate_column_formula


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
        decimal: int | None = None,
        index: int | None = None,
        mask: Sequence[bool] | None = None,
    ) -> Column:
        column = Column(
            name,
            col_type,
            data,
            units=units,
            comment=comment,
            dtype=dtype,
            decimal=decimal,
            mask=mask,
        )
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

    def column_index(self, column: Column) -> int:
        return self.columns.index(column)

    def move_column(self, from_index: int, to_index: int) -> None:
        column = self.columns.pop(from_index)
        self.columns.insert(to_index, column)

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

    def unique_column_name(self, base: str) -> str:
        existing = set(self.column_names)
        if base not in existing:
            return base
        i = 1
        while f"{base}{i}" in existing:
            i += 1
        return f"{base}{i}"

    def unique_sheet_name(self) -> str:  # convenience for callers
        return self.name

    # -- rows ----------------------------------------------------------------
    def ensure_rows(self, count: int) -> None:
        for column in self.columns:
            if len(column) < count:
                column.insert_blanks(len(column), count - len(column))

    def insert_rows(self, index: int, count: int = 1) -> None:
        for column in self.columns:
            column.insert_blanks(index, count)

    def delete_rows(self, index: int, count: int = 1) -> None:
        for column in self.columns:
            data = column.data
            column.data = np.concatenate([data[:index], data[index + count :]])

    def set_value(self, row: int, column_index: int, value: Any) -> None:
        column = self.columns[column_index]
        if row >= len(column):
            self.ensure_rows(row + 1)
        column.set(row, value)

    def apply_formula(self, column: Column, expression: str) -> None:
        """Fill ``column`` from a formula referencing other columns by name."""
        values = evaluate_column_formula(self, expression, len(column) or self.num_rows)
        column.data = values

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
    def to_dict(self, *, include_data: bool = True) -> dict[str, Any]:
        return {
            "name": self.name,
            "columns": [c.to_dict(include_data=include_data) for c in self.columns],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Worksheet:
        sheet = cls(payload.get("name", "Sheet1"))
        for col_payload in payload.get("columns", []):
            sheet.insert_column(Column.from_dict(col_payload))
        return sheet

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Worksheet(name={self.name!r}, cols={self.num_columns}, rows={self.num_rows})"
