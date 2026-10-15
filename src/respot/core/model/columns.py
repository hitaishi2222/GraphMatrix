"""Typed data columns for Respot worksheets."""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterator, Sequence

import numpy as np
from numpy.typing import NDArray


class ColumnType(str, Enum):
    """Column designation, mirroring the X/Y/Z naming scientists expect.

    The value doubles as the display string and the on-disk token.
    """

    X = "X"
    Y = "Y"
    YERR = "YErr"
    XERR = "XErr"
    Z = "Z"
    LABEL = "Label"
    GROUP = "Group"
    DATE = "Date"
    TEXT = "Text"
    DISREGARD = "Disregard"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value

    @property
    def is_numeric(self) -> bool:
        return self not in (ColumnType.LABEL, ColumnType.TEXT)


def _to_array(data: Any, dtype: Any = None) -> NDArray[Any]:
    """Coerce arbitrary input into a 1-D numpy array."""
    if data is None:
        return np.empty(0, dtype=dtype or np.float64)
    arr = np.asarray(data, dtype=dtype)
    if arr.ndim != 1:
        arr = arr.reshape(-1)
    return arr


class Column:
    """A single typed column of data plus its metadata."""

    def __init__(
        self,
        name: str,
        col_type: ColumnType | str = ColumnType.Y,
        data: Sequence[Any] | NDArray[Any] | None = None,
        *,
        units: str = "",
        comment: str = "",
        dtype: Any = None,
    ) -> None:
        self.name = name
        self.col_type = ColumnType(col_type)
        self.units = units
        self.comment = comment
        self._data: NDArray[Any] = _to_array(data, dtype)

    # -- access --------------------------------------------------------------
    @property
    def data(self) -> NDArray[Any]:
        """The underlying (mutable) array. Treat as a live reference."""
        return self._data

    @property
    def values(self) -> list[Any]:
        """Values as a plain Python list (copy)."""
        return self._data.tolist()

    @property
    def dtype(self) -> np.dtype:
        return self._data.dtype

    def __len__(self) -> int:
        return int(self._data.shape[0])

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __getitem__(self, index: Any) -> Any:
        return self._data[index]

    def get(self, row: int) -> Any:
        return self._data[row]

    def set(self, row: int, value: Any) -> None:
        if not 0 <= row < len(self):
            raise IndexError(f"row {row} out of range for column {self.name!r}")
        self._data[row] = value

    def append(self, value: Any) -> None:
        self._data = np.append(self._data, value)

    def extend(self, values: Sequence[Any]) -> None:
        self._data = np.concatenate([self._data, _to_array(values, self._data.dtype)])

    # -- serialization -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "col_type": self.col_type.value,
            "units": self.units,
            "comment": self.comment,
            "dtype": str(self._data.dtype),
            "data": self._data.tolist(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Column":
        return cls(
            payload["name"],
            payload.get("col_type", ColumnType.Y),
            payload.get("data", []),
            units=payload.get("units", ""),
            comment=payload.get("comment", ""),
            dtype=payload.get("dtype"),
        )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Column(name={self.name!r}, type={self.col_type.value}, n={len(self)})"
