"""Typed data columns for GraphMatrix worksheets."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from enum import Enum
from typing import Any

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
        return self not in (ColumnType.LABEL, ColumnType.TEXT, ColumnType.DATE)


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
        decimal: int | None = None,
        mask: Sequence[bool] | NDArray[Any] | None = None,
    ) -> None:
        self.name = name
        self.col_type = ColumnType(col_type)
        self.units = units
        self.comment = comment
        self.decimal = decimal
        self._data: NDArray[Any] = _to_array(data, dtype)
        self._mask: NDArray[np.bool_] | None = (
            np.asarray(mask, dtype=bool) if mask is not None else None
        )

    # -- access --------------------------------------------------------------
    @property
    def data(self) -> NDArray[Any]:
        """The underlying (mutable) array. Treat as a live reference."""
        return self._data

    @data.setter
    def data(self, values: Sequence[Any] | NDArray[Any]) -> None:
        self._data = _to_array(values, self._data.dtype if len(self._data) else None)

    @property
    def values(self) -> list[Any]:
        """Values as a plain Python list (copy)."""
        return self._data.tolist()

    @property
    def dtype(self) -> np.dtype:
        return self._data.dtype

    @property
    def is_numeric(self) -> bool:
        return self._data.dtype.kind in "fiub" or self.col_type.is_numeric

    @property
    def mask(self) -> NDArray[np.bool_] | None:
        return self._mask

    def float_data(self) -> NDArray[np.float64]:
        """Data as float64 (masked values as NaN), for analysis/plotting."""
        arr = np.asarray(self._data, dtype=float)
        if self._mask is not None and self._mask.size == arr.size:
            arr = np.where(self._mask, np.nan, arr)
        return arr

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

    def insert_blanks(self, index: int, count: int = 1) -> None:
        """Insert ``count`` blank values at ``index``.

        Integer and boolean columns are promoted to float so a blank is a real
        NaN rather than a wrapped-around sentinel (which numpy would otherwise
        produce when casting NaN into an integer dtype).
        """
        index = max(0, min(int(index), len(self)))
        count = max(0, int(count))
        if count == 0:
            return
        data = self._data
        dtype = data.dtype
        head, tail = data[:index], data[index:]
        if np.issubdtype(dtype, np.floating):
            pad = np.full(count, np.nan, dtype=dtype)
            self._data = np.concatenate([head, pad, tail])
        elif np.issubdtype(dtype, np.datetime64):
            pad = np.full(count, np.datetime64("NaT"), dtype=dtype)
            self._data = np.concatenate([head, pad, tail])
        elif np.issubdtype(dtype, np.integer) or np.issubdtype(dtype, np.bool_):
            pad = np.full(count, np.nan)
            self._data = np.concatenate([head.astype(float), pad, tail.astype(float)])
        else:
            # String/object columns: use an empty object so blanks are visible
            # and can later be replaced by text or numbers.
            pad = np.full(count, "", dtype=object)
            self._data = np.concatenate([head.astype(object), pad, tail.astype(object)])

    # -- serialization -------------------------------------------------------
    def to_dict(self, *, include_data: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "col_type": self.col_type.value,
            "units": self.units,
            "comment": self.comment,
            "dtype": str(self._data.dtype),
        }
        if self.decimal is not None:
            payload["decimal"] = self.decimal
        if include_data:
            payload["data"] = self._data.tolist()
            if self._mask is not None:
                payload["mask"] = self._mask.tolist()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Column:
        return cls(
            payload["name"],
            payload.get("col_type", ColumnType.Y),
            payload.get("data", []),
            units=payload.get("units", ""),
            comment=payload.get("comment", ""),
            dtype=payload.get("dtype"),
            decimal=payload.get("decimal"),
            mask=payload.get("mask"),
        )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Column(name={self.name!r}, type={self.col_type.value}, n={len(self)})"
