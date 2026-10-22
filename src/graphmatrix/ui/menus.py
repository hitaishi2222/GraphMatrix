"""Menu, toolbar and shortcut wiring for the main window.

Every command the window offers is registered here, once: an :class:`ActionSpec`
(given a menu, a shortcut and a tooltip) paired with the bound method that runs
it. Keeping the whole catalogue in one module means a new command has one place
to be added, and the main window stays about window behaviour. The functions
receive the window and attach the extra state they build (menus, action groups)
to it, exactly as they did when this code lived in the window class.
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenu

from graphmatrix.core.journals import journal_names
from graphmatrix.core.model import GRAPH_TYPE_LABELS, GRAPH_TYPES, graph_type_label
from graphmatrix.ui.actions import ActionSpec
from graphmatrix.ui.theme import current_preset, presets


def _slug(text: str) -> str:
    """A stable action-id fragment for free-form labels (journal preset names)."""
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")


def register_actions(window) -> None:
    """Register every action of ``window`` and build its menus."""
    r = window.registry
    r = window.registry
    file_actions = [
        (
            "file.new",
            "New Project",
            QKeySequence.StandardKey.New,
            window._action_new,
            False,
        ),
        (
            "file.open",
            "Open Project...",
            QKeySequence.StandardKey.Open,
            window._action_open,
            False,
        ),
        (
            "file.save",
            "Save Project",
            QKeySequence.StandardKey.Save,
            window._action_save,
            False,
        ),
        (
            "file.save_as",
            "Save Project As...",
            "Ctrl+Shift+S",
            window._action_save_as,
            False,
        ),
        ("file.import", "Import Data...", "Ctrl+I", window._action_import, True),
        ("file.close", "Close Tab", "Ctrl+W", window._action_close_tab, False),
        ("file.exit", "Exit", "Ctrl+Q", window.close, True),
    ]
    # "Open Recent" belongs directly under "Open Project…", so the first two
    # entries are registered around it and the rest follow.
    for action_id, text, shortcut, slot, sep in file_actions[:2]:
        r.register(
            ActionSpec(action_id, text, shortcut, menu="File", separator_before=sep),
            slot,
        )
    window._recent_menu = QMenu("Open Recent", window)
    recent_action = r.register(
        ActionSpec("file.recent", "Open Recent", menu="File"), None
    )
    recent_action.setMenu(window._recent_menu)
    for action_id, text, shortcut, slot, sep in file_actions[2:]:
        r.register(
            ActionSpec(action_id, text, shortcut, menu="File", separator_before=sep),
            slot,
        )

    r.register(
        ActionSpec("edit.undo", "Undo", QKeySequence.StandardKey.Undo, menu="Edit"),
        window._action_undo,
        enabled=False,
    )
    r.register(
        ActionSpec("edit.redo", "Redo", "Ctrl+Shift+Z", menu="Edit"),
        window._action_redo,
        enabled=False,
    )
    r.register(
        ActionSpec("edit.rename", "Rename…", "F2", menu="Edit", separator_before=True),
        window._action_rename,
    )

    # Theme presets: one checkable action each, grouped into a View submenu
    # that the toolbar also exposes as a dropdown.
    window._theme_menu = QMenu("Theme", window)
    window._theme_group = QActionGroup(window)
    window._theme_group.setExclusive(True)
    window._theme_actions: dict[str, QAction] = {}
    for theme_preset in presets():
        action = r.register(
            ActionSpec(
                f"view.theme.{theme_preset.id}",
                theme_preset.label,
                None,
                checkable=True,
                tooltip=theme_preset.description,
            ),
            lambda _checked=False, pid=theme_preset.id: window._action_set_theme(pid),
        )
        action.setActionGroup(window._theme_group)
        action.setChecked(theme_preset.id == current_preset())
        window._theme_actions[theme_preset.id] = action
        window._theme_menu.addAction(action)
    theme_menu_action = r.register(ActionSpec("view.theme", "Theme", menu="View"), None)
    theme_menu_action.setMenu(window._theme_menu)

    # Tab navigation: the window holds sheets, graphs and the welcome page, so
    # cycling them from the keyboard beats hunting for the tab bar.
    for action_id, text, shortcut, step in (
        ("view.next_tab", "Next Tab", "Ctrl+Tab", 1),
        ("view.prev_tab", "Previous Tab", "Ctrl+Shift+Tab", -1),
    ):
        r.register(
            ActionSpec(action_id, text, shortcut, menu="View", separator_before=True),
            lambda _checked=False, delta=step: window._action_next_tab(delta),
        )

    for action_id, text, slot, sep in (
        ("data.add_workbook", "Add Workbook", window._action_add_workbook, False),
        ("data.add_worksheet", "Add Worksheet", window._action_add_worksheet, False),
        ("data.add_graph", "Add Graph", window._action_add_graph, False),
        ("data.sample", "Add Sample Data", window._action_sample_data, True),
    ):
        r.register(
            ActionSpec(action_id, text, None, menu="Data", separator_before=sep),
            slot,
        )

    # Worksheet row/column edits, with spreadsheet-style keyboard shortcuts.
    # The menu keeps them discoverable; the shortcuts work from any sheet.
    window._rows_cols_menu = QMenu("Rows and Columns", window)
    for action_id, text, shortcut, slot, tooltip in (
        (
            "data.add_row",
            "Add Row at End",
            "Ctrl+Alt+N",
            window._action_add_row,
            "Append a row to the active worksheet",
        ),
        (
            "data.add_column",
            "Add Column at End",
            "Ctrl+Alt+C",
            window._action_add_column,
            "Append a Y column to the active worksheet",
        ),
        (
            "data.insert_row",
            "Insert Row Above Selection",
            "Ctrl+Alt+=",
            window._action_insert_row_above,
            "Insert as many rows as are selected, above them",
        ),
        (
            "data.insert_row_below",
            "Insert Row Below Selection",
            None,
            window._action_insert_row_below,
            "Insert as many rows as are selected, below them",
        ),
        (
            "data.delete_rows",
            "Delete Selected Rows",
            "Ctrl+Alt+-",
            window._action_delete_rows,
            "Delete the selected worksheet rows (undoable)",
        ),
        (
            "data.delete_columns",
            "Delete Selected Columns",
            "Ctrl+Alt+Shift+-",
            window._action_delete_columns,
            "Delete the selected worksheet columns (undoable)",
        ),
    ):
        action = r.register(
            ActionSpec(action_id, text, shortcut, tooltip=tooltip), slot
        )
        window._rows_cols_menu.addAction(action)
    rows_cols_action = r.register(
        ActionSpec(
            "data.rows_cols",
            "Rows and Columns",
            None,
            menu="Data",
            separator_before=True,
        ),
        None,
    )
    rows_cols_action.setMenu(window._rows_cols_menu)

    # Graph layout templates (simple/stack/2Y/x-twin/grid): checkable
    # actions so the current type is visible from the menu bar.
    window._graph_type_menu = QMenu("Graph Type", window)
    window._graph_type_group = QActionGroup(window)
    window._graph_type_group.setExclusive(True)
    window._graph_type_actions: dict[str, QAction] = {}
    for gtype in GRAPH_TYPES:
        action = r.register(
            ActionSpec(
                f"graph.type.{_slug(gtype.value)}",
                GRAPH_TYPE_LABELS[gtype.value],
                None,
                checkable=True,
                tooltip=f"Lay the graph out as {graph_type_label(gtype)}",
            ),
            lambda _checked=False, value=gtype.value: window._action_set_graph_type(
                value
            ),
        )
        action.setActionGroup(window._graph_type_group)
        window._graph_type_actions[gtype.value] = action
        window._graph_type_menu.addAction(action)
    graph_type_menu_action = r.register(
        ActionSpec("graph.type", "Graph Type", None, menu="Graph"), None
    )
    graph_type_menu_action.setMenu(window._graph_type_menu)

    # Journal presets: checkable actions mirroring the theme submenu.
    window._journal_menu = QMenu("Journal Preset", window)
    window._journal_group = QActionGroup(window)
    window._journal_group.setExclusive(True)
    window._journal_actions: dict[str, QAction] = {}
    for preset_name in journal_names():
        action = r.register(
            ActionSpec(
                f"graph.journal.{_slug(preset_name)}",
                preset_name,
                None,
                checkable=True,
                tooltip=f"Restyle plots and export typography for {preset_name}",
            ),
            lambda _checked=False, name=preset_name: window._action_apply_journal(name),
        )
        action.setActionGroup(window._journal_group)
        window._journal_actions[preset_name] = action
        window._journal_menu.addAction(action)
    journal_menu_action = r.register(
        ActionSpec("graph.journal", "Journal Preset", None, menu="Graph"), None
    )
    journal_menu_action.setMenu(window._journal_menu)

    for action_id, text, slot, sep in (
        (
            "graph.add_plot",
            "Add Plot to Active Graph",
            window._action_add_plot,
            False,
        ),
        ("graph.add_layer", "Add Layer", window._action_add_layer, False),
        (
            "graph.new_from_data",
            "New Graph From Data",
            window._action_add_graph,
            False,
        ),
        (
            "graph.add_ref_line",
            "Add Reference Line…",
            window._action_add_reference_line,
            True,
        ),
        ("graph.hover", "Data Readout (Hover)", window._action_toggle_hover, False),
        (
            "graph.add_annotation",
            "Add Annotation...",
            window._action_add_annotation,
            True,
        ),
        (
            "graph.save_template",
            "Save Style Template...",
            window._action_save_template,
            True,
        ),
        (
            "graph.apply_template",
            "Apply Style Template...",
            window._action_apply_template,
            False,
        ),
        ("graph.export", "Export Active Graph...", window._action_export_graph, True),
    ):
        r.register(
            ActionSpec(action_id, text, None, menu="Graph", separator_before=sep),
            slot,
        )
    window.registry.action("graph.hover").setCheckable(True)

    # Canvas zoom. The same three actions work from the canvas tool
    # strip and from the keyboard; they act on the panel that is being
    # edited.
    for action_id, text, shortcut, slot in (
        ("graph.zoom_in", "Zoom In", "Ctrl+=", window._action_zoom_in),
        ("graph.zoom_out", "Zoom Out", "Ctrl+-", window._action_zoom_out),
        ("graph.zoom_fit", "Fit Data to Panel", "Ctrl+0", window._action_zoom_fit),
    ):
        r.register(
            ActionSpec(
                action_id,
                text,
                shortcut,
                menu="Graph",
                tooltip=f"{text} of the active graph panel",
            ),
            slot,
        )

    for action_id, text, slot, sep in (
        (
            "analyze.descriptive",
            "Descriptive Statistics...",
            window._action_descriptive,
            False,
        ),
        ("analyze.regression", "Regression...", window._action_regression, False),
        ("analyze.fit", "Nonlinear Fit...", window._action_fit, False),
        ("analyze.slope", "Slope / Range Fit...", window._action_slope, False),
        ("analyze.peaks", "Peak Analysis...", window._action_peaks, True),
        (
            "analyze.deconvolution",
            "Peak Deconvolution...",
            window._action_deconvolution,
            False,
        ),
        ("analyze.signal", "Signal Processing...", window._action_signal, False),
        (
            "analyze.statistics",
            "Statistics / t-test / ANOVA...",
            window._action_statistics,
            False,
        ),
        (
            "analyze.batch_stats",
            "Batch Statistics...",
            window._action_batch_stats,
            False,
        ),
        (
            "analyze.digitize",
            "Digitize Curve from Image...",
            window._action_digitize,
            True,
        ),
    ):
        r.register(
            ActionSpec(action_id, text, None, menu="Analyze", separator_before=sep),
            slot,
        )

    r.register(
        ActionSpec(
            "export.graph",
            "Export Active Graph...",
            "Ctrl+E",
            menu="Export",
        ),
        window._action_export_graph,
    )
    r.register(
        ActionSpec("export.all_graphs", "Export All Graphs...", None, menu="Export"),
        window._action_export_all_graphs,
    )
    r.register(
        ActionSpec("export.sheet", "Export Worksheet as CSV...", None, menu="Export"),
        window._action_export_sheet,
    )
    r.register(
        ActionSpec(
            "export.script",
            "Export Project as Python Script...",
            None,
            menu="Export",
            separator_before=True,
        ),
        window._action_export_script,
    )
    r.register(
        ActionSpec("export.bundle", "Export Analysis Bundle...", None, menu="Export"),
        window._action_export_bundle,
    )

    r.register(
        ActionSpec("tools.palette", "Command Palette...", "Ctrl+Shift+P", menu="Tools"),
        window._action_command_palette,
    )
    r.register(
        ActionSpec("tools.methods", "Analysis Methods...", None, menu="Tools"),
        window._action_show_methods,
    )
    r.register(
        ActionSpec(
            "tools.console",
            "Python Console",
            None,
            menu="Tools",
            checkable=True,
            separator_before=True,
        ),
        window._toggle_console,
    )
    r.register(
        ActionSpec(
            "tools.record",
            "Record Macro",
            None,
            menu="Tools",
            checkable=True,
            separator_before=True,
        ),
        window._toggle_record,
    )
    r.register(
        ActionSpec("tools.save_macro", "Save Recorded Macro...", None, menu="Tools"),
        window._action_save_macro,
    )
    r.register(
        ActionSpec("tools.run_macro", "Run Script...", None, menu="Tools"),
        window._action_run_macro,
    )
    r.register(
        ActionSpec(
            "tools.batch",
            "Batch Import...",
            None,
            menu="Tools",
            separator_before=True,
        ),
        window._action_batch_import,
    )
    r.register(
        ActionSpec(
            "tools.batch_analysis", "Batch Analysis (Recipe)...", None, menu="Tools"
        ),
        window._action_batch_analysis,
    )
    r.register(
        ActionSpec(
            "tools.live", "Live Data...", None, menu="Tools", separator_before=True
        ),
        window._action_live_data,
    )
    r.register(
        ActionSpec(
            "view.preferences",
            "Preferences...",
            "Ctrl+,",
            menu="View",
            separator_before=True,
        ),
        window._action_preferences,
    )
    r.register(
        ActionSpec(
            "help.shortcuts",
            "Keyboard Shortcuts...",
            QKeySequence.StandardKey.HelpContents,
            menu="Help",
        ),
        window._action_shortcuts,
    )
    r.register(
        ActionSpec("help.about", "About GraphMatrix", None, menu="Help"),
        window._action_about,
    )
