"""Project: the root document, with `.rsproj` save/open.

A `.rsproj` file is a zip archive containing ``project.json`` (the manifest) plus
``arrays/col_*.npy`` entries for numeric column data. Large numeric payloads live
in the binary entries; metadata and non-numeric data stay in JSON. The envelope is
format-versioned so it can evolve without breaking older files.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .graph import Graph
from .workbook import Workbook

FORMAT = "graphmatrix-project"
FORMAT_VERSION = 3
_MANIFEST = "project.json"


def _is_numeric_dtype(dtype: np.dtype) -> bool:
    return np.dtype(dtype).kind in "fiub"


def _externalize(node: Any, arrays: dict[str, bytes]) -> Any:
    """Replace numeric column data with a reference to a .npy entry."""
    if isinstance(node, dict):
        if "col_type" in node and "data" in node:
            node = dict(node)
            try:
                dtype = np.dtype(node.get("dtype", "float64"))
            except TypeError:
                dtype = None
            if dtype is not None and _is_numeric_dtype(dtype):
                array = np.asarray(node["data"], dtype=dtype)
                key = f"arrays/col_{len(arrays):05d}.npy"
                buffer = io.BytesIO()
                np.save(buffer, array)
                arrays[key] = buffer.getvalue()
                del node["data"]
                node["array"] = key
            return node
        return {k: _externalize(v, arrays) for k, v in node.items()}
    if isinstance(node, list):
        return [_externalize(v, arrays) for v in node]
    return node


def _internalize(node: Any, zf: zipfile.ZipFile) -> Any:
    """Load numeric column data back from .npy entries."""
    if isinstance(node, dict):
        if "array" in node:
            node = dict(node)
            array = np.load(io.BytesIO(zf.read(node["array"])), allow_pickle=False)
            del node["array"]
            node["data"] = array
            return node
        return {k: _internalize(v, zf) for k, v in node.items()}
    if isinstance(node, list):
        return [_internalize(v, zf) for v in node]
    return node


class Project:
    """The root document: workbooks (data) and graphs (figures)."""

    def __init__(self, name: str = "Untitled") -> None:
        self.name = name
        self.workbooks: list[Workbook] = []
        self.graphs: list[Graph] = []
        self.versions: list[dict[str, Any]] = []

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

    # -- versions ------------------------------------------------------------
    def create_version(self, name: str, note: str = "") -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("version name is required")
        if any(v.get("name") == name for v in self.versions):
            raise ValueError(f"version {name!r} already exists")
        snapshot = self.to_dict()
        snapshot.pop("versions", None)
        version = {"name": name, "created": datetime.now().isoformat(timespec="seconds"),
                   "note": note, "snapshot": snapshot}
        self.versions.append(version)
        return version

    def restore_version(self, name: str) -> None:
        version = next((v for v in self.versions if v.get("name") == name), None)
        if version is None:
            raise KeyError(f"no version {name!r}")
        snapshot = version["snapshot"]
        self.name = snapshot.get("name", self.name)
        self.workbooks = [Workbook.from_dict(b) for b in snapshot.get("workbooks", [])]
        self.graphs = [Graph.from_dict(g) for g in snapshot.get("graphs", [])]

    def delete_version(self, name: str) -> None:
        self.versions = [v for v in self.versions if v.get("name") != name]

    def rename_version(self, old: str, new: str) -> None:
        new = new.strip()
        if not new or any(v.get("name") == new for v in self.versions if v.get("name") != old):
            raise ValueError("invalid or duplicate version name")
        for v in self.versions:
            if v.get("name") == old:
                v["name"] = new

    # -- lookup --------------------------------------------------------------
    def sheet(self, source: str):
        """Resolve a "Book/Sheet" reference to a Worksheet, or None."""
        if "/" not in source:
            return None
        book_name, sheet_name = source.split("/", 1)
        book = self.workbook(book_name)
        return book.sheet(sheet_name) if book else None

    def unique_name(self, prefix: str) -> str:
        existing = {b.name for b in self.workbooks} | {g.name for g in self.graphs}
        if prefix not in existing:
            return prefix
        i = 1
        while f"{prefix}{i}" in existing:
            i += 1
        return f"{prefix}{i}"

    def remap_sources(self, old: str, new: str) -> None:
        """Rewrite plot references so ``old``/``old/...`` becomes ``new``.

        ``old`` is a source prefix: a workbook name ("Book1") or a qualified
        sheet ("Book1/Sheet1"). Used when renaming a workbook or worksheet so
        existing graphs keep pointing at their data.
        """
        if old == new:
            return
        for graph in self.graphs:
            for layer in graph.layers:
                for spec in layer.plots:
                    if spec.source == old:
                        spec.source = new
                    elif spec.source.startswith(old + "/"):
                        spec.source = new + spec.source[len(old):]

    # -- serialization -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "version": FORMAT_VERSION,
            "name": self.name,
            "workbooks": [b.to_dict() for b in self.workbooks],
            "graphs": [g.to_dict() for g in self.graphs],
            "versions": self.versions,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Project":
        fmt = payload.get("format")
        if fmt not in (None, FORMAT):
            raise ValueError(f"not a GraphMatrix project (format={fmt!r})")
        project = cls(payload.get("name", "Untitled"))
        project.workbooks = [Workbook.from_dict(b) for b in payload.get("workbooks", [])]
        project.graphs = [Graph.from_dict(g) for g in payload.get("graphs", [])]
        project.versions = payload.get("versions", []) or []
        return project

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays: dict[str, bytes] = {}
        manifest = _externalize(self.to_dict(), arrays)
        manifest["version"] = FORMAT_VERSION
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(_MANIFEST, json.dumps(manifest, indent=2))
            for key, blob in arrays.items():
                zf.writestr(key, blob)
        return path

    @classmethod
    def open(cls, path: str | Path) -> "Project":
        path = Path(path)
        with zipfile.ZipFile(path, "r") as zf:
            payload = json.loads(zf.read(_MANIFEST).decode("utf-8"))
            payload = _internalize(payload, zf)
        return cls.from_dict(payload)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Project(name={self.name!r}, books={len(self.workbooks)}, graphs={len(self.graphs)})"
