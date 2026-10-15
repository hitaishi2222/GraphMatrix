"""Import/export tests (M1)."""

from __future__ import annotations

import numpy as np

from respot.core.io import importer
from respot.core.model import ColumnType, Worksheet


def test_csv_roundtrip(tmp_path):
    sheet = Worksheet("S")
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0, 2.0], units="s")
    sheet.add_column("Y1", ColumnType.Y, [0.0, 1.0, 4.0])
    path = tmp_path / "data.csv"
    importer.export_delimited(sheet, path)
    assert path.exists()

    imported = importer.import_sheet(path)
    assert imported.num_rows == 3
    assert [c.col_type for c in imported.columns][:2] == [ColumnType.X, ColumnType.Y]
    np.testing.assert_allclose(imported.column("Y1").data, [0.0, 1.0, 4.0])
    # Units embedded in the header survive the round-trip.
    assert imported.column("X1").units == "s"


def test_csv_headerless_inference(tmp_path):
    path = tmp_path / "raw.txt"
    path.write_text("0 1\n1 2\n2 4\n", encoding="utf-8")
    sheet = importer.import_sheet(path)
    assert sheet.num_rows == 3
    assert sheet.num_columns >= 2


def test_excel_roundtrip(tmp_path):
    from respot.core.io import excel_io
    from respot.core.model import Workbook

    book = Workbook("B")
    sheet = book.add_sheet(Worksheet("Data"))
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0, 2.0])
    sheet.add_column("Y1", ColumnType.Y, [10.0, 20.0, 30.0])
    path = tmp_path / "book.xlsx"
    excel_io.write_workbook(book, path)

    reimported = importer.import_file(path)
    assert reimported.num_sheets == 1
    assert reimported.sheets[0].column("Y1") is not None
    np.testing.assert_allclose(reimported.sheets[0].column("Y1").data, [10.0, 20.0, 30.0])


def test_parquet_roundtrip(tmp_path):
    from respot.core.io import parquet_io

    sheet = Worksheet("S")
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0, 2.0])
    sheet.add_column("Y1", ColumnType.Y, [1.5, 2.5, 3.5])
    path = tmp_path / "data.parquet"
    parquet_io.write_sheet(sheet, path)

    reimported = importer.import_sheet(path)
    np.testing.assert_allclose(reimported.column("Y1").data, [1.5, 2.5, 3.5])


def test_supported_extensions_include_common():
    exts = importer.supported_extensions()
    for ext in (".csv", ".txt", ".xlsx", ".parquet"):
        assert ext in exts
