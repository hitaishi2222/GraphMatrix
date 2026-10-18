"""End-to-end MCP demo: drive GraphMatrix's MCP server like an AI assistant.

Spawns the GraphMatrix MCP server (stdio transport) as a subprocess, connects
with the official MCP client SDK, and exercises the features added to
GraphMatrix after the MCP server first shipped:

- colour-mapped scatter plots (M10: PlotSpec.z + PlotStyle.cmap)
- numeric fit regions         (M10: x_min / x_max)
- peak integration            (M10: find_peaks(integrate=True))
- batch statistics            (M10: api.batch_stats)
- project versions + restore  (46f4c27: Project.create_version / restore_version)
- enriched ``summary``        (MCP update: versions field in the payload)
- live data tailing           (M11: LiveFileSource polled through ``run``,
  rows appended with the same undoable commands the GUI board uses)

Outputs land in ``examples/mcp_demo_out/``: a saved project, exported PDFs and
a transcript log.

Run:  python examples/mcp_demo.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import numpy as np
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC = REPO / "src"
OUT = HERE / "mcp_demo_out"
DATA = OUT / "data"


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------
def make_spectra_csv(path: Path, seed: int = 7) -> None:
    """Two-peak spectrum plus a colour column (signal-to-baseline ratio)."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 100, 400)
    y = (
        0.3
        + 1.8 * np.exp(-0.5 * ((x - 30) / 3.5) ** 2)  # peak 1
        + 1.2 * np.exp(-0.5 * ((x - 62) / 5.0) ** 2)  # peak 2
        + rng.normal(0, 0.02, x.size)
    )
    z = y * (1.0 + x / 200.0)  # colour-mapping demo column
    lines = ["X,Y,Z", *(f"{a:.6g},{b:.6g},{c:.6g}" for a, b, c in zip(x, y, z))]
    path.write_text("\n".join(lines) + "\n")


def make_calibration_csv(path: Path, seed: int = 3) -> None:
    """Linear calibration that is only linear above x = 40 (bent baseline below)."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 100, 50)
    y = np.where(x >= 40, 2.0 * x + 1.0, 0.5 * x + 10.0) + rng.normal(0, 0.4, x.size)
    lines = ["X,Y", *(f"{a:.6g},{b:.6g}" for a, b in zip(x, y))]
    path.write_text("\n".join(lines) + "\n")


def make_live_log(path: Path, t0: float, n: int, seed: int = 11) -> None:
    """First batch of a sensor log: drifting sinusoid sampled every 0.25 s."""
    rng = np.random.default_rng(seed)
    t = t0 + np.arange(n) * 0.25
    signal = 20.0 + 0.05 * t + 2.0 * np.sin(t / 3.0) + rng.normal(0, 0.2, t.size)
    lines = ["t,signal", *(f"{a:.6g},{b:.6g}" for a, b in zip(t, signal))]
    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# MCP plumbing
# ---------------------------------------------------------------------------
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


SRC_HELPER = """
def _src(prefix):
    for b in project.workbooks:
        if b.name.lower().startswith(prefix):
            return f"{b.name}/{b.sheets[0].name}"
    raise KeyError(prefix)
"""


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

            tools = await session.list_tools()
            log("server tools", sorted(t.name for t in tools.tools))

            # ---- connect: fresh in-memory project ---------------------------
            conn = parse(await session.call_tool("connect", {"path": None}))
            log("connect", {k: v for k, v in conn.items() if k == "summary"})
            pid = conn["project_id"]

            # ---- run 1: import data, colour-mapped scatter (M10), save ------
            code_import = f"""
api.import_data(r"{DATA / "spectra.csv"}")
api.import_data(r"{DATA / "calibration.csv"}")

api.add_graph("Spectrum Colour")
api.add_plot("Spectrum Colour", _src("spectra"), "X", "Y",
             style="color-mapped scatter", z="Z", cmap="viridis")
for g in project.graphs:
    g.first_layer.z_label = "Signal ratio"

