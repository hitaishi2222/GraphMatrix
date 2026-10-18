"""Publication-quality graph export (M4) via matplotlib.

The live canvas uses pyqtgraph, but export goes through matplotlib's vector
backends for font-embedded PDF/SVG/EPS and high-DPI raster output. Both render
the *same* resolved series (``core.plotting``) with the same style mapping.
"""

from __future__ import annotations

from pathlib import Path

from ..journals import export_rcparams, figure_size
from ..model import Graph, PlotStyle, Project
from ..plotting import auto_axis_labels, resolve_layer

_PALETTE = (
    "#1f77b4", "#d62728", "#2ca02c", "#9467bd",
    "#ff7f0e", "#17becf", "#8c564b", "#e377c2",
)

#: Plot-theme (canvas) colours mirrored from ``ui.theme`` so export stays
#: WYSIWYG without core importing the UI layer.
_PLOT_THEME_COLORS = {
    "classic-dark": ("#191a1d", "#d7dae0"),
    "classic-light": ("#ffffff", "#202124"),
    "modern-dark": ("#0e1015", "#dde1ea"),
    "modern-light": ("#ffffff", "#1b1e2b"),
    "plot-classic-light": ("#ffffff", "#202124"),
    "plot-classic-dark": ("#191a1d", "#d7dae0"),
    "plot-seaborn": ("#f0f0f0", "#262626"),
    "plot-earth": ("#f6f1e7", "#3b2f2f"),
    "plot-monochrome": ("#ffffff", "#000000"),
    "plot-publication": ("#ffffff", "#000000"),
}

_FORMATS = {".pdf", ".svg", ".eps", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}

#: Human-readable list of the formats users may export to.
SUPPORTED_FORMATS = ("pdf", "svg", "eps", "png", "tif", "jpg")

#: Respot line-style token -> matplotlib linestyle.
_LINESTYLES = {
    "solid": "-",
    "dash": "--",
    "dot": ":",
    "dashdot": "-.",
    "longdash": (0, (8, 3)),
}


def _linestyle(name: str) -> object:
    return _LINESTYLES.get((name or "solid").lower(), "-")


