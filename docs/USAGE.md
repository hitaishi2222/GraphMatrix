# Using GraphMatrix

## Launch

```bash
PYTHONPATH=src python -m graphmatrix
```

The window has a **Project Explorer** (left), a **Properties** inspector (right),
a tabbed workspace (center), and a **Python Console** (bottom, hidden by default).

To **rename** the project, a workbook, a worksheet, or a graph, right-click it in the
Project Explorer → **Rename…**, or select it and press **F2** (the Properties
inspector's **Name** field is editable too). Renaming a workbook or worksheet
rewrites the data references used by any graph built on it, so existing plots keep
working; every rename is a single undoable step.

## The workflow

### 1. Get data in

- **File → Import Data…** (Ctrl+I): CSV/TSV/TXT/DAT, Excel (.xlsx), Parquet, HDF5/NetCDF.
- **Drag and drop** data files (or a `.rsproj`) onto the window.
- **Data → Add Sample Data**: drops a sine wave into the selected worksheet.
- **Tools → Batch Import…**: import many files at once (one undoable step).

Columns are typed (`X`, `Y`, `YErr`, `Z`, `Label`, `Group`, `Date`, `Text`). Importers
infer types; first numeric column becomes X, the rest Y. A header written as
`Name (units)` round-trips through CSV.

### 2. Edit the worksheet

Double-click a cell to edit (the change is undoable). Click the **+** button just to
the right of the last column header to append a column. Right-click a **column
header** for rename / units / comment / type / decimal places / **formula** / insert /
delete. Right-click a **row number** for insert/delete rows, or right-click a **cell**
for the same row/column actions plus **copy / cut / paste** cell blocks
(Ctrl+C / Ctrl+X / Ctrl+V; a paste is a single undo step). Drag a column header to
**reorder** columns.

Row and column shortcuts (also in **Data → Rows and Columns**):

- `Ctrl+Alt+N` — add a row at the end
- `Ctrl+Alt+C` — add a column at the end
- `Ctrl+Alt+=` — insert row(s) above the selection
- `Ctrl+Alt+-` — delete the selected row(s)
- `Ctrl+Alt+Shift+-` — delete the selected column(s)
- `F2` — rename the selected column

Formulas reference columns by name and use numpy functions, e.g. `sin(X1) + 2`,
`Y1 * exp(-X1/3)`, `log(Y1)`. They are sandboxed — no arbitrary code execution.

### 3. Graph it

- **Data → Add Graph** creates a graph and auto-plots the first X/Y pair.
- **Graph → Add Plot to Active Graph…** chooses source sheet, X, Y, Y error, style.
- **Drag a column** from the Project Explorer onto a graph to plot it (an X column
  pairs with the sheet's first Y; a Y column with the first X).
- **Right-click a column header**, or select a whole column in the grid and
  right-click it → **Plot “Column”**, to graph it against its partner X/Y. If no
  graph is open, one is created for you.
- The graph sidebar edits plot style/**line style (solid/dash/dot/dashdot/longdash)**/
  color/symbol/**Y axis (left/right)** and axis scale/labels/limits/**Y2 label**/legend.
- **Graph → Add Annotation…** places a text label; **Graph → Save/Apply Style
  Template…** copies a graph's whole look onto another graph.
- **Reference lines** — **Graph → Add Reference Line…** (or the sidebar's **Add H-line**
  / **Add V-line**) draws a horizontal or vertical guide at a chosen value with its own
  color, width, dash style, and optional label. Lines belong to a layer and are
  undoable; they appear in exports too.
- **Data readout** — **Graph → Data Readout (Hover)** (or the sidebar toggle) shows a
  crosshair plus the nearest data point's series, `x`, and `y` under the mouse. The
  readout is drawn in the corner of the figure by the canvas overlay, so it is
  interface, not figure content: it never appears in exported figures.
- **Canvas tools** — a small floating toolbar in the top-right corner of every graph
  offers **zoom in**, **zoom out**, **fit** (reset the panel to the data's limits) and
  the **data readout** switch. It fades out when the pointer leaves the figure. Like
  the readout, it is a widget and never reaches an exported file.
- **Panel marker** — in a grid, a stack or an X-twin, the panel you are editing is
  framed in the figure and named in the corner ("Panel 2 / 4"). Selecting a series in
  the **Plots** list jumps the marker to that series' panel, so the sidebar and the
  figure always agree.
- Styles: line, scatter, line+symbol, bar, area, step, error bar. Multi-layer and
  **dual Y axis** supported. Large series are downsampled automatically while panning.
- **Journal presets** — **Graph → Journal Preset** applies a publisher's figure size
  and typography (Nature, Science, APS, IEEE — single & double column) to the active
  graph: it restyles the plots' line widths and marker sizes and records the preset so
  the exporter uses the matching font sizes and default dimensions. Undoable.
- **Plot theme** — the **Plot theme** combo in the graph sidebar sets the canvas
  colours of that graph (Follow app theme, Classic light/dark, Seaborn, Earth,
  Monochrome, Publication). The export follows the same theme, so the file looks like
  the preview. A journal preset always exports on white paper.
- **Export — what you see is what you get.** The exporter reuses the canvas
  renderer: same background, foreground, grid, title, legend and axis labels. The
  exported file is exactly the requested size in millimetres (no hidden cropping), and
  exporting from the window keeps the on-screen proportions of the figure.

#### Graph layout types

Use **Graph → Graph Type**, the **Graph type** combo in the toolbar, the right-click
menu on a graph in the Project Explorer, or the **Properties** inspector to switch
between:

- **Simple** — one plot frame.
- **Stack** — layers stacked vertically, sharing X. New stack graphs start with two
  panels; **Graph → Add Layer** adds more. **Y delta** shifts each successive panel's
  data (waterfall-style).
- **Double Y (2Y)** — one frame with a secondary right axis; set a plot's **Y axis**
  to *Right* in the plot sidebar.
- **X-Twin** — layers side by side, sharing Y.
- **Grid** — an R×C grid of panels; set **Grid rows/columns** and **Panel gap X/Y**.

The sidebar's **Axes → Layout** tab and the Properties inspector only enable the
fields that apply to the current type. Type changes are undoable and never delete
layers or plots; the Project Explorer labels each graph with its type, e.g.
`Graph1  [Stack (vertical panels)]`.

**Axes → Ticks → Y axis → Hide** removes a panel's Y axis line, ticks, and labels.
It is handy for stacks where the traces should read as clean waveforms; legends
are drawn per panel after the plots. All changes are undoable.

### 4. Analyze

Everything is under **Analyze**:

- **Descriptive Statistics** — N, mean, std, quartiles, skew, kurtosis, CI.
- **Regression** — linear and polynomial.
- **Nonlinear Fit** — 9 built-in models (Gaussian, Lorentzian, exponential decay/growth,
  sinusoid, power law, sigmoid, step, log-normal) via lmfit, reporting parameters ±
  standard error, R², χ², AIC/BIC.
- **Peak Analysis** — peak positions, heights, prominence, FWHM.
- **Peak Deconvolution** — fit a sum of overlapping Gaussian or Lorentzian peaks
  (give approximate centres, or leave blank to auto-detect) with a constant baseline.
- **Slope / Range Fit** — linear fit of a series between two X values, reporting slope,
  intercept, R², the slope's standard error, and Δy/Δx over the window. The report can
  **Annotate on graph**, writing `slope = … (R² = …)` as an undoable text label.
- **Signal Processing** — FFT, Savitzky–Golay / moving-average smoothing, Butterworth
  filters, derivative, integration, interpolation, and **baseline correction**
  (polynomial, linear, ALS, rolling-ball, rubber-band, median). Baseline results return
  both the fitted `Baseline` and the `Corrected` signal.
- **Statistics** — t-tests, one-way ANOVA, Pearson/Spearman correlation, histogram.
- **Digitize Curve from Image** — recover `(x, y)` points from a picture of a plot.
  Load a PNG/JPEG/TIFF, click the four calibration anchors in order (X1, X2, Y1, Y2 —
  two points per axis, each mapping a pixel coordinate to a data value; the pixel
  spinboxes let you nudge them), then **Extract**. Choose a darkness threshold, flip it
  for light-on-dark traces, restrict the X range, or tick **Isolate colour** and give a
  hex colour + tolerance to pull one trace out of a busy figure. The result adds to the
  project like any other analysis curve.

Every report can push its **curves back into the project**: "Add as columns" (undoable)
or "Plot on active graph" (adds the curve as columns and a plot).

### 4b. Reproducibility

- **Tools → Analysis Methods…** shows a plain-language methods write-up: data imports,
  analysis runs (with their summaries), and notable operations, in order.
- **Export → Export Project as Python Script…** writes a script that rebuilds every
  workbook and graph through the console API.
- **Export → Export Analysis Bundle…** writes a folder containing the project,
  `data/*.csv`, `figures/*`, `reproduce.py`, `methods.md`, and `provenance.json` — the
  whole piece of work, reproducible and documented.

### 5. Export

- **Export → Export Active Graph…** — PDF/SVG/EPS (vector, font-embedded) or
  PNG/TIFF (raster) at a chosen size in mm and DPI. Dual-axis and annotations included.
- **Export → Export All Graphs…** — batch export every graph in the project to a folder.
- **Export → Export Worksheet as CSV…**
- **"Match on-screen proportions"** (in the export dialog, on by default) makes the
  file look exactly like the preview: it takes the shape of the figure on screen and
  scales the typography, line widths and markers with the page, so nothing is
  re-proportioned. Turn it off for print-sized figures with standard point-sized
  typography (or pick a journal preset, which always uses its own sizes).

### 6. Automate

- **Tools → Command Palette…** (`Ctrl+Shift+P`) — fuzzy-search every action and run it.
- **Tools → Python Console**: a live Python REPL scoped to your project.
- **Tools → Record Macro** → make edits → **Save Recorded Macro…** writes a runnable
  script. **Tools → Run Script…** replays it.
- **Tools → Batch Analysis (Recipe)…**: pick a recipe (JSON) and many data files; each
  file is imported, analyzed, and gets a text report + a figure in the output folder.

## MCP server

Install the optional extra (`pip install "graphmatrix[mcp]"`). The server is
started by the *client* (Pi, Claude Desktop, …), so GraphMatrix itself has no
server UI to configure:

```bash
graphmatrix-mcp                                   # stdio (the usual setup)
graphmatrix-mcp --transport http --port 8765     # a shared, persistent endpoint
```

Client config:

```json
{ "mcpServers": { "graphmatrix": { "command": "graphmatrix-mcp" } } }
```

```json
{ "mcpServers": { "graphmatrix-live": { "url": "http://127.0.0.1:8765/mcp" } } }
```

#### The live bridge

Every running window listens on a local Unix socket
(`~/.local/state/graphmatrix/ipc-<pid>.sock`). That bridge is what the *live*
tools use to edit the open project — it is part of the application, independent
of the MCP server, and it needs no configuration. The window also registers
itself in `~/.local/state/graphmatrix/instance.json` at startup so assistants
can find it.

#### Driving the open window from an assistant

When GraphMatrix is already running, an assistant should use the *live* tools
instead of `run`: they act on the project in the window, so results are visible
immediately and remain undoable.

1. `live_describe` — find the data. It lists every worksheet with its typed
   columns, the plottable X/Y pairs, every graph with its panels and series,
   and the graph templates (`simple`, `stack`, `double-y`, `x-twin`, `grid`)
   and plot styles this build supports.
2. `live_add_data` — when no data exists yet, create a sheet directly:
   `columns=[{"name": "X", "type": "X", "generate": {"kind": "linspace", "start": 0, "stop": 10, "count": 41}}, {"name": "Y", "type": "Y", "generate": {"kind": "sin", "count": 41}}]`.
3. `live_create_graph` — make the figure:
   `name="Stacked", graph_type="stack", panels=2, source="Measurements/Run1", x="X", y="Oscillation", style="line"`.
   The graph opens as a tab straight away.
4. `live_add_plot` — fill the remaining panels:
   `graph="Stacked", source="Measurements/Run1", x="X", y="Counts", panel=2, replace=True`.
   `panel` is 1-based, `replace=True` clears the panel first, and
   `y_axis="right"` puts the series on a double-Y graph's second axis.
5. `live_set_property` — label it: `graph="Stacked", key="x_label", value="time (s)"`.
6. `live_export` / `live_save` — write the figure out or persist the project.

`live_run` is still there for anything the high-level tools do not cover: it
executes Python against the same live project through the same command stack.

#### Analysis recipes

A recipe records _what_ to compute (not the data), so it can be re-run anywhere:

```python
from graphmatrix.core.recipes import Recipe, run_recipe, save_recipe

recipe = Recipe("fit", {"model": "Exponential Decay"}, label="exp decay")
r = run_recipe(recipe, x, y)  # x, y from anywhere
save_recipe(recipe, "exp.json")  # batch it via Tools → Batch Analysis
```

Supported operations: `descriptive`, `regression`, `fit`, `peaks`, `deconvolution`,
`signal`, `slope`. A `signal` recipe can name a baseline, e.g.
`Recipe("signal", {"operation": "Baseline (ALS)", "lam": 1e6})`, and a `slope` recipe
takes optional `x0`/`x1` bounds.

## Scripting examples

The console exposes `api` (a `GraphMatrixAPI`), `project`, `np`, `numpy`, `scipy`, plus the
model classes. Scripted changes go through the same commands as the GUI, so they are
undoable.

```python
# Build a workbook and plot it
api.add_workbook("Demo")
api.add_worksheet("Demo", "Sheet1")
x = np.linspace(0, 10, 300)
api.add_column("Demo/Sheet1", "X1", "X", data=x, units="s")
api.add_column("Demo/Sheet1", "Y1", "Y", data=3 * np.exp(-x / 2) + 0.1)
api.add_graph("Fit", "Demo/Sheet1", "X1", "Y1")

# Fit and inspect
r = api.fit("Exponential Decay", "Demo/Sheet1", "X1", "Y1")
print(r.to_text())

# Add the fitted curve back as columns
fitx, fity = r.curves["Fit"]
api.add_column("Demo/Sheet1", "Fit_X", "X", data=fitx)
api.add_column("Demo/Sheet1", "Fit_Y", "Y", data=fity)

# Persist
api.save("demo.rsproj")
```

Figure-as-code and reproducible bundles are one call each:

```python
from graphmatrix.core.code_export import project_to_script
from graphmatrix.core.report import export_analysis_bundle

print(project_to_script(project))  # a script that rebuilds the project
export_analysis_bundle(
    project, None, "bundle"
)  # data/ + figures/ + reproduce.py + methods.md
```

The digitizer is also importable (pixel anchors → data values):

```python
from graphmatrix.core.analysis.digitize import digitize_curve

result = digitize_curve(
    "scan.png",
    x_anchors=((60, 0.0), (740, 10.0)),  # (pixel, value) × 2 for the x axis
    y_anchors=((560, 0.0), (60, 5.0)),  # (pixel, value) × 2 for the y axis
)
x, y = result.curves["Digitized"]
```

## Appearance / themes

**View → Theme** (or the **Theme** dropdown on the toolbar) switches between four
presets. The choice is remembered between runs.

| Preset                     | Colour scheme | Design                                              |
| -------------------------- | ------------- | --------------------------------------------------- |
| **Classic Dark** (default) | dark          | neutral, square-ish                                 |
| **Classic Light**          | light         | neutral, square-ish                                 |
| **Modern Dark**            | dark          | deeper surfaces, indigo accent, rounded and compact |
| **Modern Light**           | light         | airy surfaces, indigo accent, rounded and compact   |

The design language ("classic" vs "modern") and the colour scheme are independent,
so the plot canvas, axes, legends, and annotations are recoloured to match whichever
preset is active.

## Keyboard shortcuts

| Action                     | Shortcut                 |
| -------------------------- | ------------------------ |
| New project                | Ctrl+N                   |
| Open project               | Ctrl+O                   |
| Save project               | Ctrl+S                   |
| Save project as            | Ctrl+Shift+S             |
| Import data                | Ctrl+I                   |
| Close tab                  | Ctrl+W                   |
| Copy / Cut / Paste (cells) | Ctrl+C / Ctrl+X / Ctrl+V |
| Undo / Redo                | Ctrl+Z / Ctrl+Shift+Z    |
| Rename selected item       | F2                       |
| Export active graph        | Ctrl+E                   |
| Command palette            | Ctrl+Shift+P             |
| Preferences                | Ctrl+,                   |
| All keyboard shortcuts     | F1                       |
| Zoom in / out / fit panel  | Ctrl+= / Ctrl+- / Ctrl+0 |
| Quit                       | Ctrl+Q                   |

**Help → Keyboard Shortcuts…** (F1) lists every command with its key, and the list
can be filtered as you type. On macOS the `Ctrl` keys are the Command key and
`F1` is the platform's help key.

## Preferences

**View → Preferences…** (Ctrl+,) holds the settings that are yours to choose:

| Tab         | Setting                                                     |
| ----------- | ----------------------------------------------------------- |
| Appearance  | Theme (the same four presets as View → Theme)                |
| Worksheet   | Decimals of newly created columns                            |
| Canvas      | Whether `Ctrl` + mouse wheel zooms the panel under the pointer |
| Export      | Default file format, resolution (DPI) and size in millimetres |
| General     | Whether to ask before unsaved changes are discarded           |

The values are stored with the theme preset and are remembered between runs.
**Restore Defaults** puts every setting back to its original value.

## Zooming a graph

Every graph panel has a small tool strip above the figure with **zoom in**,
**zoom out**, **fit** and the **data readout** switch. The percentage next to
them shows how much of the data the panel shows (100 % is the full range);
clicking it fits the data again. The same three commands are on the keyboard
(`Ctrl+=`, `Ctrl+-`, `Ctrl+0`) and act on the panel that is being edited, so a
stack or a grid zooms one panel at a time. `Ctrl` + mouse wheel zooms around
the pointer.

## Project files

`.rsproj` is a zip archive: `project.json` (manifest) plus `arrays/*.npy` for numeric
column data. It is inspectable and versioned, and does **not** try to read Origin's
`.opj`/`.opju` format.
