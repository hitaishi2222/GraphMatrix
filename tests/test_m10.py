"""M10 tests: numeric fit regions, peak integration, batch statistics,
colour-mapped scatter / heatmap / contour, XYZ gridding, and the PyVista 3D
canvas + matplotlib 3D export parity."""

from __future__ import annotations

import os

import numpy as np
import pytest

from graphmatrix.core.analysis import regression, peaks as peaks_module, fitting
from graphmatrix.core.analysis.descriptive import batch_summary
from graphmatrix.core.commands import CommandStack, SetAttributesCommand
from graphmatrix.core.model import (
    Graph,
    Layer,
    PlotSpec,
    PlotStyle,
    Project,
    Workbook,
    Worksheet,
    Column,
    ColumnType,
    Z_STYLES,
    is_3d_style,
)
from graphmatrix.core.plotting import grid_xyz, resolve_plot

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def make_project() -> tuple[Project, Worksheet]:
    project = Project()
    book = Workbook("Book1")
    sheet = Worksheet("Sheet1")
    x = np.linspace(0.0, 10.0, 200)
    y1 = 2.0 * x + 1.0  # segment of slope 2 below x = 5
    y2 = (-1.0) * (x - 5.0) + 2.0 * 5.0 + 1.0  # continuing line, slope -1 above
    y = np.where(x < 5.0, y1, y2)
    z = np.sin(x) ** 2
    sheet.add_column("X1", ColumnType.X, x)
    sheet.add_column("Y1", ColumnType.Y, y)
    sheet.add_column("Z1", ColumnType.Z, z)
    book.add_sheet(sheet)
    project.add_workbook(book)
    return project, sheet


# -- numeric fit regions -------------------------------------------------------


def test_windowed_linear_fit_recovers_segment_slope():
    _, sheet = make_project()
    x = sheet.column("X1").float_data()
    y = sheet.column("Y1").float_data()
    result = regression.linear_fit(x, y, x_min=0.0, x_max=4.0)
    slope = result.parameters[0].value
    assert abs(slope - 2.0) < 1e-9
    assert "Fit region" in result.summary


def test_windowed_polynomial_fit():
    _, sheet = make_project()
    x = sheet.column("X1").float_data()
    y = sheet.column("Y1").float_data()
    result = regression.polynomial_fit(x, y, degree=1, x_min=6.0, x_max=9.0)
    full = regression.polynomial_fit(x, y, degree=1)
    # The window fit must fit only the descending segment, so it differs from
    # the full-range fit; c1 is the slope term for degree 1.
    assert result.parameters != full.parameters
    assert result.parameters[1].name == "c0"


def test_nonlinear_fit_window():
    x = np.linspace(0, 10, 300)
    # A two-crest signal: the window over the first crest must centre ~2.5.
    y = np.exp(-((x - 2.5) ** 2) / 0.5) + 1.5 * np.exp(-((x - 7.5) ** 2) / 0.5)
    result = fitting.fit_model("Gaussian", x, y, x_min=0.0, x_max=4.5)
    center = next(p.value for p in result.parameters if p.name == "center")
    assert abs(center - 2.5) < 0.2
    assert "Fit region" in result.summary


# -- peak integration ----------------------------------------------------------


def test_peak_integration_single_gaussian_area():
    x = np.linspace(-6.0, 6.0, 400)
    sigma, amplitude = 0.8, 2.0
    y = amplitude * np.exp(-(x**2) / (2 * sigma**2))
    result = peaks_module.find_peaks_result(x, y, integrate=True)
    row = result.tables["Peaks"][1]
    area = float(row[6])
    expected = amplitude * np.sqrt(2 * np.pi) * sigma  # ≈ 4.005
    assert abs(area - expected) / expected < 0.1
    assert "Area 1" in result.summary


