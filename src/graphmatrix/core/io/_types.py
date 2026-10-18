"""Column-type inference shared by the importers."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ..model import Column, ColumnType, Worksheet


def infer_dtype(values: Sequence[object]) -> np.dtype:
    """Best-effort dtype: numeric if everything parses as float, else object."""
    arrays = [v for v in values if v is not None and v != ""]
    if not arrays:
        return np.dtype(np.float64)
    try:
        np.asarray(arrays, dtype=float)
        return np.dtype(np.float64)
    except (ValueError, TypeError):
        return np.dtype(object)


def _split_units(name: str) -> tuple[str, str]:
    """Split a ``Name (units)`` header into its name and unit string."""
    name = name.strip()
    if name.endswith(")") and "(" in name:
        base, _, rest = name.rpartition("(")
        base = base.strip()
        units = rest[:-1].strip()
        if base and units:
            return base, units
    return name, ""


def _name_type(name: str, index: int) -> ColumnType:
    token = name.strip().lower()
    if token in ("x", "x1", "time", "wavelength"):
        return ColumnType.X
    if token in ("y", "y1", "signal", "intensity", "value"):
        return ColumnType.Y
    return ColumnType.X if index == 0 else ColumnType.Y


def build_worksheet(
    name: str, header: Sequence[str] | None, rows: Sequence[Sequence[object]]
) -> Worksheet:
    """Build a worksheet from a header + rows, inferring types and designations."""
    ncols = max([len(r) for r in rows] + ([len(header)] if header else [0]), default=0)
    if header is None:
        names = [f"C{i + 1}" for i in range(ncols)]
        units = [""] * ncols
    else:
        cleaned = [
            str(h).strip() if str(h).strip() else f"C{i + 1}"
            for i, h in enumerate(header)
        ]
        cleaned += [f"C{i + 1}" for i in range(len(cleaned), ncols)]
        pairs = [_split_units(item) for item in cleaned]
        names = [name for name, _ in pairs]
        units = [unit for _, unit in pairs]

    sheet = Worksheet(name)
    for col_index in range(ncols):
        raw = [row[col_index] if col_index < len(row) else None for row in rows]
        dtype = infer_dtype(raw)
        if dtype == np.dtype(object):
            data = ["" if v is None else str(v) for v in raw]
            col_type = ColumnType.TEXT
        else:
            data = [np.nan if v in (None, "") else float(v) for v in raw]
            col_type = _name_type(names[col_index], col_index)
        sheet.add_column(names[col_index], col_type, data, units=units[col_index])
    return sheet


def first_xy_names(sheet: Worksheet) -> tuple[str | None, str | None]:
    x = next((c.name for c in sheet.columns if c.col_type == ColumnType.X), None)
    y = next((c.name for c in sheet.columns if c.col_type == ColumnType.Y), None)
    return x, y


__all__ = ["infer_dtype", "build_worksheet", "first_xy_names", "Column"]
