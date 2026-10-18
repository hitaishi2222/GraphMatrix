# GraphMatrix — Roadmap

Where `PLAN.md` records the locked decisions and the M0–M6 build order, this file
looks **forward**: the feature backlog, how it is sequenced, and the detailed plan
for the increment currently being built. `PLAN.md` stays the source of truth for
architecture and status; this file is the queue.

Status legend: ✅ shipped · 🔨 building now · 📋 planned · 💭 idea / not committed.

---

## 0. How to read this

- **Milestones M0–M6** in `PLAN.md` are done. This roadmap starts at **M7** and runs
  forward; **M7, M8, M9, and M10 are shipped**, and the M11 **linked-brushing v1**
  increment landed 2026-10-18 (see §6).
- Every item carries a **value / cost** guess and a **depends-on** note, so the order
  is arguable from the table alone.
- Shipped increments (§2–§4) keep their acceptance tests as a record; preview
  milestones (§5+) are one paragraph each until they reach the front of the queue.
- Guiding rule, unchanged from `PLAN.md` §1.3: win the common 80% (import → plot →
  fit → export) and keep it scriptable; do not chase Origin's long tail.

---

## 1. Backlog — next-level features (make it genuinely great)

| Idea | Value | Cost | Status | Notes |
|------|-------|------|--------|-------|
| Multi-panel figure layouts (grid of graphs, shared axes) | High | L | 📋 | Single most-requested Origin feature. |
| Graph insets / picture-in-picture axes | High | M | 📋 | Nested axes box on a graph. |
| Interactive fit region (drag X window on canvas) | High | M | 📋 | Reuses slope_between; drives fit/slope. |
| Linked brushing across graphs & sheet | High | L | ✅ M11 (v1) | Shared `BrushSelection`; orange tint on sheet rows + ring highlights on every affected canvas; click-a-point on a graph selects the row. Drag-window brushing still open. |
| Time machine (scrub undo history) | Low | M | 💭 | Replay commands to a point. |
| Column formulas with auto-recalculate | Medium | M | 📋 | Set Column Values that update on input change. |
| NetCDF import/export | Medium | M | 📋 | xarray optional extra. |
| Contour / heatmap from X-Y-Z matrix | High | L | 📋 | Needs matrix column type. |
| 3D surface / scatter / 3D fit | High | L | 📋 | Vispy/PyVista behind PlotCanvas. |
| Box / violin plots | Medium | M | 📋 | Stats-forward. |
| Color-mapped scatter (3rd variable -> color) | High | M | 📋 | Color column + colorbar. |
| LaTeX / mathtext in labels and annotations | Medium | S | 📋 | matplotlib mathtext nearly free. |
| Confidence / prediction bands on fits | Medium | M | ✅ Shipped (M7-M9 pass). |
| Peak integration (area per fitted peak) | Medium | S | ✅ M10 (`peaks` `integrate` + Peaks dialog + recipes). |
| Natural-language command grammar | Medium | M | 📋 | Builds on palette. |
| Live / streaming data board | Medium | L | 💭 | Tail file/serial port, auto-refresh. |
| Figure diff (before/after) | Low | M | 💭 | Render two graphs and diff. |
| Units engine | Medium | L | 💭 | Dimensional tracking + conversion. |
| Signed installers + auto-update | High | L | 📋 | OS certs; CI already builds bundles. |
| Crash reporting (opt-in) | Low | M | 💭 | After first public build. |
| Plugin host + versioned API | Medium | M | 📋 | Stability promise. |
| Recipe editor UI | Medium | M | 📋 | Form-based editor for JSON recipes. |
| Headless CLI pipelines | Medium | M | ✅ | `graphmatrix run pipeline.yaml`. |
| Arrow-backed column store | Medium | L | 💭 | Only when dataset forces it. |
| GPU canvas for >=1e6 points | High | L | 💭 | Benchmark before committing. |
| Multi-dataset batch statistics table | Medium | M | ✅ M10 (`descriptive.batch_summary` + Analyze → Batch Statistics). |
| Color-mapped scatter (3rd variable -> color) | High | M | ✅ M10 (`PlotSpec.z` + `cmap`, colourbar). |
| Contour / heatmap from X-Y-Z | High | L | ✅ M10 (`grid_xyz` + `tricontourf`; scattered XYZ, no matrix type needed). |
| 3D surface / scatter / 3D fit | High | L | 🟩 M10 shipped scatter+surface on **PyVista** (locked backend); 3D *fit* still queued. |

