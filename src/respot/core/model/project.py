"""Project: the root document, with `.rsproj` save/open.

A `.rsproj` file is a zip archive containing ``project.json``. When datasets grow
(M1) large arrays move to binary entries, but this envelope stays the same.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from .graph import Graph
from .workbook import Workbook

FORMAT = "respot-project"
FORMAT_VERSION = 1
_MANIFEST = "project.json"


class Project:
    """The root document: workbooks (data) and graphs (figures)."""

    def __init__(self, name: str = "Untitled") -> None:
        self.name = name
        self.workbooks: list[Workbook] = []
        self.graphs: list[Graph] = []

    # -- workbooks -----------------------------------------------------------
    def add_workbook(self, workbook: Workbook, *, index: int | None = None) -> Workbook:
        if index is None:
            self.workbooks.append(workbook)
        else:
            self.workbooks.insert(index, workbook)
        return workbook

    def remove_workbook(self, workbook: Workbook) -> int:
        index = self.workbooks.index(workbook)
        del self.workbooks[index]
        return index

    def workbook(self, name: str) -> Workbook | None:
        for book in self.workbooks:
            if book.name == name:
                return book
        return None

    # -- graphs --------------------------------------------------------------
    def add_graph(self, graph: Graph, *, index: int | None = None) -> Graph:
        if index is None:
            self.graphs.append(graph)
        else:
            self.graphs.insert(index, graph)
        return graph

    def remove_graph(self, graph: Graph) -> int:
        index = self.graphs.index(graph)
        del self.graphs[index]
        return index

    def graph(self, name: str) -> Graph | None:
        for item in self.graphs:
            if item.name == name:
                return item
        return None

    # -- naming --------------------------------------------------------------
    def unique_name(self, prefix: str) -> str:
        existing = {b.name for b in self.workbooks} | {g.name for g in self.graphs}
        if prefix not in existing:
            return prefix
        i = 1
        while f"{prefix}{i}" in existing:
            i += 1
        return f"{prefix}{i}"

    # -- serialization -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "version": FORMAT_VERSION,
            "name": self.name,
            "workbooks": [b.to_dict() for b in self.workbooks],
            "graphs": [g.to_dict() for g in self.graphs],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Project":
        fmt = payload.get("format")
        if fmt not in (None, FORMAT):
            raise ValueError(f"not a Respot project (format={fmt!r})")
        project = cls(payload.get("name", "Untitled"))
        project.workbooks = [Workbook.from_dict(b) for b in payload.get("workbooks", [])]
        project.graphs = [Graph.from_dict(g) for g in payload.get("graphs", [])]
        return project

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(_MANIFEST, payload)
        return path

    @classmethod
    def open(cls, path: str | Path) -> "Project":
        path = Path(path)
        with zipfile.ZipFile(path, "r") as zf:
            data = json.loads(zf.read(_MANIFEST).decode("utf-8"))
        return cls.from_dict(data)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Project(name={self.name!r}, books={len(self.workbooks)}, graphs={len(self.graphs)})"
