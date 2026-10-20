"""Stacked-line figures: bands that show the trend, not the absolute value."""

from __future__ import annotations

import numpy as np
import pytest

from graphmatrix.core.bands import (
    Y_MODE_NORMALIZED,
    band_baselines,
    finite_range,
    layer_band_transform,
    log_transform,
    scale_to_band,
)
from graphmatrix.core.commands import CommandStack, SetGraphTypeCommand
from graphmatrix.core.io.export import export_graph
from graphmatrix.core.model import (
    ColumnType,
    Graph,
    Layer,
    PlotSpec,
    Project,
    Workbook,
    Worksheet,
)


def _project_with_two_curves():
    """A small sheet with two curves of very different magnitude."""
    project = Project("T")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0, 2 * np.pi, 120)
    sheet.add_column("X1", ColumnType.X, x)
    sheet.add_column("Y1", ColumnType.Y, np.sin(x))
    # Two orders of magnitude bigger than Y1.
    sheet.add_column("Y2", ColumnType.Y, 100 * np.cos(x))
    graph = project.add_graph(Graph("Graph1", title="Bands"))
    graph.first_layer.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y1", legend="sin"))
    second = Layer("Layer 2")
    second.add_plot(PlotSpec("Book1/Sheet1", "X1", "Y2", legend="cos"))
    graph.layers.append(second)
    return project, graph


# -- the band maths ---------------------------------------------------------


def test_normalisation_maps_the_values_onto_zero_and_one():
    values = np.array([10.0, 20.0, 30.0])
    scaled = scale_to_band(values, 10.0, 30.0)
    assert scaled[0] == pytest.approx(0.0)
    assert scaled[-1] == pytest.approx(1.0)
    assert scaled[1] == pytest.approx(0.5)


def test_a_flat_series_is_drawn_flat_instead_of_dividing_by_zero():
    transform, height, factor = layer_band_transform(
        np.array([5.0, 5.0, 5.0]), mode=Y_MODE_NORMALIZED
    )
    assert np.allclose(transform(np.array([5.0, 5.0, 5.0])), 0.0)
    assert height == pytest.approx(1.0)
    assert factor == 0.0


def test_missing_values_are_ignored_by_the_range_and_stay_gaps():
    values = np.array([1.0, np.nan, 3.0])
    low, high = finite_range(values)
    assert (low, high) == (1.0, 3.0)
    scaled = scale_to_band(values, low, high)
    assert np.isnan(scaled[1])


def test_a_log_layer_keeps_its_own_values():
    values = np.array([1.0, 10.0, 100.0])
    transform, height, _factor = layer_band_transform(
        values, mode=Y_MODE_NORMALIZED, log=True
    )
    drawn = transform(values)
    # The log scale is kept: the values are decades, not a 0..1 band.
    assert drawn[-1] == pytest.approx(2.0)
    assert height == pytest.approx(2.0)
    assert np.allclose(
        log_transform(np.array([0.0, 1.0])), [np.nan, 0.0], equal_nan=True
    )


def test_the_bands_never_overlap():
    baselines = band_baselines([1.0, 1.0, 1.0], pitch=1.2)
    assert baselines == [0.0, 1.2, 2.4]


def test_a_tall_band_pushes_the_bands_above_it_up():
    baselines = band_baselines([1.0, 5.0, 1.0], pitch=1.2)
    assert baselines[1] == pytest.approx(1.2)
    assert baselines[2] == pytest.approx(1.2 + 5.2)


# -- the model ---------------------------------------------------------------


def test_the_graph_type_is_a_preset_over_one_panel():
    graph = Graph("G")
    graph.graph_type = "stack-line"
    graph.sync_layout()
    assert (graph.layout_rows, graph.layout_cols) == (1, 1)


def test_switching_to_a_stacked_line_normalises_the_layers_and_undoes_it():
    graph = Graph("G")
    graph.add_layer(Layer("Layer 2"))
    commands = CommandStack()
    commands.push(SetGraphTypeCommand(graph, "stack-line"))
    assert [layer.y_mode for layer in graph.layers] == ["normalized", "normalized"]
    commands.undo()
    assert [layer.y_mode for layer in graph.layers] == ["absolute", "absolute"]


def test_the_layer_mode_survives_a_save_and_load():
    graph = Graph("G")
    graph.first_layer.y_mode = "normalized"
    graph.stack_offset = 2.0
    restored = Graph.from_dict(graph.to_dict())
    assert restored.first_layer.y_mode == "normalized"
    assert restored.stack_offset == pytest.approx(2.0)


def test_an_unknown_layer_mode_falls_back_to_absolute():
    layer = Layer()
    layer.y_mode = "nonsense"
    assert layer.y_mode == "absolute"


# -- the exporter ------------------------------------------------------------