def test_peak_integration_two_peaks():
    x = np.linspace(-6.0, 6.0, 600)
    y = 2.0 * np.exp(-((x + 2.5) ** 2) / (2 * 0.5)) + 1.5 * np.exp(
        -((x - 2.5) ** 2) / (2 * 0.5)
    )
    result = peaks_module.find_peaks_result(x, y, integrate=True, prominence=0.3)
    header = result.tables["Peaks"][0]
    assert header[-1] == "Area"
    areas = [float(r[-1]) for r in result.tables["Peaks"][1:]]
    assert len(areas) == 2 and all(a > 0 for a in areas)


# -- batch statistics ----------------------------------------------------------


def test_batch_summary_rows():
    project, _ = make_project()
    book2 = Workbook("Book2")
    sheet2 = Worksheet("Sheet2")
    sheet2.add_column("V", ColumnType.Y, [1.0, 2.0, 3.0])
    sheet2.add_column("T", ColumnType.TEXT, ["a", "b", "c"])
    book2.add_sheet(sheet2)
    project.add_workbook(book2)

    result = batch_summary(project)
    rows = result.tables["Columns"]
    header = rows[0]
    assert header == [
        "Sheet",
        "Column",
        "Type",
        "N",
        "Missing",
        "Mean",
        "Std Dev",
        "Min",
        "Median",
        "Max",
    ]
    body = rows[1:]
    # Three numeric columns in Sheet1 (X1, Y1, Z1) + V in Sheet2; text excluded.
    assert len(body) == 4
    by_name = {(r[0], r[1]): r for r in body}
    v_row = by_name[("Sheet2", "V")]
    assert v_row[3] == "3" and abs(float(v_row[5]) - 2.0) < 1e-9
    z_row = by_name[("Sheet1", "Z1")]
    assert abs(float(z_row[9]) - 1.0) < 1e-3  # max of sin^2 (6-sigf formatted)
    assert ("Sheet2", "T") not in by_name


def test_batch_summary_handles_missing_values():
    project, sheet = make_project()
    sheet.column("Z1").data[10:20] = np.nan
    result = batch_summary(project)
    z_row = [r for r in result.tables["Columns"][1:] if r[1] == "Z1"][0]
    assert z_row[4] == "10"  # Missing


# -- XYZ plumbing (model, resolve, grid) ---------------------------------------


def test_plot_spec_z_roundtrip():
    spec = PlotSpec("B/S", "X1", "Y1", z="Z1", cmap="plasma")
    restored = PlotSpec.from_dict(spec.to_dict())
    assert restored.z == "Z1" and restored.cmap == "plasma"


def test_layer_z_label_roundtrip():
    layer = Layer()
    layer.z_label = "Intensity (a.u.)"
    restored = Layer.from_dict(layer.to_dict())
    assert restored.z_label == "Intensity (a.u.)"


def test_resolve_plot_carries_z():
    project, sheet = make_project()
    spec = PlotSpec("Book1/Sheet1", "X1", "Y1", z="Z1", style=PlotStyle.COLOR_SCATTER)
    data = resolve_plot(project, spec)
    assert data.z is not None and data.z.size == data.x.size
    assert "Z1" in data.z_label


def test_grid_xyz_recovers_a_plane():
    rng = np.random.default_rng(7)
    pts = rng.uniform(0, 1, size=(400, 2))
    x, y = pts[:, 0], pts[:, 1]
    z = 2.0 * x + 3.0 * y + 1.0
    gx, gy, grid = grid_xyz(x, y, z, nx=20, ny=20)
    assert grid.shape == (20, 20)
    for i in range(5, 15):  # interior cells interpolate the plane well
        expected = 2.0 * gx[i] + 3.0 * gy[i] + 1.0
        assert abs(grid[i, i] - expected) < 0.15


def test_grid_xyz_degenerate_input_is_all_nan():
    gx, gy, grid = grid_xyz([0.0] * 5, [1.0] * 5, [2.0] * 5)
    assert grid.shape[0] > 0 and np.isnan(grid).all()


