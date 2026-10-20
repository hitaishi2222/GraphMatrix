"""Publication-quality graph export (M4) via matplotlib.

The live canvas uses pyqtgraph, but export goes through matplotlib's vector
backends for font-embedded PDF/SVG/EPS and high-DPI raster output. Both render
the *same* resolved series (``core.plotting``) with the same style mapping.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..journals import export_rcparams, figure_size
from ..model import AxisScale, Graph, PlotStyle, Project, Z_STYLES, is_3d_style
from ..plot_themes import resolve_theme, series_color
from ..plotting import auto_axis_labels, grid_xyz, resolve_layer

#: Plot-theme (canvas) colours live in ``core.plot_themes`` so the live canvas
#: and this exporter cannot drift apart.

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


def _axis_is_log(value: object) -> bool:
    """True when an axis-scale value means "log" (enum or plain string)."""
    try:
        return AxisScale(value).value == "log"
    except (TypeError, ValueError):
        return False


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
    theme: str = "",
    aspect: float | None = None,
    scale: float = 1.0,
    white_background: bool = False,
    view_limits: dict[int, tuple[float, float, float, float]] | None = None,
) -> Path:
    """Render a graph to a file.

    ``theme`` is the application preset the canvas follows (the graph's own
    ``plot_theme`` wins over it), so the exported figure looks like the
    preview. ``aspect`` (``width / height``) overrides the requested height so
    the file can keep the on-screen proportions. ``scale`` shrinks the
    typography, line widths and markers by that factor, which is what keeps a
    small export looking like a big on-screen canvas.

    ``white_background`` forces the print-safe palette (white paper, black
    ink). A dark application theme otherwise produces a black-background
    figure, which is fine on screen but unusable in a paper.

    ``view_limits`` maps a layer index to the limits
    ``(x_min, x_max, y_min, y_max)`` of the view on screen. Passing them
    keeps the "what you see is what you get" rule for a figure that was
    zoomed or panned.
    """
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
    if aspect:
        height_mm = width_mm / max(0.05, float(aspect))
    height_mm = 75.0 if height_mm is None else height_mm
    figsize = (width_mm / 25.4, height_mm / 25.4)

    rc = export_rcparams(preset_name) if preset_name else _scaled_rcparams(scale)
    use_3d = any(
        is_3d_style(spec.style)
        for graph_layer in graph.layers
        for spec in graph_layer.plots
    )
    with mpl.rc_context(rc):
        fig = plt.figure(figsize=figsize, dpi=dpi)
        _use_constrained_layout(fig, graph)
        rows = max(1, int(getattr(graph, "layout_rows", 1) or 1))
        cols = max(1, int(getattr(graph, "layout_cols", 1) or 1))
        if use_3d:
            axes = [fig.add_subplot(111, projection="3d")]
        elif rows * cols > 1:
            grid = fig.subplots(rows, cols, squeeze=False)
            axes = [ax for row in grid for ax in row]
        else:
            axes = [fig.add_subplot(111)]
        plot_theme = getattr(graph, "plot_theme", "")
        if white_background:
            # Print request: white paper, black ink, whatever the app looks like.
            bg, fg, grid_alpha = resolve_theme("plot-publication")
        elif plot_theme:
            # An explicit per-graph theme wins.
            bg, fg, grid_alpha = resolve_theme(plot_theme)
        elif preset_name:
            # A journal preset is a publication request: white paper, black ink.
            bg, fg, grid_alpha = resolve_theme("plot-publication")
        else:
            bg, fg, grid_alpha = resolve_theme("", theme)
        _render_figure(
            fig,
            axes,
            graph,
            project,
            (bg, fg, grid_alpha),
            scale,
            view_limits=view_limits,
        )
        _apply_theme(fig, bg, fg, grid_alpha)
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
        fig.savefig(path, format=fmt, dpi=dpi, transparent=transparent)
        plt.close(fig)
    return path


def _use_constrained_layout(fig, graph: Graph) -> None:
    """Let matplotlib lay the panels out without label collisions.

    The constrained-layout engine reserves the space each panel's tick
    labels, axis labels and legend need, so a figure exported at print size
    (where the panels are small) never draws one panel's labels on top of
    its neighbour. The panel gaps of the graph are passed on as the spacing
    between the panels, so the layout still follows the user's settings.
    """
    gap_x = max(0.0, float(getattr(graph, "panel_gap_x", 12.0) or 0.0) / 100.0)
    gap_y = max(0.0, float(getattr(graph, "panel_gap_y", 12.0) or 0.0) / 100.0)
    try:
        fig.set_layout_engine("constrained", wspace=gap_x, hspace=gap_y)
    except Exception:  # noqa: BLE001 - very old matplotlib: keep the default
        pass


def _share_y_for_twins(fig, axes, graph: Graph) -> None:
    """Give every panel of an X-Twin graph the same Y range.

    An X-Twin is defined by panels that share their Y axis, so the panels
    must be scaled to the same data range - otherwise the two halves of the
    figure cannot be compared by eye.
    """
    if str(getattr(graph, "graph_type", "")) != "x-twin":
        return
    low = None
    high = None
    for ax in axes:
        try:
            bottom, top = ax.get_ylim()
        except Exception:  # noqa: BLE001 - axes may not be scaled yet
            continue
        low = bottom if low is None else min(low, bottom)
        high = top if high is None else max(high, top)
    if low is None or high is None or low == high:
        return
    for ax in axes:
        try:
            ax.set_ylim(low, high)
        except Exception:  # noqa: BLE001
            continue


def _scaled_rcparams(scale: float) -> dict[str, Any]:
    """matplotlib defaults scaled to the exported figure.

    Font sizes, line widths and marker sizes are absolute (points), so a
    100 mm export of a figure that fills the screen would look completely
    different unless they are scaled with the page.
    """
    factor = max(0.05, float(scale or 1.0))
    if abs(factor - 1.0) < 1e-6:
        return {}
    return {
        "font.size": 10.0 * factor,
        "axes.labelsize": 10.0 * factor,
        "axes.titlesize": 10.0 * factor,
        "xtick.labelsize": 10.0 * factor,
        "ytick.labelsize": 10.0 * factor,
        "legend.fontsize": 10.0 * factor,
        "lines.linewidth": 1.5 * factor,
        "lines.markersize": 6.0 * factor,
        "axes.linewidth": 0.8 * factor,
    }


def _apply_theme(fig, bg: str, fg: str, grid_alpha: float) -> None:
    """Apply the canvas theme to a rendered figure.

    The live canvas draws the same background, foreground, grid and legend
    colours, so the exported file looks like the preview.
    """
    fig.patch.set_facecolor(bg)
    for ax in fig.axes:
        ax.set_facecolor(bg)
        ax.tick_params(colors=fg)
        for axis in (ax.xaxis, ax.yaxis):
            if axis.label is not None:
                axis.label.set_color(fg)
        if ax.title is not None:
            ax.title.set_color(fg)
        for spine in ax.spines.values():
            spine.set_color(fg)
        ax.grid(True, alpha=grid_alpha, color=fg)
        leg = ax.get_legend()
        if leg is not None:
            for text in leg.get_texts():
                text.set_color(fg)


def _render_figure(
    fig,
    axes,
    graph: Graph,
    project: Project,
    colors: tuple[str, str, float],
    scale: float = 1.0,
    view_limits: dict[int, tuple[float, float, float, float]] | None = None,
) -> None:
    """Draw each layer onto its own panel, honouring the graph's layout type."""
    if not axes:
        return
    _bg, fg, _grid = colors
    factor = max(0.05, float(scale or 1.0))
    single_panel = len(axes) == 1
    graph_type = getattr(graph, "graph_type", "simple")
    right_axes: dict[int, object] = {}
    offset_panels = graph_type in ("stack", "x-twin")
    y_delta = float(getattr(graph, "y_delta", 0.0) or 0.0)

    for panel_index, layer in enumerate(graph.layers):
        axis_index = 0 if single_panel else min(panel_index, len(axes) - 1)
        ax_left = axes[axis_index]
        ax_right = right_axes.get(axis_index)
        offset = panel_index * y_delta if offset_panels else 0.0

        if _axis_is_log(layer.x_scale):
            ax_left.set_xscale("log")
        if _axis_is_log(layer.y_scale):
            ax_left.set_yscale("log")
            if ax_right is not None:
                ax_right.set_yscale("log")

        series = resolve_layer(project, layer)
        for plot_index, (spec, data) in enumerate(zip(layer.plots, series)):
            color = spec.color or series_color(plot_index)
            _z_label = (
                getattr(layer, "z_label", "") or getattr(data, "z_label", "") or "Value"
            )
            if getattr(spec, "y_axis", "left") == "right":
                if ax_right is None:
                    ax_right = ax_left.twinx()
                    right_axes[axis_index] = ax_right
                    if _axis_is_log(layer.y_scale):
                        ax_right.set_yscale("log")
                _draw(
                    ax_right,
                    spec,
                    data,
                    color,
                    fig=fig,
                    z_label=_z_label,
                    y_offset=offset,
                    scale=factor,
                )
            else:
                _draw(
                    ax_left,
                    spec,
                    data,
                    color,
                    fig=fig,
                    z_label=_z_label,
                    y_offset=offset,
                    scale=factor,
                )

        label_kwargs = {}
        if getattr(layer, "label_font_family", ""):
            label_kwargs["fontfamily"] = layer.label_font_family
        label_kwargs["fontsize"] = (getattr(layer, "label_font_size", 12.0) or 12.0) * factor
        if getattr(layer, "label_color", ""):
            label_kwargs["color"] = layer.label_color

        x_label, y_label = auto_axis_labels(project, layer)
        last_panel = panel_index == len(graph.layers) - 1
        if graph_type == "stack" and not last_panel:
            # A stack shares one X axis: the upper panels hide theirs, exactly
            # as the live canvas does.
            ax_left.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
            ax_left.spines["bottom"].set_visible(False)
            ax_left.xaxis.label.set_visible(False)
        if x_label and not (graph_type == "stack" and not last_panel):
            ax_left.set_xlabel(x_label, **label_kwargs)
        if y_label and not (graph_type == "x-twin" and panel_index != 0):
            ax_left.set_ylabel(y_label, **label_kwargs)
        if layer.y2_label and ax_right is not None:
            ax_right.set_ylabel(layer.y2_label, **label_kwargs)

        if layer.x_min is not None or layer.x_max is not None:
            ax_left.set_xlim(left=layer.x_min, right=layer.x_max)
        if layer.y_min is not None or layer.y_max is not None:
            ax_left.set_ylim(bottom=layer.y_min, top=layer.y_max)
        view = (view_limits or {}).get(panel_index)
        if view is not None:
            # The view on screen wins: a zoomed or panned figure is exported
            # the way it is seen.
            try:
                ax_left.set_xlim(view[0], view[1])
                ax_left.set_ylim(view[2], view[3])
            except Exception:  # noqa: BLE001 - bad limits: keep the auto range
                pass

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

        if not getattr(layer, "show_y_axis", True):
            ax_left.tick_params(axis="y", which="both", left=False, labelleft=False)
            ax_left.spines["left"].set_visible(False)
            ax_left.yaxis.label.set_visible(False)

        for ref in getattr(layer, "ref_lines", []):
            style = _linestyle(ref.line_style)
            position = (
                ref.position + offset
                if ref.orientation == "h" and offset
                else ref.position
            )
            if ref.orientation == "v":
                line = ax_left.axvline(
                    position, color=ref.color, linewidth=ref.width * factor, linestyle=style
                )
            else:
                line = ax_left.axhline(
                    position, color=ref.color, linewidth=ref.width * factor, linestyle=style
                )
            if ref.label:
                _label_reference_line(ax_left, ref, line)

        if getattr(layer, "show_legend", True):
            handles, labels = ax_left.get_legend_handles_labels()
            if ax_right is not None:
                h2, l2 = ax_right.get_legend_handles_labels()
                handles, labels = handles + h2, labels + l2
            if labels:
                legend = ax_left.legend(handles, labels, loc="best", frameon=False)
                for text in legend.get_texts():
                    text.set_color(fg)

    for annotation in getattr(graph, "annotations", []):
        axes[0].text(
            annotation.x,
            annotation.y,
            annotation.text,
            transform=axes[0].transAxes,
            color=annotation.color,
            fontsize=annotation.size * factor,
            ha="left",
            va="top",
        )

    if graph.title:
        title_kwargs = {}
        if getattr(graph, "title_font_family", ""):
            title_kwargs["fontfamily"] = graph.title_font_family
        title_kwargs["fontsize"] = (getattr(graph, "title_font_size", 14.0) or 14.0) * factor
        if getattr(graph, "title_color", ""):
            title_kwargs["color"] = graph.title_color
        else:
            title_kwargs["color"] = fg
        fig.suptitle(graph.title, **title_kwargs)

    # The panels are laid out by matplotlib's constrained layout engine: it
    # reserves room for tick labels, axis labels and the title, so a small
    # print-size figure never draws one panel's tick labels on top of its
    # neighbour. The live canvas uses the same engine with the same panel
    # gaps, so the preview and the file agree.
    if len(axes) > 1:
        _share_y_for_twins(fig, axes, graph)


