# Respot

A cross-platform scientific data analysis and graphing GUI.

Respot aims to be a Python-first, open alternative to tools like OriginPro:
typed worksheet columns, publication-quality 2D graphs, a real analysis toolkit,
and scriptable automation. It targets Windows, macOS, and Linux from a single codebase.

> Status: **M1–M6 functionally implemented** (M0 skeleton + worksheets, 2D graphs,
> analysis, export, scripting, packaging scaffolding). See [`PLAN.md`](PLAN.md) §0
> for an honest per-milestone status. 3D is deliberately deferred.

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
  masking, formulas, editable grid, row/column operations.
- **Import/export** — CSV/TSV, Excel, Parquet, HDF5; export worksheets to CSV.
- **Graphs** — multi-layer 2D; line/scatter/line+symbol/bar/area/step/error-bar;
  editable axes and legend; live-linked to data.
- **Analysis** — descriptive stats, linear/polynomial regression, nonlinear fitting
  (Gaussian, Lorentzian, exponential, sinusoid, sigmoid, … via lmfit), peak finding,
  FFT, smoothing, filters, derivative/integral/interpolation, t-tests, ANOVA,
  correlation, histogram.
- **Publication export** — PDF/SVG/EPS/PNG/TIFF via matplotlib, sized in mm at your DPI.
- **Automation** — embedded Python console, macro recording → runnable script, batch import.

## Documentation

- [`PLAN.md`](PLAN.md) — architecture, decisions, milestones, current status, risks.
- [`docs/USAGE.md`](docs/USAGE.md) — how to use every feature, with scripting examples.
- [`docs/PACKAGING.md`](docs/PACKAGING.md) — building and signing distributable bundles.
