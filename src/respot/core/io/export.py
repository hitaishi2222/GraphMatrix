"""Publication-quality graph export (M4) via matplotlib.

The live canvas uses pyqtgraph, but export goes through matplotlib's vector
backends for font-embedded PDF/SVG/EPS and high-DPI raster output. Both render
the *same* resolved series (``core.plotting``) with the same style mapping.
"""

from __future__ import annotations

from pathlib import Path

from ..model import Graph, PlotStyle, Project
from ..plotting import auto_axis_labels, resolve_layer

_PALETTE = (
    "#1f77b4", "#d62728", "#2ca02c", "#9467bd",
    "#ff7f0e", "#17becf", "#8c564b", "#e377c2",
)

_FORMATS = {".pdf", ".svg", ".eps", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}


def export_graph(
    graph: Graph,
    project: Project,
    path: str | Path,
    *,
    width_mm: float = 100.0,
    height_mm: float = 75.0,
    dpi: int = 300,
    transparent: bool = False,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figsize = (width_mm / 25.4, height_mm / 25.4)

    fig, ax_left = plt.subplots(figsize=figsize, dpi=dpi)
    ax_right = None

    for layer in graph.layers:
        if layer.x_scale.value == "log":
            ax_left.set_xscale("log")
        if layer.y_scale.value == "log":
            ax_left.set_yscale("log")
            if ax_right is not None:
                ax_right.set_yscale("log")

        series = resolve_layer(project, layer)
        for plot_index, (spec, data) in enumerate(zip(layer.plots, series)):
            color = spec.color or _PALETTE[plot_index % len(_PALETTE)]
            if getattr(spec, "y_axis", "left") == "right":
                if ax_right is None:
                    ax_right = ax_left.twinx()
                    if layer.y_scale.value == "log":
                        ax_right.set_yscale("log")
                _draw(ax_right, spec, data, color)
            else:
                _draw(ax_left, spec, data, color)

        x_label, y_label = auto_axis_labels(project, layer)
        if x_label:
            ax_left.set_xlabel(x_label)
        if y_label and not ax_left.get_ylabel():
            ax_left.set_ylabel(y_label)
        if layer.y2_label and ax_right is not None:
            ax_right.set_ylabel(layer.y2_label)
        if layer.x_min is not None or layer.x_max is not None:
            ax_left.set_xlim(left=layer.x_min, right=layer.x_max)
        if layer.y_min is not None or layer.y_max is not None:
            ax_left.set_ylim(bottom=layer.y_min, top=layer.y_max)

    if graph.layers and graph.layers[0].show_legend:
        handles, labels = ax_left.get_legend_handles_labels()
        if ax_right is not None:
            h2, l2 = ax_right.get_legend_handles_labels()
            handles, labels = handles + h2, labels + l2
        if labels:
            ax_left.legend(handles, labels, loc="best", fontsize=8, frameon=False)

    for annotation in getattr(graph, "annotations", []):
        ax_left.text(annotation.x, annotation.y, annotation.text, transform=ax_left.transAxes,
                     color=annotation.color, fontsize=annotation.size, ha="left", va="top")

    if graph.title:
        fig.suptitle(graph.title)

    fig.tight_layout()
    fmt = path.suffix.lower().lstrip(".") if path.suffix else "pdf"
    if fmt == "tiff":
        fmt = "tif"
    fig.savefig(path, format=fmt, dpi=dpi, transparent=transparent, bbox_inches="tight")
    plt.close(fig)
    return path


def _draw(ax, spec, data, color) -> None:
    style = PlotStyle(spec.style)
    label = data.legend or None
    x, y = data.x, data.y

    if style is PlotStyle.SCATTER:
        ax.plot(x, y, linestyle="none", marker=spec.symbol, markersize=spec.symbol_size * 0.6,
                color=color, label=label)
    elif style is PlotStyle.LINE:
        ax.plot(x, y, color=color, linewidth=spec.line_width, label=label)
    elif style is PlotStyle.LINE_SYMBOL:
        ax.plot(x, y, color=color, linewidth=spec.line_width, marker=spec.symbol,
                markersize=spec.symbol_size * 0.6, label=label)
    elif style is PlotStyle.BAR:
        ax.bar(x, y, color=color, label=label)
    elif style is PlotStyle.AREA:
        ax.fill_between(x, y, alpha=0.3, color=color)
        ax.plot(x, y, color=color, linewidth=spec.line_width, label=label)
    elif style is PlotStyle.STEP:
        ax.step(x, y, where="mid", color=color, linewidth=spec.line_width, label=label)
    elif style is PlotStyle.ERRORBAR:
        ax.errorbar(x, y, yerr=data.yerr, xerr=data.xerr, color=color,
                    linewidth=spec.line_width, marker=spec.symbol,
                    markersize=spec.symbol_size * 0.6, capsize=3, label=label)


__all__ = ["export_graph", "_FORMATS"]
