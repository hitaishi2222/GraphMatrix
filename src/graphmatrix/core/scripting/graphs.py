"""Intent-level graph building blocks for agents (MCP) and scripts.

GraphMatrix is scriptable at two levels:

* the object level — :class:`graphmatrix.core.scripting.api.GraphMatrixAPI`
  exposes every model object, which is powerful but demands that the caller
  already knows the object model (layers, panels, plot specs, …);
* the intent level — this module. Each helper answers one plain-language
  request ("make me a 2x2 grid of these two columns", "put this series on the
  right-hand Y axis") and returns a plain, JSON-friendly dictionary so an MCP
  client can hand the result straight back to a model.

Everything here is Qt-free, works on a bare :class:`Project`, and pushes
:class:`~graphmatrix.core.commands.Command` objects, so edits made through the
MCP tools are undoable in the GUI like any other edit.

The functions take ``(project, commands, ...)`` so they can be called both
from the in-app console (``api.project``, ``api.commands``) and from the MCP
server, which reaches the live GUI over the IPC bridge.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Sequence

from ..commands import (
    AddColumnCommand,
    AddGraphCommand,
    AddLayerCommand,
    AddPlotCommand,
    AddWorkbookCommand,
    AddWorksheetCommand,
    Command,
    CommandStack,
    RemoveGraphCommand,
    RemovePlotCommand,
    SetAttributesCommand,
    SetGraphTypeCommand,
)
from ..model import (
    AxisScale,
    Column,
    ColumnType,
    Graph,
    GraphType,
    Layer,
    PlotSpec,
    PlotStyle,
    Project,
    Workbook,
    Worksheet,
)

#: Human-readable description of every graph template, with the number of
#: panels it shows. Used by the MCP tools so a model can pick a type without
#: guessing.
GRAPH_TYPE_HELP: dict[str, str] = {
    "simple": "One panel, one X/Y pair.",
    "stack": "Panels stacked vertically, sharing the X axis.",
    "double-y": "One panel with a second (right-hand) Y axis.",
    "x-twin": "Panels side by side, sharing the Y axis.",
    "grid": "An R x C grid of panels.",
}

#: Plot styles the backends understand.
PLOT_STYLES: tuple[str, ...] = tuple(style.value for style in PlotStyle)

#: Column types a worksheet can hold.
COLUMN_TYPES: tuple[str, ...] = tuple(ct.value for ct in ColumnType)


class GraphToolError(RuntimeError):
    """Raised for bad requests (unknown graph, wrong panel, unknown style)."""


# ---------------------------------------------------------------- utilities


def _push(commands: CommandStack | None, command: Command) -> Command:
    """Execute a command through the stack (undoable) or straight away."""
    if commands is not None:
        return commands.push(command)
    command.execute()
    return command


def _graph(project: Project, name: str) -> Graph:
    graph = project.graph(name)
    if graph is None:
        known = ", ".join(g.name for g in project.graphs) or "none"
        raise GraphToolError(f"no graph named {name!r} (have: {known})")
    return graph


def _sheet(project: Project, source: str) -> tuple[Workbook, Worksheet]:
    """Resolve ``"Book/Sheet"`` (or a unique sheet name) to a worksheet."""
    if "/" in source:
        book_name, _, sheet_name = source.partition("/")
        book = project.workbook(book_name)
        if book is not None:
            sheet = book.sheet(sheet_name)
            if sheet is not None:
                return book, sheet
    for book in project.workbooks:
        sheet = book.sheet(source)
        if sheet is not None:
            return book, sheet
    known = ", ".join(
        f"{b.name}/{s.name}" for b in project.workbooks for s in b.sheets
    ) or "none"
    raise GraphToolError(f"no worksheet {source!r} (have: {known})")


def _column_type(value: str | ColumnType) -> ColumnType:
    try:
        return ColumnType(value)
    except ValueError as exc:
        raise GraphToolError(
            f"unknown column type {value!r} (have: {', '.join(COLUMN_TYPES)})"
        ) from exc


def _plot_style(value: str | PlotStyle) -> PlotStyle:
    try:
        return PlotStyle(value)
    except ValueError as exc:
        raise GraphToolError(
            f"unknown plot style {value!r} (have: {', '.join(PLOT_STYLES)})"
        ) from exc


def _graph_type(value: str | GraphType) -> GraphType:
    try:
        return GraphType(value)
    except ValueError as exc:
        raise GraphToolError(
            f"unknown graph type {value!r} "
            f"(have: {', '.join(GRAPH_TYPE_HELP)})"
        ) from exc


def _panel_count(graph_type: GraphType, panels: int | None, rows: int | None,
                 cols: int | None) -> int:
    """How many panels a graph of this type should have."""
    if graph_type == GraphType.GRID:
        r = max(1, int(rows or 2))
        c = max(1, int(cols or 2))
        return r * c
    if graph_type in (GraphType.STACK, GraphType.X_TWIN):
        return max(1, int(panels or 2))
    return 1


# ------------------------------------------------------------- description


def describe_project(
    project: Project, commands: CommandStack | None = None
) -> dict[str, Any]:
    """A detailed, model-friendly map of the project.

    Tells an agent what data exists, which columns can be plotted, and what
    every graph currently shows — the three things needed before making a
    sensible new graph.
    """
    workbooks = []
    for book in project.workbooks:
        sheets = []
        for sheet in book.sheets:
            columns = [
                {
                    "name": col.name,
                    "type": col.col_type.value,
                    "rows": len(col),
                    "units": col.units,
                    "comment": col.comment,
                }
                for col in sheet.columns
            ]
            x_cols = [c["name"] for c in columns if c["type"] == "X"]
            y_cols = [c["name"] for c in columns if c["type"] == "Y"]
            sheets.append(
                {
                    "name": sheet.name,
                    "label": f"{book.name}/{sheet.name}",
                    "rows": sheet.num_rows,
                    "columns": columns,
                    "x_columns": x_cols,
                    "y_columns": y_cols,
                    "plottable_pairs": [
                        {"x": x, "y": y} for x in x_cols for y in y_cols
                    ],
                }
            )
        workbooks.append({"name": book.name, "sheets": sheets})

    graphs = []
    for graph in project.graphs:
        graphs.append(
            {
                "name": graph.name,
                "title": graph.title,
                "graph_type": graph.graph_type,
                "layout": [graph.layout_rows, graph.layout_cols],
                "panels": [
                    {
                        "panel": index + 1,
                        "layer": layer.name,
                        "x_label": layer.x_label,
                        "y_label": layer.y_label,
                        "y2_label": layer.y2_label,
                        "show_y_axis": layer.show_y_axis,
                        "show_legend": layer.show_legend,
                        "plots": [
                            {
                                "source": spec.source,
                                "x": spec.x,
                                "y": spec.y,
                                "style": PlotStyle(spec.style).value,
                                "legend": spec.legend,
                                "y_axis": spec.y_axis,
                                "z": spec.z,
                                "cmap": spec.cmap,
                            }
                            for spec in layer.plots
                        ],
                    }
                    for index, layer in enumerate(graph.layers)
                ],
            }
        )

    return {
        "name": project.name,
        "workbooks": workbooks,
        "graphs": graphs,
        "capabilities": {
            "graph_types": GRAPH_TYPE_HELP,
            "plot_styles": list(PLOT_STYLES),
            "column_types": list(COLUMN_TYPES),
        },
    }


# ------------------------------------------------------------ graph making


def create_graph(
    project: Project,
    commands: CommandStack | None,
    *,
    name: str = "Graph",
    graph_type: str = "simple",
    source: str = "",
    x: str = "",
    y: str = "",
    style: str = "line+symbol",
    legend: str = "",
    title: str = "",
    panels: int | None = None,
    rows: int | None = None,
    cols: int | None = None,
    y_axis: str = "left",
    z: str = "",
    cmap: str = "viridis",
    replicate: bool = True,
    strict: bool = True,
) -> dict[str, Any]:
    """Create a graph of any template, optionally with its first plot.

    ``graph_type`` is one of ``simple``, ``stack``, ``double-y``, ``x-twin`` or
    ``grid``. ``panels`` (stack/x-twin) and ``rows``/``cols`` (grid) control how
    many panels the figure has. When a data source is given, the same series is
    drawn in every panel unless ``replicate`` is false — the usual way to get a
    readable multi-panel figure before the panels are filled individually with
    :func:`add_plot`.
    """
    gtype = _graph_type(graph_type)
    plot_style = _plot_style(style)
    count = _panel_count(gtype, panels, rows, cols)

    graph = Graph(project.unique_name(name or "Graph"))
    graph.graph_type = gtype.value
    graph.title = title
    if gtype == GraphType.GRID:
        graph.layout_rows = max(1, int(rows or 2))
        graph.layout_cols = max(1, int(cols or 2))
    while len(graph.layers) < count:
        graph.add_layer(Layer(f"Layer {len(graph.layers) + 1}"))
    graph.sync_layout()

    if source and x and y:
        if strict:
            _book, sheet = _sheet(project, source)
            if sheet.column(x) is None:
                raise GraphToolError(f"no column {x!r} in {source!r}")
            if sheet.column(y) is None:
                raise GraphToolError(f"no column {y!r} in {source!r}")
        spec = PlotSpec(
            source=source,
            x=x,
            y=y,
            style=plot_style,
            legend=legend or y,
            y_axis=y_axis,
            z=z,
            cmap=cmap,
        )
        targets = graph.layers if replicate else graph.layers[:1]
        for layer in targets:
            layer.add_plot(copy.deepcopy(spec))

    _push(commands, AddGraphCommand(project, graph))
    return {
        "graph": graph.name,
        "graph_type": graph.graph_type,
        "layout": [graph.layout_rows, graph.layout_cols],
        "panels": len(graph.layers),
        "plots": sum(len(layer.plots) for layer in graph.layers),
    }


def add_plot(
    project: Project,
    commands: CommandStack | None,
    graph_name: str,
    *,
    source: str,
    x: str,
    y: str,
    style: str = "line+symbol",
    legend: str = "",
    panel: int = 1,
    y_axis: str = "left",
    z: str = "",
    cmap: str = "viridis",
    color: str = "",
    symbol: str = "o",
    line_style: str = "solid",
    line_width: float = 2.0,
    replace: bool = False,
    strict: bool = True,
) -> dict[str, Any]:
    """Add one series to a panel of an existing graph.

    ``panel`` is 1-based. Panels that do not exist yet are created, so a stack
    or grid can be filled panel by panel. With ``replace`` the panel's
    existing series are removed first — handy when a new graph replicated its
    first series into every panel and one panel should show something else.
    """
    graph = _graph(project, graph_name)
    plot_style = _plot_style(style)
    if strict:
        _book, sheet = _sheet(project, source)
        if sheet.column(x) is None:
            raise GraphToolError(f"no column {x!r} in {source!r}")
        if sheet.column(y) is None:
            raise GraphToolError(f"no column {y!r} in {source!r}")
    if y_axis not in ("left", "right"):
        raise GraphToolError("y_axis must be 'left' or 'right'")

    while len(graph.layers) < panel:
        layer = Layer(f"Layer {len(graph.layers) + 1}")
        _push(commands, AddLayerCommand(graph, layer))
    layer = graph.layers[panel - 1]
    if replace:
        for existing in list(layer.plots):
            _push(commands, RemovePlotCommand(graph, layer, existing))

    spec = PlotSpec(
        source=source,
        x=x,
        y=y,
        style=plot_style,
        legend=legend or y,
        y_axis=y_axis,
        z=z,
        cmap=cmap,
        color=color,
        symbol=symbol,
        line_style=line_style,
        line_width=line_width,
    )
    _push(commands, AddPlotCommand(graph, layer, spec))
    graph.sync_layout()
    if graph.graph_type == GraphType.GRID:
        graph.layout_rows = max(1, math.ceil(len(graph.layers) / graph.layout_cols))
    return {
        "graph": graph.name,
        "panel": panel,
        "plots": len(layer.plots),
        "series": f"{y} vs {x} ({source})",
    }


def set_graph_type(
    project: Project,
    commands: CommandStack | None,
    graph_name: str,
    graph_type: str,
    *,
    panels: int | None = None,
    rows: int | None = None,
    cols: int | None = None,
) -> dict[str, Any]:
    """Switch a graph's template and, if asked, resize its panels."""
    graph = _graph(project, graph_name)
    gtype = _graph_type(graph_type)
    _push(commands, SetGraphTypeCommand(graph, gtype.value))

    target = _panel_count(gtype, panels, rows, cols)
    while len(graph.layers) < target:
        layer = Layer(f"Layer {len(graph.layers) + 1}")
        _push(commands, AddLayerCommand(graph, layer))
    if gtype == GraphType.GRID:
        graph.layout_rows = max(1, int(rows or graph.layout_rows or 2))
        graph.layout_cols = max(1, int(cols or graph.layout_cols or 2))
    graph.sync_layout()
    if gtype == GraphType.GRID:
        graph.layout_rows = max(1, math.ceil(len(graph.layers) / graph.layout_cols))
    return {
        "graph": graph.name,
        "graph_type": graph.graph_type,
        "layout": [graph.layout_rows, graph.layout_cols],
        "panels": len(graph.layers),
    }


