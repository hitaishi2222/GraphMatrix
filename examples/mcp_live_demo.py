"""End-to-end *live* MCP demo: drive a running GraphMatrix window.

The session demo (``examples/mcp_demo.py``) works on a project inside the MCP
server process. This one drives the **window you are looking at**: it connects
to the MCP server, then uses the live tools, which talk to the running GUI over
its local IPC bridge. Every change lands in the open project, is undoable with
Ctrl+Z, and shows up immediately as a new tab.

The workflow it demonstrates:

1. ``live_describe``   — what data and figures does the window hold?
2. ``live_add_data``   — create a worksheet and fill it with columns
3. ``live_create_graph`` — make a figure of any template (simple, stack,
   double-y, x-twin, grid) and open it as a tab
4. ``live_add_plot``   — fill the remaining panels (1-based, ``replace=True``)
5. ``live_set_property`` — labels, axis scales, legend
6. ``live_export`` / ``live_save`` — write the figures out, persist the project

Prerequisite: a GraphMatrix window is running (the bridge socket lives in
``~/.local/state/graphmatrix/``). The script refuses to start without one.

Run:  python examples/mcp_live_demo.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC = REPO / "src"
OUT = HERE / "mcp_demo_out" / "live"


def parse(result):
    """Turn a CallToolResult into a Python object (dict / list / str)."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and set(structured) == {"result"}:
        structured = structured["result"]
    if structured is not None:
        return structured
    for block in result.content:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return text
    return None


def block(payload) -> str:
    text = (
        json.dumps(payload, indent=2, ensure_ascii=False)
        if isinstance(payload, (dict, list))
        else str(payload)
    )
    return "\n".join("  " + line for line in text.split("\n")).rstrip()


def running_gui() -> str | None:
    """Path of the socket of a live GraphMatrix window, if there is one."""
    sys.path.insert(0, str(SRC))
    from graphmatrix.core.ipc import running_socket_path

    return running_socket_path()


