"""Graph-layout UI (types, tree actions, properties) and MCP control-panel tests."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# -- model + command ---------------------------------------------------------


def test_graph_type_syncs_layout_and_roundtrips():
    from graphmatrix.core.model import Graph, GraphType

    graph = Graph("G")
    assert graph.graph_type == GraphType.SIMPLE.value
    assert (graph.layout_rows, graph.layout_cols) == (1, 1)

    graph.add_layer()
    graph.graph_type = GraphType.STACK.value
    graph.sync_layout()
    assert (graph.layout_rows, graph.layout_cols) == (2, 1)

    graph.add_layer()
    graph.sync_layout()
    assert (graph.layout_rows, graph.layout_cols) == (3, 1)

    graph.graph_type = GraphType.X_TWIN.value
    graph.sync_layout()
    assert (graph.layout_rows, graph.layout_cols) == (1, 3)

    graph.graph_type = GraphType.GRID.value
    graph.layout_rows, graph.layout_cols = 2, 2
    graph.sync_layout()
    assert (graph.layout_rows, graph.layout_cols) == (2, 2)

    graph.graph_type = GraphType.DOUBLE_Y.value
    graph.sync_layout()
    assert (graph.layout_rows, graph.layout_cols) == (1, 1)
    assert graph.num_layers == 3  # switching type never drops layers

    graph.first_layer.show_y_axis = False
    restored = Graph.from_dict(graph.to_dict())
    assert restored.graph_type == GraphType.DOUBLE_Y.value
    assert restored.panel_gap_x == graph.panel_gap_x
    assert restored.y_delta == graph.y_delta
    assert restored.first_layer.show_y_axis is False


def test_set_graph_type_command_is_undoable():
    from graphmatrix.core.commands import CommandStack, SetGraphTypeCommand
    from graphmatrix.core.model import Graph, GraphType

    graph = Graph("G")
    graph.add_layer()
    stack = CommandStack()
    stack.push(SetGraphTypeCommand(graph, GraphType.STACK.value))
    assert graph.graph_type == GraphType.STACK.value
    assert (graph.layout_rows, graph.layout_cols) == (2, 1)

    stack.undo()
    assert graph.graph_type == GraphType.SIMPLE.value
    assert (graph.layout_rows, graph.layout_cols) == (1, 1)

    stack.redo()
    assert graph.graph_type == GraphType.STACK.value
    assert (graph.layout_rows, graph.layout_cols) == (2, 1)


def test_mcp_summary_reports_graph_type():
    from graphmatrix.core.model import Graph, Project
    from graphmatrix.mcp_server import _summary

    project = Project("T")
    graph = Graph("G")
    graph.graph_type = "stack"
    graph.add_layer()
    graph.sync_layout()
    project.add_graph(graph)

    item = _summary(project)["graphs"][0]
    assert item["graph_type"] == "stack"
    assert item["layout"] == [2, 1]


# -- Project Explorer --------------------------------------------------------


def test_project_tree_shows_type_and_offers_add_delete(qapp):
    from graphmatrix.core.model import Graph, Project
    from graphmatrix.ui.project_panel import ProjectPanel

    project = Project("T")
    graph = project.add_graph(Graph("Graph1"))
    panel = ProjectPanel()
    panel.set_project(project)
    try:
        item = panel.tree.topLevelItem(0).child(0)
        assert "Graph1" in item.text(0)
        assert "Simple" in item.text(0)

        graph.graph_type = "grid"
        panel.refresh()
        item = panel.tree.topLevelItem(0).child(0)
        assert "Grid" in item.text(0)

        added: list[tuple[str, str]] = []
        deleted: list[object] = []
        retyped: list[tuple[object, str]] = []
        panel.add_requested.connect(lambda kind, detail: added.append((kind, detail)))
        panel.delete_requested.connect(deleted.append)
        panel.graph_type_requested.connect(
            lambda target, value: retyped.append((target, value))
        )

        menu = panel.build_context_menu(graph)
        graph_menu = panel.context_graph_menu
        stack_action = next(
            action
            for action in graph_menu.actions()
            if action.text() == "Stack (vertical panels)"
        )
        stack_action.trigger()
        assert added[-1] == ("graph", "stack")

        delete_action = next(
            action for action in menu.actions() if action.text() == "Delete Graph"
        )
        delete_action.trigger()
        assert deleted[-1] is graph

        # Existing graphs can be retyped from the tree as well.
        type_menu = panel.context_type_menu
        assert type_menu is not None
        stack_type = next(
            action for action in type_menu.actions() if action.text().startswith("Stack")
        )
        stack_type.trigger()
        assert retyped[-1] == (graph, "stack")
    finally:
        panel.deleteLater()


# -- main window -------------------------------------------------------------


def test_main_window_graph_type_menu_toolbar_and_properties(qapp):
    from graphmatrix.ui.main_window import MainWindow
    from graphmatrix.ui.properties_panel import PropertiesPanel

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        window._action_add_graph("stack")
        view = window._active_graph_view
        assert view is not None
        graph = view.graph

        # The template starts with two panels, and every control agrees.
        assert graph.graph_type == "stack"
        assert graph.num_layers == 2
        assert (graph.layout_rows, graph.layout_cols) == (2, 1)
        assert window.graph_type_combo.currentData() == "stack"
        assert window.graph_type_combo.isEnabled()
        assert window._graph_type_actions["stack"].isChecked()

        # Menu action switches the active graph and is undoable.
        window._graph_type_actions["grid"].trigger()
        assert graph.graph_type == "grid"
        assert window.graph_type_combo.currentData() == "grid"
        window.commands.undo()
        assert graph.graph_type == "stack"
        assert window._graph_type_actions["stack"].isChecked()

        # Type-specific properties appear in the inspector.
        window._apply_property(graph, "Graph type", "Grid (multi-panel)")
        assert graph.graph_type == "grid"
        rows = dict(PropertiesPanel._describe(graph))
        assert {"Graph type", "Grid rows", "Grid cols"} <= set(rows)
        assert {"Panel gap X (%)", "Panel gap Y (%)"} <= set(rows)
        assert "Y delta" not in rows

        before_cols = graph.layout_cols
        window._apply_property(graph, "Grid cols", str(before_cols + 2))
        assert graph.layout_cols == before_cols + 2
        window.commands.undo()
        assert graph.layout_cols == before_cols

        # Stack shows Y delta instead of grid/gap rows.
        window._apply_property(graph, "Graph type", "Stack")
        assert graph.graph_type == "stack"
        rows = dict(PropertiesPanel._describe(graph))
        assert "Y delta" in rows
        assert "Grid rows" not in rows

        # The tree's Add submenu funnels into the same creation path.
        before = len(window.project.graphs)
        window._on_tree_add_requested("graph", "x-twin")
        assert len(window.project.graphs) == before + 1
        new_graph = window.project.graphs[-1]
        assert new_graph.graph_type == "x-twin"
        assert new_graph.num_layers == 2

        # Right-click delete closes the tab and is undoable.
        window._action_delete_object(new_graph)
        assert new_graph not in window.project.graphs
        window.commands.undo()
        assert new_graph in window.project.graphs
    finally:
        window.close()


# -- MCP control -------------------------------------------------------------


def test_y_axis_visibility_toggle(qapp):
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        window._action_sample_data()
        window._action_add_graph()
        view = window._active_graph_view
        layer = view.graph.first_layer
        assert layer.show_y_axis is True

        view.group_axis.setCurrentIndex(2)  # Ticks tab
        view.yaxis_visible_check.setCurrentIndex(1)  # Hide
        assert layer.show_y_axis is False
        window.commands.undo()
        assert layer.show_y_axis is True
    finally:
        window.close()


def test_mcp_server_cli_options():
    from graphmatrix.mcp_server import build_parser

    default = build_parser().parse_args([])
    assert default.transport == "stdio"
    assert default.port == 8765

    parsed = build_parser().parse_args(
        ["--transport", "http", "--host", "0.0.0.0", "--port", "9000", "--no-banner"]
    )
    assert parsed.transport == "http"
    assert parsed.host == "0.0.0.0"
    assert parsed.port == 9000
    assert parsed.no_banner is True


def test_the_window_has_no_mcp_server_ui(qapp):
    """The MCP server is launched by the client, so the app ships no MCP UI."""
    from graphmatrix.ui.main_window import MainWindow

    window = MainWindow()
    window.confirm_on_close = False
    try:
        assert not hasattr(window, "dock_mcp")
        assert not hasattr(window, "mcp_panel")
        assert not hasattr(window, "mcp_indicator")
        with pytest.raises(KeyError):
            window.registry.action("tools.mcp")
    finally:
        window.close()


def test_mcp_server_cli_options():
    from graphmatrix.mcp_server import build_parser

    default = build_parser().parse_args([])
    assert default.transport == "stdio"
    assert default.port == 8765

    parsed = build_parser().parse_args(
        ["--transport", "http", "--host", "0.0.0.0", "--port", "9000", "--no-banner"]
    )
    assert parsed.transport == "http"
    assert parsed.host == "0.0.0.0"
    assert parsed.port == 9000
    assert parsed.no_banner is True