---

## 1. Backlog (core)

Grouped by area, roughly highest value first. "Cost" is a coarse T-shirt size for a
first working version, not the polished one.

### 1.1 Graph interaction (M7 — shipped ✅)

| Feature | Value | Cost | Notes |
|---------|-------|------|-------|
| Dashed / dotted line styles | High | S | Small model + canvas + export change; unblocks reference-line UX. |
| Horizontal & vertical reference lines (H-lines / V-lines) | High | M | New `ReferenceLine` model on the layer, canvas + export + UI list. |
| Hover point info (crosshair + nearest-point readout) | High | M | Canvas-only; needs x-sorted series for fast search. Not exported. |
| Slope between two X values ("range fit") | High | S | Core `slope_between`; annotate slope on the graph. |

### 1.2 Analysis (M10)

| Feature | Value | Cost | Notes |
|---------|-------|------|-------|
| Baseline corrections: linear, ALS, rolling-ball, rubber-band, median | High | M | ✅ Shipped in M7 (`core.analysis.signal`). |
| Fit-region selection (fit only over an X window) | High | M | ✅ M10 — numeric x-min/x-max in regression/nonlinear/slope dialogs + recipes. |
| Confidence / prediction bands on fits | Medium | M | ✅ Shipped (lmfit `eval_uncertainty`; Fit ±1σ curves). |
| Multi-dataset batch statistics table | Medium | M | ✅ M10 (`descriptive.batch_summary`; row per column, Recover Analyst-style). |
| Peak integration (area per fitted peak) | Medium | S | ✅ M10 (prominence-base bounds + dialog/recipe option). |
| Derivative spectroscopy (1st/2nd) helper | Low | S | `differentiate` exists; add presets/labels. |

### 1.3 Worksheet & data (M12)

| Feature | Value | Cost | Notes |
|---------|-------|------|-------|
| Column-sort / filter by expression, virtual rows | Medium | M | Must keep row indices stable for graph sources. |
| Worksheet calculations: set values, normalize, sort within selection | Medium | M | Origin's "Set Column Values" is its workhorse. |
| Auto-recalculate formulas when inputs change | Medium | M | Currently formulas evaluate on demand. |
| NetCDF import/export | Medium | M | Planned in §1.1 of PLAN; `xarray` optional extra. |
| Image / raster plane import (grayscale → Z matrix) | Low | L | Road to contour/heatmap; needs a matrix column type. |
| Date/time axis formatting from `Date` columns | Low | M | Tick locators + parser; matplotlib already does the display side. |

### 1.4 Plot types (M10)

| Feature | Value | Cost | Notes |
|---------|-------|------|-------|
| Contour / heatmap from an X–Y–Z matrix | High | L | ✅ M10 — scattered XYZ via `grid_xyz` / `tricontourf`; matrix *column type* (true raster import) still queued. |
| 3D surface / scatter / 3D fit | High | L | ✅ M10 scatter + surface on **PyVista** (locked backend); 3D *fit* queued. |
| Box / violin plots | Medium | M | Stats-forward, cheap via matplotlib; canvas version needs custom items. |
| Pie / doughnut | Low | S | Rare in lab work; export-only may suffice. |
| Waterfall / stacked offset lines | Medium | S | Offset each series by a constant; very useful for spectra. |
| Color-mapped scatter (third variable → color) | High | M | ✅ M10 — `PlotSpec.z` + `cmap` + colourbar on canvas and export. |

### 1.5 Publication & layout (M11)

