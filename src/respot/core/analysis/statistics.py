"""Hypothesis tests, correlation, and histograms (scipy.stats)."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy import stats

from .result import AnalysisResult


def _clean(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, float)
    return arr[np.isfinite(arr)]


def ttest_ind(a: Sequence[float], b: Sequence[float]) -> AnalysisResult:
    a, b = _clean(a), _clean(b)
    result = AnalysisResult(kind="ttest", title="Independent Two-Sample t-test")
    if a.size < 2 or b.size < 2:
        result.notes = "Each sample needs at least 2 points."
        return result
    stat, p = stats.ttest_ind(a, b, equal_var=False)
    result.summary = {
        "t statistic": float(stat), "p-value": float(p),
        "Mean A": float(np.mean(a)), "Mean B": float(np.mean(b)),
        "N A": float(a.size), "N B": float(b.size),
    }
    result.notes = "Significant at 0.05" if p < 0.05 else "Not significant at 0.05"
    return result


def ttest_rel(a: Sequence[float], b: Sequence[float]) -> AnalysisResult:
    a, b = _clean(a), _clean(b)
    n = min(a.size, b.size)
    a, b = a[:n], b[:n]
    result = AnalysisResult(kind="ttest", title="Paired t-test")
    if n < 2:
        result.notes = "Need at least 2 paired points."
        return result
    stat, p = stats.ttest_rel(a, b)
    result.summary = {"t statistic": float(stat), "p-value": float(p), "N pairs": float(n)}
    return result


def ttest_1samp(a: Sequence[float], popmean: float = 0.0) -> AnalysisResult:
    a = _clean(a)
    result = AnalysisResult(kind="ttest", title="One-Sample t-test")
    if a.size < 2:
        result.notes = "Need at least 2 points."
        return result
    stat, p = stats.ttest_1samp(a, popmean)
    result.summary = {
        "t statistic": float(stat), "p-value": float(p),
        "Sample mean": float(np.mean(a)), "Pop. mean": float(popmean), "N": float(a.size),
    }
    return result


def anova_oneway(groups: Sequence[Sequence[float]]) -> AnalysisResult:
    cleaned = [_clean(g) for g in groups]
    cleaned = [g for g in cleaned if g.size > 0]
    result = AnalysisResult(kind="anova", title="One-Way ANOVA")
    if len(cleaned) < 2:
        result.notes = "Need at least two groups."
        return result
    stat, p = stats.f_oneway(*cleaned)
    table = [["Group", "N", "Mean", "Std Dev"]]
    for i, g in enumerate(cleaned):
        table.append([str(i + 1), str(g.size), f"{np.mean(g):.6g}", f"{np.std(g, ddof=1) if g.size > 1 else 0:.6g}"])
    result.tables["Groups"] = table
    result.summary = {"F statistic": float(stat), "p-value": float(p), "Groups": float(len(cleaned))}
    return result


def correlation(x: Sequence[float], y: Sequence[float], *, method: str = "pearson") -> AnalysisResult:
    x, y = np.asarray(x, float), np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    result = AnalysisResult(kind="correlation", title=f"Correlation ({method})")
    if x.size < 3:
        result.notes = "Need at least 3 points."
        return result
    if method == "spearman":
        r, p = stats.spearmanr(x, y)
    else:
        r, p = stats.pearsonr(x, y)
    result.summary = {"r": float(r), "r²": float(r * r), "p-value": float(p), "N": float(x.size)}
    return result


def correlation_matrix(names: Sequence[str], columns: Sequence[Sequence[float]]) -> AnalysisResult:
    data = np.column_stack([np.asarray(c, float) for c in columns])
    result = AnalysisResult(kind="correlation", title="Correlation Matrix")
    corr = np.corrcoef(data, rowvar=False)
    table = [["", *names]]
    for i, name in enumerate(names):
        table.append([name, *[f"{corr[i, j]:.3f}" for j in range(len(names))]])
    result.tables["Matrix"] = table
    return result


def histogram(data: Sequence[float], *, bins: int = 10) -> AnalysisResult:
    values = _clean(data)
    result = AnalysisResult(kind="histogram", title="Histogram")
    if values.size == 0:
        result.notes = "No data."
        return result
    counts, edges = np.histogram(values, bins=bins)
    centers = 0.5 * (edges[:-1] + edges[1:])
    result.curves["Histogram"] = (centers, counts.astype(float))
    result.tables["Bins"] = [["Bin center", "Count"]] + [
        [f"{centers[i]:.6g}", str(int(counts[i]))] for i in range(len(counts))
    ]
    result.summary = {"N": float(values.size), "Bins": float(bins)}
    return result


__all__ = [
    "ttest_ind", "ttest_rel", "ttest_1samp", "anova_oneway",
    "correlation", "correlation_matrix", "histogram",
]
