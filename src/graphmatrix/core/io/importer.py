"""Unified import/export dispatch.

``import_file(path)`` decides the reader by extension. Built-in readers:

- ``.csv``/``.tsv``/``.txt``/``.dat`` → delimited text
- ``.xlsx``/``.xlsm`` → Excel
- ``.parquet`` → Parquet
- ``.h5``/``.hdf5``/``.nc`` → HDF5/NetCDF-4 (best effort)

Register additional handlers with ``register_importer`` (plugins use this).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np

from ..model import ColumnType, Workbook, Worksheet

ImportError_ = ValueError
_Reader = Callable[[Path], Worksheet]
_BookReader = Callable[[Path], Workbook]

_SHEET_READERS: dict[str, _Reader] = {}
_BOOK_READERS: dict[str, _BookReader] = {}


def register_importer(extensions, reader: _Reader) -> None:
    """Register a sheet-level reader for one or more extensions (with dot)."""
    if isinstance(extensions, str):
        extensions = [extensions]
    for ext in extensions:
        _SHEET_READERS[ext.lower()] = reader


def supported_extensions() -> list[str]:
    return sorted(set(_SHEET_READERS) | set(_BOOK_READERS))


def _register_builtins() -> None:
    from . import delimited, excel_io, parquet_io

    register_importer([".csv", ".tsv", ".txt", ".dat"], delimited.read_sheet)
    _SHEET_READERS[".parquet"] = parquet_io.read_sheet
    _BOOK_READERS[".xlsx"] = excel_io.read_workbook
    _BOOK_READERS[".xlsm"] = excel_io.read_workbook
    register_importer([".h5", ".hdf5", ".nc"], _read_hdf5)


def _read_hdf5(path: Path) -> Worksheet:
    import h5py

    with h5py.File(path, "r") as handle:
        dataset_name = next(
            (k for k in handle.keys() if isinstance(handle[k], h5py.Dataset)), None
        )
        if dataset_name is None:
            raise ImportError_(f"no dataset found in {path.name}")
        array = np.asarray(handle[dataset_name])
    sheet = Worksheet(path.stem)
    if array.ndim == 1:
        sheet.add_column("Y1", ColumnType.Y, array)
    else:
        for col in range(array.shape[1]):
            sheet.add_column(
                f"C{col + 1}", ColumnType.X if col == 0 else ColumnType.Y, array[:, col]
            )
    return sheet


_READY = False


def _ensure_ready() -> None:
    global _READY
    if not _READY:
        _register_builtins()
        _READY = True


def import_sheet(path: str | Path) -> Worksheet:
    """Import a single sheet from a file."""
    _ensure_ready()
    path = Path(path)
    ext = path.suffix.lower()
    if ext in _SHEET_READERS:
        return _SHEET_READERS[ext](path)
    book = _BOOK_READERS.get(ext)
    if book is not None:
        workbook = book(path)
        return workbook.sheets[0] if workbook.sheets else Worksheet(path.stem)
    # Last resort: try delimited text.
    from . import delimited

    return delimited.read_sheet(path)


def import_file(path: str | Path) -> Workbook:
    """Import a file into a Workbook (multi-sheet for Excel)."""
    _ensure_ready()
    path = Path(path)
    ext = path.suffix.lower()
    if ext in _BOOK_READERS:
        return _BOOK_READERS[ext](path)
    book = Workbook(path.stem)
    book.add_sheet(import_sheet(path))
    return book


def export_delimited(
    sheet: Worksheet, path: str | Path, *, delimiter: str = ","
) -> Path:
    from . import delimited

    return delimited.write_sheet(sheet, path, delimiter=delimiter)