def test_a_stacked_line_exports_one_panel_with_bands(tmp_path):
    project, graph = _project_with_two_curves()
    graph.graph_type = "stack-line"
    graph.sync_layout()
    for layer in graph.layers:
        layer.y_mode = "normalized"
    out = export_graph(graph, project, tmp_path / "bands.png", dpi=80)
    assert out.exists() and out.stat().st_size > 0

    # The two bands are drawn one above the other: the second band sits
    # higher than the first, and neither of them reaches the other's values.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from graphmatrix.core.io.export import _render_figure

    fig, ax = plt.subplots()
    axes = [ax]
    _render_figure(fig, axes, graph, project, ("#ffffff", "#000000", 0.2))
    lines = axes[0].get_lines()
    assert len(lines) == 2
    first = np.asarray(lines[0].get_ydata(), dtype=float)
    second = np.asarray(lines[1].get_ydata(), dtype=float)
    assert second.min() > first.max()
    # Both bands are normalised: they run from 0 to 1 over their own range.
    assert first.max() - first.min() == pytest.approx(1.0)
    assert second.max() - second.min() == pytest.approx(1.0)
    plt.close(fig)


def test_a_stacked_line_hides_the_y_numbers_but_keeps_the_axis(tmp_path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from graphmatrix.core.io.export import _render_figure

    project, graph = _project_with_two_curves()
    graph.graph_type = "stack-line"
    graph.sync_layout()
    fig, ax = plt.subplots()
    axes = [ax]
    _render_figure(fig, axes, graph, project, ("#ffffff", "#000000", 0.2))
    ax = axes[0]
    fig.canvas.draw()
    # The axis line and its ticks stay, the numbers go.
    assert ax.spines["left"].get_visible()
    # matplotlib drops the tick labels when they are hidden; the ticks stay.
    assert ax.get_yticklabels() == []
    assert len(ax.get_yticks()) > 1
    plt.close(fig)


def test_an_absolute_band_keeps_its_own_values(tmp_path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from graphmatrix.core.io.export import _render_figure

    project, graph = _project_with_two_curves()
    graph.graph_type = "stack-line"
    graph.sync_layout()
    graph.first_layer.y_mode = "absolute"
    fig, ax = plt.subplots()
    axes = [ax]
    _render_figure(fig, axes, graph, project, ("#ffffff", "#000000", 0.2))
    first = np.asarray(axes[0].get_lines()[0].get_ydata(), dtype=float)
    # sin(x) keeps its own values (the second layer is 100x bigger and sits
    # above it, on its own band).
    assert first.max() == pytest.approx(1.0, abs=1e-3)
    assert first.min() == pytest.approx(-1.0, abs=1e-3)
    plt.close(fig)


# -- the scripting API --------------------------------------------------------


def test_the_api_can_create_a_stacked_line_with_normalised_bands():
    from graphmatrix.core.scripting.graphs import create_graph

    project, _graph = _project_with_two_curves()
    result = create_graph(
        project,
        CommandStack(),
        name="Bands",
        graph_type="stack-line",
        panels=2,
        source="Book1/Sheet1",
        x="X1",
        y="Y1",
    )
    graph = project.graph("Bands")
    assert result["graph_type"] == "stack-line"
    assert len(graph.layers) == 2
    assert all(layer.y_mode == "normalized" for layer in graph.layers)


def test_the_api_can_set_the_layer_mode_and_the_band_pitch():
    from graphmatrix.core.scripting.graphs import set_property

    project, graph = _project_with_two_curves()
    set_property(project, CommandStack(), graph.name, "y_mode", "normalized", panel=1)
    set_property(project, CommandStack(), graph.name, "stack_offset", "2.0")
    assert graph.first_layer.y_mode == "normalized"
    assert graph.stack_offset == pytest.approx(2.0)


# -- the other surfaces -------------------------------------------------------


def test_the_generated_script_reproduces_the_figure():
    from graphmatrix.core.code_export import project_to_script

    project, graph = _project_with_two_curves()
    graph.graph_type = "stack-line"
    graph.sync_layout()
    graph.first_layer.y_mode = "normalized"
    graph.stack_offset = 1.5
    script = project_to_script(project)
    assert "g.graph_type = 'stack-line'" in script
    assert "g.stack_offset = 1.5" in script
    assert "layer.y_mode = 'normalized'" in script


def test_a_style_template_keeps_the_layer_mode():
    from graphmatrix.core.templates import apply_template, graph_to_template

    _project, graph = _project_with_two_curves()
    graph.first_layer.y_mode = "normalized"
    template = graph_to_template(graph, name="t")
    assert template["layers"][0]["y_mode"] == "normalized"

    graph.first_layer.y_mode = "absolute"
    apply_template(graph, template)
    assert graph.first_layer.y_mode == "normalized"


def test_the_graph_type_reaches_the_mcp_tools():
    from graphmatrix.core.scripting.graphs import GRAPH_TYPE_HELP

    assert "stack-line" in GRAPH_TYPE_HELP
    assert "band" in GRAPH_TYPE_HELP["stack-line"]
