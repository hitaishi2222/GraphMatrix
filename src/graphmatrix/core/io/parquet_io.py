"""Parquet import/export via pyarrow."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..model import ColumnType, Worksheet
from ._types import infer_dtype


def read_sheet(path: str | Path, *, sheet_name: str | None = None) -> Worksheet:
    import pyarrow.parquet as pq

    path = Path(path)
    table = pq.read_table(path)
    data = table.to_pydict()
    sheet = Worksheet(sheet_name or path.stem)
    for index, (name, values) in enumerate(data.items()):
        dtype = infer_dtype(values)
        if dtype == np.dtype(object):
            col_type = ColumnType.TEXT
            column_data = ["" if v is None else str(v) for v in values]
        else:
            col_type = ColumnType.X if index == 0 else ColumnType.Y
            column_data = [np.nan if v is None else float(v) for v in values]
        sheet.add_column(name, col_type, column_data)
    return sheet


def write_sheet(sheet: Worksheet, path: str | Path) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = {
        c.name: [c.get(i) if i < len(c) else None for i in range(sheet.num_rows)]
        for c in sheet.columns
    }
    pq.write_table(pa.table(columns), path)
    return path


__all__ = ["read_sheet", "write_sheet"]
