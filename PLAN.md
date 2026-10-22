# GraphMatrix — Detailed Plan

A cross-platform, Python-first scientific data analysis and graphing GUI, positioned
as an open alternative to OriginPro.

This document is the source of truth for **what we are building, why we chose the
stack we did, and in what order**. It is updated as milestones close.

---

## 0. Current status

_Last updated: 2026-10-18 (after the M10 analysis-depth / colour / 3D pass). Forward plan
lives in [`ROADMAP.md`](ROADMAP.md)._

| Milestone | Status | Notes |
|-----------|--------|-------|
| M0 — Skeleton | ✅ Done | Model, commands, shell, panels, plugin loader, tests. |
| M1 — Worksheet | 🟢 Functional | Editable grid, column properties/units/comments/types, decimal formatting, formulas, masking, row insert/delete, **undoable copy/cut/paste of cell blocks**, **column drag-reorder**, CSV/TSV/Excel/Parquet/HDF5 import, **drag-and-drop file import**, binary `.rsproj` payloads. |
| M2 — 2D graph canvas | 🟢 Functional | Multi-layer graphs, line/scatter/line+symbol/bar/area/step/errorbar styles, axes scales/labels/limits, legend, live-linked data, **secondary (dual) Y axis**, **text annotations**, **style templates (save/apply)**, **LOD downsampling**, **drag-column-to-layer**, all editable via undoable commands. |
| M3 — Analysis | 🟢 Functional | Descriptive stats; linear/polynomial/multiple regression; **nonlinear fitting (lmfit)** with parameter errors, R², χ², AIC/BIC, residuals; peak finding + FWHM; **peak deconvolution (multi-peak Gaussian/Lorentzian, `curve_fit`)**; **analysis recipes** (save + re-run on any series); FFT, Savitzky–Golay/moving-average smoothing, Butterworth filters, derivative, integration, interpolation, polynomial baseline; t-tests, ANOVA, correlation, histogram. |
| M4 — Publication export | 🟢 Functional | PDF/SVG/EPS/PNG/TIFF via matplotlib, size + DPI options, all plot styles, dual-axis + annotations, **batch export of every graph in a project**. |
| M5 — Automation | 🟢 Functional | Embedded Python console, macro recording → runnable script, script runner, batch import, **batch analysis pipeline (recipe → per-file report + figure over many files)**. |
| M6 — Ship | 🟡 Scaffolded | PyInstaller spec, GitHub Actions CI matrix (Win/macOS/Linux × py3.11/3.13), packaging docs. |
| **M7 — Graph interaction & range tools** | 🟢 Functional | **Dashed/dotted line styles**, **H-lines & V-lines (undoable `ReferenceLine` on the layer, drawn on canvas + export)**, **hover crosshair + nearest-point readout**, **slope over an X range** (`core.analysis.ranged`, annotate-on-graph), **baseline corrections** (linear, ALS, rolling-ball, rubber-band, median). Details in `ROADMAP.md` §2. |
| **M8 — Provenance, reproducibility & journal output** | 🟢 Functional | **`Command.describe()` + `ProvenanceLog`** → a `methods.md` write-up; **figure-as-code** (`project_to_script`); **analysis bundle** export (`project.rsproj` + `data/*.csv` + `figures/` + `reproduce.py` + `methods.md` + `provenance.json`); **journal presets** (Nature/Science/APS/IEEE sizes + typography, applied per graph and honoured on export). Menus: Graph → Journal Preset, Export → Project as Python Script / Analysis Bundle, Tools → Analysis Methods. Details in `ROADMAP.md` §3. |
| **M9 — Curve digitizer & command palette** | 🟢 Functional | **Digitize a curve from an image** (`core.analysis.digitize`: darkness/colour isolation, axis-anchor calibration, region + aggregate options) with a click-to-place dialog; **command palette** (`Ctrl+Shift+P`) fuzzy-searching every registered action. Details in `ROADMAP.md` §4. |
| **M10 — Analysis depth, colour & 3D plot types** | 🟢 Functional | **Numeric fit regions** (x-min/x-max in regression/nonlinear/recipes — locked UX), **peak integration** (per-peak area between prominence bases), **batch statistics table** (`descriptive.batch_summary`, Analyze → Batch Statistics), **colour-mapped scatter / heatmap / contour** (`PlotSpec.z` + `cmap`, colourbar, scattered-XYZ gridding via `core.plotting.grid_xyz`), and **3D scatter + surface on PyVista** — backend **locked to PyVista**; live scene by `pyvistaqt` behind `PlotCanvas`, vector 3D export via matplotlib. New styles: `color-mapped scatter`, `heatmap`, `contour`, `3d scatter`, `3d surface`. Details in `ROADMAP.md` §5. |
| 3D (closed) | 🔒 PyVista | The "Deferred — 3D" placeholder is resolved: live 3D on PyVista (`plot3d` extra), export on matplotlib 3D. 3D *fit* remains queued in the backlog. |
| **M11 — Interactive superpowers** | 🟡 Partial | **Linked brushing v1 shipped** (2026-10-18): `ui.brushing.BrushSelection` (view state, never serialized/undoable) links sheet and graph views — orange row tint in worksheets, ring overlay on plotted points of matching series, click-a-point-on-a-graph selects the worksheet row, overlays survive re-renders. Live-data board and the drag-a-fit-region gesture remain queued. Details in `ROADMAP.md` §6. |