def delete_graph(
    project: Project, commands: CommandStack | None, graph_name: str
) -> dict[str, Any]:
    """Remove a graph from the project (undoable)."""
    graph = _graph(project, graph_name)
    _push(commands, RemoveGraphCommand(project, graph))
    return {"deleted": graph.name, "graphs": len(project.graphs)}


# ------------------------------------------------------------------- data


def add_data(
    project: Project,
    commands: CommandStack | None,
    *,
    book: str = "Book",
    sheet: str = "Sheet1",
    columns: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a worksheet and fill it with columns.

    Each column is a dict::

        {"name": "X", "type": "X", "values": [0, 1, 2]}
        {"name": "Y", "type": "Y", "generate": {"kind": "sin", "count": 50}}

    ``values`` takes a literal list; ``generate`` builds a series without
    shipping numbers over the wire. Generator kinds: ``linspace`` (start,
    stop, count), ``arange`` (start, stop, step), ``sin``/``cos`` (count, and
    optionally ``amp``, ``freq``, ``phase``), ``random`` (count, ``seed``,
    ``scale``), ``ramp`` (count).
    """
    if not columns:
        raise GraphToolError("columns must not be empty")

    workbook = project.workbook(book)
    if workbook is None:
        workbook = Workbook(project.unique_name(book))
        _push(commands, AddWorkbookCommand(project, workbook))
    target = workbook.sheet(sheet)
    if target is None:
        target = Worksheet(sheet)
        _push(commands, AddWorksheetCommand(workbook, target))

    created = []
    for spec in columns:
        name = str(spec.get("name") or "").strip()
        if not name:
            raise GraphToolError("every column needs a name")
        col_type = _column_type(spec.get("type", "Y"))
        values = spec.get("values")
        if values is None and spec.get("generate"):
            values = _generate(spec["generate"])
        column = Column(
            name,
            col_type,
            values,
            units=str(spec.get("units", "")),
            comment=str(spec.get("comment", "")),
        )
        _push(commands, AddColumnCommand(target, column, source=f"{workbook.name}/{sheet}"))
        created.append({"name": name, "type": col_type.value, "rows": len(column)})

    return {
        "book": workbook.name,
        "sheet": target.name,
        "source": f"{workbook.name}/{target.name}",
        "columns": created,
        "rows": target.num_rows,
    }


def _generate(spec: dict[str, Any]) -> list[float]:
    """Build a numeric series from a small generator description."""
    import numpy as np

    kind = str(spec.get("kind", "linspace")).lower()
    count = int(spec.get("count", 50) or 50)
    if kind == "linspace":
        return list(
            np.linspace(
                float(spec.get("start", 0.0)),
                float(spec.get("stop", 1.0)),
                count,
            )
        )
    if kind == "arange":
        return list(
            np.arange(
                float(spec.get("start", 0.0)),
                float(spec.get("stop", float(count))),
                float(spec.get("step", 1.0)),
            )
        )
    if kind in ("sin", "cos"):
        x = np.linspace(0.0, 1.0, count)
        amp = float(spec.get("amp", 1.0))
        freq = float(spec.get("freq", 1.0))
        phase = float(spec.get("phase", 0.0))
        wave = np.sin(2 * np.pi * freq * x + phase) if kind == "sin" else np.cos(
            2 * np.pi * freq * x + phase
        )
        return list(amp * wave)
    if kind == "random":
        rng = np.random.default_rng(int(spec.get("seed", 0)))
        scale = float(spec.get("scale", 1.0))
        return list(rng.normal(0.0, scale, count))
    if kind == "ramp":
        return list(np.arange(count, dtype=float))
    raise GraphToolError(
        f"unknown generator {kind!r} (have: linspace, arange, sin, cos, random, ramp)"
    )


# --------------------------------------------------------------- properties


#: Properties that belong to the graph itself.
GRAPH_PROPERTIES = (
    "title",
    "title_font_family",
    "title_font_size",
    "title_color",
    "panel_gap_x",
    "panel_gap_y",
    "y_delta",
    "layout_rows",
    "layout_cols",
    "plot_theme",
    "journal_preset",
)

#: Properties that belong to a panel (layer).
PANEL_PROPERTIES = (
    "x_label",
    "y_label",
    "y2_label",
    "z_label",
    "x_scale",
    "y_scale",
    "x_min",
    "x_max",
    "y_min",
    "y_max",
    "show_legend",
    "show_y_axis",
    "minor_ticks",
    "tick_direction",
    "label_font_family",
    "label_font_size",
    "label_color",
)

_BOOLS = {"true": True, "yes": True, "on": True, "1": True,
          "false": False, "no": False, "off": False, "0": False}


def _coerce(key: str, value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _BOOLS:
            return _BOOLS[lowered]
        if key in ("x_scale", "y_scale"):
            try:
                return AxisScale(lowered)
            except ValueError as exc:
                raise GraphToolError(
                    f"{key} must be 'linear' or 'log', got {value!r}"
                ) from exc
        try:
            if "." in value or "e" in lowered:
                return float(value)
            return int(value)
        except ValueError:
            return value
    return value


def set_property(
    project: Project,
    commands: CommandStack | None,
    graph_name: str,
    key: str,
    value: Any,
    *,
    panel: int = 1,
) -> dict[str, Any]:
    """Set one property of a graph or of one of its panels.

    Graph properties: ``title``, ``panel_gap_x``, ``panel_gap_y``,
    ``y_delta``, ``layout_rows``, ``layout_cols``, ``plot_theme``,
    ``journal_preset``, ``title_font_size``, ``title_color``.
    Panel properties: ``x_label``, ``y_label``, ``y2_label``, ``z_label``,
    ``x_scale``, ``y_scale``, ``x_min``, ``x_max``, ``y_min``, ``y_max``,
    ``show_legend``, ``show_y_axis``, ``minor_ticks``, ``tick_direction``,
    ``label_font_size``, ``label_font_family``, ``label_color``.
    """
    graph = _graph(project, graph_name)
    key = key.strip()
    if key in GRAPH_PROPERTIES:
        target: Any = graph
    elif key in PANEL_PROPERTIES:
        if panel < 1 or panel > len(graph.layers):
            raise GraphToolError(
                f"panel {panel} does not exist on {graph_name!r} "
                f"({len(graph.layers)} panels)"
            )
        target = graph.layers[panel - 1]
    else:
        raise GraphToolError(
            f"unknown property {key!r} "
            f"(graph: {', '.join(GRAPH_PROPERTIES)}; "
            f"panel: {', '.join(PANEL_PROPERTIES)})"
        )
    _push(commands, SetAttributesCommand(target, f"Set {key}", **{key: _coerce(key, value)}))
    return {"graph": graph.name, "property": key, "value": _coerce(key, value)}


# ------------------------------------------------------------------ export


def _resolve_graphs(project: Project, selection: Sequence[str] | None) -> list[str]:
    """Turn a selection into graph names.

    Accepts names (``"Damped"``), 1-based positions (``"2"``) and ranges
    (``"2-4"``), separated by commas — the same syntax the session ``export``
    tool uses.
    """
    if not selection:
        return [g.name for g in project.graphs]
    if isinstance(selection, str):
        selection = [selection]
    names: list[str] = []
    for chunk in str(",".join(str(s) for s in selection)).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk and all(part.strip().isdigit() for part in chunk.split("-", 1)):
            low, high = (int(p) for p in chunk.split("-", 1))
            low, high = min(low, high), max(low, high)
            for position in range(low, high + 1):
                names.append(_graph_at(project, position))
            continue
        if chunk.isdigit():
            names.append(_graph_at(project, int(chunk)))
            continue
        names.append(chunk)
    return names


def _graph_at(project: Project, position: int) -> str:
    if position < 1 or position > len(project.graphs):
        raise GraphToolError(
            f"graph position {position} out of range (1..{len(project.graphs)})"
        )
    return project.graphs[position - 1].name


def export_graphs(
    project: Project,
    commands: CommandStack | None = None,
    graphs: Sequence[str] | None = None,
    *,
    out_dir: str = ".",
    format: str = "pdf",
    dpi: int = 300,
    width_mm: float = 100.0,
    height_mm: float = 75.0,
    transparent: bool = False,
    theme: str = "",
    aspect: float | None = None,
    scale: float = 1.0,
    white_background: bool = False,
) -> dict[str, Any]:
    """Export graphs to files and return the list of written paths.

    ``theme`` is the application theme the canvas follows, so the files look
    like the preview; ``aspect`` keeps the on-screen proportions and ``scale``
    shrinks the typography so a small page shows the same proportions.
    ``white_background`` forces the print-safe palette (white paper, black
    ink) whatever the application theme looks like.
    """
    from pathlib import Path

    from ..io.export import export_graph

    targets = _resolve_graphs(project, graphs)
    if not targets:
        raise GraphToolError("project has no graphs to export")
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name in targets:
        graph = _graph(project, name)
        safe = (
            "".join(c if c.isalnum() or c in "-_." else "_" for c in graph.name).strip("_")
            or "graph"
        )
        target = out_path / f"{safe}.{format.lower()}"
        export_graph(
            graph,
            project,
            target,
            width_mm=width_mm,
            height_mm=height_mm,
            dpi=dpi,
            transparent=transparent,
            theme=theme,
            aspect=aspect,
            scale=scale,
            white_background=white_background,
        )
        written.append(str(target))
    return {"files": written}


__all__ = [
    "COLUMN_TYPES",
    "GRAPH_PROPERTIES",
    "GRAPH_TYPE_HELP",
    "PANEL_PROPERTIES",
    "PLOT_STYLES",
    "GraphToolError",
    "add_data",
    "add_plot",
    "create_graph",
    "delete_graph",
    "describe_project",
    "export_graphs",
    "set_graph_type",
    "set_property",
]
