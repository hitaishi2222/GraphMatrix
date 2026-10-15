# Respot — Detailed Plan

A cross-platform, Python-first scientific data analysis and graphing GUI, positioned
as an open alternative to OriginPro.

This document is the source of truth for **what we are building, why we chose the
stack we did, and in what order**. It is updated as milestones close.

---

## 0. Current status

_Last updated: 2026-10-15 (after the M8/M9 provenance-and-digitizer pass). Forward plan
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
| Deferred — 3D | ⚪ Not started | Still planned after M2, behind the `PlotCanvas` interface. |

**Test status:** `python -m pytest -q` → **120 passed**, no display required
(`QT_QPA_PLATFORM=offscreen`). Covers the model/formula layer, I/O round-trips,
the full analysis toolkit (incl. deconvolution and the baseline methods), recipes
+ the batch pipeline, publication export (incl. dual-axis/annotations, dashed lines,
reference lines and journal presets), graph templates, scripting/macro replay,
reference lines + hover + slope, provenance + bundle round-trip, the digitizer, and a
headless end-to-end UI smoke test (incl. the command palette and digitize dialog).

**Honest caveats:** genuinely deferred (not bugs), and the reasons are external or
out of scope:

- **Vispy/GPU backend** — not wired; the `PlotCanvas` interface keeps the door open.
  Performance for >1e5 points is untested (LOD downsampling is on by default).
- **CMYK output** — matplotlib's vector backends cannot emit CMYK directly; not done.
- **Graph insets / layered annotations** — text annotations exist; insets do not.
- **Installers, code-signing, notarization, auto-update** — require OS tooling and
  certificates we cannot produce here; CI already builds signed-ready bundles.
- **Apache Arrow-backed columns (D4)** — storage is still numpy; Arrow is used only
  for Parquet I/O. Migrating the column store is a large, orthogonal refactor.

Treat M1–M5 as "usably functional with the common 80% done," not "finished."

---

## 1. Vision and scope

### 1.1 What Respot is

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
| D9 | Plugin system | **Modules exposing `register(context)`** in `respot/plugins/` | Zero-config discovery; same mechanism can later load third-party plugins from a user directory. |
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
src/respot/
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
{ "format": "respot-project", "version": 1, "name": "Untitled",
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

A plugin is a module under `respot/plugins/` exposing:

```python
def register(context) -> None:
    # context: window, registry, commands, plugins_menu
```

`load_plugins()` imports each module, calls `register`, and reports failures without
crashing startup. Plugins may import Qt (they are a UI concern); they should reach the
model through `context.commands`, not by mutating it directly.

**Scripting (M5):** the same `Command` objects are the scripting vocabulary. An embedded
`code.InteractiveConsole` gets a namespace exposing the project, the command stack, and
convenience API; "record macro" simply serializes the command log. This is Respot's
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

### Deferred — 3D
Slots in **after M2**, reusing the canvas interface:
- Evaluate **Vispy/PyVista** (Python-first, Qt-embeddable) vs **VTK** (heavier, most capable).
- Surface/contour/3D-scatter/3D-fit on the same `Graph`/`Layer` model extended with a `z` axis.
- Keep it behind the existing `PlotCanvas` abstraction so 2D never regresses.

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