**Test status:** `python -m pytest -q` → **143 passed**, no display required
(`QT_QPA_PLATFORM=offscreen`). Covers the model/formula layer, I/O round-trips,
the full analysis toolkit (incl. deconvolution, numeric fit regions, peak
integration, batch statistics), recipes + the batch pipeline, publication export
(incl. dual-axis/annotations, dashed lines, reference lines, journal presets, and
every colour/3D style), graph templates, scripting/macro replay, reference lines +
hover + slope, provenance + bundle round-trip, the digitizer, the XYZ/colour plumbing
(`grid_xyz`, resolved `z`), the PyVista 3D canvas, and a headless end-to-end UI smoke
test (incl. the command palette, digitize dialog, and the GraphView backend swap).

**Honest caveats:** genuinely deferred (not bugs), and the reasons are external or
out of scope:

- **3D camera transfer** — the live PyVista camera orientation is not copied into
  the matplotlib-3D export yet; exports use a sensible default view.
- **GPU/2D scale** — the 2D canvas is still matplotlib/pyqtgraph (LOD downsampling
  on by default); PyVista hosts only the *3D* live scene for now.
- **CMYK output** — matplotlib's vector backends cannot emit CMYK directly; not done.
- **Graph insets / layered annotations** — text annotations exist; insets do not.
- **Installers, code-signing, notarization, auto-update** — require OS tooling and
  certificates we cannot produce here; CI already builds signed-ready bundles.
- **Apache Arrow-backed columns (D4)** — storage is still numpy; Arrow is used only
  for Parquet I/O. Migrating the column store is a large, orthogonal refactor.

Treat M1–M5 as "usably functional with the common 80% done," not "finished."

---

## 1. Vision and scope

### 1.1 What GraphMatrix is

A desktop application for scientists and engineers to:

1. **Import** measurement/simulation data from common formats (CSV, Excel, Parquet, HDF5, NetCDF, images).
2. **Organize** it in typed worksheet columns (`X`, `Y`, `YErr`, `Z`, labels, groups, dates).
3. **Analyze** it with a correct, reportable statistics/fitting/signal toolkit.
4. **Graph** it at publication quality — multi-layer, multi-axis 2D first, 3D later.
5. **Automate** it through an embedded Python console, macros, and batch processing.
6. **Persist** everything — data, graphs, analysis recipes — in a single project file.

### 1.2 Explicit non-goals (for now)

- **Origin file compatibility.** We do not read/write `.opj`/`.opju`. Our own format is `.rsproj`. This removes the single largest source of scope creep.
- **3D plotting** in the initial milestones. Designed for, deferred.
- **Web/cloud product.** Desktop only; the core is kept UI-agnostic so a future
  headless/batch or web frontend is possible, but we do not build it now.
- **Being a general spreadsheet.** The worksheet grid serves plotting and analysis, not accounting.

### 1.3 Positioning

Win on: **scriptability (Python-native), cross-platform parity, and a clean, modern
worksheet → graph → analysis workflow.** Do not try to out-feature Origin's 30-year
library surface on day one; instead make the common 80% (import → plot → fit → export)
faster and more scriptable than the incumbent.

---

