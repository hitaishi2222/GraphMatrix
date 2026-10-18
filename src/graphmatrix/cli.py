"""Command-line interface for GraphMatrix.

The GUI remains the primary frontend; this CLI exposes a small, scriptable
surface for opening projects, exporting graphs, inspecting them, and checking
the local environment.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import click

from graphmatrix import __version__

_REQUIRED_MODULES = [
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("matplotlib", "matplotlib"),
    ("PySide6", "PySide6"),
    ("pyqtgraph", "pyqtgraph"),
    ("lmfit", "lmfit"),
    ("openpyxl", "openpyxl"),
    ("pyarrow", "pyarrow"),
]

_OPTIONAL_MODULES = [
    ("h5py", "h5py (HDF5)"),
    ("fastmcp", "fastmcp (MCP server)"),
    ("mcp", "mcp (MCP SDK)"),
]


def _parse_graph_selection(spec: str | None, total: int) -> list[int]:
    """Parse ``"1,3-5"`` (1-based) into sorted unique 0-based indices."""
    if not spec:
        return list(range(total))
    result: list[int] = []
    cleaned = spec.strip().strip("()").strip("[]")
    for chunk in cleaned.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            left, right = chunk.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            if start > end:
                start, end = end, start
            for n in range(start, end + 1):
                result.append(n - 1)
        else:
            result.append(int(chunk) - 1)
    # validate + dedupe, preserving order
    seen: set[int] = set()
    out: list[int] = []
    for idx in result:
        if idx < 0 or idx >= total:
            raise click.ClickException(f"graph index {idx + 1} out of range (1..{total})")
        if idx not in seen:
            seen.add(idx)
            out.append(idx)
    return out


def _sanitize(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name).strip("_") or "graph"


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """GraphMatrix — scientific data analysis and graphing."""
    if ctx.invoked_subcommand is None:
        # Backward-compatible: bare `graphmatrix` opens the GUI.
        from graphmatrix.app import run

        raise SystemExit(run([]))


@cli.command("run")
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
def run_cmd(paths: tuple[str, ...]) -> None:
    """Open project file(s) in the GUI, or run a YAML pipeline headlessly."""
    pipelines = [p for p in paths if str(p).lower().endswith((".yaml", ".yml"))]
    others = [p for p in paths if not str(p).lower().endswith((".yaml", ".yml"))]
    if pipelines:
        from graphmatrix.core.pipelines import run_pipeline

        for p in pipelines:
            run_pipeline(p)
        if others:
            from graphmatrix.app import run

            raise SystemExit(run(others))
        return
    from graphmatrix.app import run

    raise SystemExit(run(list(paths)))


@cli.command("export")
@click.argument("project", type=click.Path(exists=True, dir_okay=False))
@click.option("-g", "--graphs", default=None, help="Graph selection, e.g. 1,3-5 or (1,3).")
@click.option("--format", "fmt", default="pdf",
              type=click.Choice(["pdf", "svg", "eps", "png", "tif", "tiff", "jpg", "jpeg"], case_sensitive=False))
@click.option("--out", "out_dir", default=None, help="Output directory (default: <project>_export).")
@click.option("--dpi", default=300, type=int)
@click.option("--width", default=100.0, type=float, help="Figure width in mm.")
@click.option("--height", default=75.0, type=float, help="Figure height in mm.")
@click.option("--transparent", is_flag=True, help="Transparent background.")
def export_cmd(project, graphs, fmt, out_dir, dpi, width, height, transparent) -> None:
    """Export graphs from a project file."""
    from graphmatrix.core.io.export import export_graph
    from graphmatrix.core.model import Project

    proj = Project.open(project)
    if not proj.graphs:
        raise click.ClickException("project has no graphs")

    indices = _parse_graph_selection(graphs, len(proj.graphs))
    if out_dir is None:
        out_dir = Path(project).with_suffix("").name + "_export"
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for idx in indices:
        graph = proj.graphs[idx]
        target = out_path / f"{_sanitize(graph.name)}.{fmt.lower()}"
        export_graph(graph, proj, target, width_mm=width, height_mm=height,
                     dpi=dpi, transparent=transparent)
        click.echo(f"exported: {target}")

    click.echo(f"done: {len(indices)} graph(s) -> {out_path}")


@cli.command("list")
@click.argument("project", type=click.Path(exists=True, dir_okay=False))
def list_cmd(project: str) -> None:
    """List graphs available in a project file."""
    from graphmatrix.core.model import Project

    proj = Project.open(project)
    if not proj.graphs:
        click.echo("No graphs in project.")
        return
    click.echo(f"{proj.name}: {len(proj.graphs)} graph(s)")
    for i, graph in enumerate(proj.graphs, 1):
        nplots = sum(len(layer.plots) for layer in graph.layers)
        click.echo(f"  {i}. {graph.name}  ({len(graph.layers)} layer(s), {nplots} plot(s))")


@cli.command("doctor")
def doctor_cmd() -> None:
    """Check the environment and report missing pieces."""
    ok = True
    click.echo(f"GraphMatrix {__version__}")
    click.echo(f"Python: {sys.version.split()[0]}")
    click.echo("")

    click.echo("Required modules:")
    for mod, label in _REQUIRED_MODULES:
        spec = importlib.util.find_spec(mod)
        if spec is None:
            ok = False
            click.echo(f"  [MISSING] {label}")
        else:
            try:
                m = importlib.import_module(mod)
                ver = getattr(m, "__version__", "")
            except Exception as exc:  # noqa: BLE001
                ok = False
                ver = f"ERROR: {exc}"
            click.echo(f"  [ok]      {label} {ver}".rstrip())

    click.echo("")
    click.echo("Optional modules:")
    for mod, label in _OPTIONAL_MODULES:
        spec = importlib.util.find_spec(mod)
        if spec is None:
            click.echo(f"  [missing] {label} (optional)")
        else:
            try:
                m = importlib.import_module(mod)
                ver = getattr(m, "__version__", "")
            except Exception as exc:  # noqa: BLE001
                ver = f"ERROR: {exc}"
            click.echo(f"  [ok]      {label} {ver}".rstrip())

    click.echo("")
    click.echo("Environment:")
    import os

    for key in ("XDG_SESSION_TYPE", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM", "HYPRLAND_INSTANCE_SIGNATURE"):
        click.echo(f"  {key}={os.environ.get(key, '')}")

    # matplotlib backend sanity
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig = plt.figure()
        plt.close(fig)
        click.echo("  matplotlib backend: ok (Agg)")
    except Exception as exc:  # noqa: BLE001
        ok = False
        click.echo(f"  matplotlib backend: ERROR {exc}")

    click.echo("")
    if ok:
        click.echo("All required components are available.")
    else:
        click.echo("Some required components are missing; install the project dependencies.")
        raise SystemExit(1)


def main() -> int:
    try:
        cli()
    except SystemExit as exc:  # click raises SystemExit
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