| Feature | Value | Cost | Notes |
|---------|-------|------|-------|
| Graph insets / picture-in-picture axes | High | M | Deferred from M4; a nested axes box. |
| Multi-panel figure layout (grid of graphs) | High | L | The single most-requested Origin feature after insets. |
| LaTeX / mathtext in labels and annotations | Medium | S | matplotlib mathtext is nearly free; canvas falls back to plain. |
| Error-bar / fill-between style polish, minor ticks, tick direction | Medium | S | ✅ Shipped (minor ticks + tick direction; error-bar polish remains). |
| CMYK-safe PDF export | Low | M | Needs a real CMYK pipeline (Ghostscript); documented gap in PLAN. |

### 1.6 Scripting & automation (M13)

| Feature | Value | Cost | Notes |
|---------|-------|------|-------|
| Third-party plugin directory + versioned API | Medium | M | PLAN open question #3; ship the host and a stability promise. |
| Recipe editor UI | Medium | M | Today recipes are JSON on disk; a form-based editor lowers the barrier. |
| Scheduled / headless CLI (`graphmatrix run pipeline.yaml`) | Medium | M | Core is already Qt-free; mostly argument plumbing. |
| Macro library with named steps | Low | M | Extends the recorder. |

### 1.7 Engineering & ship (M14)

| Feature | Value | Cost | Notes |
|---------|-------|------|-------|
| Arrow-backed column store | Medium | L | PLAN D4/D6 debt; only when a dataset forces it. |
| Vispy/GPU canvas for ≥1e6 points | High | L | Keep behind `PlotCanvas`; benchmark before committing. |
| Signed installers + auto-update | High | L | Needs OS certs; CI already builds signed-ready bundles. |
| Crash reporting, opt-in telemetry | Low | M | After first public build. |

### 1.8 Differentiating ideas

The "what would make GraphMatrix more than a smaller Origin" list. M8 and M9 shipped the
first five; the rest are queued and scheduled in §6–§7.

| Idea | Value | Cost | Status | Notes |
|------|-------|------|--------|-------|
| Provenance & reproducibility bundle | High | M | ✅ M8 | `Command.describe()` + `ProvenanceLog`; a folder with project, CSVs, figures, `methods.md`, `reproduce.py`. |
| Figure-as-code round-trip | High | M | ✅ M8 | `project_to_script`; the bundle's `reproduce.py`, also exportable on its own. |
| Journal figure presets | High | S | ✅ M8 | `core/journals.py`; Nature/Science/APS/IEEE sizes + typography; applied per graph and honoured on export. |
| Curve digitizer (image → data) | Medium | M | ✅ M9 | `core/analysis/digitize.py` + dialog; darkness or colour isolation, axis-anchor calibration. |
| Command palette ("Ask GraphMatrix" v1) | Medium | S | ✅ M9 | Fuzzy action search, `Ctrl+Shift+P`. |
| Natural-language command grammar | Medium | M | 📋 | "plot Y1 vs X1", "baseline ALS" → API calls. Builds on the palette. |
| Interactive fit region | High | M | 📋 | Drag an X window on the canvas → fit/slope. Numeric regions shipped in M10; the gesture would fill the same fields. |
| Live / streaming data board | Medium | L | 💭 | Tail a file or serial port and auto-refresh a graph (`QFileSystemWatcher`). |
| Linked brushing across graphs & sheet | High | L | ✅ M11 (v1) | Shared selection; highlight a point in every view at once. Drag-window brushing still open. |
| Time machine (scrub the undo history) | Low | M | 💭 | The undo stack as a slider; replay commands to a point. |
| Figure diff (before / after) | Low | M | 💭 | Render two graphs and diff them; useful for review and regressions. |
| Units engine | Medium | L | 💭 | Dimensional tracking + conversion on display; invasive to the model. |

---

## 2. Shipped — M7: graph interaction & range tools ✅

**Theme:** make the canvas *readable and measurable*, not just pretty. Everything
here is pan/zoom-friendly, undoable, serialized in the project, and reproduced by the
matplotlib exporter.

