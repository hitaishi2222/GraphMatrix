"""Project save/open round-trip tests."""

from __future__ import annotations

import numpy as np

from graphmatrix.core.model import Column, ColumnType, Graph, Project, Workbook, Worksheet


def _sample_project() -> Project:
    project = Project("Demo")
    book = project.add_workbook(Workbook("Book1"))
    sheet = book.add_sheet(Worksheet("Sheet1"))
    sheet.add_column("X1", ColumnType.X, np.linspace(0, 2 * np.pi, 50), units="rad")
    sheet.add_column("Y1", ColumnType.Y, np.sin(np.linspace(0, 2 * np.pi, 50)), comment="sin(x)")
    project.add_graph(Graph("Graph1"))
    return project


def test_save_creates_file(tmp_path):
    path = tmp_path / "demo.rsproj"
    _sample_project().save(path)
    assert path.exists()
    assert path.stat().st_size > 0


def test_roundtrip_preserves_everything(tmp_path):
    path = tmp_path / "demo.rsproj"
    original = _sample_project()
    original.save(path)

    reloaded = Project.open(path)
    assert reloaded.name == "Demo"
    assert [b.name for b in reloaded.workbooks] == ["Book1"]
    sheet = reloaded.workbooks[0].sheets[0]
    assert sheet.name == "Sheet1"
    assert sheet.column_names == ["X1", "Y1"]
    assert sheet.column("X1").units == "rad"
    assert sheet.column("Y1").comment == "sin(x)"
    assert sheet.num_rows == 50
    np.testing.assert_allclose(sheet.column("Y1").data, np.sin(np.linspace(0, 2 * np.pi, 50)))
    assert [g.name for g in reloaded.graphs] == ["Graph1"]


def test_rejects_foreign_format(tmp_path):
    import json
    import zipfile

    path = tmp_path / "bad.rsproj"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("project.json", json.dumps({"format": "something-else"}))

    try:
        Project.open(path)
    except ValueError as exc:
        assert "not a GraphMatrix project" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
