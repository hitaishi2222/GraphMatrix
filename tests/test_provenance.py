"""Provenance log tests (M8)."""

from __future__ import annotations

from graphmatrix.core.analysis.result import AnalysisResult
from graphmatrix.core.commands import AddGraphCommand, AddPlotCommand, CommandStack
from graphmatrix.core.model import ColumnType, Graph, PlotSpec, Project, Workbook, Worksheet
from graphmatrix.core.provenance import ProvenanceLog, format_summary


def _project():
    project = Project("P")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    sheet.add_column("X1", ColumnType.X, [1.0, 2.0, 3.0])
    sheet.add_column("Y1", ColumnType.Y, [1.0, 4.0, 9.0])
    return project, book, sheet


def test_silent_commands_are_not_recorded():
    project, _, _ = _project()
    stack = CommandStack()
    log = ProvenanceLog()
    log.attach(stack)
    stack.push(AddGraphCommand(project, Graph("Graph1")))
    assert log.count == 0


def test_described_commands_are_recorded():
    project, _, _ = _project()
    stack = CommandStack()
    log = ProvenanceLog()
    log.attach(stack)
    graph = Graph("Graph1")
    stack.push(AddGraphCommand(project, graph))
    stack.push(AddPlotCommand(graph, graph.first_layer, PlotSpec("Book1/Sheet1", "X1", "Y1")))
    assert any("Plotted" in entry.text for entry in log.entries)


def test_methods_markdown_groups_into_sections():
    log = ProvenanceLog()
    log.record_import("run42.csv", "Book1")
    log.record_analysis(AnalysisResult("fit", "Gaussian Fit", summary={"R2": 0.998}), source="Book1/Sheet1")
    log.record_note("Excluded run 7 — detector glitch")
    md = log.methods_markdown(Project("Demo"))
    assert md.startswith("# Methods — Demo")
    assert "Imported run42.csv" in md
    assert "## Data" in md and "## Analysis" in md and "## Notes" in md
    assert "Gaussian Fit" in md and "R2 = 0.998" in md


def test_methods_markdown_without_entries():
    md = ProvenanceLog().methods_markdown(Project("Empty"))
    assert "No recorded operations" in md


def test_roundtrip_serialization():
    log = ProvenanceLog()
    log.record_import("a.csv", "Book1")
    again = ProvenanceLog.from_dict(log.to_dict())
    assert [e.text for e in again.entries] == ["Imported a.csv"]
    assert again.entries[0].kind == "import"


def test_format_summary_tolerates_non_numeric():
    assert format_summary({"n": 5, "note": "hi"}) == "n = 5; note = hi"