### 2.1 Deliverables

1. **Dashed / dotted line styles.**
   - `PlotSpec.line_style` (`solid` · `dash` · `dot` · `dashdot` · `longdash`),
     serialized and template-captured.
   - Rendered in pyqtgraph (`Qt.PenStyle`) and matplotlib (`linestyle`).

2. **Reference lines (H-lines & V-lines).**
   - New `ReferenceLine` model (`orientation` h/v, `position`, `color`, `width`,
     `line_style`, `label`), attached to a `Layer` so it inherits that layer's axes.
   - `AddReferenceLineCommand` / `RemoveReferenceLineCommand`, fully undoable.
   - Canvas `add_reference_line(...)` via `pg.InfiniteLine`; matplotlib `axhline` /
     `axvline` in export.
   - Graph sidebar list with add/remove; a small dialog chooses orientation, value,
     colour, width, style, and an optional label.

3. **Hover point info.**
   - Canvas crosshair (a faint V and H line) following the mouse plus a readout of
     the **nearest data point**: series legend, `x`, `y`.
   - Fast nearest-point search: series are kept x-sorted once, so a hover costs a
     `searchsorted` plus a few neighbours, not an O(n) scan.
   - Toggle (View/Graph menu) and remembered per canvas. Export ignores it.

4. **Slope between an X range.**
   - Core `slope_between(x, y, x0, x1)` → `AnalysisResult` with slope, intercept, R²,
     standard error, Δy/Δx over the window, and a "Fit" curve.
   - **Analyze → Slope / Range Fit…** dialog; the result can be added to the graph and
     offers a one-click **"Annotate on graph"** that writes `slope = … (R² = …)` as a
     text annotation (undoable).

5. **Baseline corrections.**
   - `core.analysis.signal`: `baseline_linear`, `baseline_als` (asymmetric least
     squares), `baseline_rolling_ball`, `baseline_rubber_band`, `baseline_median`,
     plus a `baseline_correction(method=…)` dispatcher.
   - Each returns `Baseline` + `Corrected` curves, so the Signal dialog's existing
     "add to graph / add as columns" path works unchanged.
   - Signal dialog gains a baseline-method selector; recipes can name the method.

### 2.2 Design notes

- **Why reference lines live on the `Layer`, not the `Graph`:** a layer owns an axes
  configuration (scale, limits, dual-Y). A line at `y = 0` means something different
  on a log layer than on its neighbour. Layer scope matches that.
- **Why hover is canvas-only:** the readout is an interaction, not content. Keeping it
  out of the model means no churn in the project format and no export complexity.
- **Why slope is a core function, not a canvas gesture:** it composes. The same
  function powers the dialog, the (planned) drag-to-fit gesture, and a script line.
- **Baseline stays in `signal.py`:** it already owns detrending-style operations; a
  new module would split closely related code for no gain.

### 2.3 Acceptance tests

- Model round-trip: `PlotSpec.line_style` and `Layer.ref_lines` survive
  `to_dict`/`from_dict`.
- Commands: add/remove a reference line is one undoable step each.
- `slope_between` recovers a known slope to 1e-9 and reports the window bounds.
- Every `baseline_correction` method returns a `Corrected` curve that is flatter
  (smaller std) than the raw signal on a synthetic ramp-plus-peak.
- Export: a graph with a dashed series and one H-line + one V-line writes a PDF
  without error.
- Headless UI: add an H-line and a V-line through the `GraphView`, toggle hover, run
  the slope dialog, and confirm each is reflected in the model.

### 2.4 Explicitly out of scope for M7 (now M10/M11 work)

- Dragging reference lines with the mouse (add/remove/edit numerically first).
- Hover readout in exported files.
- Region-select-to-fit with the mouse (see §6, interactive fit region).

---

## 3. Shipped — M8: provenance, reproducibility & journal output ✅

**Theme:** a figure is only trustworthy if someone else — or future you — can rebuild
it. M8 turns the command stream into a methods paragraph and a folder that reproduces
the whole project.