def _draw(
    ax, spec, data, color, fig=None, z_label="", y_offset=0.0, scale: float = 1.0
) -> None:
    factor = max(0.05, float(scale or 1.0))
    style = PlotStyle(spec.style)
    label = data.legend or None
    x, y = data.x, data.y
    if y_offset:
        y = np.asarray(y, dtype=float) + y_offset
    ls = _linestyle(getattr(spec, "line_style", "solid"))

    if style in Z_STYLES:
        render_xyz_mpl(
            ax,
            fig,
            style,
            data,
            cmap=getattr(spec, "cmap", "viridis"),
            color=color,
            width=spec.line_width * factor,
            symbol=spec.symbol,
            symbol_size=spec.symbol_size * factor,
            line_style=ls,
            label=label,
            z_label=z_label or (getattr(data, "z_label", "") or "Value"),
        )
        return

    if style is PlotStyle.SCATTER:
        ax.plot(
            x,
            y,
            linestyle="none",
            marker=spec.symbol,
            markersize=spec.symbol_size * 0.6 * factor,
            color=color,
            label=label,
        )
    elif style is PlotStyle.LINE:
        ax.plot(x, y, color=color, linewidth=spec.line_width * factor, linestyle=ls, label=label)
    elif style is PlotStyle.LINE_SYMBOL:
        ax.plot(
            x,
            y,
            color=color,
            linewidth=spec.line_width * factor,
            marker=spec.symbol,
            markersize=spec.symbol_size * 0.6 * factor,
            linestyle=ls,
            label=label,
        )
    elif style is PlotStyle.BAR:
        ax.bar(x, y, color=color, label=label)
    elif style is PlotStyle.AREA:
        ax.fill_between(x, y, alpha=0.3, color=color)
        ax.plot(x, y, color=color, linewidth=spec.line_width * factor, linestyle=ls, label=label)
    elif style is PlotStyle.STEP:
        ax.step(
            x,
            y,
            where="mid",
            color=color,
            linewidth=spec.line_width * factor,
            linestyle=ls,
            label=label,
        )
    elif style is PlotStyle.ERRORBAR:
        ax.errorbar(
            x,
            y,
            yerr=data.yerr,
            xerr=data.xerr,
            color=color,
            linewidth=spec.line_width * factor,
            linestyle=ls,
            marker=spec.symbol,
            markersize=spec.symbol_size * 0.6 * factor,
            capsize=3 * factor,
            label=label,
        )


