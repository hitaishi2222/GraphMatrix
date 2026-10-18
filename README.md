# GraphMatrix

![GraphMatrix banner](assets/banner.svg)

A cross-platform scientific data analysis and graphing GUI.

GraphMatrix aims to be a Python-first, open alternative to tools like OriginPro:
typed worksheet columns, publication-quality 2D graphs, a real analysis toolkit,
and scriptable automation. It targets Windows, macOS, and Linux from a single codebase.

> Status: **M1–M10 functionally implemented** (M0 skeleton + worksheets, 2D graphs,
> analysis, export, scripting, M7 graph-interaction, M8 provenance/journal output,
> M9 digitizer + command palette, and M10 analysis-depth + colour-mapped/heatmap/
> contour plots + 3D scatter/surface on **PyVista**) plus the M11 start —
> **linked brushing** between worksheets and graphs. See [`PLAN.md`](PLAN.md) §0
> for an honest per-milestone status, and [`ROADMAP.md`](ROADMAP.md) for what
> comes next.
>
> **GraphMatrix is still in active development.** APIs, file formats, and UI details
> may change between releases; please report issues and back up your projects.

## Installation

### From source (recommended for now)

```bash
git clone https://github.com/hitaishi2222/GraphMatrix.git
cd GraphMatrix
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,mcp]"
graphmatrix
```

### Requirements

- Python 3.10+
- PySide6, NumPy, SciPy, matplotlib, pyqtgraph, lmfit, openpyxl, pyarrow
- Optional: h5py (HDF5), fastmcp (MCP server)

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# run the app
PYTHONPATH=src python -m graphmatrix

# run the tests (core only, no GUI required)
pytest
```

Or install as a package:

```bash
pip install -e ".[dev]"
graphmatrix
```

## Layout

```
src/graphmatrix/
  core/        Qt-free engine: model, commands, project I/O, analysis, scripting
  ui/          PySide6 views: main window, panels, graph editor, dialogs, console
  plugins/     Drop-in plugins discovered at startup
tests/         Core + analysis + I/O + export + scripting + headless UI tests
examples/      Sample scripts and projects
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
- **Provenance & reproducibility** — GraphMatrix records what you did in plain language
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

## Command-line interface

GraphMatrix ships a small CLI for scripting and headless use:

```bash
graphmatrix --help
graphmatrix run project.rsproj            # open project(s) in the GUI
graphmatrix list project.rsproj          # list graphs in a project
graphmatrix export project.rsproj -g 1,3-5 --format pdf --out ./out
graphmatrix run pipeline.yaml            # run a headless YAML pipeline
graphmatrix doctor                      # check environment and dependencies
```

- `run` opens one or more project files in the GUI.
- `list` prints the graphs available in a project (1-based indices).
- `export` exports all or selected graphs (`1`, `1,3`, `1-3`, `(1,3)`).
- `doctor` verifies Python, required/optional modules, and the display environment.
- Pipelines are YAML files with steps: `import`, `column`, `graph`, `plot`, `fit`,
  `analyze`, `export`, `save`, and `code`.

## MCP server

GraphMatrix exposes an MCP server for AI assistants (stdio transport):

```bash
pip install "graphmatrix[mcp]"
graphmatrix-mcp
```

Tools: `connect`, `summary` (workbooks, sheets, graphs, and project versions),
`run` (Python against the GraphMatrix API — including pipelines, versioning,
batch statistics, colour/XYZ plots, numeric fit regions via
`api.fit(..., x_min=..., x_max=...)`, and live data tailing via
`graphmatrix.core.live.LiveFileSource`), and `export`. Example client config:

```json
{ "mcpServers": { "graphmatrix": { "command": "graphmatrix-mcp" } } }
```

## Supported formats

- **Import:** CSV/TSV, Excel (`.xlsx`/`.xls`), Parquet, HDF5/NetCDF (optional)
- **Export:** PDF, SVG, EPS, PNG, TIFF, JPEG (publication-ready, sized in mm at your DPI)
- **3D plotting** (live scene): optional extra — `pip install pyvista pyvistaqt`

## Keyboard shortcuts

- `Ctrl+N` New project · `Ctrl+O` Open · `Ctrl+S` Save
- `Ctrl+Z` / `Ctrl+Shift+Z` Undo / Redo
- `Ctrl+Shift+P` Command palette
- `F2` Rename selected object

## Troubleshooting

- **Hyprland / Wayland:** GraphMatrix sets its app id to `graphmatrix` so it tiles.
  If your compositor still floats it, check window rules matching `python3` or `graphmatrix`.
- **Headless tests:** run with `QT_QPA_PLATFORM=offscreen`.
- **Missing optional deps:** run `graphmatrix doctor`.

## Contributing

Contributions are welcome. Please open an issue or pull request. Keep `core/` free of PySide6
imports so the engine stays testable and headless.

## License

MIT (see `LICENSE` if present).

## Documentation

- [`PLAN.md`](PLAN.md) — architecture, decisions, milestones, current status, risks.
- [`ROADMAP.md`](ROADMAP.md) — forward plan: backlog by area, M7+ sequencing.
- [`docs/USAGE.md`](docs/USAGE.md) — how to use every feature, with scripting examples.
- [`docs/PACKAGING.md`](docs/PACKAGING.md) — building and signing distributable bundles.
