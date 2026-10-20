"""Publication export tests (M4)."""

from __future__ import annotations

import numpy as np
import pytest

from graphmatrix.core.io.export import export_graph
from graphmatrix.core.model import (
    Annotation,
    ColumnType,
    Graph,
    PlotSpec,
    PlotStyle,
    Project,
    Workbook,
    Worksheet,
)


def _project_with_graph():
    project = Project("T")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0, 2 * np.pi, 100)
    sheet.add_column("X1", ColumnType.X, x, units="rad")
    sheet.add_column("Y1", ColumnType.Y, np.sin(x), units="V")
    graph = project.add_graph(Graph("Graph1", title="Sine"))
    graph.first_layer.add_plot(
        PlotSpec("Book1/Sheet1", "X1", "Y1", style=PlotStyle.LINE_SYMBOL, legend="sin")
    )
    return project, graph


def test_export_vector_and_raster(tmp_path):
    project, graph = _project_with_graph()
    for ext in ("pdf", "svg", "eps", "png"):
        out = export_graph(graph, project, tmp_path / f"fig.{ext}")
        assert out.exists() and out.stat().st_size > 0


def test_export_all_styles(tmp_path):
    project, graph = _project_with_graph()
    layer = graph.first_layer
    for style in PlotStyle:
        layer.plots[0].style = style
        out = export_graph(graph, project, tmp_path / f"fig_{style.name}.png")
        assert out.exists() and out.stat().st_size > 0


def test_export_dual_axis_and_annotation(tmp_path):
    project = Project("T")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0, 10, 120)
    sheet.add_column("X1", ColumnType.X, x)
    sheet.add_column("Y1", ColumnType.Y, np.sin(x))
    sheet.add_column("Y2", ColumnType.Y, 100 * np.cos(x))
    graph = project.add_graph(Graph("Graph1", title="Dual"))
    layer = graph.first_layer
    layer.y2_label = "Second"
    layer.plots.append(PlotSpec("Book1/Sheet1", "X1", "Y1", legend="sin"))
    layer.plots.append(
        PlotSpec("Book1/Sheet1", "X1", "Y2", legend="cos", y_axis="right")
    )
    graph.annotations.append(Annotation("peak", x=0.6, y=0.2))

    out = export_graph(graph, project, tmp_path / "dual.pdf")
    assert out.exists() and out.stat().st_size > 0


def test_export_grid_and_stack_layouts(tmp_path):
    from graphmatrix.core.model import Layer

    project, graph = _project_with_graph()
    second = Layer("Layer 2")
    second.plots.append(PlotSpec("Book1/Sheet1", "X1", "Y1", legend="sin2"))
    graph.layers.append(second)

    graph.graph_type = "grid"
    graph.layout_rows, graph.layout_cols = 2, 2
    graph.sync_layout()
    grid_out = export_graph(graph, project, tmp_path / "grid.png")
    assert grid_out.exists() and grid_out.stat().st_size > 0

    graph.graph_type = "stack"
    graph.y_delta = 1.0
    graph.sync_layout()
    stack_out = export_graph(graph, project, tmp_path / "stack.pdf")
    assert stack_out.exists() and stack_out.stat().st_size > 0


def test_unsupported_format_raises_a_clear_error(tmp_path):
    project, graph = _project_with_graph()
    with pytest.raises(ValueError, match="Unsupported export format"):
        export_graph(graph, project, tmp_path / "fig.bmp")


def test_jpeg_suffix_maps_to_jpg(tmp_path):
    project, graph = _project_with_graph()
    out = export_graph(graph, project, tmp_path / "fig.jpeg")
    assert out.exists() and out.stat().st_size > 0


# -- WYSIWYG: the export must look like the preview -------------------------


def _corner_colour(path):
    from PIL import Image

    with Image.open(path) as im:
        return im.convert("RGB").getpixel((1, 1))


def test_export_follows_the_requested_theme(tmp_path):
    project, graph = _project_with_graph()
    dark = export_graph(
        graph, project, tmp_path / "dark.png", dpi=60, theme="classic-dark"
    )
    light = export_graph(
        graph, project, tmp_path / "light.png", dpi=60, theme="plot-publication"
    )
    assert _corner_colour(dark) == (25, 26, 29)  # classic-dark background
    assert _corner_colour(light) == (255, 255, 255)  # publication background


def test_graph_plot_theme_wins_over_the_application_theme(tmp_path):
    project, graph = _project_with_graph()
    graph.plot_theme = "plot-earth"
    out = export_graph(
        graph, project, tmp_path / "earth.png", dpi=60, theme="classic-dark"
    )
    assert _corner_colour(out) == (246, 241, 231)  # plot-earth background


def test_journal_preset_exports_on_white_paper(tmp_path):
    project, graph = _project_with_graph()
    graph.journal_preset = "nature"
    out = export_graph(
        graph, project, tmp_path / "journal.png", dpi=60, theme="classic-dark"
    )
    assert _corner_colour(out) == (255, 255, 255)


def test_apply_theme_paints_background_grid_and_legend():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba

    from graphmatrix.core.io.export import _apply_theme

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], label="s")
    ax.legend()
    _apply_theme(fig, "#101112", "#f0f0f0", 0.3)

    assert fig.patch.get_facecolor() == to_rgba("#101112")
    assert ax.get_facecolor() == to_rgba("#101112")
    grid = ax.get_xgridlines()
    assert grid and grid[0].get_color() == "#f0f0f0"
    assert ax.get_legend().get_texts()[0].get_color() == "#f0f0f0"
    plt.close(fig)


def test_export_keeps_the_screen_aspect_ratio(tmp_path):
    project, graph = _project_with_graph()
    out = export_graph(
        graph, project, tmp_path / "wide.png", width_mm=100, dpi=60, aspect=2.0
    )
    from PIL import Image

    with Image.open(out) as im:
        width, height = im.size
    assert width / height == pytest.approx(2.0, rel=0.05)


def test_scaled_rcparams_shrink_the_typography():
    from graphmatrix.core.io.export import _scaled_rcparams

    assert _scaled_rcparams(1.0) == {}
    scaled = _scaled_rcparams(0.5)
    assert scaled["font.size"] == 5.0
    assert scaled["lines.linewidth"] == pytest.approx(0.75)
    assert scaled["lines.markersize"] == pytest.approx(3.0)


def test_a_scaled_export_draws_smaller_type(tmp_path):
    """A small page must show the same proportions as a big canvas."""
    import numpy as np

    project, graph = _project_with_graph()

    def title_ink(path):
        from PIL import Image

        with Image.open(path) as im:
            rgb = np.asarray(im.convert("RGB"))
        background = rgb[1, 1]
        mask = (rgb != background).any(axis=2)
        # The title is the first block of inked rows at the top of the figure.
        rows = np.where(mask.any(axis=1))[0]
        if rows.size == 0:
            return 0
        first = int(rows[0])
        last = first
        for row in rows[1:]:
            if int(row) != last + 1:
                break
            last = int(row)
        return int(mask[first : last + 1, :].sum())

    big = export_graph(
        graph, project, tmp_path / "big.png", width_mm=100, dpi=100, scale=1.0
    )
    small = export_graph(
        graph, project, tmp_path / "small.png", width_mm=100, dpi=100, scale=0.4
    )
    # The title is drawn smaller, so the band that holds it carries less ink.
    assert title_ink(small) < title_ink(big) * 0.6
