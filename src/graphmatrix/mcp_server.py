"""MCP server exposing GraphMatrix projects to AI assistants.

Run with: ``graphmatrix-mcp`` (stdio transport) or ``python -m graphmatrix.mcp_server``.
Install the optional dependency first: ``pip install graphmatrix[mcp]``.
"""

from __future__ import annotations

import contextlib
import io
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
        raise RuntimeError("fastmcp is not installed; run `pip install graphmatrix[mcp]`")
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
                    {"name": sheet.name, "columns": sheet.column_names, "rows": sheet.num_rows}
                    for sheet in book.sheets
                ],
            }
            for book in project.workbooks
        ],
        "graphs": [
            {
                "index": i + 1,
                "name": graph.name,
                "layers": len(graph.layers),
                "plots": sum(len(layer.plots) for layer in graph.layers),
            }
            for i, graph in enumerate(project.graphs)
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
    elif path is None and running and running.get("project") and Path(running["project"]).exists():
        project = Project.open(running["project"])
    else:
        project = Project(Path(path).stem if path else "Untitled")
    pid = str(uuid.uuid4())
    _SESSIONS[pid] = (project, CommandStack())
    return {"project_id": pid, "summary": _summary(project),
            "running_instance": running}


def summary(project_id: str) -> dict[str, Any]:
    """Return workbooks, sheets, columns, and graphs for a project."""
    if project_id not in _SESSIONS:
        raise ValueError("unknown project_id")
    project, _ = _SESSIONS[project_id]
    return _summary(project)


def run(project_id: str, code: str) -> dict[str, Any]:
    """Execute Python against the project using the GraphMatrix API."""
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
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in graph.name).strip("_") or "graph"
        target = out_path / f"{safe}.{format.lower()}"
        export_graph(graph, project, target, width_mm=width_mm, height_mm=height_mm,
                     dpi=dpi, transparent=transparent)
        files.append(str(target))
    return {"files": files}


mcp = _make_mcp() if FastMCP is not None else None

if mcp is not None:
    mcp.tool(connect)
    mcp.tool(summary)
    mcp.tool(run)
    mcp.tool(export)


def main() -> int:
    if mcp is None:
        print("fastmcp is not installed; run `pip install graphmatrix[mcp]`", file=sys.stderr)
        return 1
    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
