"""Canvas chrome: the floating overlay, panel marker, zoom tools, readout.

The overlay is a plain widget, so the readout can never leak into an exported
figure — that is checked here as well.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def canvas(qapp):
    from graphmatrix.ui.canvas.matplotlib_canvas import MatplotlibCanvas

    c = MatplotlibCanvas()
    c.set_grid(1, 1)
    c.plot([0.0, 1.0, 2.0], [0.0, 1.0, 0.0], style="line", name="Signal")
    return c


class _Event:
    """A stand-in for matplotlib's motion event."""

    def __init__(self, axes, xdata, ydata, x=10, y=20):
        self.inaxes = axes
        self.xdata = xdata
        self.ydata = ydata
        self.x = x
        self.y = y


def test_the_canvas_has_a_floating_overlay(canvas):
    overlay = canvas.overlay()
    assert overlay is not None
    # The overlay lives above the plot, so it must not eat the pointer events
    # meant for the canvas.
    assert overlay.testAttribute(
        __import__(
            "PySide6.QtCore", fromlist=["Qt"]
        ).Qt.WidgetAttribute.WA_TransparentForMouseEvents
    )
    # The tool buttons are ordinary widgets on the workspace around the
    # figure: they are always clickable and never cover the plot.
    tools = canvas._tools
    assert tools.parent() is canvas.widget()
    for button in (tools._zoom_in, tools._zoom_out, tools._fit, tools._hover):
        assert button.isEnabled()


def test_the_hover_readout_lives_in_the_overlay_not_in_the_figure(canvas):
    canvas.set_hover(True)
    canvas._on_hover(_Event(canvas._ax_left, 1.0, 1.0, x=100, y=50))
    overlay = canvas.overlay()
    assert "Signal" in overlay._readout_label.text()
    # Nothing was added to the figure, so an export stays clean.
    assert len(canvas._fig.axes[0].texts) == 0
    assert canvas._fig.axes[0].lines  # only the data line


def test_the_readout_is_removed_when_the_hover_leaves(canvas):
    canvas.set_hover(True)
    canvas._on_hover(_Event(canvas._ax_left, 1.0, 1.0))
    assert canvas.overlay()._readout_label.text()
    canvas._clear_readout()
    assert canvas.overlay()._readout_label.text() == ""


def test_zoom_and_fit_change_the_limits(canvas):
    before = canvas._ax_left.get_xlim()
    canvas.zoom_in()
    zoomed = canvas._ax_left.get_xlim()
    assert zoomed[1] - zoomed[0] < before[1] - before[0]
    canvas.zoom_out()
    assert canvas._ax_left.get_xlim() == pytest.approx(before, abs=1e-6)
    canvas._ax_left.set_xlim(0.0, 0.5)
    canvas.fit()
    assert canvas._ax_left.get_xlim() != pytest.approx((0.0, 0.5))


def test_the_panel_marker_names_the_edited_panel(canvas):
    canvas.set_grid(2, 2)
    canvas.set_active_panel(1, 4)
    overlay = canvas.overlay()
    assert overlay._panel_text == "Panel 2 / 4"
    assert overlay._panel_label.text() == "Panel 2 / 4"
    # A single-panel figure shows no marker at all.
    canvas.set_grid(1, 1)
    canvas.set_active_panel(0, 1)
    assert canvas.overlay()._panel_text == ""


def test_the_graph_view_draws_a_stacked_line_as_bands(qapp):
    """The live canvas must show the bands, not the absolute values."""
    import numpy as np

    from graphmatrix.core.model import (
        ColumnType,
        Graph,
        PlotSpec,
        Project,
        Workbook,
        Worksheet,
    )
    from graphmatrix.ui.graph_view import GraphView

    project = Project("T")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0, 10, 40)
    sheet.add_column("X1", ColumnType.X, x)
    sheet.add_column("Y1", ColumnType.Y, np.sin(x))
    sheet.add_column("Y2", ColumnType.Y, 100 * np.cos(x))
    graph = project.add_graph(Graph("G"))
    graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1", legend="a"))
    graph.add_layer().add_plot(PlotSpec("Book1/Sheet1", "X1", "Y2", legend="b"))
    graph.graph_type = "stack-line"
    graph.sync_layout()
    for layer in graph.layers:
        layer.y_mode = "normalized"

    from graphmatrix.core.commands import CommandStack

    view = GraphView(graph, project, CommandStack())
    try:
        view.refresh()
        canvas = view.canvas
        # One panel holds every band.
        assert len(canvas._axes) == 1
        series = canvas._series
        assert len(series) == 2
        first = np.asarray(series[0][1], dtype=float)
        second = np.asarray(series[1][1], dtype=float)
        # The bands are normalised and stacked one above the other.
        assert first.max() - first.min() == pytest.approx(1.0)
        assert second.min() > first.max()
        # The readout still shows the worksheet values, not the drawn ones.
        raw = canvas._readout_values(0)[1]
        assert raw.max() == pytest.approx(1.0, abs=1e-2)
        assert raw.min() == pytest.approx(-1.0, abs=1e-2)
    finally:
        view.deleteLater()


def test_the_graph_view_marks_the_panel_of_the_selected_plot(qapp):
    import numpy as np

    from graphmatrix.core.model import (
        ColumnType,
        Graph,
        PlotSpec,
        Project,
        Workbook,
        Worksheet,
    )
    from graphmatrix.ui.graph_view import GraphView

    project = Project("T")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0, 10, 20)
    sheet.add_column("X1", ColumnType.X, x)
    sheet.add_column("Y1", ColumnType.Y, np.sin(x))
    graph = project.add_graph(Graph("G"))
    graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1", legend="a"))
    graph.add_layer().add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1", legend="b"))
    graph.graph_type = "stack"
    graph.sync_layout()

    from graphmatrix.core.commands import CommandStack

    view = GraphView(graph, project, CommandStack())
    try:
        view.refresh()
        # Selecting the series of the second layer marks the second panel.
        view.plot_list.setCurrentRow(1)
        assert view.canvas.overlay()._panel_text == "Panel 2 / 2"
        view.plot_list.setCurrentRow(0)
        assert view.canvas.overlay()._panel_text == "Panel 1 / 2"
    finally:
        view.deleteLater()


def test_the_checked_tool_chip_follows_the_preset_accent(qapp):
    """The floating tool strip must not keep a stale accent in a new theme."""
    from graphmatrix.ui import theme
    from graphmatrix.ui.canvas.overlay import _chrome

    original = theme.current_preset()
    try:
        theme.set_preset("classic-dark")
        classic = _chrome(dark=True)["checked"]
        theme.set_preset("shadcn-dark")
        neutral = _chrome(dark=True)["checked"]
    finally:
        theme.set_preset(original)
    # classic-dark's indigo accent is what the old hardcoded value was.
    assert classic == "rgba(76,141,255,70)"
    assert neutral == "rgba(250,250,250,70)"
