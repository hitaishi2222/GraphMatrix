"""CSV / TSV / whitespace delimited text I/O.

Delimiter detection is deliberately more forgiving than ``csv.Sniffer``: comma,
semicolon, tab, and pipe are detected directly, and files that are separated by
arbitrary runs of whitespace are parsed with ``str.split`` (Sniffer notoriously
chokes on space-separated scientific data).
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..model import Worksheet
from ._types import build_worksheet

_CANDIDATES = (",", ";", "\t", "|")
_SINGLE = "\x00"  # sentinel: no delimiter found, keep each line as one field


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def _detect_delimiter(lines: list[str]) -> str | None:
    sample = lines[:50]
    for candidate in _CANDIDATES:
        if all(candidate in line for line in sample if line):
            return candidate
    # Whitespace-separated: multiple tokens per line, consistently.
    token_counts = [len(line.split()) for line in sample if line]
    if token_counts and min(token_counts) > 1:
        return None  # whitespace mode
    return _SINGLE  # no delimiter: one column


def _guess_header(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    first = rows[0]
    rest_numeric = all(
        _is_number(cell) for row in rows[1:6] for cell in row if cell != ""
    )
    first_has_text = any(not _is_number(cell) for cell in first if cell != "")
    return first_has_text and rest_numeric


def read_sheet(
    path: str | Path,
    *,
    delimiter: str | None = None,
    has_header: bool | None = None,
    sheet_name: str | None = None,
) -> Worksheet:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return Worksheet(sheet_name or path.stem)

    if delimiter is None:
        delimiter = _detect_delimiter(lines)

    if delimiter is None:  # whitespace mode
        rows = [line.split() for line in lines]
    else:
        reader = csv.reader(lines, delimiter=delimiter, skipinitialspace=True)
        rows = [[cell.strip() for cell in row] for row in reader]

    if has_header is None:
        has_header = _guess_header(rows)

    header = rows[0] if has_header else None
    body = rows[1:] if has_header else rows
    return build_worksheet(sheet_name or path.stem, header, body)


def write_sheet(sheet: Worksheet, path: str | Path, *, delimiter: str = ",") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        writer.writerow(
            [f"{c.name} ({c.units})" if c.units else c.name for c in sheet.columns]
        )
        for row in range(sheet.num_rows):
            writer.writerow(
                [
                    column.get(row) if row < len(column) else ""
                    for column in sheet.columns
                ]
            )
    return path


__all__: list[str] = ["read_sheet", "write_sheet"]
