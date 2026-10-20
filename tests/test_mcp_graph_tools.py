"""Agent-facing graph toolkit and the live MCP tools built on top of it."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from graphmatrix.core.commands import CommandStack  # noqa: E402
from graphmatrix.core.model import Project  # noqa: E402
from graphmatrix.core.scripting import graphs as G  # noqa: E402


@pytest.fixture()
def project():
    proj = Project("Demo")
    G.add_data(
        proj,
        None,
        book="Data",
        sheet="S1",
        columns=[
            {
                "name": "X",
                "type": "X",
                "generate": {"kind": "linspace", "start": 0, "stop": 10, "count": 11},
            },
            {"name": "Y1", "type": "Y", "generate": {"kind": "sin", "count": 11}},
            {"name": "Y2", "type": "Y", "values": list(range(11))},
        ],
    )
    return proj


# -- data --------------------------------------------------------------------


def test_add_data_creates_columns_and_generates_series(project):
    result = G.add_data(
        project,
        None,
        book="Data",
        sheet="S2",
        columns=[
            {"name": "X", "type": "X", "generate": {"kind": "ramp", "count": 4}},
            {"name": "Y", "type": "Y", "generate": {"kind": "cos", "count": 4}},
        ],
    )
    assert result["source"] == "Data/S2"
    assert [c["name"] for c in result["columns"]] == ["X", "Y"]
    sheet = project.sheet("Data/S2")
    assert list(sheet.column("X").float_data()) == [0.0, 1.0, 2.0, 3.0]
    assert len(sheet.column("Y")) == 4


def test_add_data_rejects_empty_columns(project):
    with pytest.raises(G.GraphToolError):
        G.add_data(project, None, columns=[])


def test_unknown_generator_is_reported(project):
    with pytest.raises(G.GraphToolError):
        G.add_data(
            project,
            None,
            book="Data",
            sheet="S3",
            columns=[{"name": "X", "type": "X", "generate": {"kind": "quark"}}],
        )


# -- graph creation ----------------------------------------------------------


@pytest.mark.parametrize(
    "graph_type,kwargs,expected_layout,expected_panels",
    [
        ("simple", {}, [1, 1], 1),
        ("stack", {"panels": 3}, [3, 1], 3),
        ("stack-line", {"panels": 3}, [1, 1], 3),
        ("x-twin", {"panels": 2}, [1, 2], 2),
        ("grid", {"rows": 2, "cols": 3}, [2, 3], 6),
        ("double-y", {}, [1, 1], 1),
    ],
)
def test_create_graph_builds_the_right_layout(
    project, graph_type, kwargs, expected_layout, expected_panels
):
    result = G.create_graph(
        project,
        None,
        name="G",
        graph_type=graph_type,
        source="Data/S1",
        x="X",
        y="Y1",
        **kwargs,
    )
    assert result["graph_type"] == graph_type
    assert result["layout"] == expected_layout
    assert result["panels"] == expected_panels
    graph = project.graph(result["graph"])
    assert len(graph.layers) == expected_panels
    # The series is replicated into every panel by default.
    assert all(layer.plots for layer in graph.layers)
    assert all(spec.y == "Y1" for layer in graph.layers for spec in layer.plots)


def test_create_graph_without_data_makes_an_empty_figure(project):
    result = G.create_graph(project, None, name="Empty", graph_type="stack", panels=2)
    graph = project.graph(result["graph"])
    assert len(graph.layers) == 2
    assert all(not layer.plots for layer in graph.layers)


def test_create_graph_rejects_unknown_type_and_missing_columns(project):
    with pytest.raises(G.GraphToolError):
        G.create_graph(project, None, name="Bad", graph_type="spiral")
    with pytest.raises(G.GraphToolError):
        G.create_graph(project, None, name="Bad", source="Data/S1", x="X", y="Nope")
    with pytest.raises(G.GraphToolError):
        G.create_graph(project, None, name="Bad", source="Nope/S9", x="X", y="Y1")


def test_graph_changes_are_undoable(project):
    stack = CommandStack()
    G.create_graph(stack and project or project, stack, name="Undo", source="Data/S1", x="X", y="Y1")
    assert project.graph("Undo") is not None
    stack.undo()
    assert project.graph("Undo") is None
    stack.redo()
    assert project.graph("Undo") is not None


def test_add_plot_targets_a_panel_and_a_second_y_axis(project):
    G.create_graph(project, None, name="G", graph_type="grid", rows=1, cols=2,
                   source="Data/S1", x="X", y="Y1")
    result = G.add_plot(
        project, None, "G", source="Data/S1", x="X", y="Y2", panel=2, y_axis="right"
    )
    assert result["panel"] == 2
    graph = project.graph("G")
    # Panel 2 already holds the replicated series; the new one is added to it.
    assert len(graph.layers[1].plots) == 2
    assert graph.layers[1].plots[-1].y == "Y2"
    assert graph.layers[1].plots[-1].y_axis == "right"
    # A panel that does not exist yet is created.
    G.add_plot(project, None, "G", source="Data/S1", x="X", y="Y2", panel=3)
    assert len(project.graph("G").layers) == 3


def test_add_plot_reports_unknown_graph_and_column(project):
    G.create_graph(project, None, name="G")
    with pytest.raises(G.GraphToolError):
        G.add_plot(project, None, "Missing", source="Data/S1", x="X", y="Y1")
    with pytest.raises(G.GraphToolError):
        G.add_plot(project, None, "G", source="Data/S1", x="X", y="Missing")


def test_add_plot_can_replace_the_content_of_a_panel(project):
    G.create_graph(
        project,
        None,
        name="G",
        graph_type="grid",
        rows=1,
        cols=2,
        source="Data/S1",
        x="X",
        y="Y1",
    )
    G.add_plot(
        project, None, "G", source="Data/S1", x="X", y="Y2", panel=2, replace=True
    )
    layer = project.graph("G").layers[1]
    assert [spec.y for spec in layer.plots] == ["Y2"]


def test_set_graph_type_switches_template_and_panel_count(project):
    G.create_graph(project, None, name="G", source="Data/S1", x="X", y="Y1")
    result = G.set_graph_type(project, None, "G", "stack", panels=3)
    assert result["graph_type"] == "stack"
    assert result["layout"] == [3, 1]
    assert result["panels"] == 3
    # Switching back keeps the data.
    G.set_graph_type(project, None, "G", "simple")
    assert project.graph("G").layers[0].plots


def test_set_property_sets_graph_and_panel_properties(project):
    G.create_graph(project, None, name="G", source="Data/S1", x="X", y="Y1")
    G.set_property(project, None, "G", "title", "Damped oscillation")
    G.set_property(project, None, "G", "x_label", "time (s)")
    G.set_property(project, None, "G", "show_y_axis", "false")
    G.set_property(project, None, "G", "x_scale", "log")
    graph = project.graph("G")
    assert graph.title == "Damped oscillation"
    assert graph.first_layer.x_label == "time (s)"
    assert graph.first_layer.show_y_axis is False
    assert str(graph.first_layer.x_scale) == "log"


def test_set_property_rejects_unknown_key_and_panel(project):
    G.create_graph(project, None, name="G")
    with pytest.raises(G.GraphToolError):
        G.set_property(project, None, "G", "nonsense", "1")
    with pytest.raises(G.GraphToolError):
        G.set_property(project, None, "G", "x_label", "x", panel=7)


def test_delete_graph_removes_it(project):
    G.create_graph(project, None, name="G")
    G.delete_graph(project, None, "G")
    assert project.graph("G") is None


# -- description -------------------------------------------------------------


def test_describe_project_lists_data_and_graphs(project):
    G.create_graph(project, None, name="G", source="Data/S1", x="X", y="Y1")
    description = G.describe_project(project)
    sheet = description["workbooks"][0]["sheets"][0]
    assert sheet["label"] == "Data/S1"
    assert sheet["x_columns"] == ["X"]
    assert sheet["y_columns"] == ["Y1", "Y2"]
    assert sheet["plottable_pairs"] == [
        {"x": "X", "y": "Y1"},
        {"x": "X", "y": "Y2"},
    ]
    graph = description["graphs"][0]
    assert graph["name"] == "G"
    assert graph["panels"][0]["plots"][0]["y"] == "Y1"
    assert "stack" in description["capabilities"]["graph_types"]
    assert "line+symbol" in description["capabilities"]["plot_styles"]


# -- export ------------------------------------------------------------------


def test_export_graphs_writes_files(project, tmp_path):
    G.create_graph(project, None, name="G", source="Data/S1", x="X", y="Y1")
    out = tmp_path / "out"
    result = G.export_graphs(project, None, out_dir=str(out), format="png", dpi=50)
    assert len(result["files"]) == 1
    assert os.path.exists(result["files"][0])


def test_export_graphs_accepts_names_positions_and_ranges(project, tmp_path):
    G.create_graph(project, None, name="A", source="Data/S1", x="X", y="Y1")
    G.create_graph(project, None, name="B", source="Data/S1", x="X", y="Y2")
    out = tmp_path / "named"
    result = G.export_graphs(
        project, None, graphs="A", out_dir=str(out), format="png", dpi=50
    )
    assert len(result["files"]) == 1 and result["files"][0].endswith("A.png")
    result = G.export_graphs(
        project, None, graphs=["A"], out_dir=str(out), format="png", dpi=50
    )
    assert len(result["files"]) == 1


def test_export_graphs_accepts_positions_and_ranges(project, tmp_path):
    G.create_graph(project, None, name="A", source="Data/S1", x="X", y="Y1")
    G.create_graph(project, None, name="B", source="Data/S1", x="X", y="Y2")
    result = G.export_graphs(
        project, None, graphs=["1-2"], out_dir=str(tmp_path), format="png", dpi=50
    )
    assert len(result["files"]) == 2


# -- MCP server --------------------------------------------------------------


def test_mcp_server_exposes_the_live_graph_tools():
    from graphmatrix import mcp_server

    for name in (
        "live_describe",
        "live_create_graph",
        "live_add_plot",
        "live_set_graph_type",
        "live_add_data",
        "live_set_property",
        "live_delete_graph",
        "live_save",
        "live_export",
    ):
        assert callable(getattr(mcp_server, name)), name


def test_live_call_embeds_arguments_as_python_literals(monkeypatch):
    from graphmatrix import mcp_server

    seen: dict = {}

    def fake_request(op, **payload):
        seen.update(payload)
        return {
            "ok": True,
            "stdout": mcp_server._JSON_MARKER + '{"graph": "G"}',
        }

    monkeypatch.setattr("graphmatrix.core.ipc.request", fake_request)
    result = mcp_server._live_call(
        "create_graph",
        open_graphs=True,
        name="G",
        panels=None,
        replicate=True,
        title="it's fine",
    )
    assert result == {"graph": "G"}
    assert seen["open_graphs"] is True
    code = seen["code"]
    # Booleans and None must survive as Python, not as JSON.
    assert "'replicate': True" in code
    assert "'panels': None" in code
    assert "it's fine" in code


def test_live_call_raises_on_gui_error(monkeypatch):
    from graphmatrix import mcp_server

    monkeypatch.setattr(
        "graphmatrix.core.ipc.request",
        lambda op, **payload: {"ok": False, "error": "KeyError: nope"},
    )
    with pytest.raises(RuntimeError):
        mcp_server._live_call("create_graph", name="G")
