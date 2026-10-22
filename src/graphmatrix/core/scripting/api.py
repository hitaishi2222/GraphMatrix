"""Programmatic API — the namespace the console, macros, and batch jobs use.

This is GraphMatrix's answer to LabTalk, except it is just Python: the API mutates the
project through the same Commands the GUI uses, so scripted changes are undoable
and recordable.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from ..commands import (
    AddColumnCommand,
    AddWorkbookCommand,
    AddWorksheetCommand,
    Command,
    CommandStack,
)
from ..io.importer import import_file
from ..model import (
    LINE_STYLES,
    Annotation,
    AxisScale,
    Column,
    ColumnType,
    Graph,
    Layer,
    PlotSpec,
    PlotStyle,
    Project,
    ReferenceLine,
    Workbook,
    Worksheet,
)


class GraphMatrixAPI:
    """A thin, name-resolving facade over a :class:`Project`."""

    def __init__(self, project: Project, commands: CommandStack | None = None) -> None:
        self.project = project
        self.commands = commands

    # -- infrastructure ------------------------------------------------------
    def _push(self, command: Command) -> Command:
        if self.commands is not None:
            return self.commands.push(command)
        command.execute()
        return command

    def sheet(self, source: str) -> Worksheet:
        """Resolve "Book/Sheet" (or a unique sheet name) to a Worksheet."""
        if "/" in source:
            found = self.project.sheet(source)
            if found is not None:
                return found
        for book in self.project.workbooks:
            found = book.sheet(source)
            if found is not None:
                return found
        raise KeyError(f"no worksheet {source!r}")

    def graph(self, name: str) -> Graph:
        graph = self.project.graph(name)
        if graph is None:
            raise KeyError(f"no graph {name!r}")
        return graph

    # -- construction --------------------------------------------------------
    def new_project(self, name: str = "Untitled") -> Project:
        self.project = Project(name)
        return self.project

    def add_workbook(self, name: str = "Book") -> Workbook:
        book = Workbook(self.project.unique_name(name))
        self._push(AddWorkbookCommand(self.project, book))
        return book

    def add_worksheet(self, book_name: str, sheet_name: str | None = None) -> Worksheet:
        book = self.project.workbook(book_name)
        if book is None:
            book = self.add_workbook(book_name)
        sheet = Worksheet(sheet_name or book.next_sheet_name())
        self._push(AddWorksheetCommand(book, sheet))
        return sheet

    def add_column(
        self,
        source: str,
        name: str,
        col_type: str = "Y",
        data: Sequence[Any] | None = None,
        *,
        units: str = "",
        comment: str = "",
        mask: Sequence[bool] | None = None,
    ) -> Column:
        sheet = self.sheet(source)
        column = Column(
            name, ColumnType(col_type), data, units=units, comment=comment, mask=mask
        )
        self._push(AddColumnCommand(sheet, column, source=source))
        return column

    def add_graph(
        self,
        name: str = "Graph",
        source: str | None = None,
        x: str | None = None,
        y: str | None = None,
        *,
        style: str = "line+symbol",
        legend: str = "",
        graph_type: str = "simple",
        title: str = "",
        panels: int | None = None,
        rows: int | None = None,
        cols: int | None = None,
    ) -> Graph:
        """Create a graph, optionally with its first plot.

        ``graph_type`` selects the figure template: ``simple``, ``stack``,
        ``stack-line``, ``double-y``, ``x-twin`` or ``grid`` (see
        :mod:`graphmatrix.core.scripting.graphs`).
        """
        from .graphs import create_graph

        result = create_graph(
            self.project,
            self.commands,
            name=name,
            graph_type=graph_type,
            source=source or "",
            x=x or "",
            y=y or "",
            style=style,
            legend=legend,
            title=title,
            panels=panels,
            rows=rows,
            cols=cols,
            strict=False,
        )
        return self.graph(result["graph"])

    def create_graph(self, name: str = "Graph", **kwargs: Any) -> Graph:
        """Create a graph of any template; keyword arguments mirror
        :func:`graphmatrix.core.scripting.graphs.create_graph`."""
        from .graphs import create_graph as _create

        payload = dict(kwargs)
        payload.setdefault("name", name)
        result = _create(self.project, self.commands, strict=False, **payload)
        return self.graph(result["graph"])

    def describe_project(self) -> dict[str, Any]:
        """A detailed, model-friendly map of the project (data + graphs)."""
        from .graphs import describe_project

        return describe_project(self.project)

    def set_graph_type(
        self,
        graph_name: str,
        graph_type: str,
        *,
        panels: int | None = None,
        rows: int | None = None,
        cols: int | None = None,
    ) -> Graph:
        """Switch a graph's template (and optionally its panel count)."""
        from .graphs import set_graph_type as _set

        _set(
            self.project,
            self.commands,
            graph_name,
            graph_type,
            panels=panels,
            rows=rows,
            cols=cols,
        )
        return self.graph(graph_name)

    def set_property(
        self, graph_name: str, key: str, value: Any, *, panel: int = 1
    ) -> Graph:
        """Set one graph or panel property (labels, axis scale, legend, …)."""
        from .graphs import set_property as _set

        _set(self.project, self.commands, graph_name, key, value, panel=panel)
        return self.graph(graph_name)

    def add_plot(
        self,
        graph_name: str,
        source: str,
        x: str,
        y: str,
        *,
        style: str = "line+symbol",
        legend: str = "",
        z: str = "",
        cmap: str = "viridis",
        panel: int = 1,
        y_axis: str = "left",
    ) -> PlotSpec:
        """Add a series to a graph; ``panel`` is 1-based."""
        from .graphs import add_plot as _add

        _add(
            self.project,
            self.commands,
            graph_name,
            source=source,
            x=x,
            y=y,
            style=style,
            legend=legend,
            panel=panel,
            y_axis=y_axis,
            z=z,
            cmap=cmap,
            strict=False,
        )
        graph = self.graph(graph_name)
        layer = graph.layers[min(panel, len(graph.layers)) - 1]
        return layer.plots[-1]

    # -- data ----------------------------------------------------------------
    def import_data(self, path: str, *, book_name: str | None = None) -> Workbook:
        book = import_file(path)
        if book_name:
            book.name = self.project.unique_name(book_name)
        else:
            book.name = self.project.unique_name(book.name)
        self._push(AddWorkbookCommand(self.project, book))
        return book

    def column(self, source: str, name: str) -> Column:
        column = self.sheet(source).column(name)
        if column is None:
            raise KeyError(f"no column {name!r} in {source!r}")
        return column

    # -- analysis (thin delegates) ------------------------------------------
    def describe(self, source: str, name: str):
        from ..analysis import descriptive

        return descriptive.summarize(self.column(source, name).float_data(), name)

    def fit(
        self,
        model: str,
        source: str,
        x: str,
        y: str,
        *,
        yerr: str | None = None,
        p0: dict[str, float] | None = None,
        x_min: float | None = None,
        x_max: float | None = None,
    ):
        from ..analysis import fitting

        sheet = self.sheet(source)
        yerr_data = sheet.column(yerr).float_data() if yerr else None
        return fitting.fit_model(
            model,
            sheet.column(x).float_data(),
            sheet.column(y).float_data(),
            yerr=yerr_data,
            p0=p0,
            x_min=x_min,
            x_max=x_max,
        )

    def linear_fit(
        self,
        source: str,
        x: str,
        y: str,
        *,
        x_min: float | None = None,
        x_max: float | None = None,
    ):
        from ..analysis import regression

        sheet = self.sheet(source)
        return regression.linear_fit(
            sheet.column(x).float_data(),
            sheet.column(y).float_data(),
            x_min=x_min,
            x_max=x_max,
        )

    def polynomial_fit(
        self,
        source: str,
        x: str,
        y: str,
        degree: int = 2,
        *,
        x_min: float | None = None,
        x_max: float | None = None,
    ):
        from ..analysis import regression

        sheet = self.sheet(source)
        return regression.polynomial_fit(
            sheet.column(x).float_data(),
            sheet.column(y).float_data(),
            degree,
            x_min=x_min,
            x_max=x_max,
        )

    def find_peaks(self, source: str, x: str, y: str, **kwargs):
        from ..analysis import peaks

        sheet = self.sheet(source)
        return peaks.find_peaks_result(
            sheet.column(x).float_data(), sheet.column(y).float_data(), **kwargs
        )

    def batch_stats(self):
        """Descriptive statistics over every numeric column in the project (M10)."""
        from ..analysis import descriptive

        return descriptive.batch_summary(self.project)

    # -- persistence ---------------------------------------------------------
    def save(self, path: str) -> Path:
        return self.project.save(path)

    def load(self, path: str) -> Project:
        self.project = Project.open(path)
        return self.project


def make_namespace(api: GraphMatrixAPI) -> dict[str, Any]:
    """The globals available in the console / macros."""
    import math

    import scipy

    return {
        "api": api,
        "project": api.project,
        "np": np,
        "numpy": np,
        "scipy": scipy,
        "math": math,
        "Project": Project,
        "Workbook": Workbook,
        "Worksheet": Worksheet,
        "Column": Column,
        "ColumnType": ColumnType,
        "Graph": Graph,
        "PlotSpec": PlotSpec,
        "PlotStyle": PlotStyle,
        "Layer": Layer,
        "AxisScale": AxisScale,
        "ReferenceLine": ReferenceLine,
        "Annotation": Annotation,
        "LINE_STYLES": LINE_STYLES,
    }


__all__ = ["GraphMatrixAPI", "make_namespace"]
