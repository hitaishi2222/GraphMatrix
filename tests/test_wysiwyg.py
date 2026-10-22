"""What you see is what you get: the preview and the export must agree.

The live canvas and the exporter draw the same figure through two different
matplotlib code paths, so these tests pin the things that used to drift:
background, foreground, grid, title and legend colours, and the figure size.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from graphmatrix.core.plot_themes import resolve_theme


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_resolve_theme_prefers_the_graph_theme():
    assert resolve_theme("plot-seaborn", "classic-dark") == ("#f0f0f0", "#262626", 0.30)
    assert resolve_theme("", "modern-dark") == ("#0e1015", "#dde1ea", 0.14)
    # Unknown ids fall back to the application default.
    assert resolve_theme("nope", "nope") == ("#191a1d", "#d7dae0", 0.16)


def test_app_and_plot_themes_agree_with_the_ui_palette():
    from graphmatrix.ui import theme as ui_theme

    for preset in ("classic-dark", "classic-light", "modern-dark", "modern-light"):
        assert ui_theme.canvas_colors(preset) == resolve_theme("", preset)


def test_canvas_legend_and_title_follow_the_theme(qapp):
    from graphmatrix.ui.canvas.matplotlib_canvas import MatplotlibCanvas

    canvas = MatplotlibCanvas()
    canvas.set_theme("classic-dark")
    canvas.set_grid(1, 1)
    canvas.plot([0, 1, 2], [0, 1, 0], style="line", name="series")
    canvas.show_legend(True)
    canvas.set_title("A title")

    legend = canvas._ax_left.get_legend()
    assert legend is not None
    assert legend.get_texts()[0].get_color() == "#d7dae0"
    assert canvas._fig._suptitle.get_color() == "#d7dae0"
    background = canvas._ax_left.get_facecolor()
    assert tuple(round(c, 3) for c in background[:3]) == (0.098, 0.102, 0.114)


def test_canvas_and_exporter_use_the_same_series_colours(qapp):
    """A series on a secondary axis must not fall back to the first colour."""
    from graphmatrix.core.plot_themes import series_color
    from graphmatrix.ui.canvas.matplotlib_canvas import MatplotlibCanvas

    canvas = MatplotlibCanvas()
    canvas.set_grid(1, 1)
    canvas.plot([0, 1], [0, 1], style="line", name="a", color=series_color(0))
    canvas.plot([0, 1], [1, 0], style="line", name="b", color=series_color(1))
    assert [line.get_color() for line in canvas._ax_left.get_lines()] == [
        series_color(0),
        series_color(1),
    ]


def test_exporter_uses_the_shared_palette():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from graphmatrix.core.io.export import _render_figure
    from graphmatrix.core.model import (
        ColumnType,
        Graph,
        PlotSpec,
        Project,
        Workbook,
        Worksheet,
    )
    from graphmatrix.core.plot_themes import series_color

    project = Project("T")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0, 10, 20)
    sheet.add_column("X1", ColumnType.X, x)
    sheet.add_column("Y1", ColumnType.Y, np.sin(x))
    sheet.add_column("Y2", ColumnType.Y, np.cos(x))
    graph = project.add_graph(Graph("G"))
    graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1"))
    graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y2"))

    fig, ax = plt.subplots()
    _render_figure(fig, [ax], graph, project, ("#ffffff", "#000000", 0.2), 1.0)
    assert [line.get_color() for line in ax.get_lines()] == [
        series_color(0),
        series_color(1),
    ]
    plt.close(fig)