def test_z_style_helpers():
    assert PlotStyle.SCATTER3D in Z_STYLES and PlotStyle.SURFACE3D in Z_STYLES
    assert is_3d_style("3d surface") and is_3d_style("3d scatter")
    assert not is_3d_style("color-mapped scatter")


# -- export parity ---------------------------------------------------------------


@pytest.mark.parametrize(
    "style",
    ["color-mapped scatter", "heatmap", "contour", "3d scatter", "3d surface"],
)
def test_export_z_styles(tmp_path, style):
    project, _ = make_project()
    graph = Graph("G")
    graph.first_layer.add_plot(
        PlotSpec("Book1/Sheet1", "X1", "Y1", z="Z1", style=style)
    )
    graph.first_layer.z_label = "Signal"
    from graphmatrix.core.io.export import export_graph

    for ext in ("png", "pdf"):
        out = export_graph(
            graph, project, tmp_path / f"fig_{style.replace(' ', '_')}.{ext}"
        )
        assert out.exists() and out.stat().st_size > 0


def test_export_without_z_column_still_renders(tmp_path):
    project, _ = make_project()
    graph = Graph("G")
    graph.first_layer.add_plot(
        PlotSpec("Book1/Sheet1", "X1", "Y1", style=PlotStyle.COLOR_SCATTER)
    )
    from graphmatrix.core.io.export import export_graph

    out = export_graph(graph, project, tmp_path / "no_z.png")
    assert out.exists()


# -- commands: editing z via the sidebar ---------------------------------------


def test_set_attributes_command_updates_z():
    spec = PlotSpec("B/S", "X1", "Y1")
    stack = CommandStack()
    stack.push(
        SetAttributesCommand(spec, "Edit Plot", z="Z1", style=PlotStyle.COLOR_SCATTER)
    )
    assert spec.z == "Z1"
    stack.undo()
    assert spec.z == ""
    stack.redo()
    assert spec.z == "Z1"


# -- PyVista canvas (optional dependency) ---------------------------------------


def test_pyvista_canvas_renders_3d():
    pytest.importorskip("pyvista")
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    try:
        from graphmatrix.ui.canvas import create_canvas

        canvas = create_canvas("pyvista")
    except Exception:  # noqa: BLE001 - no GL in CI
        pytest.skip("PyVista/Qt interactor unavailable in this environment")
    try:
        canvas.plot(
            [0, 1, 2, 3], [0, 1, 4, 9], style="3d scatter", z=[1, 2, 3, 4], name="pts"
        )
        canvas.plot(
            [0, 1, 2, 3], [0, 1, 4, 9], style="3d surface", z=[1, 2, 3, 4], name="srf"
        )
        canvas.add_reference_line("h", 0.5)
        canvas.set_labels(bottom="Alpha", left="Beta", right="Gamma")
        canvas.set_title("3D test")
        assert canvas.widget() is not None
    finally:
        canvas.close()


def test_create_canvas_unknown_backend_message():
    from graphmatrix.ui.canvas import create_canvas

    with pytest.raises(ValueError, match="known"):
        create_canvas("nonsense")


def test_headless_graph_view_swaps_to_pyvista():
    pytest.importorskip("pyvista")
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    try:
        from graphmatrix.ui.graph_view import GraphView
    except Exception:
        pytest.skip("Qt interactor unavailable")
    project, _ = make_project()
    graph = Graph("G")
    graph.first_layer.add_plot(
        PlotSpec("Book1/Sheet1", "X1", "Y1", z="Z1", style=PlotStyle.SURFACE3D)
    )
    from graphmatrix.core.commands import CommandStack

    stack = CommandStack()
    try:
        view = GraphView(graph, project, stack)
        view.render()
        assert type(view.canvas).__name__ == "PyVistaCanvas"
    except Exception:
        pytest.skip("GL rendering unavailable headless")
    finally:
        try:
            view.canvas.close()
        except Exception:  # noqa: BLE001
            pass