### 3.1 Deliverables

1. **Command provenance.**
   - `Command.describe() -> str | None`; meaningful commands override it (plots,
     reference lines, annotations, renames, column writes, macros), bookkeeping
     commands stay silent.
   - `ProvenanceLog` (`core/provenance.py`) records those descriptions **plus**
     explicit analysis results and imports, and renders `methods.md` grouped into
     Data / Analysis / Operations / Notes.
   - Attached to the live `CommandStack`, so every edit is captured without UI code
     sprinkling calls everywhere.

2. **Figure-as-code.**
   - `core/code_export.project_to_script(project)` emits a Python script using only
     the console namespace (`api`, `PlotSpec`, `Layer`, `ReferenceLine`, `Annotation`).
     It rebuilds workbooks, columns (including masks and units), and every graph.
   - NaN/inf round-trip as literals; CSV copies are the compact representation.

3. **Analysis bundle.**
   - `core/report.export_analysis_bundle(project, provenance, out_dir)` writes
     `project.rsproj`, `data/<Book>__<Sheet>.csv`, `figures/<Graph>.<fmt>`,
     `reproduce.py`, `methods.md`, and `provenance.json`.

4. **Journal presets.**
   - `core/journals.py`: Default + Nature / Science / APS / IEEE (single & double
     column) — width/height in mm, DPI, font/label/legend/tick sizes, and recommended
     line & marker sizes.
   - `apply_journal_preset(graph, name)` restyles a graph's plots (idempotently) and
     records the preset on `Graph.journal_preset`; the exporter reads it and wraps
     rendering in `matplotlib.rc_context` with the preset's typography, defaulting the
     figure size to the preset.

5. **UI wiring.**
   - **Graph → Journal Preset ▸** (checkable submenu, kept in sync with the active
     graph, undoable via a macro of `SetAttributesCommand`).
   - **Export → Export Project as Python Script…**, **Export → Export Analysis
     Bundle…**, **Tools → Analysis Methods…** (renders `methods.md`).

### 3.2 Design notes

- **Provenance is fed, not inferred.** Structural commands describe themselves; the
  analysis dialogs hand over their `AnalysisResult` at the point it is produced, where
  the summary is richest. This avoids guessing a fit's meaning from a column add.
- **The bundle is plain files.** Data and figures survive without GraphMatrix installed;
  only `reproduce.py` needs the app.
- **Presets set absolute values, not scales.** Applying a preset twice must not
  compound line widths, so `apply_journal_preset` assigns rather than multiplies.
- **`journal_preset` lives on `Graph`,** not `Layer`, because physical size and base
  font are properties of the whole figure.

### 3.3 Acceptance tests

- `ProvenanceLog` records described commands and ignores silent ones; `methods.md`
  groups entries and tolerates non-numeric summaries; JSON round-trips.
- `project_to_script` output, executed in a fresh project namespace, reproduces graph
  titles, presets, scales, labels, plots, reference lines, annotations, units, and
  masks.
- A bundle writes all parts and `methods.md` contains a recorded analysis.
- `apply_journal_preset` restyles plots idempotently, survives serialization, and
  `export_graph` honours the preset (dimensional + rcParams checks).
- Headless UI: apply a preset through the menu action (checked, undoable), and run
  the palette filter.

### 3.4 Explicitly out of scope for M8

- Persisting provenance inside the `.rsproj` (it lives with a session/bundle).
- Round-tripping *analysis steps* (as opposed to rebuilt state) — the bundle is
  state-based, not a literal step log.
- Live-updating `methods.md` (it is written on export).

---

## 4. Shipped — M9: curve digitizer & command palette ✅

**Theme:** get data *in* from imperfect sources, and get commands *fast*.

### 4.1 Deliverables

