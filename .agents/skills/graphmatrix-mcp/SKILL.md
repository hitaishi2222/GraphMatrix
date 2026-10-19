---
name: graphmatrix-mcp
description: Drive the GraphMatrix scientific plotting app through its MCP tools — make graphs of any template (simple, stack, grid, double-Y, X-twin), add data, plot series, label axes, export figures, and save projects, either in the running window or in a headless session. Use when the task is to create, inspect, restyle or export GraphMatrix figures, or to script GraphMatrix projects.
---

# GraphMatrix over MCP

GraphMatrix is a desktop app for worksheets and publication-quality figures.
Its MCP server exposes two ways to work:

- **live tools** — edit the project in the **running window**. Changes appear
  immediately, are undoable with `Ctrl+Z`, and are seen by the user.
- **session tools** (`connect`, `summary`, `run`, `export`) — work on a project
  inside the server process, with no window involved.

Prefer the live tools when a window is open: the user sees the result.

## Live workflow (a window is running)

1. **`live_describe`** — always start here. It returns every worksheet with its
   typed columns, the plottable X/Y pairs, every graph with its panels and
   series, plus the graph templates and plot styles this build supports.
2. **`live_add_data`** — if the project has no usable data, create a sheet:
   ```json
   {"book": "Demo", "sheet": "Physics",
    "columns": [
      {"name": "X", "type": "X", "generate": {"kind": "linspace", "start": 0, "stop": 10, "count": 61}},
      {"name": "Signal", "type": "Y", "generate": {"kind": "sin", "count": 61, "amp": 1.0, "freq": 2.0}},
      {"name": "Noise", "type": "Y", "generate": {"kind": "random", "count": 61, "seed": 3, "scale": 0.15}}
    ]}
   ```
   Generators: `linspace` (start, stop, count), `arange` (start, stop, step),
   `sin`/`cos` (count, amp, freq, phase), `random` (count, seed, scale), `ramp`
   (count). `values: [...]` puts literal numbers in a column instead.
3. **`live_create_graph`** — make the figure. It opens as a tab straight away.
   ```json
   {"name": "Stacked", "graph_type": "stack", "panels": 3,
    "source": "Demo/Physics", "x": "X", "y": "Signal", "style": "line"}
   ```
4. **`live_add_plot`** — fill the other panels:
   ```json
   {"graph": "Stacked", "source": "Demo/Physics", "x": "X", "y": "Noise",
    "style": "scatter", "panel": 2, "replace": true}
   ```
   `panel` is **1-based**. `replace: true` clears the panel first — use it
   whenever the panel already shows a replicated series. `y_axis: "right"` puts
   a series on the secondary axis of a double-Y graph.
5. **`live_set_property`** — label the figure:
   ```json
   {"graph": "Stacked", "key": "x_label", "value": "time (s)"}
   ```
   Graph properties: `title`, `panel_gap_x`, `panel_gap_y`, `y_delta`,
   `layout_rows`, `layout_cols`, `plot_theme`, `journal_preset`,
   `title_font_size`, `title_color`.
   Panel properties: `x_label`, `y_label`, `y2_label`, `z_label`, `x_scale`,
   `y_scale`, `x_min`, `x_max`, `y_min`, `y_max`, `show_legend`,
   `show_y_axis`, `minor_ticks`, `tick_direction`, `label_font_size`,
   `label_font_family`, `label_color`.
6. **`live_export`** — write the figures out (`out_dir`, `format`, `dpi`).
   The export uses the window's theme and, with `match_screen` (default), the
   on-screen proportions, so the file looks like the preview.
7. **`live_save`** — persist the project (`path`).
8. **`live_screenshot`** — capture the window to check the result visually.

`live_run` executes arbitrary Python against the same live project when the
high-level tools do not cover something. `live_open` replaces the project in
the window; `live_delete_graph` removes a graph.

## Figure templates

| `graph_type` | Layout | Notes |
| --- | --- | --- |
| `simple` | 1 panel | one X/Y pair |
| `stack` | `panels` rows | panels share X; `y_delta` shifts them |
| `double-y` | 1 panel | second Y axis via `y_axis: "right"` |
| `x-twin` | `panels` columns | panels share Y |
| `grid` | `rows` × `cols` | one panel per cell |

Plot styles: `line`, `scatter`, `line+symbol`, `bar`, `area`, `step`,
`errorbar`, `color-mapped scatter`, `heatmap`, `contour`, `3d scatter`,
`3d surface`. The colour/3D styles need a `z` column.

## Session workflow (no window)

```text
connect            -> {"project_id": ...}
summary            -> workbooks, sheets, graphs, versions
run                -> Python against the GraphMatrixAPI of that project
export             -> write the figures to a folder
```

Inside `run`, the namespace has `api` (a `GraphMatrixAPI`), `project`, `np`,
`scipy`, `math`. Intent-level helpers are on `api`: `api.create_graph(...,
graph_type="stack")`, `api.add_plot(...)`, `api.set_graph_type(...)`,
`api.set_property(...)`, `api.describe_project()`.

## Gotchas

- **`live_create_graph` replicates the first series into every panel.** Fill a
  panel with a different series by passing `replace: true` to `live_add_plot`.
- **A graph's *Plot theme* decides how it looks and how it exports.** Set it
  with `live_set_property` (`key: "plot_theme"`, e.g. `plot-publication` for a
  white, print-safe figure). A *journal preset* always exports on white paper.
- **Everything is undoable.** If a step goes wrong, the user can press
  `Ctrl+Z`; there is no need to clean up by hand.
- **The live tools need a running window.** If they report that no instance is
  running, ask the user to start GraphMatrix — the bridge socket lives in
  `~/.local/state/graphmatrix/`.
- **`live_export` names files after the graph**, so two graphs with the same
  name overwrite each other.

## Reference material

- `examples/mcp_live_demo.py` — runs the whole live workflow against a running
  window and prints a transcript.
- `docs/USAGE.md` — the human-facing manual (plotting, layouts, export).