## 2. Locked decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Language / GUI | **Python + PySide6 (Qt)** | Team has strong Python. Qt is the only mature cross-platform toolkit with first-class dockable windows (Origin's whole UX). PySide6 is LGPL — commercially friendly, unlike PyQt's GPL. |
| D2 | 2D plot canvas | **pyqtgraph now, Vispy as the escape hatch** | pyqtgraph is Qt-native and fast to build on. Vispy (OpenGL/GPU) takes over when we outgrow it. Both sit behind one `PlotCanvas` interface so swapping is cheap. |
| D3 | Publication export | **matplotlib (vector backends)** | Used only for PDF/SVG/EPS export, never for the live canvas. Best-in-class for font-embedded vector output. |
| D4 | Data model | **numpy arrays now, Apache Arrow (`pyarrow`) in M1** | numpy is the scientific lingua franca; Arrow gives columnar memory-mapping and zero-copy interop when datasets grow. |
| D5 | Numerics | **numpy, scipy, `lmfit`, statsmodels, scikit-image** | `lmfit` alone delivers Origin-grade nonlinear fitting *with* the fit report, parameter uncertainties, and confidence intervals. |
| D6 | Undo/redo + scripting | **Command pattern from day one** | Every model mutation is a `Command`. Undo/redo and macro/script recording fall out for free; retrofitting is brutal. |
| D7 | Project file | **zip + `project.json`** (binary arrays later) | Human-inspectable, diffable, easy to version. Can add HDF5/no memory-map payloads without changing the envelope. |
| D8 | Packaging | **PyInstaller first, Nuitka if startup/protection demands it** | Simplest path to signed bundles on 3 OSes; revisit if cold-start or IP protection becomes a problem. |
| D9 | Plugin system | **Modules exposing `register(context)`** in `graphmatrix/plugins/` | Zero-config discovery; same mechanism can later load third-party plugins from a user directory. |
| D10 | Core/UI boundary | **`core/` must never import PySide6** | Testability, headless batch mode, and a future native acceleration seam. Enforced in review + (later) a lint check. |

---

## 3. Architecture

### 3.1 The seam

```
            ┌──────────────────────────────────────────────┐
            │                    ui/  (PySide6)            │
            │  MainWindow · docks · panels · PlotCanvas    │
            └───────────────▲──────────────────────────────┘
                            │  reads/mutates via Commands
            ┌───────────────┴──────────────────────────────┐
            │                 core/  (no Qt)               │
            │  model · commands · io · analysis · scripting│
            └──────────────────────────────────────────────┘
```

The UI **never** mutates the model directly. It pushes a `Command` onto the
`CommandStack`, which executes it and notifies subscribers so views refresh. This is
what makes undo/redo, script recording, and headless batch mode possible later.

### 3.2 Module map

```
src/graphmatrix/
  __main__.py            entry point
  app.py                 QApplication bootstrap
  core/                  ── Qt-free engine ──
    model/
      columns.py         ColumnType, Column (typed, units/comment)
      worksheet.py       Worksheet (typed columns, row count)
      workbook.py         Workbook (ordered worksheets)
      graph.py            Graph, Layer (plot specs arrive in M2)
      project.py          Project (root), save/open (.rsproj)
    commands.py          Command, CommandStack, structural commands, MacroCommand
    io/                  importers/exporters (M1+)
    analysis/            fits/stats/dsp (M3+)
  ui/                    ── PySide6 only ──
    actions.py           ActionSpec + ActionRegistry (menus/toolbar)
    main_window.py       QMainWindow, docks, tabs, workflow wiring
    project_panel.py     project → workbook → sheet → graph tree
    properties_panel.py  inspector for the selected object
    worksheet_view.py    read-only grid view of a worksheet (editing in M1)
    canvas/
      base.py            PlotCanvas interface + factory
      pyqtgraph_canvas.py pyqtgraph implementation
  plugins/
    loader.py            discovery + PluginContext
    hello.py             example plugin
tests/                   core unit tests (headless)
```

### 3.3 Why the boundary matters

- **Testability:** all of `core/` is unit-testable with no display.
- **Batch/headless:** the same engine can run analysis over many files in CI.
- **Performance escape hatch:** when a hot path (large import, heavy fit) outgrows
  Python, rewrite *that* `core/` module in Rust (`PyO3`) or Cython — the UI is untouched.
- **Future frontends:** a web or CLI shell can target the same core API.

---

## 4. Data model reference

| Type | Responsibility | Key fields |
|------|----------------|------------|
| `Column` | one typed data series | `name`, `col_type` (`X`/`Y`/`YErr`/`Z`/`Label`/`Group`/`Date`/`Text`), `units`, `comment`, `data: np.ndarray` |
| `Worksheet` | a sheet of columns | `name`, `columns: list[Column]`, `num_rows` |
| `Workbook` | ordered sheets | `name`, `sheets: list[Worksheet]` |
| `Graph` | a figure | `name`, `layers: list[Layer]` |
| `Layer` | one plotting layer (M2) | `name`, `plots` |
| `Project` | root document | `name`, `workbooks`, `graphs`; `save()` / `open()` |

