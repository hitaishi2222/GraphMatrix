"""MCP server exposing GraphMatrix projects to AI assistants.

Run with: ``graphmatrix-mcp`` (stdio transport) or ``python -m graphmatrix.mcp_server``.
For a port-based server that the GUI can start and stop, use
``graphmatrix-mcp --transport http --port 8765``.
Install the optional dependency first: ``pip install graphmatrix[mcp]``.

Two families of tools are offered:

*session tools* (``connect``, ``summary``, ``run``, ``export``) work on a
project opened in the server's own process;

*live tools* (``live_summary``, ``live_describe``, ``live_create_graph``,
``live_add_plot``, ``live_set_graph_type``, ``live_add_data``,
``live_set_property``, ``live_delete_graph``, ``live_save``, ``live_export``,
``live_run``, ``live_open``, ``live_screenshot``) act on the GraphMatrix
window that is running on this machine. They are the intended path for an
assistant that should drive the application the user is looking at: changes
land in the open project, are undoable with Ctrl+Z, and are visible at once.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import uuid
from pathlib import Path
from typing import Any

try:
    from fastmcp import FastMCP
except Exception:  # pragma: no cover - optional dependency
    FastMCP = None  # type: ignore[assignment]


def _make_mcp():
    if FastMCP is None:
        raise RuntimeError(
            "fastmcp is not installed; run `pip install graphmatrix[mcp]`"
        )
    return FastMCP("graphmatrix")


# In-memory project sessions: project_id -> (Project, CommandStack)
_SESSIONS: dict[str, tuple[Any, Any]] = {}


def _summary(project) -> dict[str, Any]:
    return {
        "name": project.name,
        "workbooks": [
            {
                "name": book.name,
                "sheets": [
                    {
                        "name": sheet.name,
                        "columns": sheet.column_names,
                        "rows": sheet.num_rows,
                    }
                    for sheet in book.sheets
                ],
            }
            for book in project.workbooks
        ],
        "graphs": [
            {
                "index": i + 1,
                "name": graph.name,
                "graph_type": getattr(graph, "graph_type", "simple"),
                "layout": [
                    getattr(graph, "layout_rows", 1),
                    getattr(graph, "layout_cols", 1),
                ],
                "layers": len(graph.layers),
                "plots": sum(len(layer.plots) for layer in graph.layers),
            }
            for i, graph in enumerate(project.graphs)
        ],
        "versions": [
            {
                "name": v.get("name", ""),
                "created": v.get("created", ""),
                "note": v.get("note", ""),
            }
            for v in getattr(project, "versions", [])
        ],
    }


def _parse_graph_selection(spec, total: int) -> list[int]:
    if not spec:
        return list(range(total))
    result: list[int] = []
    text = str(spec).strip().strip("()").strip("[]")
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            left, right = chunk.split("-", 1)
            start, end = int(left.strip()), int(right.strip())
            if start > end:
                start, end = end, start
            for n in range(start, end + 1):
                result.append(n - 1)
        else:
            result.append(int(chunk) - 1)
    seen: set[int] = set()
    out: list[int] = []
    for idx in result:
        if idx < 0 or idx >= total:
            raise ValueError(f"graph index {idx + 1} out of range (1..{total})")
        if idx not in seen:
            seen.add(idx)
            out.append(idx)
    return out


def connect(path: str | None = None) -> dict[str, Any]:
    """Open an existing project file, or create a new in-memory project."""
    from graphmatrix.core.commands import CommandStack
    from graphmatrix.core.model import Project

    from graphmatrix.core.instance import get as get_instance

    running = get_instance()
    if path and Path(path).exists():
        project = Project.open(path)
    elif (
        path is None
        and running
        and running.get("project")
        and Path(running["project"]).exists()
    ):
        project = Project.open(running["project"])
    else:
        project = Project(Path(path).stem if path else "Untitled")
    pid = str(uuid.uuid4())
    _SESSIONS[pid] = (project, CommandStack())
    return {
        "project_id": pid,
        "summary": _summary(project),
        "running_instance": running,
    }


def summary(project_id: str) -> dict[str, Any]:
    """Return workbooks, sheets, columns, and graphs for a project."""
    if project_id not in _SESSIONS:
        raise ValueError("unknown project_id")
    project, _ = _SESSIONS[project_id]
    return _summary(project)


def run(project_id: str, code: str) -> dict[str, Any]:
    """Execute Python against the project using the GraphMatrix API.

    The namespace holds ``api`` (a :class:`GraphMatrixAPI`), ``project``,
    ``np``/``numpy``, ``scipy`` and ``math``. Intent-level helpers live on
    ``api`` too: ``api.create_graph(..., graph_type="stack")``,
    ``api.add_plot(...)``, ``api.set_graph_type(...)``,
    ``api.set_property(...)`` and ``api.describe_project()``.
    """
    if project_id not in _SESSIONS:
        raise ValueError("unknown project_id")
    project, commands = _SESSIONS[project_id]
    from graphmatrix.core.scripting.api import GraphMatrixAPI, make_namespace

    api = GraphMatrixAPI(project, commands)
    ns = make_namespace(api)
    buf = io.StringIO()
    err = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            exec(compile(code, "<mcp>", "exec"), ns)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "stdout": buf.getvalue(),
            "stderr": err.getvalue() + f"{type(exc).__name__}: {exc}",
        }
    _SESSIONS[project_id] = (api.project, commands)
    return {"ok": True, "stdout": buf.getvalue(), "stderr": err.getvalue()}


def export(
    project_id: str,
    graphs: str | None = None,
    out_dir: str = ".",
    format: str = "pdf",
    dpi: int = 300,
    width_mm: float = 100.0,
    height_mm: float = 75.0,
    transparent: bool = False,
) -> dict[str, Any]:
    """Export selected graphs (default: all) to a directory."""
    if project_id not in _SESSIONS:
        raise ValueError("unknown project_id")
    project, _ = _SESSIONS[project_id]
    from graphmatrix.core.io.export import export_graph

    if not project.graphs:
        raise ValueError("project has no graphs")
    indices = _parse_graph_selection(graphs, len(project.graphs))
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    for idx in indices:
        graph = project.graphs[idx]
        safe = (
            "".join(c if c.isalnum() or c in "-_." else "_" for c in graph.name).strip(
                "_"
            )
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
        )
        files.append(str(target))
    return {"files": files}


# -- live instance control (direct IPC to the running GUI) -------------------

#: Marker used to pick the JSON payload out of the GUI's stdout.
_JSON_MARKER = "<<<GRAPHMATRIX_JSON>>>"


class UnsupportedOp(RuntimeError):
    """The running GUI is older than this server and lacks the op."""


def _gui(op: str, **payload: Any) -> dict[str, Any]:
    """Send one op to the running GUI and return its answer."""
    from graphmatrix.core.ipc import request

    res = request(op, **payload)
    if not res.get("ok"):
        error = str(res.get("error", ""))
        if "unknown op" in error:
            raise UnsupportedOp(error)
        raise RuntimeError(error)
    return res


def _live_call(func: str, *, open_graphs: bool = False, **kwargs: Any) -> dict[str, Any]:
    """Call a helper of :mod:`graphmatrix.core.scripting.graphs` in the GUI.

    The GUI may predate the helper module, but Python imports it on demand,
    and it is reloaded on every call so the toolkit in a long-running window
    never goes stale.
    """
    from graphmatrix.core.ipc import request

    code = (
        "import importlib, json\n"
        "from graphmatrix.core.scripting import graphs as G\n"
        "G = importlib.reload(G)\n"
        f"_gm_result = G.{func}(api.project, api.commands, **{kwargs!r})\n"
        f"print({_JSON_MARKER!r} + json.dumps(_gm_result, default=str))\n"
    )
    res = request("run", code=code, open_graphs=open_graphs)
    if not res.get("ok"):
        raise RuntimeError(str(res.get("error", "live call failed")))
    stdout = res.get("stdout", "")
    if _JSON_MARKER not in stdout:
        raise RuntimeError(f"live call {func!r} returned no result: {stdout[-500:]!r}")
    line = stdout.split(_JSON_MARKER, 1)[1].strip().splitlines()[0]
    return json.loads(line)


def live_summary() -> dict[str, Any]:
    """Summary of the project open in the running GraphMatrix window."""
    from graphmatrix.core.ipc import request

    return request("summary")["summary"]


def live_describe() -> dict[str, Any]:
    """Detailed map of the live project: data, columns, graphs, capabilities.

    Use this first: it lists every worksheet with its typed columns (and which
    X/Y pairs are ready to plot), every graph with its panels and series, and
    the graph templates and plot styles this build supports.
    """
    try:
        return _gui("describe")["description"]
    except UnsupportedOp:
        return _live_call("describe_project")


def live_create_graph(
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
    open: bool = True,
) -> dict[str, Any]:
    """Create a graph in the running GUI and show it as a tab.

    ``graph_type`` is ``simple``, ``stack`` (panels share X), ``double-y``
    (second Y axis on the right), ``x-twin`` (panels share Y) or ``grid``
    (``rows`` x ``cols`` panels). ``panels`` sets the panel count for stack
    and x-twin. When ``source``/``x``/``y`` are given the series is drawn in
    every panel (set ``replicate=False`` to keep it in the first panel only).
    """
    return _live_call(
        "create_graph",
        open_graphs=bool(open),
        name=name,
        graph_type=graph_type,
        source=source,
        x=x,
        y=y,
        style=style,
        legend=legend,
        title=title,
        panels=panels,
        rows=rows,
        cols=cols,
        y_axis=y_axis,
        z=z,
        cmap=cmap,
        replicate=replicate,
    )


def live_add_plot(
    graph: str,
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
) -> dict[str, Any]:
    """Add one series to a panel of an existing graph in the running GUI.

    ``panel`` is 1-based; panels that do not exist yet are created, so a stack
    or grid can be filled panel by panel. ``y_axis="right"`` puts the series
    on the secondary axis of a double-Y graph. With ``replace`` the panel's
    current series are removed first.
    """
    return _live_call(
        "add_plot",
        graph_name=graph,
        source=source,
        x=x,
        y=y,
        style=style,
        legend=legend,
        panel=panel,
        y_axis=y_axis,
        z=z,
        cmap=cmap,
        color=color,
        symbol=symbol,
        line_style=line_style,
        line_width=line_width,
        replace=replace,
    )


def live_set_graph_type(
    graph: str,
    graph_type: str,
    panels: int | None = None,
    rows: int | None = None,
    cols: int | None = None,
) -> dict[str, Any]:
    """Switch a graph's template (and optionally its panel count)."""
    return _live_call(
        "set_graph_type",
        graph_name=graph,
        graph_type=graph_type,
        panels=panels,
        rows=rows,
        cols=cols,
    )


