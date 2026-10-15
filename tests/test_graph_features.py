"""Graph feature tests: dashed lines, reference lines, hover, slope, baselines."""

from __future__ import annotations

import numpy as np
import pytest

from respot.core.analysis import ranged, signal
from respot.core.commands import (
    AddReferenceLineCommand,
    CommandStack,
    RemoveReferenceLineCommand,
)
from respot.core.model import (
    LINE_STYLES,
    ColumnType,
    Graph,
    Layer,
    PlotSpec,
    Project,
    ReferenceLine,
    Workbook,
    Worksheet,
)


# -- model / serialization ---------------------------------------------------


def test_plot_spec_line_style_roundtrip():
    spec = PlotSpec("B/S", "X1", "Y1", line_style="dashdot")
    payload = spec.to_dict()
    assert payload["line_style"] == "dashdot"
    assert PlotSpec.from_dict(payload).line_style == "dashdot"


def test_line_styles_cover_the_presets():
    assert set(LINE_STYLES) == {"solid", "dash", "dot", "dashdot", "longdash"}


def test_layer_reference_lines_roundtrip():
    graph = Graph("G")
    layer = graph.first_layer
    layer.add_ref_line(ReferenceLine("v", 3.0, color="#ff0000", label="edge"))
    layer.add_ref_line(ReferenceLine("h", -1.5, line_style="dot"))

    restored = Graph.from_dict(graph.to_dict())
    lines = restored.first_layer.ref_lines
    assert len(lines) == 2
    assert (lines[0].orientation, lines[0].position, lines[0].label) == ("v", 3.0, "edge")
    assert lines[1].line_style == "dot"


def test_reference_line_command_undo_redo():
    layer = Layer()
    stack = CommandStack()
    line = ReferenceLine("h", 1.5)

    stack.push(AddReferenceLineCommand(layer, line))
    assert layer.ref_lines == [line]
    stack.undo()
    assert layer.ref_lines == []
    stack.redo()
    assert layer.ref_lines == [line]

    stack.push(RemoveReferenceLineCommand(layer, line))
    assert layer.ref_lines == []
    stack.undo()
    assert layer.ref_lines == [line]


def test_template_captures_line_style():
    from respot.core.templates import apply_template, graph_to_template

    source = Graph("G")
    source.first_layer.plots.append(PlotSpec("B/S", "X1", "Y1", line_style="dot"))
    template = graph_to_template(source)
    assert template["layers"][0]["plots"][0]["line_style"] == "dot"

    target = Graph("G2")
    target.first_layer.plots.append(PlotSpec("B/S", "X2", "Y2"))
    apply_template(target, template)
    assert target.first_layer.plots[0].line_style == "dot"


# -- slope over a range ------------------------------------------------------


def test_slope_between_recovers_slope():
    x = np.linspace(0.0, 10.0, 201)
    y = 2.5 * x - 1.0
    result = ranged.slope_between(x, y, 2.0, 8.0)
    assert result.kind == "slope"
    assert result.summary["Slope"] == pytest.approx(2.5, abs=1e-9)
    assert result.summary["Intercept"] == pytest.approx(-1.0, abs=1e-9)
    assert result.summary["R²"] == pytest.approx(1.0, abs=1e-9)
    assert result.summary["X min"] == pytest.approx(2.0, abs=0.11)
    assert result.summary["X max"] == pytest.approx(8.0, abs=0.11)
    assert "Fit" in result.curves


def test_slope_between_handles_reversed_bounds():
    x = np.linspace(0.0, 10.0, 101)
    y = 3.0 * x
    forward = ranged.slope_between(x, y, 2.0, 6.0)
    reversed_bounds = ranged.slope_between(x, y, 6.0, 2.0)
    assert forward.summary["Slope"] == pytest.approx(reversed_bounds.summary["Slope"])


def test_slope_between_empty_range_is_graceful():
    x = np.linspace(0.0, 1.0, 10)
    result = ranged.slope_between(x, x, 5.0, 6.0)
    assert not result.summary
    assert result.notes


# -- baseline corrections ----------------------------------------------------


@pytest.mark.parametrize("method", signal.BASELINE_METHODS)
def test_baseline_correction_reduces_spread(method):
    x = np.linspace(0.0, 10.0, 400)
    y = 0.5 * x + 4.0 * np.exp(-((x - 5.0) ** 2) / 0.5)
    result = signal.baseline_correction(x, y, method=method)
    assert "Baseline" in result.curves and "Corrected" in result.curves
    assert result.summary["Corrected std"] < result.summary["Raw std"]


def test_run_operation_dispatches_baseline_names():
    x = np.linspace(0.0, 10.0, 200)
    y = 0.2 * x + np.exp(-((x - 5.0) ** 2))
    assert signal.run_operation("Baseline (linear)", x, y).title == "Linear Baseline"
    assert signal.run_operation("Baseline (ALS)", x, y).kind == "baseline"
    assert signal.run_operation("Baseline (median)", x, y).kind == "baseline"
    assert "Baseline (rubber band)" in signal.operations()


def test_recipe_can_run_a_slope_operation():
    from respot.core.recipes import Recipe, run_recipe

    x = np.linspace(0.0, 10.0, 101)
    y = 4.0 * x + 2.0
    result = run_recipe(Recipe("slope", {"x0": 1.0, "x1": 9.0}), x, y)
    assert result.summary["Slope"] == pytest.approx(4.0, abs=1e-9)


# -- export ------------------------------------------------------------------


def _simple_project() -> tuple[Project, Graph]:
    project = Project("P")
    book = project.add_workbook(Workbook("B"))
    sheet = book.add_sheet(Worksheet("S"))
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0, 2.0, 3.0])
    sheet.add_column("Y1", ColumnType.Y, [0.0, 1.0, 4.0, 9.0])
    graph = Graph("G")
    layer = graph.first_layer
    layer.plots.append(PlotSpec("B/S", "X1", "Y1", line_style="dash"))
    layer.add_ref_line(ReferenceLine("h", 2.0, label="threshold"))
    layer.add_ref_line(ReferenceLine("v", 1.5))
    project.add_graph(graph)
    return project, graph


def test_export_dashed_and_reference_lines(tmp_path):
    from respot.core.io.export import export_graph

    project, graph = _simple_project()
    out = export_graph(graph, project, tmp_path / "fig.pdf")
    assert out.exists() and out.stat().st_size > 0
