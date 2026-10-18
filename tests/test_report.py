"""Analysis bundle export + figure-as-code round trip (M8)."""

from __future__ import annotations

import numpy as np

from graphmatrix.core.analysis.result import AnalysisResult
from graphmatrix.core.model import ColumnType, Graph, PlotSpec, PlotStyle, Project, Workbook, Worksheet
from graphmatrix.core.provenance import ProvenanceLog
from graphmatrix.core.report import export_analysis_bundle
from graphmatrix.core.scripting.api import GraphMatrixAPI, make_namespace


def _project() -> tuple[Project, Graph]:
    project = Project("Bundle Demo")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    x = np.linspace(0.0, 1.0, 20)
    sheet.add_column("X1", ColumnType.X, x, units="s")
    sheet.add_column("Y1", ColumnType.Y, np.sin(3 * x), units="V")
    graph = project.add_graph(Graph("Graph1", title="Sine"))
    graph.first_layer.add_plot(
        PlotSpec("Book1/Sheet1", "X1", "Y1", style=PlotStyle.LINE_SYMBOL, legend="sin")
    )
    return project, graph


def test_bundle_writes_every_part(tmp_path):
    project, _ = _project()
    log = ProvenanceLog()
    log.record_import("run1.csv", "Book1")
    log.record_analysis(AnalysisResult("fit", "Linear Fit", summary={"slope": 2.0}), source="Book1/Sheet1")
    bundle = export_analysis_bundle(project, log, tmp_path / "out", figure_formats=("png",))

    root = bundle.root
    for name in ("project.rsproj", "reproduce.py", "methods.md", "provenance.json"):
        assert (root / name).exists(), name
    assert (root / "data" / "Book1__Sheet1.csv").exists()
    assert (root / "figures" / "Graph1.png").exists()
    assert "Linear Fit" in (root / "methods.md").read_text()


def test_reproduce_script_rebuilds_figures(tmp_path):
    project, _ = _project()
    bundle = export_analysis_bundle(project, None, tmp_path / "out", figure_formats=())
    script = (bundle.root / "reproduce.py").read_text()

    replay = Project("Replay")
    api = GraphMatrixAPI(replay)
    namespace = make_namespace(api)
    namespace["api"] = api
    exec(compile(script, "<reproduce>", "exec"), namespace)

    graph = replay.graph("Graph1")
    assert graph is not None
    assert graph.title == "Sine"
    spec = graph.first_layer.plots[0]
    assert (spec.x, spec.y, spec.legend) == ("X1", "Y1", "sin")
    sheet = replay.sheet("Book1/Sheet1")
    assert sheet.column("Y1").units == "V"
    assert len(sheet.column("Y1")) == 20


def test_bundle_without_provenance_skips_methods(tmp_path):
    project, _ = _project()
    bundle = export_analysis_bundle(project, None, tmp_path / "out", figure_formats=())
    assert not (bundle.root / "methods.md").exists()
    assert "project" in bundle.files
