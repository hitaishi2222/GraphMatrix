"""Descriptive statistics."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy import stats

from .result import AnalysisResult


def summarize(
    data: Sequence[float], name: str = "Data", *, cl: float = 0.95
) -> AnalysisResult:
    values = np.asarray(data, dtype=float)
    values = values[np.isfinite(values)]
    n = values.size
    result = AnalysisResult(
        kind="descriptive", title=f"Descriptive Statistics — {name}"
    )
    if n == 0:
        result.notes = "No finite data."
        return result

    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1)) if n > 1 else 0.0
    sem = std / np.sqrt(n) if n > 1 else 0.0
    half = float(stats.t.ppf(0.5 + cl / 2, n - 1) * sem) if n > 1 else 0.0
    q1, q3 = np.percentile(values, [25, 75])

    result.summary = {
        "N": float(n),
        "Mean": mean,
        "Std Dev": std,
        "Variance": float(np.var(values, ddof=1)) if n > 1 else 0.0,
        "Std Error": float(sem),
        f"CI {cl:.0%} ±": half,
        "Min": float(np.min(values)),
        "Max": float(np.max(values)),
        "Range": float(np.max(values) - np.min(values)),
        "Median": float(np.median(values)),
        "Q1": float(q1),
        "Q3": float(q3),
        "IQR": float(q3 - q1),
        "Skewness": float(stats.skew(values, bias=False)) if n > 2 else 0.0,
        "Kurtosis": float(stats.kurtosis(values, bias=False)) if n > 3 else 0.0,
        "Sum": float(np.sum(values)),
    }
    return result


def batch_summary(project) -> AnalysisResult:
    """One report row per numeric column across every sheet in the project.

    The "many datasets at a glance" table: pairs with the batch pipelines, and
    is the M10 standings report — Sheet, Column, Type, N, Missing, Mean, SD,
    Min, Median, Max.
    """
    header = [
        "Sheet",
        "Column",
        "Type",
        "N",
        "Missing",
        "Mean",
        "Std Dev",
        "Min",
        "Median",
        "Max",
    ]
    rows = [header]
    for book in project.workbooks:
        for sheet in book.sheets:
            for column in sheet.columns:
                if not column.is_numeric:
                    continue
                values = column.float_data()
                missing = int(np.sum(~np.isfinite(values)))
                values = values[np.isfinite(values)]
                name = f"{sheet.name}"
                col_name = column.name
                if values.size == 0:
                    rows.append(
                        [
                            name,
                            col_name,
                            str(column.col_type),
                            "0",
                            str(missing),
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]
                    )
                    continue
                rows.append(
                    [
                        name,
                        col_name,
                        str(column.col_type),
                        str(values.size),
                        str(missing),
                        f"{float(np.mean(values)):.6g}",
                        f"{float(np.std(values, ddof=1)) if values.size > 1 else 0:.6g}",
                        f"{float(np.min(values)):.6g}",
                        f"{float(np.median(values)):.6g}",
                        f"{float(np.max(values)):.6g}",
                    ]
                )
    result = AnalysisResult(kind="batch-stats", title="Batch Statistics")
    result.tables["Columns"] = rows
    n_columns = max(len(rows) - 1, 0)
    result.summary = {
        "Sheets": float(sum(len(b.sheets) for b in project.workbooks)),
        "Columns": float(n_columns),
    }
    if n_columns == 0:
        result.notes = "No numeric columns in the project."
    return result


def summarize_columns(sheet, names: Sequence[str]) -> AnalysisResult:
    rows = [["Column", "N", "Mean", "Std Dev", "Min", "Max"]]
    for name in names:
        column = sheet.column(name)
        if column is None:
            continue
        values = column.float_data()
        values = values[np.isfinite(values)]
        if values.size == 0:
            rows.append([name, "0", "", "", "", ""])
            continue
        rows.append(
            [
                name,
                str(values.size),
                f"{np.mean(values):.6g}",
                f"{np.std(values, ddof=1) if values.size > 1 else 0:.6g}",
                f"{np.min(values):.6g}",
                f"{np.max(values):.6g}",
            ]
        )
    result = AnalysisResult(
        kind="descriptive", title="Descriptive Statistics — Columns"
    )
    result.tables["Summary"] = rows
    return result


__all__ = ["batch_summary", "summarize", "summarize_columns"]
