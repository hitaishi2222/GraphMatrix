"""Canvas chrome: the floating overlay, panel marker, zoom tools, readout.

The overlay is a plain widget, so the readout and the crosshair can never leak
into an exported figure — that is checked here as well.
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
    # The overlay lives above the plot but never eats pointer events.
    assert overlay.testAttribute(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.WidgetAttribute.WA_TransparentForMouseEvents)


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
    canvas._remove_crosshair()
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
