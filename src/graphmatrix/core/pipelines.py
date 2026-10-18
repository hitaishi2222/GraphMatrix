"""Headless pipeline runner for GraphMatrix projects.

A pipeline is a small YAML document describing a sequence of operations on a
project (import data, build graphs, run analyses, export figures, save). It lets
the same workflow run unattended from the CLI or in CI without opening the GUI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .commands import CommandStack
from .model import Project
from .scripting.api import GraphMatrixAPI


def _as_dict(step: Any) -> dict[str, Any]:
    if isinstance(step, dict):
        return step
    raise ValueError(f"pipeline step must be a mapping, got {type(step).__name__}")


def run_pipeline(path: str | Path) -> Project:
    """Execute a YAML pipeline file and return the resulting project."""
    path = Path(path)
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(spec, dict):
        raise ValueError("pipeline root must be a mapping")

    project_path = spec.get("project")
    if project_path:
        project = Project.open(project_path)
    else:
        project = Project(spec.get("name", "Pipeline"))
    api = GraphMatrixAPI(project, CommandStack())
    out_project_path = spec.get("output") or spec.get("save")

    for raw in spec.get("steps", []):
        step = _as_dict(raw)
        if "import" in step:
            info = step["import"]
            if isinstance(info, str):
                info = {"path": info}
            api.import_data(info["path"], book_name=info.get("book"))
        elif "column" in step:
            info = step["column"]
            api.add_column(
                info["source"],
                info["name"],
                info.get("type", "Y"),
                data=info.get("data"),
                units=info.get("units", ""),
                comment=info.get("comment", ""),
            )
        elif "graph" in step:
            info = step["graph"]
            api.add_graph(
                info.get("name", "Graph"),
                source=info.get("source"),
                x=info.get("x"),
                y=info.get("y"),
                style=info.get("style", "line+symbol"),
                legend=info.get("legend", ""),
            )
        elif "plot" in step:
            info = step["plot"]
            api.add_plot(
                info["graph"],
                info["source"],
                info["x"],
                info["y"],
                style=info.get("style", "line+symbol"),
                legend=info.get("legend", ""),
            )
        elif "fit" in step:
            info = step["fit"]
            result = api.fit(
                info["model"],
                info["source"],
                info["x"],
                info["y"],
                yerr=info.get("yerr"),
            )
            print(result.to_text())
        elif "analyze" in step:
            info = step["analyze"]
            kind = info.pop("kind", None)
            if kind == "peaks":
                r = api.find_peaks(
                    info["source"],
                    info["x"],
                    info["y"],
                    **{k: v for k, v in info.items() if k not in ("source", "x", "y")},
                )
            elif kind == "describe":
                r = api.describe(info["source"], info["name"])
            else:
                raise ValueError(f"unknown analyze kind: {kind!r}")
            print(getattr(r, "to_text", lambda: r)())
        elif "export" in step:
            info = step["export"]
            from .io.export import export_graph

            graphs_spec = info.get("graphs", "all")
            if graphs_spec == "all":
                indices = list(range(len(project.graphs)))
            else:
                indices = [int(i) - 1 for i in graphs_spec]
            out_dir = Path(info.get("out", "."))
            out_dir.mkdir(parents=True, exist_ok=True)
            fmt = info.get("format", "pdf")
            for idx in indices:
                graph = project.graphs[idx]
                safe = (
                    "".join(
                        c if c.isalnum() or c in "-_." else "_" for c in graph.name
                    ).strip("_")
                    or "graph"
                )
                target = out_dir / f"{safe}.{fmt.lower()}"
                export_graph(
                    graph,
                    project,
                    target,
                    width_mm=info.get("width", 100.0),
                    height_mm=info.get("height", 75.0),
                    dpi=info.get("dpi", 300),
                    transparent=info.get("transparent", False),
                )
                print(f"exported: {target}")
        elif "save" in step:
            info = step["save"]
            target = info if isinstance(info, str) else info.get("path")
            api.save(target)
            print(f"saved: {target}")
        elif "code" in step:
            ns = {"api": api, "project": api.project}
            exec(compile(step["code"], "<pipeline>", "exec"), ns)  # noqa: S102
        else:
            raise ValueError(f"unknown pipeline step: {list(step)}")

    if out_project_path and not any(
        isinstance(s, dict) and "save" in s for s in spec.get("steps", [])
    ):
        api.save(out_project_path)
        print(f"saved: {out_project_path}")

    return api.project


__all__ = ["run_pipeline"]