api.save(r"{OUT / "spectra.gm"}")
"books: " + ", ".join(b.name for b in project.workbooks)
"""
            run1 = parse(
                await session.call_tool(
                    "run", {"project_id": pid, "code": SRC_HELPER + code_import}
                )
            )
            log("run: import + colour-mapped scatter (M10 z/cmap)", run1)
            if not run1["ok"]:
                raise SystemExit(run1["stderr"])

            # ---- run 2: snapshot the raw import (versioning, 46f4c27) -------
            run2 = parse(
                await session.call_tool(
                    "run",
                    {
                        "project_id": pid,
                        "code": "project.create_version('v1-import', "
                        "note='raw spectra + calibration imported')\n'ok'",
                    },
                )
            )
            log("run: create_version('v1-import')", run2)

            # ---- run 3: peak integration (M10) ------------------------------
            code_peaks = """
peaks = api.find_peaks(_src("spectra"), "X", "Y", prominence=0.4, integrate=True)
print(peaks.to_text())
"""
            run3 = parse(
                await session.call_tool(
                    "run", {"project_id": pid, "code": SRC_HELPER + code_peaks}
                )
            )
            log("run: find_peaks(integrate=True) — peak integration", run3)
            if run3.get("stdout"):
                text = block(run3["stdout"])
                transcript.append(text)
                print(text)
            if not run3["ok"]:
                raise SystemExit(run3["stderr"])

            # ---- run 4: numeric fit region (M10) ----------------------------
            code_fit = f"""
bad = api.linear_fit(_src("calibration"), "X", "Y")          # whole range bent
good = api.linear_fit(_src("calibration"), "X", "Y", x_min=40.0)  # numeric region
print('all-range slope ', repr(bad.parameters[0].display()), ' R2', round(bad.summary['R²'], 4))
print('fit-region slope', repr(good.parameters[0].display()), ' R2', round(good.summary['R²'], 4))
print('region:', good.summary.get('Fit region'))
"""
            run4 = parse(
                await session.call_tool(
                    "run", {"project_id": pid, "code": SRC_HELPER + code_fit}
                )
            )
            log("run: linear_fit(x_min=40) — numeric fit region", run4)
            if run4.get("stdout"):
                text = block(run4["stdout"])
                transcript.append(text)
                print(text)
            if not run4["ok"]:
                raise SystemExit(run4["stderr"])

            # ---- run 5: batch stats + heatmap + two versions + restore ------
            code_final = f"""
import graphmatrix.core.analysis.descriptive as descriptive
print(api.batch_stats().to_text())

api.add_graph("Spectrum Heatmap")
api.add_plot("Spectrum Heatmap", _src("spectra"), "X", "Y",
             style="heatmap", z="Z", cmap="inferno")

project.create_version('v2-analysis', note='fit region, integrated peaks, heatmap')

# prove version restore works end to end
project.restore_version('v1-import')
print('graphs after restore to v1:', [g.name for g in project.graphs])
project.restore_version('v2-analysis')
print('graphs after restore to v2:', [g.name for g in project.graphs])
api.save(r"{OUT / "spectra.gm"}")
"done"
"""
            run5 = parse(
                await session.call_tool(
                    "run", {"project_id": pid, "code": SRC_HELPER + code_final}
                )
            )
            log("run: batch_stats + heatmap + versions + restore", run5)
            if run5.get("stdout"):
                text = block(run5["stdout"])
                transcript.append(text)
                print(text)
            if not run5["ok"]:
                raise SystemExit(run5["stderr"])

            # ---- run 6: live tailing (M11) — LiveFileSource over MCP -----------
            code_live = f"""
from pathlib import Path

from graphmatrix.core.commands import (
    AddColumnCommand,
    AddWorksheetCommand,
    SetCellsCommand,
)
from graphmatrix.core.live import LiveFileSource
from graphmatrix.core.model import Column, ColumnType, Worksheet