def export_graph(
    graph: Graph,
    project: Project,
    path: str | Path,
    *,
    width_mm: float | None = None,
    height_mm: float | None = None,
    dpi: int = 300,
    transparent: bool = False,
    preset: str | None = None,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    preset_name = preset if preset is not None else getattr(graph, "journal_preset", "")
    if preset_name:
        p_width, p_height = figure_size(preset_name)
        if width_mm is None:
            width_mm = p_width
        if height_mm is None:
            height_mm = p_height
    width_mm = 100.0 if width_mm is None else width_mm
    height_mm = 75.0 if height_mm is None else height_mm
    figsize = (width_mm / 25.4, height_mm / 25.4)

    rc = export_rcparams(preset_name) if preset_name else {}
    with mpl.rc_context(rc):
        fig, ax_left = plt.subplots(figsize=figsize, dpi=dpi)
        plot_theme = getattr(graph, "plot_theme", "")
        _colors = _PLOT_THEME_COLORS.get(plot_theme)
        if _colors is not None:
            bg, fg = _colors
            fig.patch.set_facecolor(bg)
            ax_left.set_facecolor(bg)
            ax_left.tick_params(colors=fg)
            ax_left.xaxis.label.set_color(fg)
            ax_left.yaxis.label.set_color(fg)
            for spine in ax_left.spines.values():
                spine.set_color(fg)
        _render_figure(fig, ax_left, graph, project)
        fmt = path.suffix.lower().lstrip(".") if path.suffix else "pdf"
        if fmt == "tiff":
            fmt = "tif"
        elif fmt == "jpeg":
            fmt = "jpg"
        if fmt not in SUPPORTED_FORMATS:
            plt.close(fig)
            supported = ", ".join(f".{f}" for f in SUPPORTED_FORMATS)
            raise ValueError(
                f"Unsupported export format '.{fmt}'. Choose one of: {supported}."
            )
        fig.savefig(path, format=fmt, dpi=dpi, transparent=transparent, bbox_inches="tight")
        plt.close(fig)
    return path


def _render_figure(fig, ax_left, graph: Graph, project: Project) -> None:
    """Draw every layer, plot, reference line, and annotation onto ``ax_left``."""
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

        # Minor ticks + tick direction (publication polish).
        direction = getattr(layer, "tick_direction", "out") or "out"
        if getattr(layer, "minor_ticks", True):
            ax_left.minorticks_on()
            if ax_right is not None:
                ax_right.minorticks_on()
        for _ax in (ax_left, ax_right):
            if _ax is None:
                continue
            _ax.tick_params(which="both", direction=direction)

        for ref in getattr(layer, "ref_lines", []):
            style = _linestyle(ref.line_style)
            if ref.orientation == "v":
                line = ax_left.axvline(ref.position, color=ref.color, linewidth=ref.width,
                                       linestyle=style)
            else:
                line = ax_left.axhline(ref.position, color=ref.color, linewidth=ref.width,
                                       linestyle=style)
            if ref.label:
                _label_reference_line(ax_left, ref, line)

    if graph.layers and graph.layers[0].show_legend:
        handles, labels = ax_left.get_legend_handles_labels()
        if ax_right is not None:
            h2, l2 = ax_right.get_legend_handles_labels()
            handles, labels = handles + h2, labels + l2
        if labels:
            ax_left.legend(handles, labels, loc="best", frameon=False)

    for annotation in getattr(graph, "annotations", []):
        ax_left.text(annotation.x, annotation.y, annotation.text, transform=ax_left.transAxes,
                     color=annotation.color, fontsize=annotation.size, ha="left", va="top")

    if graph.title:
        fig.suptitle(graph.title)

    fig.tight_layout()


def _draw(ax, spec, data, color) -> None:
    style = PlotStyle(spec.style)
    label = data.legend or None
    x, y = data.x, data.y
    ls = _linestyle(getattr(spec, "line_style", "solid"))

    if style is PlotStyle.SCATTER:
        ax.plot(x, y, linestyle="none", marker=spec.symbol, markersize=spec.symbol_size * 0.6,
                color=color, label=label)
    elif style is PlotStyle.LINE:
        ax.plot(x, y, color=color, linewidth=spec.line_width, linestyle=ls, label=label)
    elif style is PlotStyle.LINE_SYMBOL:
        ax.plot(x, y, color=color, linewidth=spec.line_width, marker=spec.symbol,
                markersize=spec.symbol_size * 0.6, linestyle=ls, label=label)
    elif style is PlotStyle.BAR:
        ax.bar(x, y, color=color, label=label)
    elif style is PlotStyle.AREA:
        ax.fill_between(x, y, alpha=0.3, color=color)
        ax.plot(x, y, color=color, linewidth=spec.line_width, linestyle=ls, label=label)
    elif style is PlotStyle.STEP:
        ax.step(x, y, where="mid", color=color, linewidth=spec.line_width, linestyle=ls, label=label)
    elif style is PlotStyle.ERRORBAR:
        ax.errorbar(x, y, yerr=data.yerr, xerr=data.xerr, color=color,
                    linewidth=spec.line_width, linestyle=ls, marker=spec.symbol,
                    markersize=spec.symbol_size * 0.6, capsize=3, label=label)


def _label_reference_line(ax, ref, line) -> None:
    """Attach a small text label to a reference line at the top edge of the axes."""
    try:
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
    except Exception:  # noqa: BLE001 - axes may be pre-autoscale
        return
    pad = 0.01 * (ymax - ymin if ymax != ymin else 1.0)
    if ref.orientation == "v":
        ax.text(ref.position, ymax - pad, ref.label, color=ref.color, fontsize=8,
                ha="left", va="top", rotation=90)
    else:
        ax.text(xmax, ref.position, ref.label, color=ref.color, fontsize=8,
                ha="right", va="bottom")


__all__ = ["export_graph", "_FORMATS", "SUPPORTED_FORMATS"]