1. **Curve digitizer.**
   - `core/analysis/digitize.py::digitize_curve(image, x_anchors, y_anchors, …)`:
     reads a PNG/JPEG/TIFF (or ndarray), builds a darkness mask (or isolates a target
     colour with a tolerance), walks each pixel column between the x-anchors, and
     inverts the linear pixel→data map defined by two calibration points per axis.
   - Options: `threshold`, `invert` (light-on-dark), `color` + `tolerance`,
     `x_start`/`x_end` region restriction, and an `aggregate`
     (median/mean/top/bottom) for thick or multi-pixel traces.
   - Returns an `AnalysisResult`, so the existing "add as columns / add to graph"
     path works unchanged.

2. **Digitize dialog.**
   - **Analyze → Digitize Curve from Image…**: load an image, click the four anchors
     in order (X1, X2, Y1, Y2; editable pixel spinboxes as a fallback), type the data
     value for each, set extraction options, and Extract.

3. **Command palette.**
   - `ui/command_palette.py` fuzzy-searches every registered action (subsequence
     match that rewards prefixes and word starts) and runs the chosen one.
   - **Tools → Command Palette…** (`Ctrl+Shift+P`).

### 4.2 Design notes

- **Digitizing is calibration, not guesswork.** Two anchors per axis define an exact
  affine map; everything else is mask selection. The result is only as good as the
  anchors, so the report says so and the points can be overlaid to check.
- **The palette is "Ask GraphMatrix" v1.** A safe, useful index over what already exists;
  a natural-language grammar (§1.8) is the next layer once the command surface is
  stable and discoverable.

### 4.3 Acceptance tests

- `digitize_curve` recovers a known slope from a synthetic black-on-white line;
  colour isolation picks one trace from a noisy background; region restriction
  bounds x; identical axis anchors raise.
- Headless UI: the digitize dialog, fed a synthetic image and anchors, returns a curve
  with the expected point count.

### 4.4 Explicitly out of scope for M9

- Auto-detecting axes/text (OCR-style) — manual anchors first.
- Log-axis calibration (the affine map is linear; a log axis would need a second map).
- Multi-curve extraction in one pass (isolate colours one at a time for now).

---

## 5. Shipped — M10: analysis depth, colour & 3D plot types ✅

