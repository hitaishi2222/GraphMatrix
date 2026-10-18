"""Tests for the data-model additions: mask, formula, graph specs."""

from __future__ import annotations

import numpy as np
import pytest

from graphmatrix.core.model import (
    AxisScale,
    Column,
    ColumnType,
    FormulaError,
    Graph,
    Layer,
    PlotSpec,
    PlotStyle,
    Project,
    Workbook,
    Worksheet,
)


def test_column_mask_and_float_data():
    column = Column("Y1", ColumnType.Y, [1.0, 2.0, 3.0], mask=[False, True, False])
    values = column.float_data()
    assert np.isnan(values[1])
    assert values[0] == 1.0


def test_column_decimal_roundtrip():
    column = Column("Y1", ColumnType.Y, [1.23456], decimal=2)
    restored = Column.from_dict(column.to_dict())
    assert restored.decimal == 2


def test_formula_evaluation():
    sheet = Worksheet("S")
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0, 2.0])
    sheet.add_column("Y1", ColumnType.Y, np.zeros(3))
    sheet.apply_formula(sheet.column("Y1"), "2*X1 + 1")
    np.testing.assert_allclose(sheet.column("Y1").data, [1.0, 3.0, 5.0])


def test_formula_rejects_unknown_names():
    sheet = Worksheet("S")
    sheet.add_column("X1", ColumnType.X, [1.0])
    with pytest.raises(FormulaError):
        sheet.apply_formula(sheet.column("X1"), "os.system('rm -rf /')")


def test_plot_spec_and_layer_roundtrip():
    spec = PlotSpec(source="Book1/Sheet1", x="X1", y="Y1", style=PlotStyle.BAR, color="#ff0000", legend="data")
    layer = Layer("Layer 1", x_scale=AxisScale.LOG)
    layer.add_plot(spec)
    graph = Graph("Graph1", title="T")
    graph.layers = [layer]
    restored = Graph.from_dict(graph.to_dict())
    assert restored.title == "T"
    assert restored.layers[0].x_scale is AxisScale.LOG
    assert restored.layers[0].plots[0].style is PlotStyle.BAR
    assert restored.layers[0].plots[0].legend == "data"


def test_resolve_plot_returns_arrays():
    from graphmatrix.core.plotting import resolve_plot

    project = Project()
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    sheet.add_column("X1", ColumnType.X, [0.0, 1.0, 2.0])
    sheet.add_column("Y1", ColumnType.Y, [0.0, 1.0, 4.0], units="V")
    resolved = resolve_plot(project, PlotSpec("Book1/Sheet1", "X1", "Y1"))
    assert resolved is not None
    np.testing.assert_allclose(resolved.y, [0.0, 1.0, 4.0])
    assert resolved.y_label == "Y1 (V)"
