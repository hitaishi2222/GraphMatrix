# Respot

A cross-platform scientific data analysis and graphing GUI.

Respot aims to be a Python-first, open alternative to tools like OriginPro:
typed worksheet columns, publication-quality 2D graphs, a real analysis toolkit,
and scriptable automation. It targets Windows, macOS, and Linux from a single codebase.

> Status: **M1–M9 functionally implemented** (M0 skeleton + worksheets, 2D graphs,
> analysis, export, scripting, M7 graph-interaction, M8 provenance/journal output, and
> M9 digitizer + command palette). See [`PLAN.md`](PLAN.md) §0 for an honest
> per-milestone status, and [`ROADMAP.md`](ROADMAP.md) for what comes next. 3D is
> deliberately deferred.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# run the app
PYTHONPATH=src python -m respot

# run the tests (core only, no GUI required)
pytest
```

Or install as a package:

```bash
pip install -e ".[dev]"
respot
```

## Layout

```
src/respot/
  core/        Qt-free engine: model, commands, project I/O, analysis, scripting
  ui/          PySide6 views: main window, panels, graph editor, dialogs, console
  plugins/     Drop-in plugins discovered at startup
tests/         Core + analysis + I/O + export + scripting + headless UI tests
packaging/     PyInstaller spec + build script
docs/          Usage and packaging guides
.github/       CI matrix (Windows/macOS/Linux)
```

The golden rule: **`core/` never imports PySide6.** That keeps the engine
testable, headless-batchable, and free to be accelerated later without touching the UI.

## Capabilities

- **Worksheets** — typed columns (X/Y/YErr/Z/label/group/date/text), units, comments,
  masking, formulas, editable grid, undoable copy/paste, row/column operations,
  column drag-reorder, drag-and-drop file import.
- **Import/export** — CSV/TSV, Excel, Parquet, HDF5; export worksheets to CSV.
- **Graphs** — multi-layer 2D; line/scatter/line+symbol/bar/area/step/error-bar;
  dashed/dotted line styles; horizontal & vertical reference lines; hover crosshair
  and nearest-point readout; secondary (dual) Y axis; text annotations; editable axes
  and legend; style templates; drag a column from the tree to plot it; live-linked to data.
- **Analysis** — descriptive stats, linear/polynomial regression, nonlinear fitting
  (Gaussian, Lorentzian, exponential, sinusoid, sigmoid, … via lmfit), peak finding,
  **peak deconvolution** (multi-peak Gaussian/Lorentzian), **slope over an X range**,
  FFT, smoothing, filters, **baseline correction** (polynomial/linear/ALS/rolling-ball/
  rubber-band/median), derivative/integral/interpolation, t-tests, ANOVA, correlation,
  histogram.
- **Recipes** — save an analysis and re-run it on any series, or batch it across many files.
- **Provenance & reproducibility** — Respot records what you did in plain language
  (**Tools → Analysis Methods…**) and exports an **analysis bundle** (project + data
  CSVs + figures + `reproduce.py` + `methods.md`) that rebuilds every figure.
- **Digitizing** — recover an `(x, y)` curve from a picture of a plot
  (**Analyze → Digitize Curve from Image…**): calibrate with two anchors per axis, then
  extract by darkness or by colour.
- **Journal presets** — one-click Nature/Science/APS/IEEE figure sizes and typography
  (**Graph → Journal Preset**), honoured by the exporter.
- **Command palette** — `Ctrl+Shift+P` fuzzy-searches and runs any action.
- **Publication export** — PDF/SVG/EPS/PNG/TIFF via matplotlib, sized in mm at your DPI,
  dual-axis + annotations, and batch export of every graph in the project.
- **Automation** — embedded Python console, macro recording → runnable script, batch
  import, and a batch analysis pipeline (recipe → per-file report + figure).
- **Appearance** — four theme presets (Classic/Modern × Dark/Light) with matching
  plot-canvas colours, switchable from **View → Theme** and remembered between runs.

## Documentation

- [`PLAN.md`](PLAN.md) — architecture, decisions, milestones, current status, risks.
- [`ROADMAP.md`](ROADMAP.md) — forward plan: backlog by area, M7+ sequencing.
- [`docs/USAGE.md`](docs/USAGE.md) — how to use every feature, with scripting examples.
- [`docs/PACKAGING.md`](docs/PACKAGING.md) — building and signing distributable bundles.
