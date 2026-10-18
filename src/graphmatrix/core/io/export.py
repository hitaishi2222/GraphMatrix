"""Publication-quality graph export (M4) via matplotlib.

The live canvas uses pyqtgraph, but export goes through matplotlib's vector
backends for font-embedded PDF/SVG/EPS and high-DPI raster output. Both render
the *same* resolved series (``core.plotting``) with the same style mapping.
"""

from __future__ import annotations

from pathlib import Path

from ..journals import export_rcparams, figure_size
from ..model import Graph, PlotStyle, Project, Z_STYLES, is_3d_style
from ..plotting import auto_axis_labels, grid_xyz, resolve_layer

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

#: GraphMatrix line-style token -> matplotlib linestyle.
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
    use_3d = any(
        is_3d_style(spec.style)
        for graph_layer in graph.layers
        for spec in graph_layer.plots
    )
    with mpl.rc_context(rc):
        fig = plt.figure(figsize=figsize, dpi=dpi)
        ax_left = fig.add_subplot(111, projection="3d") if use_3d else fig.add_subplot(111)
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
            _z_label = getattr(layer, "z_label", "") or getattr(data, "z_label", "") or "Value"
            if getattr(spec, "y_axis", "left") == "right":
                if ax_right is None:
                    ax_right = ax_left.twinx()
                    if layer.y_scale.value == "log":
                        ax_right.set_yscale("log")
                _draw(ax_right, spec, data, color, fig=fig, z_label=_z_label)
            else:
                _draw(ax_left, spec, data, color, fig=fig, z_label=_z_label)

        label_kwargs = {}
        if getattr(layer, "label_font_family", ""):
            label_kwargs["fontfamily"] = layer.label_font_family
        label_kwargs["fontsize"] = getattr(layer, "label_font_size", 12.0) or 12.0
        if getattr(layer, "label_color", ""):
            label_kwargs["color"] = layer.label_color

        x_label, y_label = auto_axis_labels(project, layer)
        if x_label:
            ax_left.set_xlabel(x_label, **label_kwargs)
        if y_label and not ax_left.get_ylabel():
            ax_left.set_ylabel(y_label, **label_kwargs)
        if layer.y2_label and ax_right is not None:
            ax_right.set_ylabel(layer.y2_label, **label_kwargs)

        if getattr(graph, "title", ""):
            title_kwargs = {}
            if getattr(graph, "title_font_family", ""):
                title_kwargs["fontfamily"] = graph.title_font_family
            title_kwargs["fontsize"] = getattr(graph, "title_font_size", 14.0) or 14.0
            if getattr(graph, "title_color", ""):
                title_kwargs["color"] = graph.title_color
            ax_left.set_title(graph.title, **title_kwargs)
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


def _draw(ax, spec, data, color, fig=None, z_label="") -> None:
    style = PlotStyle(spec.style)
    label = data.legend or None
    x, y = data.x, data.y
    ls = _linestyle(getattr(spec, "line_style", "solid"))

    if style in Z_STYLES:
        render_xyz_mpl(
            ax, fig, style, data, cmap=getattr(spec, "cmap", "viridis"),
            color=color, width=spec.line_width, symbol=spec.symbol,
            symbol_size=spec.symbol_size, line_style=ls, label=label,
            z_label=z_label or (getattr(data, "z_label", "") or "Value"),
        )
        return

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


_CBAR_DEFAULT_CMAP = "viridis"


def render_xyz_mpl(
    ax,
    fig,
    style: PlotStyle,
    data,
    *,
    cmap: str = "viridis",
    color: str = "",
    width: float = 2.0,
    symbol: str = "o",
    symbol_size: float = 7.0,
    line_style: object = "-",
    label: str | None = None,
    z_label: str = "Value",
) -> None:
    """Draw a Z-carrying series (color-mapped / heatmap / contour / 3D) on ``ax``.

    Shared by the live matplotlib canvas and the publication exporter so both
    render the *same* figure. Adds a colourbar to ``fig`` where meaningful.
    """
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 - needed for 3d projection side effects

    three_d = style in (PlotStyle.SCATTER3D, PlotStyle.SURFACE3D)
    size = symbol_size * 8 if style is PlotStyle.SCATTER3D else symbol_size
    ms = symbol_size * 0.6

    def _finish_colorbar(mapping, label_text: str) -> None:
        try:
            bar = fig.colorbar(mapping, ax=ax, fraction=0.046, pad=0.03)
            if label_text:
                bar.set_label(label_text)
        except Exception:  # noqa: BLE001 - colourbar is decorative
            pass

    if three_d and not hasattr(ax, "get_proj"):
        # A 3D series plotted on a 2D set of axes: fall back to a soft warning
        # contour view so the figure still renders.
        if data.z is not None and data.z.size:
            sc = ax.scatter(data.x, data.y, c=data.z, cmap=cmap, s=ms * 12, label=label)
            _finish_colorbar(sc, z_label)
        return

    if style is PlotStyle.COLOR_SCATTER:
        if data.z is None:
            # No colour column: degrade to a plain scatter.
            ax.scatter(data.x, data.y, s=ms * 55, c=color or None, label=label,
                       marker=symbol or "o")
            return
        sc = ax.scatter(data.x, data.y, c=data.z, cmap=cmap,
                        s=ms * 55, marker=symbol or "o", label=label)
        _finish_colorbar(sc, z_label)
        return

    if style is PlotStyle.HEATMAP:
        if data.z is None:
            ax.scatter(data.x, data.y, s=ms * 40, c=color or "0.3", label=label)
            return
        gx, gy, grid = grid_xyz(data.x, data.y, data.z)
        mesh = ax.pcolormesh(gx, gy, grid, cmap=cmap, shading="auto")
        _finish_colorbar(mesh, z_label)
        return

    if style is PlotStyle.CONTOUR:
        if data.z is None:
            ax.scatter(data.x, data.y, s=ms * 40, c=color or "0.3", label=label)
            return
        filled = ax.tricontourf(data.x, data.y, data.z, cmap=cmap)
        ax.tricontour(data.x, data.y, data.z, colors="k", linewidths=0.4, alpha=0.4)
        _finish_colorbar(filled, z_label)
        return

    if three_d:
        import numpy as _np

        z = data.z if data.z is not None else _np.zeros_like(data.x)
        if style is PlotStyle.SCATTER3D:
            kwargs = {}
            if data.z is not None:
                kwargs["c"] = data.z
                kwargs["cmap"] = cmap
            else:
                kwargs["color"] = color or "#1f77b4"
            ax.scatter3D(data.x, data.y, z, s=size, depthshade=False, **kwargs)
            return
        # SURFACE3D
        gx, gy, grid = grid_xyz(data.x, data.y, z)
        surface = ax.plot_surface(gx, gy, grid, cmap=cmap, linewidth=0.1,
                                  antialiased=True,
                                  color=color or None)
        _finish_colorbar(surface, z_label)
        return


__all__ = ["export_graph", "_FORMATS", "SUPPORTED_FORMATS", "render_xyz_mpl"]
