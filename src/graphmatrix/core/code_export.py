"""Figure-as-code: render a whole project as a replayable Python script.

The generated script uses only names that are always present in the GraphMatrix console
(``api`` plus ``PlotSpec``, ``Layer``, ``ReferenceLine``, ``Annotation`` …). Running
it against an empty project reproduces the workbooks, columns, and figures. It is the
"regenerate every figure and table" entry point of an analysis bundle.

Binary column data is inlined as Python literals. That makes the script self-contained
but large for big datasets; the companion ``data/*.csv`` files are the compact copy.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np

from .model import AxisScale, Column, Graph, Layer, PlotSpec, Project, ReferenceLine


def _num_repr(value: Any) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "float('nan')"
        if math.isinf(value):
            return "float('inf')" if value > 0 else "float('-inf')"
    return repr(value)


def array_literal(values: Iterable[Any]) -> str:
    """A Python list literal that round-trips NaN and infinities."""
    return "[" + ", ".join(_num_repr(v) for v in np.asarray(list(values)).tolist()) + "]"


def _header(project: Project) -> list[str]:
    return [
        '"""Reconstructed GraphMatrix script — regenerates project.',
        "",
        f"Project: {project.name}",
        f"Workbooks: {len(project.workbooks)}   Graphs: {len(project.graphs)}",
        "",
        "Run this in a fresh GraphMatrix console (Tools ▸ Python Console) to rebuild the",
        "data and figures. Existing objects with the same names are reused/renamed.",
        '"""',
        "",
    ]


def _column_line(ref: str, column: Column) -> str:
    kwargs = [f"data={array_literal(column.data)}"]
    if column.units:
        kwargs.append(f"units={column.units!r}")
    if column.comment:
        kwargs.append(f"comment={column.comment!r}")
    if column.mask is not None:
        kwargs.append(f"mask={array_literal(column.mask)}")
    return (
        f"api.add_column({ref!r}, {column.name!r}, {column.col_type.value!r}, "
        + ", ".join(kwargs)
        + ")"
    )


def _plot_literal(spec: PlotSpec) -> str:
    kwargs: list[tuple[str, str]] = [
        ("yerr", repr(spec.yerr)),
        ("xerr", repr(spec.xerr)),
        ("style", repr(str(spec.style))),
        ("color", repr(spec.color)),
        ("line_width", repr(float(spec.line_width))),
        ("symbol", repr(spec.symbol)),
        ("symbol_size", repr(float(spec.symbol_size))),
        ("legend", repr(spec.legend)),
        ("y_axis", repr(spec.y_axis)),
        ("line_style", repr(spec.line_style)),
    ]
    body = ", ".join(f"{key}={value}" for key, value in kwargs)
    return f"PlotSpec(source={spec.source!r}, x={spec.x!r}, y={spec.y!r}, {body})"


def _ref_line_literal(line: ReferenceLine) -> str:
    return (
        f"ReferenceLine(orientation={line.orientation!r}, position={line.position!r}, "
        f"color={line.color!r}, width={line.width!r}, line_style={line.line_style!r}, "
        f"label={line.label!r})"
    )


def _layer_lines(layer: Layer, *, indent: str = "") -> list[str]:
    lines = []
    x_scale = AxisScale(layer.x_scale).value
    y_scale = AxisScale(layer.y_scale).value
    if x_scale != "linear":
        lines.append(f"{indent}layer.x_scale = {x_scale!r}")
    if y_scale != "linear":
        lines.append(f"{indent}layer.y_scale = {y_scale!r}")
    for attr in ("x_label", "y_label", "y2_label"):
        value = getattr(layer, attr)
        if value:
            lines.append(f"{indent}layer.{attr} = {value!r}")
    for attr in ("x_min", "x_max", "y_min", "y_max"):
        value = getattr(layer, attr)
        if value is not None:
            lines.append(f"{indent}layer.{attr} = {value!r}")
    if not layer.show_legend:
        lines.append(f"{indent}layer.show_legend = False")
    for spec in layer.plots:
        lines.append(f"{indent}layer.plots.append({_plot_literal(spec)})")
    for line in layer.ref_lines:
        lines.append(f"{indent}layer.ref_lines.append({_ref_line_literal(line)})")
    return lines


def _graph_lines(graph: Graph) -> list[str]:
    lines = [
        f"g = api.add_graph({graph.name!r})",
    ]
    if graph.title:
        lines.append(f"g.title = {graph.title!r}")
    if graph.journal_preset:
        lines.append(f"g.journal_preset = {graph.journal_preset!r}")
    for index, layer in enumerate(graph.layers):
        if index == 0:
            lines.append("layer = g.layers[0]")
            if layer.name and layer.name != "Layer 1":
                lines.append(f"layer.name = {layer.name!r}")
        else:
            lines.append(f"layer = Layer({layer.name!r})")
            lines.append("g.layers.append(layer)")
        lines.extend(_layer_lines(layer))
    for annotation in graph.annotations:
        lines.append(
            "g.annotations.append(Annotation("
            f"text={annotation.text!r}, x={annotation.x!r}, y={annotation.y!r}, "
            f"color={annotation.color!r}, size={annotation.size!r}))"
        )
    return lines


def project_to_script(project: Project, *, header: bool = True) -> str:
    """Return a Python script that reconstructs ``project`` through the API."""
    lines: list[str] = _header(project) if header else []
    for book in project.workbooks:
        lines.append(f"api.add_workbook({book.name!r})")
        for sheet in book.sheets:
            lines.append(f"api.add_worksheet({book.name!r}, {sheet.name!r})")
            for column in sheet.columns:
                lines.append(_column_line(f"{book.name}/{sheet.name}", column))
        lines.append("")
    for graph in project.graphs:
        lines.extend(_graph_lines(graph))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["project_to_script", "array_literal"]