Every model type has `to_dict()` / `from_dict()` — the whole serialization story flows
from that, so adding a field is a one-line change to each side.

**Project file (`.rsproj`)** = a zip archive containing `project.json`:
```json
{ "format": "graphmatrix-project", "version": 1, "name": "Untitled",
  "workbooks": [ { "name": "Book1", "sheets": [
    { "name": "Sheet1", "columns": [
      { "name": "X1", "col_type": "X", "units": "rad", "dtype": "float64", "data": [...] } ] } ] } ],
  "graphs": [ { "name": "Graph1", "layers": [ { "name": "Layer 1", "plots": [] } ] } ] }
```
Large numeric payloads will move to binary entries (`.npy`/Arrow IPC) in M1 while the
envelope stays the same.

---

## 5. Commands and undo

`CommandStack.push(cmd)` executes and records; `undo()`/`redo()` move between stacks.
Subscribers are notified on every change, which is how menus, the project tree, and
open views stay in sync.

Structural commands shipped in M0:

- `AddWorkbookCommand` / `RemoveWorkbookCommand`
- `AddWorksheetCommand` / `RemoveWorksheetCommand`
- `AddColumnCommand`
- `MacroCommand` — groups several commands into one undoable step (used by "Add Sample Data")

M1+ adds value-edit commands (`SetCellValue`, `SetColumnType`, rename, reorder) and a
**recording** layer that serializes the command log into a replayable macro/script.

---

## 6. Plugin and scripting model

A plugin is a module under `graphmatrix/plugins/` exposing:

```python
def register(context) -> None:
    # context: window, registry, commands, plugins_menu
```

`load_plugins()` imports each module, calls `register`, and reports failures without
crashing startup. Plugins may import Qt (they are a UI concern); they should reach the
model through `context.commands`, not by mutating it directly.

**Scripting (M5):** the same `Command` objects are the scripting vocabulary. An embedded
`code.InteractiveConsole` gets a namespace exposing the project, the command stack, and
convenience API; "record macro" simply serializes the command log. This is GraphMatrix's
answer to LabTalk — and because it *is* Python, it composes with numpy/scipy for free.

---

## 7. Milestones

Each milestone lists deliverables and a concrete **acceptance test**.

### M0 — Application skeleton ✅ (this milestone)
**Deliverables**
- Package layout, `pyproject.toml`, entry point, README, this plan.
- Qt-free `core/` model: `Column`, `Worksheet`, `Workbook`, `Graph`, `Project` + serialization.
- Command pattern: `CommandStack`, structural commands, `MacroCommand`.
- PySide6 shell: dockable Project Explorer + Properties, tabbed workspace, menu + toolbar.
- Worksheet grid view (read-only) and a minimal pyqtgraph canvas that auto-plots X/Y.
- Plugin loader + example `hello` plugin.

**Acceptance**
- `pytest` passes (core tests, no display).
- App launches headless (`QT_QPA_PLATFORM=offscreen`) without error.
- Can create workbooks/sheets, add sample data, open a worksheet and a graph tab, undo/redo the data, save, reopen, and see identical data.

### M1 — Worksheet
**Deliverables**
- Editable grid with keyboard navigation, paste, insert/delete rows & columns.
- Column properties: type, units, comment, decimal places, mask/missing values, column formulas.
- Importers: CSV/TSV, Excel (`openpyxl`), Parquet (`pyarrow`); drag-and-drop import.
- Data model migrates to Arrow-backed columns; project format gains binary payload entries.
- Value-edit commands so all edits are undoable.

**Acceptance:** import a 1e6-row CSV without freezing; edit cells/columns with full undo; round-trip the project file.

### M2 — 2D graph canvas
**Deliverables**
- Multi-layer, multi-axis graphs; line/scatter/bar/area/error-bar styles.
- Column-designation-driven plotting (X/Y/YErr) plus drag column → layer.
- Editable axes (scale, ticks, limits), legend, titles, annotations, insets.
- Themes/templates; live-linked data (edit data → graph updates).
- Level-of-detail downsampling; Vispy backend behind the same interface for large data.

**Acceptance:** build a two-layer, dual-Y-axis publication figure from two worksheets; zoom to 1e6 points smoothly.

