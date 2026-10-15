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
- **Data → Add Sample Data**: drops a sine wave into the selected worksheet.
- **Tools → Batch Import…**: import many files at once (one undoable step).

Columns are typed (`X`, `Y`, `YErr`, `Z`, `Label`, `Group`, `Date`, `Text`). Importers
infer types; first numeric column becomes X, the rest Y.

### 2. Edit the worksheet
Double-click a cell to edit (the change is undoable). Right-click a **column header**
for rename / units / comment / type / decimal places / **formula** / insert / delete.
Right-click a **cell** for row insert/delete.

Formulas reference columns by name and use numpy functions, e.g. `sin(X1) + 2`,
`Y1 * exp(-X1/3)`, `log(Y1)`. They are sandboxed — no arbitrary code execution.

### 3. Graph it
- **Data → Add Graph** creates a graph and auto-plots the first X/Y pair.
- **Graph → Add Plot to Active Graph…** chooses source sheet, X, Y, Y error, style.
- The graph sidebar edits plot style/color/symbol and axis scale/labels/limits/legend.
- Styles: line, scatter, line+symbol, bar, area, step, error bar. Multi-layer supported.

### 4. Analyze
Everything is under **Analyze**:
- **Descriptive Statistics** — N, mean, std, quartiles, skew, kurtosis, CI.
- **Regression** — linear and polynomial.
- **Nonlinear Fit** — 9 built-in models (Gaussian, Lorentzian, exponential decay/growth,
  sinusoid, power law, sigmoid, step, log-normal) via lmfit, reporting parameters ±
  standard error, R², χ², AIC/BIC.
- **Peak Analysis** — peak positions, heights, prominence, FWHM.
- **Signal Processing** — FFT, Savitzky–Golay / moving-average smoothing, Butterworth
  filters, derivative, integration, interpolation, polynomial baseline.
- **Statistics** — t-tests, one-way ANOVA, Pearson/Spearman correlation, histogram.

Every report can push its **curves back into the project**: "Add as columns" (undoable)
or "Plot on active graph" (adds the curve as columns and a plot).

### 5. Export
- **Export → Export Active Graph…** — PDF/SVG/EPS (vector, font-embedded) or
  PNG/TIFF (raster) at a chosen size in mm and DPI.
- **Export → Export Worksheet as CSV…**

### 6. Automate
- **Tools → Python Console**: a live Python REPL scoped to your project.
- **Tools → Record Macro** → make edits → **Save Recorded Macro…** writes a runnable
  script. **Tools → Run Script…** replays it.

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
| Undo / Redo | Ctrl+Z / Ctrl+Shift+Z |
| Quit | Ctrl+Q |

## Project files

`.rsproj` is a zip archive: `project.json` (manifest) plus `arrays/*.npy` for numeric
column data. It is inspectable and versioned, and does **not** try to read Origin's
`.opj`/`.opju` format.