def _label_reference_line(ax, ref, line) -> None:
    """Attach a small text label to a reference line at the top edge of the axes."""
    try:
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
    except Exception:  # noqa: BLE001 - axes may be pre-autoscale
        return
    pad = 0.01 * (ymax - ymin if ymax != ymin else 1.0)
    if ref.orientation == "v":
        ax.text(
            ref.position,
            ymax - pad,
            ref.label,
            color=ref.color,
            fontsize=8,
            ha="left",
            va="top",
            rotation=90,
        )
    else:
        ax.text(
            xmax,
            ref.position,
            ref.label,
            color=ref.color,
            fontsize=8,
            ha="right",
            va="bottom",
        )


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
            ax.scatter(
                data.x,
                data.y,
                s=ms * 55,
                c=color or None,
                label=label,
                marker=symbol or "o",
            )
            return
        sc = ax.scatter(
            data.x,
            data.y,
            c=data.z,
            cmap=cmap,
            s=ms * 55,
            marker=symbol or "o",
            label=label,
        )
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
        surface = ax.plot_surface(
            gx,
            gy,
            grid,
            cmap=cmap,
            linewidth=0.1,
            antialiased=True,
            color=color or None,
        )
        _finish_colorbar(surface, z_label)
        return


__all__ = ["export_graph", "_FORMATS", "SUPPORTED_FORMATS", "render_xyz_mpl"]