### M3 — Analysis toolkit
**Deliverables**
- Descriptive stats, t-test/ANOVA (statsmodels), correlation, histogram.
- Linear/polynomial/multiple regression.
- **Nonlinear fitting via `lmfit`** with a full fit report (params ± err, R², residuals plot, confidence bands).
- Peak finding/deconvolution, integration/differentiation, interpolation.
- Baseline correction, smoothing, FFT/filters (scipy.signal).
- Analysis "recipes" attachable to a graph/workbook and re-runnable on new data.

**Acceptance:** fit a multi-peak spectrum, get a report graph + parameter table, save it, and re-run on a second dataset via a recipe.

### M4 — Publication export
**Deliverables**
- Vector PDF/SVG/EPS export via matplotlib backend; high-DPI PNG/TIFF.
- Font embedding, page size, transparency, CMYK option.
- Batch export across all graphs in a project using a template.

**Acceptance:** export multi-layer graphs to PDF with embedded fonts at exact journal dimensions.

### M5 — Automation
**Deliverables**
- Embedded Python console with a documented API namespace.
- "Record macro" from the command log; save/replay scripts.
- Batch processing: run an analysis recipe + export over many files/datasets.
- (Stretch) originpro-style third-party scripting package.

**Acceptance:** script a full import → fit → export pipeline in the console, save it, and run it over a folder of CSVs.

### M6 — Ship
**Deliverables**
- PyInstaller bundles + installers for Windows/macOS/Linux; code signing & notarization.
- Auto-update channel; crash reporting; telemetry (opt-in).
- Undo/redo hardening, project-format stability guarantees, docs site.
- CI building all three platforms on every tag.

**Acceptance:** a new user downloads, installs, and completes the "first figure" flow on all three OSes.

### 3D — resolved in M10 🔒
The open 3D slot is closed with the **PyVista** decision (2026-10-18):
- **Live 3D:** PyVista/VTK scene embedded in PySide6 via `pyvistaqt`, behind the
  same `PlotCanvas` interface; `GraphView` picks the backend automatically from a
  graph's styles. Requires the optional `plot3d` extra, so it never blocks installs.
- **Export:** matplotlib 3D through the normal exporter (vector PDF/SVG).
- Remaining 3D backlog: 3D *fit* surfaces, camera-aware export.

---

## 8. Cross-cutting concerns

### 8.1 Testing
- `core/` covered by fast unit tests (no Qt). Target: model, commands, I/O round-trips.
- `ui/` smoke-tested headless (`QT_QPA_PLATFORM=offscreen`): construct window, exercise actions.
- Later: golden-image tests for exported graphs.

### 8.2 Performance strategy (Python's real risk)
1. **Never loop over rows in Python.** Operate on numpy/Arrow arrays; vectorize.
2. Store columns as contiguous arrays; avoid per-cell objects in the hot path.
3. Canvas: LOD downsampling in pyqtgraph; Vispy/GPU when series exceed ~1e5–1e6 points.
4. Heavy fits/DSP ride on scipy/lmfit (C under the hood).
5. Escape hatch: PyO3/Cython for any `core/` hotspot — enabled by the Qt-free boundary.

### 8.3 Packaging and distribution (Python's other real risk)
- Freeze with PyInstaller into onedir bundles; test cold start early, not at the end.
- Windows: Authenticode signing. macOS: hardened runtime + notarization. Linux: AppImage/deb.
- CI matrix builds all three; do this from M0 so it never becomes a cliff.
- Watch Qt plugin bundling (platform plugins, image formats) — a classic frozen-app footgun.

### 8.4 Licensing
- PySide6 (LGPL), pyqtgraph (MIT), numpy/scipy (BSD), lmfit (BSD), matplotlib (PSF-based) — all compatible with a commercial closed or open product.
- Keep dependency licenses audited in CI.

---

## 9. Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Interactivity stutters on large data | Users abandon it | LOD downsampling now; Vispy/GPU backend behind the canvas interface; vectorized model |
| Distribution/packaging pain across 3 OSes | Can't ship | Nail PyInstaller + CI matrix in M0/M1, not at the end |
| Qt coupling leaks into `core/` | Lose testability + escape hatch | Hard rule D10, enforced in review and by a future import-lint |
| Analysis breadth underestimated | "It's not a real tool" | Sequence by user value (fit/stats first); lean on scipy/lmfit/statsmodels instead of writing algorithms |
| Scope creep toward Origin parity | Never ships | Non-goals in §1.2; milestone acceptance tests are the gate |
| PyQt/PySide licensing confusion | Legal risk | Locked on PySide6 (LGPL); no PyQt dependency |

---

## 10. Open questions

