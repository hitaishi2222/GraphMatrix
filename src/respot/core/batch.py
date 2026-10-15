"""Batch processing: run an operation (or an analysis recipe) over many files."""

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
    report_path: Path | None = None
    figure_path: Path | None = None


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


def run_recipe_over_files(
    paths: Iterable[str | Path],
    recipe,
    *,
    report_dir: str | Path | None = None,
    export_dir: str | Path | None = None,
    width_mm: float = 100.0,
    height_mm: float = 75.0,
    dpi: int = 300,
) -> list[BatchItem]:
    """Run an analysis recipe over many files.

    For each file: import it, run the recipe on the first X/Y columns, optionally
    write a text report and a graph (raw data + every result curve) as a PDF.
    """
    from .io._types import first_xy_names
    from .io.export import export_graph
    from .model import ColumnType, PlotSpec, Project
    from .plotting import make_default_graph
    from .recipes import run_recipe

    items: list[BatchItem] = []
    for raw in paths:
        path = Path(raw)
        try:
            book = import_file(path)
            if not book.sheets:
                raise ValueError("no sheets in file")
            sheet = book.sheets[0]
            x_name, y_name = first_xy_names(sheet)
            if x_name is None or y_name is None:
                raise ValueError("no X/Y columns found")
            x = sheet.column(x_name).float_data()
            y = sheet.column(y_name).float_data()
            result = run_recipe(recipe, x, y)

            report_path = None
            if report_dir is not None:
                report_path = Path(report_dir) / f"{path.stem}.txt"
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(result.to_text(), encoding="utf-8")

            figure_path = None
            if export_dir is not None:
                project = Project()
                project.add_workbook(book)
                graph = make_default_graph(project, "Batch")
                source = f"{book.name}/{sheet.name}"
                for name, (cx, cy) in result.curves.items():
                    cx_name = sheet.unique_column_name(f"{name}_X")
                    cy_name = sheet.unique_column_name(f"{name}_Y")
                    sheet.add_column(cx_name, ColumnType.X, cx)
                    sheet.add_column(cy_name, ColumnType.Y, cy)
                    graph.first_layer.add_plot(PlotSpec(source=source, x=cx_name, y=cy_name, legend=name))
                figure_path = Path(export_dir) / f"{path.stem}.pdf"
                figure_path.parent.mkdir(parents=True, exist_ok=True)
                export_graph(graph, project, figure_path, width_mm=width_mm, height_mm=height_mm, dpi=dpi)

            items.append(BatchItem(path=path, ok=True, result=result,
                                   report_path=report_path, figure_path=figure_path))
        except Exception as exc:  # noqa: BLE001 - per-file isolation
            items.append(BatchItem(path=path, ok=False, error=f"{type(exc).__name__}: {exc}"))
    return items


__all__ = ["process_files", "run_recipe_over_files", "BatchItem"]
