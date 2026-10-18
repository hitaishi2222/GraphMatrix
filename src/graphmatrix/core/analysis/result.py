"""Structured analysis results, shared by every analysis routine.

A routine returns an :class:`AnalysisResult`, which the UI renders as a report and
the exporter can turn into a figure. Curves are named ``(x, y)`` arrays that the UI
offers to add back as worksheet columns or graph plots.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ParamRow:
    name: str
    value: float
    error: float | None = None
    description: str = ""

    def display(self) -> str:
        if self.error is None:
            return f"{self.value:.6g}"
        return f"{self.value:.6g} ± {self.error:.3g}"


@dataclass
class AnalysisResult:
    kind: str
    title: str
    summary: dict[str, float] = field(default_factory=dict)
    parameters: list[ParamRow] = field(default_factory=list)
    tables: dict[str, list[list[str]]] = field(default_factory=dict)
    curves: dict[str, tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)
    notes: str = ""

    def to_text(self) -> str:
        lines = [self.title, "=" * len(self.title), ""]
        if self.summary:
            for key, value in self.summary.items():
                if isinstance(value, str):
                    lines.append(f"{key:<16}: {value}")
                else:
                    lines.append(f"{key:<16}: {value:.6g}")
            lines.append("")
        if self.parameters:
            lines.append("Parameters:")
            for param in self.parameters:
                lines.append(f"  {param.name:<16} {param.display()}" + (f"   {param.description}" if param.description else ""))
            lines.append("")
        for name, table in self.tables.items():
            lines.append(f"{name}:")
            for row in table:
                lines.append("  " + "  ".join(str(cell) for cell in row))
            lines.append("")
        if self.notes:
            lines.append(self.notes)
        return "\n".join(lines)


def r_squared(y: np.ndarray, y_fit: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    y_fit = np.asarray(y_fit, dtype=float)
    ss_res = float(np.nansum((y - y_fit) ** 2))
    ss_tot = float(np.nansum((y - np.nanmean(y)) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


__all__ = ["AnalysisResult", "ParamRow", "r_squared"]
