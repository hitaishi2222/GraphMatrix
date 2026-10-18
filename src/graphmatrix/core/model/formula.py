"""Safe column-formula evaluation.

Formulas reference other columns by name plus a small set of numpy functions,
e.g. ``Y1 * 2``, ``sin(X1)``, ``log(Y1) + 3``. No arbitrary code execution:
the expression is parsed and every name is checked against an allow-list.
"""

from __future__ import annotations

import ast
import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from .worksheet import Worksheet

_FUNCTIONS = {
    name: getattr(np, name)
    for name in (
        "sin",
        "cos",
        "tan",
        "arcsin",
        "arccos",
        "arctan",
        "arctan2",
        "sinh",
        "cosh",
        "tanh",
        "exp",
        "log",
        "log10",
        "log2",
        "sqrt",
        "abs",
        "sign",
        "floor",
        "ceil",
        "round",
        "where",
        "minimum",
        "maximum",
        "clip",
        "power",
        "arctan2",
    )
    if hasattr(np, name)
}
_FUNCTIONS.update({"pi": math.pi, "e": math.e, "nan": np.nan})

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Not,
    ast.FloorDiv,
    ast.Compare,
    ast.IfExp,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Tuple,
    ast.List,
    ast.Subscript,
    ast.Slice,
)


class FormulaError(ValueError):
    pass


def _check(node: ast.AST) -> None:
    if not isinstance(node, _ALLOWED_NODES):
        raise FormulaError(f"disallowed syntax: {type(node).__name__}")
    for child in ast.iter_child_nodes(node):
        _check(child)


def evaluate_column_formula(sheet: "Worksheet", expression: str, n: int) -> np.ndarray:
    """Evaluate ``expression`` against ``sheet``'s columns, returning n values."""
    expression = expression.strip()
    if expression.startswith("="):
        expression = expression[1:]
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"invalid formula: {exc.msg}") from exc
    _check(tree)

    env: dict[str, object] = dict(_FUNCTIONS)
    for index, column in enumerate(sheet.columns):
        env[column.name] = column.float_data()
        env[f"C{index + 1}"] = column.float_data()  # positional alias
    env["n"] = n

    for name in {n_ for n_ in ast.walk(tree) if isinstance(n_, ast.Name)}:
        if name.id not in env:
            raise FormulaError(f"unknown name: {name.id}")

    result = eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}}, env)  # noqa: S307 - sandboxed
    array = np.asarray(result, dtype=float)
    if array.ndim == 0:
        array = np.full(n, float(array))
    return array.reshape(-1)
