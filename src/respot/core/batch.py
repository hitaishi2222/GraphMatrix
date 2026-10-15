"""Batch processing: run an operation over many files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .io.importer import import_file
from .model import Workbook


@dataclass
class BatchItem:
    path: Path
    ok: bool
    result: object = None
    error: str | None = None


def process_files(
    paths: Iterable[str | Path],
    operation: Callable[[Workbook, Path], object],
) -> list[BatchItem]:
    """Import each file into a Workbook and run ``operation(book, path)``.

    Failures on one file do not stop the batch; each is reported in its BatchItem.
    """
    items: list[BatchItem] = []
    for raw in paths:
        path = Path(raw)
        try:
            book = import_file(path)
            result = operation(book, path)
            items.append(BatchItem(path=path, ok=True, result=result))
        except Exception as exc:  # noqa: BLE001 - per-file isolation
            items.append(BatchItem(path=path, ok=False, error=f"{type(exc).__name__}: {exc}"))
    return items


__all__ = ["process_files", "BatchItem"]