async def demo() -> list[str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "graphmatrix.mcp_server"],
        cwd=str(REPO),
        env=env,
    )

    transcript: list[str] = []

    def log(title: str, payload=None) -> None:
        head = f"\n== {title} =="
        transcript.append(head)
        print(head)
        if payload is not None:
            body = block(payload)
            transcript.append(body)
            print(body)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ---- 1. what is in the window? ----------------------------------
            description = parse(await session.call_tool("live_describe", {}))
            log(
                "live_describe — data and figures in the window",
                {
                    "project": description.get("name"),
                    "sheets": [
                        s["label"]
                        for b in description.get("workbooks", [])
                        for s in b["sheets"]
                    ],
                    "graphs": [g["name"] for g in description.get("graphs", [])],
                },
            )

            # ---- 2. data ---------------------------------------------------
            log(
                "live_add_data — a worksheet with four columns",
                parse(
                    await session.call_tool(
                        "live_add_data",
                        {
                            "book": "MCP Demo",
                            "sheet": "Physics",
                            "columns": [
                                {
                                    "name": "X",
                                    "type": "X",
                                    "generate": {
                                        "kind": "linspace",
                                        "start": 0,
                                        "stop": 10,
                                        "count": 61,
                                    },
                                },
                                {
                                    "name": "Signal",
                                    "type": "Y",
                                    "generate": {
                                        "kind": "sin",
                                        "count": 61,
                                        "amp": 1.0,
                                        "freq": 2.0,
                                    },
                                },
                                {
                                    "name": "Carrier",
                                    "type": "Y",
                                    "generate": {
                                        "kind": "sin",
                                        "count": 61,
                                        "amp": 0.35,
                                        "freq": 8.0,
                                    },
                                },
                                {
                                    "name": "Noise",
                                    "type": "Y",
                                    "generate": {
                                        "kind": "random",
                                        "count": 61,
                                        "seed": 3,
                                        "scale": 0.15,
                                    },
                                },
                            ],
                        },
                    )
                ),
            )

            source = "MCP Demo/Physics"

            # ---- 3. one figure per template --------------------------------
            log(
                "live_create_graph — simple",
                parse(
                    await session.call_tool(
                        "live_create_graph",
                        {
                            "name": "MCP Simple",
                            "graph_type": "simple",
                            "source": source,
                            "x": "X",
                            "y": "Signal",
                            "style": "line+symbol",
                            "title": "Simple — one panel, one series",
                        },
                    )
                ),
            )
            log(
                "live_create_graph — stack (3 panels, shared X)",
                parse(
                    await session.call_tool(
                        "live_create_graph",
                        {
                            "name": "MCP Stack",
                            "graph_type": "stack",
                            "panels": 3,
                            "source": source,
                            "x": "X",
                            "y": "Signal",
                            "style": "line",
                        },
                    )
                ),
            )
            log(
                "live_create_graph — grid (2x2)",
                parse(
                    await session.call_tool(
                        "live_create_graph",
                        {
                            "name": "MCP Grid",
                            "graph_type": "grid",
                            "rows": 2,
                            "cols": 2,
                            "source": source,
                            "x": "X",
                            "y": "Signal",
                            "style": "line",
                        },
                    )
                ),
            )
            log(
                "live_create_graph — double-y",
                parse(
                    await session.call_tool(
                        "live_create_graph",
                        {
                            "name": "MCP Double Y",
                            "graph_type": "double-y",
                            "source": source,
                            "x": "X",
                            "y": "Signal",
                            "style": "line+symbol",
                        },
                    )
                ),
            )
            log(
                "live_create_graph — x-twin",
                parse(
                    await session.call_tool(
                        "live_create_graph",
                        {
                            "name": "MCP X-Twin",
                            "graph_type": "x-twin",
                            "panels": 2,
                            "source": source,
                            "x": "X",
                            "y": "Signal",
                            "style": "line",
                        },
                    )
                ),
            )

            # ---- 4. fill the panels ----------------------------------------
            for graph, panel, column, style in (
                ("MCP Stack", 2, "Carrier", "line"),
                ("MCP Stack", 3, "Noise", "scatter"),
                ("MCP Grid", 2, "Carrier", "area"),
                ("MCP Grid", 3, "Noise", "scatter"),
                ("MCP Grid", 4, "Signal", "step"),
                ("MCP X-Twin", 2, "Carrier", "line"),
            ):
                log(
                    f"live_add_plot — {graph}, panel {panel}: {column}",
                    parse(
                        await session.call_tool(
                            "live_add_plot",
                            {
                                "graph": graph,
                                "source": source,
                                "x": "X",
                                "y": column,
                                "style": style,
                                "panel": panel,
                                "replace": True,
                            },
                        )
                    ),
                )

            # a series on the secondary axis of the double-Y figure
            log(
                "live_add_plot — MCP Double Y, secondary (right) axis",
                parse(
                    await session.call_tool(
                        "live_add_plot",
                        {
                            "graph": "MCP Double Y",
                            "source": source,
                            "x": "X",
                            "y": "Noise",
                            "style": "line",
                            "y_axis": "right",
                        },
                    )
                ),
            )

            # ---- 5. labels -------------------------------------------------
            for graph, key, value, panel in (
                ("MCP Simple", "x_label", "time (s)", 1),
                ("MCP Simple", "y_label", "amplitude (a.u.)", 1),
                ("MCP Stack", "x_label", "time (s)", 1),
                ("MCP Stack", "show_y_axis", "false", 2),
                ("MCP Stack", "show_y_axis", "false", 3),
                ("MCP Grid", "x_label", "time (s)", 1),
                ("MCP Double Y", "x_label", "time (s)", 1),
                ("MCP Double Y", "y_label", "signal (a.u.)", 1),
                ("MCP Double Y", "y2_label", "noise (a.u.)", 1),
                ("MCP X-Twin", "x_label", "time (s)", 1),
            ):
                await session.call_tool(
                    "live_set_property",
                    {"graph": graph, "key": key, "value": value, "panel": panel},
                )
            log("live_set_property — axis labels and hidden Y axes", "ok")

            # ---- 6. write the results out -----------------------------------
            log(
                "live_export — PNG for every figure",
                parse(
                    await session.call_tool(
                        "live_export",
                        {
                            "out_dir": str(OUT),
                            "format": "png",
                            "dpi": 120,
                        },
                    )
                ),
            )
            log(
                "live_save — persist the project",
                parse(
                    await session.call_tool(
                        "live_save",
                        {"path": str(REPO / "agent_live.gm")},
                    )
                ),
            )

    return transcript


def main() -> int:
    socket = running_gui()
    if not socket:
        print(
            "No GraphMatrix window is running.\n"
            "Start the app first (graphmatrix) — the live tools drive that window.",
            file=sys.stderr,
        )
        return 1
    print(f"Driving the running GraphMatrix window via {socket}")
    OUT.mkdir(parents=True, exist_ok=True)
    transcript = asyncio.run(demo())
    (OUT / "live_transcript.txt").write_text(
        "MCP live-session transcript (GraphMatrix)\n" + "=" * 60 + "\n"
        + "\n".join(transcript)
        + "\n",
        encoding="utf-8",
    )
    print(f"\nDone. Figures in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