def live_add_data(
    book: str = "Book",
    sheet: str = "Sheet1",
    columns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a worksheet in the live project and fill it with columns.

    Each column is a dict: ``{"name": "X", "type": "X", "values": [0, 1, 2]}``
    or ``{"name": "Y", "type": "Y", "generate": {"kind": "sin", "count": 50}}``.
    Generator kinds: ``linspace`` (start, stop, count), ``arange`` (start, stop,
    step), ``sin``/``cos`` (count, amp, freq, phase), ``random`` (count, seed,
    scale), ``ramp`` (count).
    """
    if not columns:
        raise ValueError("columns must not be empty")
    return _live_call("add_data", book=book, sheet=sheet, columns=columns)


def live_set_property(
    graph: str,
    key: str,
    value: str,
    panel: int = 1,
) -> dict[str, Any]:
    """Set a graph or panel property in the running GUI.

    Graph properties: ``title``, ``panel_gap_x``, ``panel_gap_y``,
    ``y_delta``, ``layout_rows``, ``layout_cols``, ``plot_theme``,
    ``journal_preset``, ``title_font_size``, ``title_color``.
    Panel properties: ``x_label``, ``y_label``, ``y2_label``, ``z_label``,
    ``x_scale``, ``y_scale``, ``x_min``, ``x_max``, ``y_min``, ``y_max``,
    ``show_legend``, ``show_y_axis``, ``minor_ticks``, ``tick_direction``,
    ``label_font_size``, ``label_font_family``, ``label_color``.
    """
    return _live_call(
        "set_property", graph_name=graph, key=key, value=value, panel=panel
    )


def live_delete_graph(graph: str) -> dict[str, Any]:
    """Remove a graph from the live project (undoable in the GUI)."""
    return _live_call("delete_graph", graph_name=graph)


def live_save(path: str = "") -> dict[str, Any]:
    """Save the live project. Without a path the current file is reused."""
    if path:
        try:
            return _gui("save", path=path)
        except UnsupportedOp:
            pass
    from graphmatrix.core.ipc import request

    code = (
        "try:\n"
        "    from graphmatrix.core.ipc import current_window\n"
        "except Exception:\n"
        "    current_window = lambda: None\n"
        "from pathlib import Path\n"
        f"p = Path({path!r}) if {path!r} else None\n"
        "if p is None:\n"
        "    win = current_window()\n"
        "    p = getattr(win, '_path', None)\n"
        "if p is None:\n"
        "    raise RuntimeError('no path given and the project was never saved')\n"
        "api.save(str(p))\n"
        "try:\n"
        "    win = current_window()\n"
        "    if win is not None:\n"
        "        win._path = p\n"
        "        win._set_dirty(False)\n"
        "        win._update_title()\n"
        "except Exception:\n"
        "    pass\n"
        "print('SAVED ' + str(p))\n"
    )
    res = request("run", code=code)
    if not res.get("ok"):
        raise RuntimeError(str(res.get("error", "save failed")))
    return {"saved": res.get("stdout", "").strip().removeprefix("SAVED ")}


def live_export(
    graphs: str | None = None,
    out_dir: str = ".",
    format: str = "pdf",
    dpi: int = 300,
    width_mm: float = 100.0,
    height_mm: float = 75.0,
    transparent: bool = False,
    match_screen: bool = True,
    white_background: bool = False,
) -> dict[str, Any]:
    """Export graphs of the live project (default: all) to a directory.

    ``graphs`` is a selection like ``"1,3-4"`` (1-based positions in the live
    project) or ``""`` for every graph. The export follows the theme of the
    running window and, with ``match_screen``, keeps the on-screen proportions
    of the graph, so the file looks like the preview. With
    ``white_background`` the figure is drawn on white paper with black ink
    (print-safe) whatever the window's theme is.
    """
    names = None
    if graphs:
        names = [n.strip() for n in str(graphs).split(",") if n.strip()]
    try:
        return _gui(
            "export",
            graphs=names,
            out_dir=out_dir,
            format=format,
            dpi=dpi,
            width_mm=width_mm,
            height_mm=height_mm,
            transparent=transparent,
            match_screen=bool(match_screen),
            white_background=bool(white_background),
        )
    except UnsupportedOp:
        return _live_call(
            "export_graphs",
            graphs=names,
            out_dir=out_dir,
            format=format,
            dpi=dpi,
            width_mm=width_mm,
            height_mm=height_mm,
            transparent=transparent,
            white_background=bool(white_background),
        )


def live_run(code: str, open_graphs: bool = False) -> dict[str, Any]:
    """Execute Python against the live GUI's project (instant, undoable).

    With ``open_graphs`` true, graphs created by the executed code are opened
    as tabs in the GUI right away.
    """
    from graphmatrix.core.ipc import request

    return request("run", code=code, open_graphs=open_graphs)


def live_open(path: str, force: bool = False) -> dict[str, Any]:
    """Open a project file in the running GUI window."""
    from graphmatrix.core.ipc import request

    return request("open", path=path, force=force)


def live_screenshot(path: str) -> dict[str, Any]:
    """Capture a screenshot of the running GUI window to ``path``."""
    from graphmatrix.core.ipc import request

    return request("screenshot", path=path)


mcp = _make_mcp() if FastMCP is not None else None

if mcp is not None:
    mcp.tool(connect)
    mcp.tool(summary)
    mcp.tool(run)
    mcp.tool(export)
    mcp.tool(live_summary)
    mcp.tool(live_describe)
    mcp.tool(live_create_graph)
    mcp.tool(live_add_plot)
    mcp.tool(live_set_graph_type)
    mcp.tool(live_add_data)
    mcp.tool(live_set_property)
    mcp.tool(live_delete_graph)
    mcp.tool(live_save)
    mcp.tool(live_export)
    mcp.tool(live_run)
    mcp.tool(live_open)
    mcp.tool(live_screenshot)


def build_parser() -> argparse.ArgumentParser:
    """Command-line options for the standalone MCP server entry point."""
    parser = argparse.ArgumentParser(
        prog="graphmatrix-mcp",
        description="Expose GraphMatrix projects to AI assistants over MCP.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http", "streamable-http", "sse"),
        default="stdio",
        help="stdio for editor-launched clients (default); http/sse to listen on a port.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address for http/sse transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="TCP port for http/sse transport (default: 8765).",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the FastMCP startup banner (useful for log capture).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if mcp is None:
        print(
            "fastmcp is not installed; run `pip install graphmatrix[mcp]`",
            file=sys.stderr,
        )
        return 1
    kwargs: dict[str, Any] = {}
    if args.transport != "stdio":
        kwargs = {"host": args.host, "port": args.port}
    if args.no_banner:
        kwargs["show_banner"] = False
    mcp.run(transport=args.transport, **kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