# Headless twin of Tools → Live Data…: tail one file, append via commands.
book = api.add_workbook("Live")
sheet = Worksheet("Live sensor")
api.commands.push(AddWorksheetCommand(book, sheet))
src = LiveFileSource(Path(r"{DATA / "live_sensor.csv"}"))
for i, name in enumerate(src.columns()):
    col_type = ColumnType.X if i == 0 else ColumnType.Y
    api.commands.push(AddColumnCommand(sheet, Column(name, col_type)))


def tick():
    rows = src.poll()
    if rows:
        api.commands.push(SetCellsCommand(sheet, sheet.num_rows, 0, rows))
    return len(rows)


n1 = tick()  # batch 1 is already on disk

# The writer appends batch 2 between polls — a second live tick.
t2 = 3.0 + np.arange(10) * 0.25
sig2 = 20.0 + 0.05 * t2 + 2.0 * np.sin(t2 / 3.0) + np.random.default_rng(23).normal(0, 0.2, t2.size)
with open(r"{DATA / "live_sensor.csv"}", "a", encoding="utf-8") as fh:
    fh.writelines(f"{{a:.6g}},{{b:.6g}}\\n" for a, b in zip(t2, sig2))
n2 = tick()

api.add_graph("Live Sensor")
api.add_plot("Live Sensor", "Live/Live sensor", "t", "signal", style="line+symbol")
fit = api.polynomial_fit("Live/Live sensor", "t", "signal", degree=2, x_min=1.0)
print(f"ticks appended {{n1}} + {{n2}} rows; sheet rows now {{sheet.num_rows}}")
print("poly fit N:", fit.summary["N"], "R2:", round(fit.summary["R²"], 4))
"done"
"""
            run6 = parse(
                await session.call_tool(
                    "run", {"project_id": pid, "code": SRC_HELPER + code_live}
                )
            )
            log("run: live tailing (M11 LiveFileSource + command appends)", run6)
            if run6.get("stdout"):
                text = block(run6["stdout"])
                transcript.append(text)
                print(text)
            if not run6["ok"]:
                raise SystemExit(run6["stderr"])

            # ---- run 7: live rows persist across MCP calls + save -------------
            code_persist = f"""
sheet = project.sheet("Live/Live sensor")
assert sheet.num_rows == 22, sheet.num_rows
project.create_version("v3-live", note="live sensor tail (2 ticks) + polynomial fit")
api.save(r"{OUT / "spectra.gm"}")
print("live sheet rows:", sheet.num_rows, "| versions:", [v["name"] for v in project.versions])
"""
            run7 = parse(
                await session.call_tool(
                    "run", {"project_id": pid, "code": code_persist}
                )
            )
            log("run: live rows persist across MCP calls + save", run7)
            if run7.get("stdout"):
                text = block(run7["stdout"])
                transcript.append(text)
                print(text)
            if not run7["ok"]:
                raise SystemExit(run7["stderr"])

            # ---- summary now reports versions --------------------------------
            summary = parse(await session.call_tool("summary", {"project_id": pid}))
            log("summary (now includes versions)", summary)

            # ---- export all graphs to PDF --------------------------------------
            export = parse(
                await session.call_tool(
                    "export",
                    {
                        "project_id": pid,
                        "graphs": "1-3",
                        "out_dir": str(OUT),
                        "format": "pdf",
                        "dpi": 150,
                    },
                )
            )
            log("export graphs 1-3 -> PDF", export)
            if isinstance(export, dict) and not export.get("files"):
                raise SystemExit(f"export failed: {export}")

    return transcript


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    make_spectra_csv(DATA / "spectra.csv")
    make_calibration_csv(DATA / "calibration.csv")
    make_live_log(DATA / "live_sensor.csv", t0=0.0, n=12, seed=11)

    transcript = asyncio.run(demo())

    (OUT / "mcp_transcript.txt").write_text(
        "MCP session transcript (GraphMatrix)\n"
        + "=" * 60
        + "\n"
        + "\n".join(transcript)
        + "\n",
        encoding="utf-8",
    )
    print(f"\nDone. Outputs in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
