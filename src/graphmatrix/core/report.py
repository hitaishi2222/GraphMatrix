"""Analysis bundles: one folder that reproduces and documents a project.

An *analysis bundle* is the unit a collaborator (or a future you) can actually use:
the project file, the raw data as CSV, a script that rebuilds every figure, the
exported figures, and a methods write-up. It is deliberately simple — a directory of
files — so it survives without GraphMatrix installed for the data and figures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .code_export import project_to_script
from .io.importer import export_delimited
from .io.export import export_graph
from .model import Project
from .provenance import ProvenanceLog

_FIGURE_FORMATS = ("pdf", "png")


@dataclass
class BundleResult:
    """Where a bundle's parts were written."""

    root: Path
    files: dict[str, list[str]] = field(default_factory=dict)

    def all_paths(self) -> list[Path]:
        return [Path(p) for paths in self.files.values() for p in paths]

    def summary(self) -> str:
        counts = ", ".join(f"{len(v)} {k}" for k, v in self.files.items() if v)
        return f"{self.root.name}: {counts}"


def _safe(name: str) -> str:
    """A conservative filename component (book/sheet/graph names are user text)."""
    cleaned = "".join(c if c.isalnum() or c in "-_." else "_" for c in name).strip("_")
    return cleaned or "item"


def export_analysis_bundle(
    project: Project,
    provenance: ProvenanceLog | None = None,
    out_dir: str | Path | None = None,
    *,
    dpi: int = 300,
    figure_formats: tuple[str, ...] = _FIGURE_FORMATS,
) -> BundleResult:
    """Write a reproducible, documented bundle for ``project`` into ``out_dir``.

    If ``out_dir`` is omitted, a ``<Project>-bundle`` folder is created next to the
    current working directory.
    """
    root = Path(out_dir) if out_dir is not None else Path(f"{_safe(project.name)}-bundle")
    root = root.expanduser()
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "figures").mkdir(parents=True, exist_ok=True)

    result = BundleResult(root=root, files={})

    project_path = project.save(root / "project.rsproj")
    result.files.setdefault("project", []).append(str(project_path))

    for book in project.workbooks:
        for sheet in book.sheets:
            target = root / "data" / f"{_safe(book.name)}__{_safe(sheet.name)}.csv"
            export_delimited(sheet, target)
            result.files.setdefault("data", []).append(str(target))

    script_path = root / "reproduce.py"
    script_path.write_text(project_to_script(project), encoding="utf-8")
    result.files.setdefault("script", []).append(str(script_path))

    for graph in project.graphs:
        for fmt in figure_formats:
            target = root / "figures" / f"{_safe(graph.name)}.{fmt}"
            export_graph(graph, project, target, dpi=dpi)
            if "figures" not in result.files:
                result.files["figures"] = []
            result.files["figures"].append(str(target))

    if provenance is not None:
        methods_path = root / "methods.md"
        methods_path.write_text(provenance.methods_markdown(project), encoding="utf-8")
        result.files.setdefault("methods", []).append(str(methods_path))
        prov_path = root / "provenance.json"
        prov_path.write_text(json.dumps(provenance.to_dict(), indent=2), encoding="utf-8")
        result.files.setdefault("methods", []).append(str(prov_path))

    return result


__all__ = ["BundleResult", "export_analysis_bundle"]