**Decisions locked before build (2026-10-18):**
- **3D backend: PyVista** (open question #5) — `pyvista`/`pyvistaqt` host the live
  3D scene behind the `PlotCanvas` interface (optional `plot3d` extra); publication
  export stays matplotlib-3D, so PDF/SVG output remains vector.
- **Fit regions are numeric** (open question #3) — x-min/x-max fields in the
  regression / nonlinear / slope dialogs, not a drag gesture. A drag gesture may
  still come later; it would *set* these same numbers.

**Theme:** the third data value flows from the worksheet to the canvas, fits
respect a numeric X window, and every fitted peak reports its area.

### 5.1 Deliverables

1. **Numeric fit regions.**
   - `linear_fit`, `polynomial_fit`, and `fit_model` gained `x_min`/`x_max`
     (open ends allowed, reversed bounds swapped); reports say `Fit region: a ≤ x ≤ b`.
   - Regression and Nonlinear-Fit dialogs have "Fit region: X from / X to" fields;
     recipes accept `x_min`/`x_max` for the `regression` and `fit` ops.
   - `slope_between` already scoped by bounds (M7) — this completes the trio.

2. **Peak integration.**
   - `peaks.find_peaks_result(..., integrate=True)` adds a per-peak **Area** column:
     trapezoidal area between the peak's prominence bases (the valleys it rises out
     of), bound-minimum subtracted as a local baseline.
   - Peak Analysis dialog gained an "Integrate area per peak" check; recipes accept
     `integrate: true` on the `peaks` op.

3. **Batch statistics table.**
   - `descriptive.batch_summary(project)` — one row per numeric column across every
     sheet: N, Missing, Mean, Std Dev, Min, Median, Max.
   - **Analyze → Batch Statistics…** (recorded in provenance).

4. **Colour-mapped scatter, heatmap, contour (the Z column finally plots).**
   - `PlotStyle` gained `color-mapped scatter`, `heatmap`, `contour`; `PlotSpec`
     carries `z` (colour/value column) and `cmap`; `Layer.z_label` names the
     colourbar. All serialized, template-captured, and emitted by `project_to_script`.
   - `plotting.grid_xyz` grids scattered X-Y-Z (linear + nearest fill) for
     heatmap/surface; `contour` uses matplotlib's `tricontourf` directly.
   - Colour-mapped scatter needs **no gridding** (`c=z` scatter); heatmap and contour
     degrade gracefully to a plain scatter when no Z column is set.

5. **3D scatter & surface on PyVista.**
   - `PlotStyle` gained `3d scatter` and `3d surface`; `ui/canvas/pyvista_canvas.py`
     implements the `PlotCanvas` interface on `pyvistaqt.QtInteractor` (orbit/zoom
     for free), with 2D styles drawn in the z = 0 plane so mixed graphs never blank.
   - `create_canvas("pyvista")`; `GraphView` picks/keeps/returns the right backend
     automatically as styles are edited, falling back to the colour-degraded
     matplotlib view if the `plot3d` extra is missing.
   - Export renders 3D styles through matplotlib 3D (`plot_surface` /
     `scatter3D`) — vector PDF, same model, one exporter.

### 5.2 Design notes

- **One renderer for Z styles.** `render_xyz_mpl` (in `core.io.export`) is shared by
  the live matplotlib canvas and the exporter, so colourbars, grids, and 3D surfaces
  stay WYSIWYG without core importing the UI.
- **The Z-value path is generic.** Any numeric column can supply the colour / height;
  it does not need the `Z` *type* — a `Y` column works the same way.
- **Numeric regions beat gestures... for now.** Gesture-to-fit stays a candidate
  (§6) but would fill the same dialog fields.

### 5.3 Acceptance tests

- Windowed fits recover the segment slope on a two-segment line to 1e-9 and the
  nonlinear window centres the correct crest; "Fit region" appears in reports.
- Peak integration recovers a Gaussian's analytic area (amplitude·√(2π)·σ) to < 1%
  and reports two positive areas for a two-peak spectrum.
- `batch_summary` skips text columns and counts masked/missing values.
- `grid_xyz` recovers a sampled plane to < 0.15 and stays all-NaN-safe on degenerate
  input. Model round-trips for `PlotSpec.z`/`cmap` and `Layer.z_label`.
- Export of every Z style (colour-mapped, heatmap, contour, 3D scatter, 3D surface)
  writes PNG **and** vector PDF via the normal exporter.
- Headless: GraphView re-renders a `3d surface` graph on the PyVista canvas, the
  AddPlotDialog's Z combo gates on style, and `SetAttributesCommand` round-trips `z`.

### 5.4 Explicitly out of scope for M10

- Camera-aware export (matplotlib 3D uses a default view; the live PyVista camera
  orientation is not transferred yet).
- Box / violin, waterfall, pie (queued, §1.4); matrix *column type* (grid_xyz covers
  scattered X-Y-Z first).
- Drag-a-region gesture (numeric bounds are the locked UX).

## 5. M10 — analysis depth & plot types (preview)

Extend the analysis toolkit toward "get the number and put it on the figure":
fit-region selection in the regression/nonlinear dialogs, confidence/prediction bands,
per-peak integration, and a batch statistics table. Alongside it, the highest-value
plot types: color-mapped scatter (third variable → colour) and contour/heatmap from an
X–Y–Z matrix — both need a `Z`/colour value flowing from the worksheet into the canvas.
3D stays deferred behind `PlotCanvas` and ships only when a GPU backend (Vispy/PyVista)
is actually wired.

## 6. M11 — interactive superpowers (preview → partially shipped)

The differentiation tier. **Interactive fit region** (drag an X window on the canvas →
run a fit or slope, reusing `slope_between`; with numeric regions now shipped in M10,
the gesture would simply fill those same fields); **linked brushing** (a shared selection
highlighted across every open graph and worksheet); **live data** (watch a file or
serial source and auto-refresh a graph). These share a need for a small selection/cursor
model on top of the command stack, so they are sequenced together.

**Shipped 2026-10-18 — linked brushing v1.** A non-persisted, non-undoable
`ui.brushing.BrushSelection` (source → row indices) drives every view: worksheet rows
are tinted orange (`WorksheetView.set_row_highlight`), and each canvas overlays ring
markers on the affected points of every series whose source matches
(`PlotCanvas.set_brush` — matplotlib implements it; pyqtgraph/PyVista degrade to
no-op). Clicking near a plotted point picks the nearest point within 12 px and
broadcasts its worksheet row (`canvas.point_picked` → `GraphView.brush_requested` →
MainWindow hub), so canvas→sheet and sheet→canvas are both live, including across
multiple graphs of the same sheet. The overlay survives re-renders. Not yet:
drag-window brushing, value-range brushing, highlighting across *derived* series
(fit curves) mapped back to rows.

## 7. M12 — worksheet, data & units (preview)

Round out the worksheet as a data tool: set-column-values/sort/normalize, live formula
recalculation, NetCDF I/O, date-aware axes, and the **units engine** (dimensional
tracking + display conversion). Larger and more orthogonal than M7–M10; the main risk
is row-index stability and the units engine's reach into the model, since graph sources
reference columns by name.

## 8. M13 — scripting/automation & M14 — ship (preview)

Automation polish (plugin host + versioned API, recipe editor, headless CLI) and
engineering/ship hardening (Arrow store, GPU canvas, signed installers, telemetry).
Sequenced by external dependencies — certs, a real large dataset, a GPU decision — not
by code effort. The **natural-language command grammar** and **time machine** land here
or earlier if the palette/time-travel UX earns its keep.

---

## 9. Open questions (carried forward and new)

1. **Natural-language commands (M13):** a fixed grammar ("plot A vs B", "baseline …")
   vs a looser matcher. Proposal: fixed grammar first, grow from real usage.
2. **Provenance scope:** keep it session/bundle-only (current) or persist it in the
   project for audit? Revisit if teams ask for signed reproduction.
3. **Region selection UX:** ✅ **resolved (2026-10-18) — numeric bounds.** The M10
   fit-region fields are the UX; a drag gesture remains an M11 candidate that would
   populate those same fields.
4. **Arrow migration:** still deferred (PLAN open question #2); nothing in M7–M11
   forces it.
5. **3D backend:** ✅ **resolved (2026-10-18) — PyVista**, chosen over Vispy and VTK:
   Python-first, VTK render window embeds directly in PySide6 via `pyvistaqt`, and
   publication export keeps matplotlib's vector 3D backends. Live 3D = PyVista;
   export = matplotlib 3D.

---

## 10. Changelog

| Date | Change |
|------|--------|
| 2026-10-15 | Roadmap created. Backlog grouped by area with value/cost; M7 (graph interaction & range tools) detailed and marked in progress. |
| 2026-10-15 | M7 shipped. Added §1.8 differentiating ideas; detailed and shipped M8 (provenance, reproducibility & journal output) and M9 (digitizer & command palette); renumbered the preview milestones. |
| 2026-10-17 | WYSIWYG pass: matplotlib-backed canvas (live view == export), double-click resets zoom, default title no longer shows "GraphN", flat toolbar/sidebar buttons, Wayland/Hyprland tiling fix. |
| 2026-10-17 | Publication polish: Layer.minor_ticks + Layer.tick_direction (model, serialization, export, canvas, UI). |
| 2026-10-18 | M10 shipped: numeric fit regions (regression/nonlinear/recipes), peak integration, batch statistics table, colour-mapped scatter / heatmap / contour (`PlotSpec.z` + `cmap`, colourbar, `grid_xyz`), and **PyVista locked as the 3D backend** (`3d scatter` / `3d surface` live canvas behind `PlotCanvas`, matplotlib-3D export). Open questions #3 (numeric regions) and #5 (PyVista) resolved. New tests in `test_m10.py`; suite at **143 passed**. |