1. **Canvas default for M2:** commit to Vispy early, or stay on pyqtgraph until it hurts? (Current: pyqtgraph, behind the interface.)
2. **Arrow migration timing:** M1 as planned, or defer until a real dataset forces it?
3. **Plugin host for third parties:** ship only built-ins first, or a user plugin directory + versioned API from the start?
4. **Analysis recipes format:** JSON command log vs a small DSL vs plain Python snippets.
5. **Minimum supported Python:** currently 3.10+; revisit if 3.9 support is needed.

---

## 11. Changelog

| Date | Change |
|------|--------|
| 2026-10-15 | M0 skeleton landed: model, commands, shell, panels, canvas seam, plugin loader, tests, this plan. |
| 2026-10-15 | M1–M6 implementation pass: worksheet editing + importers, multi-layer/2D graphing, analysis toolkit (lmfit), matplotlib export, Python console + macro recording + batch, PyInstaller/CI scaffolding. §0 added. |
| 2026-10-15 | Test suite green: **43 passed** (model, I/O, analysis, export, scripting, headless UI). Fixed four bugs found by the tests: Graph-menu action tuple arity, `core/batch.py` relative imports, macro snapshots now taken at push time (so a workbook added empty is not re-expanded on replay), and the close-time "unsaved changes" prompt is suppressible for headless runs. |
| 2026-10-15 | M1–M6 completion pass (closing the items previously marked "Deferred"). **M1:** undoable copy/cut/paste of cell blocks (`SetCellsCommand`), column drag-reorder (`ReorderColumnsCommand`), drag-and-drop file import onto the window. **M2:** secondary (dual) Y axis with its own legend + `y2_label`, text annotations (model + canvas + export), graph style templates (`core/templates.py`, save/apply), LOD downsampling on by default, drag-a-column-from-the-tree-to-plot. **M3:** peak deconvolution (`core/analysis/deconvolution.py`, multi-peak Gaussian/Lorentzian via `curve_fit`) + auto-detect, analysis recipes (`core/recipes.py`). **M4:** batch export of every graph. **M5:** batch analysis pipeline (`run_recipe_over_files`: recipe → per-file report + figure). New tests: commands, plotting, templates, recipes/batch, deconvolution, export dual-axis. Suite now **63 passed**. |
| 2026-10-15 | **Theming pass.** New `ui/theme.py` preset system with four presets — **Classic Dark** (default), **Classic Light**, **Modern Dark**, **Modern Light** — each bundling a palette, a Fusion style, a QSS layer, and matching plot-canvas colours. **View → Theme** submenu (toolbar dropdown) switches presets; the choice persists via `QSettings`. The canvas, axes, legends, and annotations recolour to match. New tests: `test_theme.py` + a headless preset-switching smoke test. Suite now **72 passed**. |
| 2026-10-15 | **Rename + export-hardening pass.** Renaming was previously impossible in the UI: added **Project Explorer → Rename…** (context menu), an **Edit → Rename…** / **F2** action, and an editable **Name** field in the Properties inspector. `RenameWorkbookCommand` / `RenameWorksheetCommand` rewrite graph `source` references (`Project.remap_sources`) so plots survive a rename, and every rename is one undoable step. Export paths are now normalised to a supported extension (a stray `.bmp`/unknown suffix used to crash with an opaque "Export failed"), `export_graph` raises a clear message for unsupported formats, and export exceptions print a traceback to the terminal. New tests: workbook/worksheet/project rename + source cascade, export format validation. Suite now **79 passed**. |
| 2026-10-15 | **Plot-from-column pass.** A worksheet column can now be plotted straight from its context menu: right-click a **column header**, or select a whole column and right-click a cell, then choose **Plot “Column”** (pairs the column with its first X/Y partner; creates a graph if none is open, else adds to the active one). New `WorksheetView.plot_column_requested` signal → `MainWindow._plot_column`. Test: worksheet plot-from-column smoke test. Suite now **80 passed**. |
| 2026-10-15 | **M7 graph-interaction pass.** New `ROADMAP.md` holds the forward plan (backlog by area + detailed M7). Shipped: (1) **dashed/dotted line styles** — `PlotSpec.line_style`, rendered by pyqtgraph (`Qt.PenStyle`) and matplotlib, captured by style templates; (2) **reference lines** — new `ReferenceLine` model on `Layer`, `Add`/`RemoveReferenceLineCommand`, canvas (`pg.InfiniteLine`) + export (`axhline`/`axvline`), sidebar list + dialog; (3) **hover point info** — crosshair + nearest-point readout via an x-sorted search, menu toggle, canvas-only; (4) **slope over an X range** — `core.analysis.ranged.slope_between` (slope, intercept, R², std err, Δy/Δx) + **Analyze → Slope / Range Fit…** with one-click **Annotate on graph**; (5) **baseline corrections** — linear, ALS (Eilers), rolling-ball, rubber-band (lower hull), median, behind a `baseline_correction` dispatcher, wired into the Signal dialog and recipes (recipes also gained a `slope` op). New test file `test_graph_features.py` + a reference-line/hover/slope UI smoke test. Suite now **98 passed**. |
| 2026-10-15 | **M8/M9 provenance-and-digitizer pass.** New `core/provenance.py` (`Command.describe()` on meaningful commands + `ProvenanceLog` fed by described commands, imports, and analysis results → `methods.md`). New `core/code_export.project_to_script` (figure-as-code; namespace-complete replay, NaN/inf-safe) and `core/report.export_analysis_bundle` (project + `data/*.csv` + `figures/` + `reproduce.py` + `methods.md` + `provenance.json`). New `core/journals.py` presets (Nature/Science/APS/IEEE) with `apply_journal_preset` (idempotent, undoable via a command macro) and preset-aware `export_graph` (rcParams + default figure size); `Graph.journal_preset` serialized. New `core/analysis/digitize.py` (darkness/colour mask, two anchors per axis, region + aggregate) with `ui/digitize_dialog.py` (click-to-place anchors). New `ui/command_palette.py` (`Ctrl+Shift+P`) fuzzy-searching registered actions. Menus: Graph → Journal Preset, Export → Project as Python Script / Analysis Bundle, Tools → Command Palette / Analysis Methods, Analyze → Digitize Curve from Image. Model tweaks: `Worksheet.add_column`/`api.add_column` accept masks; console namespace exposes `Layer`/`AxisScale`/`ReferenceLine`/`Annotation`. New tests `test_provenance.py`, `test_report.py`, `test_journals.py`, `test_digitize.py` + palette/journal/digitize UI smoke tests. Suite now **120 passed**. |
| 2026-10-18 | **M10 analysis-depth / colour / 3D pass.** Decisions locked: **3D backend = PyVista** (open question #5) and **fit regions = numeric bounds** (open question #3). New: numeric fit regions (`x_min`/`x_max` on `linear_fit`, `polynomial_fit`, `fit_model`, plus Regression/Fit dialog fields and recipe params); peak integration (`find_peaks_result(integrate=True)` — trapezoidal area between prominence bases, Peaks-dialog check + recipe op); batch statistics (`descriptive.batch_summary` + Analyze → Batch Statistics); colour-mapped scatter / heatmap / contour (`PlotStyle` + `PlotSpec.z`/`cmap` + `Layer.z_label`, serialized & emitted by `project_to_script`; colourbar on canvas + export); scattered-XYZ gridding (`core.plotting.grid_xyz`); 3D scatter/surface on the new `ui/canvas/pyvista_canvas.py` (PyVista, optional `plot3d` extra = `pyvista`/`pyvistaqt`; GraphView auto-swaps backends, matplotlib fallback without extras); shared `render_xyz_mpl` keeps the live canvas and the exporter WYSIWYG; 3D export via matplotlib-3D. Non-numeric summary entries handled gracefully in reports/provenance/annotations. New `tests/test_m10.py`. Suite now **143 passed**. |
| 2026-10-22 | **shadcn theme pass.** Two new presets — **shadcn Dark** / **shadcn Light** — built on the shadcn/ui token set (`background`/`foreground`/`muted`/`border`/`primary`) with a new `"shadcn"` design language: flat surfaces, hairline borders, outline buttons, a single near-black (light) / near-white (dark) primary, and 10–12px radii. Design layers are now dispatched from `_STYLE_LAYERS` instead of an `if modern` branch. Fixes found while theming: `QPalette.Highlight` follows the muted token in shadcn (the primary would paint a white block over tree indents), the tree/table `selection-background-color` follows it too, and the floating canvas tool strip now takes its checked-chip colour from the preset accent (`overlay._chrome`) instead of a hardcoded indigo — pixel-identical for Classic, correct for every new preset. Matching `APP_CANVAS_THEMES` entries, updated `test_theme.py` + a new overlay test. |
| 2026-10-22 | **Engineering-hygiene pass** (the findings from the shadcn review). **Logging**: new `graphmatrix/log.py` — one rotating file in the state dir, warnings on stderr (never stdout: the MCP server speaks JSON-RPC there), `GRAPHMATRIX_LOG_LEVEL=DEBUG` for the noisy paths; `configure()` is called by `app.run()`, `cli.main()` and the MCP server. All 48 silently swallowed exceptions now log (meaningful messages in `core/io`, `core/ipc`, `core/analysis`, `app`; DEBUG in the canvas guards, which are deliberate). **Lint**: `[tool.ruff]` in `pyproject.toml` selects E/F/W/I/UP/B/BLE/SIM/RUF/S/C4/PIE with documented ignores, `ruff format` applied, 277 findings fixed (dead `# noqa`, `typing`→`collections.abc`, import order, `contextlib.suppress`, explicit `zip(strict=False)`, unused locals/imports, `ClassVar`); a `lint` job (ruff check + format --check + mypy) now gates CI, and Python **3.10** joined the test matrix. **Types**: mypy config as a ratchet over the modules that are clean today (`log`, `core/model`, `core/commands`, `core/plot_themes`) — `mypy src/graphmatrix` still reports the rest. **Dead code**: dropped `_guess()` in `fitting.py` (computed, never used), the shadowed duplicate `test_mcp_server_cli_options`, and undefined annotations (`plotting.Sequence`, `export.Any`). **Theme**: `digitize_dialog`'s baked `#202020` backdrop and `pyvista_canvas`'s baked canvas colours now follow the preset. **Structure**: the 450-line action/menu catalogue moved from `main_window.py` (2602 → 2145 lines) into `ui/menus.py` (`register_actions(window)`), action ids unchanged. **Version**: single-sourced from `graphmatrix.__version__` via `[tool.hatch.version]`. |
| 2026-10-22 | **UI/UX pass** (after restarting the app on the new theme). **Welcome page**: a **Recent projects** list (last 5, click to open, dead entries pruned; also **File → Open Recent**), backed by `ui/recent.py` + `ui/settings.py` (the QSettings guard moved out of `theme.py`). **Fewer dead panels**: the **Graph Editor** dock now appears with the first graph instead of sitting empty forever, and opening/creating a project clears the previous selection, the Properties rows and the status readout. **Status bar** names the open object (`Book1/Sheet1 · 200 rows × 2 columns`, `Graph · 1 panel(s) · 1 plot(s)`). **Keyboard**: `Ctrl+Tab` / `Ctrl+Shift+Tab` cycle tabs (View menu). **Persistence bug**: `save_preset()` now calls `settings.sync()` — an abrupt quit used to lose the theme choice (that is why a restart came back as Modern Dark), and an empty recent list round-trips as "no key" instead of `None`. **MCP hygiene**: `instance.unregister(pid)` only removes a file that still names that pid, and the app unregisters on `aboutToQuit`, so agent discovery no longer loses a live window. New tests: `test_recent.py`, `test_instance.py`, plus dock/status/tab-navigation smoke tests. Suite now **290 passed**, gates green. |
| 2026-10-22 | **CI repair after the first push.** Two failures, one mine and one older: (1) `test_log` pinned the absolute handler count, but pytest >= 9.1 attaches its own capture handler to loggers with `propagate=False` (ours is one) — the test now asserts what `configure()` *adds* (one file + one stderr handler, no duplicate pair on a second call). (2) The shortcut tests compared `QKeySequence.toString()`, which can never be portable on macOS: Qt parses the literal `"Ctrl"` in a sequence string into Command, while a `StandardKey` keeps `Qt::CTRL`. They now compare effective `QKeySequence` objects (through the same `StandardKey` where the app uses one) and check the tooltip with `NativeText`, the format the tooltip is built with. This macOS redness predates the shadcn commit (it came in with 838cbae "portable shortcuts"). |
| 2026-10-22 | **Windows liveness-probe fix.** CI on Windows died with a `KeyboardInterrupt` inside `pathlib` at 26% — the exact point where `test_instance.py` runs. Cause: `os.kill(pid, 0)` is **not** a liveness probe on Windows; signal 0 is `CTRL_C_EVENT`, so the call sent Ctrl+C to the process group (our own). New `instance.process_alive(pid)` uses `OpenProcess`/`GetExitCodeProcess` there (`STILL_ACTIVE`), keeps `os.kill` on POSIX (treating `EPERM` as alive), and refuses pid <= 0. Both call sites — `instance.get()` and the IPC stale-endpoint cleanup, which could have interrupted the GUI or the user's terminal — now use it. The shortcut tests also compare through `ui.actions.key_sequence()`, the helper that applies the macOS Ctrl-to-Command rewrite, instead of rebuilding `QKeySequence` themselves. |
