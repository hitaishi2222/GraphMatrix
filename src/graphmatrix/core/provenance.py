"""Provenance: a plain-language log of how a project's data and figures were made.

The command pattern already knows *what* changed; the analysis dialogs know *what
was computed*. This module collects those two streams into an ordered list that can
be rendered as a methods paragraph, saved alongside a bundle, or inspected in the UI.

It is deliberately Qt-free and does not require the model to change: the log is fed
by (a) commands whose ``describe()`` returns a sentence and (b) explicit analysis
results recorded at the point they are produced.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .commands import CommandStack

_KIND_TITLES = {
    "import": "Data",
    "analysis": "Analysis",
    "operation": "Operations",
    "note": "Notes",
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_summary(summary: dict[str, Any], limit: int = 6) -> str:
    """Render an ``AnalysisResult.summary`` as ``key = value; …`` prose."""
    parts: list[str] = []
    for key, value in list(summary.items())[:limit]:
        try:
            parts.append(f"{key} = {float(value):.4g}")
        except (TypeError, ValueError):
            parts.append(f"{key} = {value}")
    return "; ".join(parts)


@dataclass
class ProvenanceEntry:
    kind: str  # "import" | "analysis" | "operation" | "note"
    text: str
    detail: str = ""
    source: str = ""
    time: str = field(default_factory=_now)


class ProvenanceLog:
    """An ordered log of data imports, analysis runs, and notable operations."""

    def __init__(self) -> None:
        self.entries: list[ProvenanceEntry] = []
        self._unsubscribe: Callable[[], None] | None = None

    # -- recording -----------------------------------------------------------
    def record(
        self, kind: str, text: str, *, detail: str = "", source: str = ""
    ) -> ProvenanceEntry:
        entry = ProvenanceEntry(kind=kind, text=text, detail=detail, source=source)
        self.entries.append(entry)
        return entry

    def record_import(
        self, path: str | Path, workbook_name: str = ""
    ) -> ProvenanceEntry:
        return self.record(
            "import", f"Imported {Path(path).name}", source=workbook_name
        )

    def record_analysis(self, result, source: str = "") -> ProvenanceEntry:
        title = getattr(result, "title", None) or getattr(result, "kind", "Analysis")
        detail = format_summary(getattr(result, "summary", {}) or {})
        return self.record("analysis", title, detail=detail, source=source)

    def record_operation(self, text: str) -> ProvenanceEntry:
        return self.record("operation", text)

    def record_note(self, text: str) -> ProvenanceEntry:
        return self.record("note", text)

    def attach(self, commands: CommandStack) -> None:
        """Record every pushed command that can describe itself."""
        if self._unsubscribe is not None:
            return
        self._unsubscribe = commands.subscribe_push(self._on_command)

    def detach(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def _on_command(self, command) -> None:
        describe = getattr(command, "describe", None)
        if describe is None:
            return
        try:
            text = describe()
        except Exception:  # noqa: BLE001 - provenance must never break an edit
            return
        if text:
            self.record("operation", text)

    # -- inspection ----------------------------------------------------------
    def clear(self) -> None:
        self.entries.clear()

    @property
    def count(self) -> int:
        return len(self.entries)

    def of_kind(self, kind: str) -> list[ProvenanceEntry]:
        return [e for e in self.entries if e.kind == kind]

    def to_text(self) -> str:
        lines = []
        for entry in self.entries:
            line = entry.text
            if entry.source:
                line += f"  [{entry.source}]"
            if entry.detail:
                line += f"  ({entry.detail})"
            lines.append(line)
        return "\n".join(lines)

    def methods_markdown(self, project=None, *, title: str | None = None) -> str:
        """A Markdown report grouped by entry kind."""
        name = getattr(project, "name", "") if project is not None else ""
        heading = title or (f"Methods — {name}" if name else "Methods")
        lines = [f"# {heading}", "", f"_Generated {_now()}._", ""]
        if not self.entries:
            lines.append("_No recorded operations._")
            return "\n".join(lines)
        for kind, section in _KIND_TITLES.items():
            entries = self.of_kind(kind)
            if not entries:
                continue
            lines.append(f"## {section}")
            for entry in entries:
                item = entry.text
                if entry.source:
                    item += f" — `{entry.source}`"
                if entry.detail:
                    item += f" ({entry.detail})"
                lines.append(f"- {item}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    # -- serialization -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "graphmatrix-provenance",
            "entries": [asdict(e) for e in self.entries],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProvenanceLog":
        log = cls()
        for item in payload.get("entries", []):
            log.entries.append(ProvenanceEntry(**item))
        return log


__all__ = ["ProvenanceEntry", "ProvenanceLog", "format_summary"]
