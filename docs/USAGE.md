# Using Respot

## Launch

```bash
PYTHONPATH=src python -m respot
```

The window has a **Project Explorer** (left), a **Properties** inspector (right),
a tabbed workspace (center), and a **Python Console** (bottom, hidden by default).

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
Double-click a cell to edit (the change is undoable). Right-click a **column header**
for rename / units / comment / type / decimal places / **formula** / insert / delete.
Right-click a **cell** for row insert/delete, or **copy / cut / paste** cell blocks
(Ctrl+C / Ctrl+X / Ctrl+V; a paste is a single undo step). Drag a column header to
**reorder** columns.

Formulas reference columns by name and use numpy functions, e.g. `sin(X1) + 2`,
`Y1 * exp(-X1/3)`, `log(Y1)`. They are sandboxed — no arbitrary code execution.

### 3. Graph it
- **Data → Add Graph** creates a graph and auto-plots the first X/Y pair.
- **Graph → Add Plot to Active Graph…** chooses source sheet, X, Y, Y error, style.
- **Drag a column** from the Project Explorer onto a graph to plot it (an X column
  pairs with the sheet's first Y; a Y column with the first X).
- The graph sidebar edits plot style/color/symbol/**Y axis (left/right)** and axis
  scale/labels/limits/**Y2 label**/legend.
- **Graph → Add Annotation…** places a text label; **Graph → Save/Apply Style
  Template…** copies a graph's whole look onto another graph.
- Styles: line, scatter, line+symbol, bar, area, step, error bar. Multi-layer and
  **dual Y axis** supported. Large series are downsampled automatically while panning.

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
- **Signal Processing** — FFT, Savitzky–Golay / moving-average smoothing, Butterworth
  filters, derivative, integration, interpolation, polynomial baseline.
- **Statistics** — t-tests, one-way ANOVA, Pearson/Spearman correlation, histogram.

Every report can push its **curves back into the project**: "Add as columns" (undoable)
or "Plot on active graph" (adds the curve as columns and a plot).

### 5. Export
- **Export → Export Active Graph…** — PDF/SVG/EPS (vector, font-embedded) or
  PNG/TIFF (raster) at a chosen size in mm and DPI. Dual-axis and annotations included.
- **Export → Export All Graphs…** — batch export every graph in the project to a folder.
- **Export → Export Worksheet as CSV…**

### 6. Automate
- **Tools → Python Console**: a live Python REPL scoped to your project.
- **Tools → Record Macro** → make edits → **Save Recorded Macro…** writes a runnable
  script. **Tools → Run Script…** replays it.
- **Tools → Batch Analysis (Recipe)…**: pick a recipe (JSON) and many data files; each
  file is imported, analyzed, and gets a text report + a figure in the output folder.

#### Analysis recipes

A recipe records *what* to compute (not the data), so it can be re-run anywhere:

```python
from respot.core.recipes import Recipe, run_recipe, save_recipe

recipe = Recipe("fit", {"model": "Exponential Decay"}, label="exp decay")
r = run_recipe(recipe, x, y)          # x, y from anywhere
save_recipe(recipe, "exp.json")       # batch it via Tools → Batch Analysis
```

Supported operations: `descriptive`, `regression`, `fit`, `peaks`, `deconvolution`, `signal`.

## Scripting examples

The console exposes `api` (a `RespotAPI`), `project`, `np`, `numpy`, `scipy`, plus the
model classes. Scripted changes go through the same commands as the GUI, so they are
undoable.

```python
# Build a workbook and plot it
api.add_workbook("Demo")
api.add_worksheet("Demo", "Sheet1")
x = np.linspace(0, 10, 300)
api.add_column("Demo/Sheet1", "X1", "X", data=x, units="s")
api.add_column("Demo/Sheet1", "Y1", "Y", data=3*np.exp(-x/2) + 0.1)
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

## Keyboard shortcuts

| Action | Shortcut |
|--------|----------|
| New project | Ctrl+N |
| Open project | Ctrl+O |
| Save project | Ctrl+S |
| Import data | Ctrl+I |
| Copy / Cut / Paste (cells) | Ctrl+C / Ctrl+X / Ctrl+V |
| Undo / Redo | Ctrl+Z / Ctrl+Shift+Z |
| Quit | Ctrl+Q |

## Project files

`.rsproj` is a zip archive: `project.json` (manifest) plus `arrays/*.npy` for numeric
column data. It is inspectable and versioned, and does **not** try to read Origin's
`.opj`/`.opju` format.
