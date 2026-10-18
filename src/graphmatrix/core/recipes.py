"""Analysis recipes: a saved, re-runnable analysis operation.

A recipe records *what* to compute (fit model, peak settings, signal operation, …)
but not the data. ``run_recipe`` applies it to any (x, y) pair — the mechanism behind
"re-run this analysis on the next dataset", and the unit of work in batch pipelines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .analysis import deconvolution, descriptive, fitting, peaks, ranged, regression, signal
from .analysis.result import AnalysisResult

RECIPE_FORMAT = "graphmatrix-recipe"
RECIPE_VERSION = 1

# Operations that only need a single series (y) use x = None.
OPERATIONS = ("descriptive", "regression", "fit", "peaks", "deconvolution", "signal", "slope")


@dataclass
class Recipe:
    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": RECIPE_FORMAT, "version": RECIPE_VERSION,
            "operation": self.operation, "params": self.params, "label": self.label,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Recipe":
        if payload.get("format") not in (None, RECIPE_FORMAT):
            raise ValueError(f"not a GraphMatrix recipe (format={payload.get('format')!r})")
        operation = payload.get("operation")
        if operation not in OPERATIONS:
            raise ValueError(f"unknown recipe operation {operation!r}")
        return cls(operation, dict(payload.get("params", {})), payload.get("label", ""))

    @property
    def name(self) -> str:
        return self.label or self.operation


def run_recipe(recipe: Recipe, x: Sequence[float] | None, y: Sequence[float]) -> AnalysisResult:
    op = recipe.operation
    p = recipe.params
    if op == "descriptive":
        return descriptive.summarize(y)
    if op == "regression":
        if p.get("mode", "linear") == "polynomial":
            return regression.polynomial_fit(x, y, degree=int(p.get("degree", 2)))
        return regression.linear_fit(x, y)
    if op == "fit":
        return fitting.fit_model(p.get("model", "Gaussian"), x, y)
    if op == "peaks":
        return peaks.find_peaks_result(x, y, prominence=p.get("prominence"), distance=p.get("distance"))
    if op == "deconvolution":
        kind = p.get("kind", "gaussian")
        centers = p.get("centers")
        if centers:
            return deconvolution.deconvolve(x, y, centers, kind=kind)
        return deconvolution.deconvolve_auto(x, y, kind=kind)
    if op == "signal":
        return signal.run_operation(
            p.get("operation", "FFT Spectrum"), x, y,
            window=int(p.get("window", 11)), order=int(p.get("order", 3)),
            cutoff=float(p.get("cutoff", 1.0)), points=int(p.get("points", 200)),
            lam=float(p.get("lam", 1e5)),
            baseline_method=p.get("baseline_method"),
        )
    if op == "slope":
        return ranged.slope_between(x, y, p.get("x0"), p.get("x1"))
    raise ValueError(f"unknown recipe operation {op!r}")


def save_recipe(recipe: Recipe, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(recipe.to_dict(), indent=2), encoding="utf-8")
    return path


def load_recipe(path: str | Path) -> Recipe:
    return Recipe.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


__all__ = ["Recipe", "run_recipe", "save_recipe", "load_recipe", "OPERATIONS", "RECIPE_FORMAT"]
