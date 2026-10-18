"""Nonlinear curve fitting via lmfit.

`fit_model` builds a model from :data:`MODELS`, guesses initial parameters (or uses
the caller's), fits, and returns an :class:`AnalysisResult` with parameters ±
standard error, goodness-of-fit, and the fitted curve — GraphMatrix's answer to Origin's
NLFit, backed by lmfit.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

from .result import AnalysisResult, ParamRow, r_squared

from .regression import _window

# (function, [param names], [default values])
_MODEL_SPECS: dict[str, tuple[Callable[..., np.ndarray], list[str], list[float]]] = {}


def _register(
    name: str, func: Callable[..., np.ndarray], params: list[str], defaults: list[float]
) -> None:
    _MODEL_SPECS[name] = (func, params, defaults)


def _gaussian(x, amplitude, center, sigma):
    return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma**2))


def _lorentzian(x, amplitude, center, gamma):
    return amplitude * gamma**2 / ((x - center) ** 2 + gamma**2)


def _exponential_decay(x, amplitude, decay, offset):
    return amplitude * np.exp(-x / decay) + offset


def _exponential_growth(x, amplitude, rate, offset):
    return amplitude * np.exp(rate * x) + offset


def _sinusoid(x, amplitude, frequency, phase, offset):
    return amplitude * np.sin(2 * np.pi * frequency * x + phase) + offset


def _power_law(x, amplitude, exponent):
    return amplitude * np.power(np.abs(x), exponent)


def _sigmoid(x, amplitude, center, width, offset):
    return amplitude / (1 + np.exp(-(x - center) / width)) + offset


def _step(x, amplitude, center, sigma):
    return amplitude * 0.5 * (1 + np.tanh((x - center) / sigma))


def _log_normal(x, amplitude, center, sigma):
    x = np.where(x <= 0, 1e-12, x)
    return amplitude * np.exp(-((np.log(x) - center) ** 2) / (2 * sigma**2))


_register("Gaussian", _gaussian, ["amplitude", "center", "sigma"], [1.0, 0.0, 1.0])
_register("Lorentzian", _lorentzian, ["amplitude", "center", "gamma"], [1.0, 0.0, 1.0])
_register(
    "Exponential Decay",
    _exponential_decay,
    ["amplitude", "decay", "offset"],
    [1.0, 1.0, 0.0],
)
_register(
    "Exponential Growth",
    _exponential_growth,
    ["amplitude", "rate", "offset"],
    [1.0, 0.1, 0.0],
)
_register(
    "Sinusoid",
    _sinusoid,
    ["amplitude", "frequency", "phase", "offset"],
    [1.0, 1.0, 0.0, 0.0],
)
_register("Power Law", _power_law, ["amplitude", "exponent"], [1.0, 1.0])
_register(
    "Sigmoid",
    _sigmoid,
    ["amplitude", "center", "width", "offset"],
    [1.0, 0.0, 1.0, 0.0],
)
_register("Step", _step, ["amplitude", "center", "sigma"], [1.0, 0.0, 1.0])
_register("Log-Normal", _log_normal, ["amplitude", "center", "sigma"], [1.0, 0.0, 1.0])


def available_models() -> list[str]:
    return sorted(_MODEL_SPECS)


def _guess(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    xmin, xmax = float(np.min(x)), float(np.max(x))
    amplitude = float(np.max(y) - np.min(y)) or 1.0
    offset = float(np.min(y))
    return np.array([amplitude, xmin + 0.3 * (xmax - xmin)], dtype=float)


def fit_model(
    model_name: str,
    x: Sequence[float],
    y: Sequence[float],
    *,
    yerr: Sequence[float] | None = None,
    p0: dict[str, float] | None = None,
    x_min: float | None = None,
    x_max: float | None = None,
) -> AnalysisResult:
    """Fit ``model_name`` to ``(x, y)``.

    ``x_min``/``x_max`` restrict the fit to a numeric X window (open ends allowed)
    — the dialog equivalent of dragging a region, per the M10 decision to scope
    fits by *numeric bounds*.
    """
    import lmfit

    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    x, y = _window(x, y, x_min, x_max)
    result = AnalysisResult(kind="fit", title=f"Nonlinear Fit — {model_name}")

    if model_name not in _MODEL_SPECS:
        result.notes = (
            f"Unknown model {model_name!r}. Known: {', '.join(available_models())}"
        )
        return result

    func, param_names, defaults = _MODEL_SPECS[model_name]
    if x.size < len(param_names) + 1:
        result.notes = "Not enough data points for this model."
        return result

    model = lmfit.Model(func, independent_vars=["x"])
    params = model.make_params()
    guess = _guess(x, y)
    for name in param_names:
        value = defaults[param_names.index(name)]
        if p0 and name in p0:
            value = p0[name]
        params[name].set(value=value)

    weights = None
    if yerr is not None:
        ye = np.asarray(yerr, float)[mask]
        ye = np.where(ye == 0, np.nan, ye)
        weights = 1.0 / ye

    try:
        fit = model.fit(y, params, x=x, weights=weights)
    except Exception as exc:  # noqa: BLE001 - report fit failures to the user
        result.notes = f"Fit failed: {exc}"
        return result

    y_fit = fit.best_fit
    result.parameters = [
        ParamRow(
            name,
            float(fit.params[name].value),
            None if fit.params[name].stderr is None else float(fit.params[name].stderr),
        )
        for name in param_names
    ]
    result.summary = {
        "R²": float(getattr(fit, "rsquared", r_squared(y, y_fit))),
        "Reduced χ²": float(fit.redchi),
        "χ²": float(fit.chisqr),
        "AIC": float(fit.aic),
        "BIC": float(fit.bic),
        "N": float(x.size),
    }
    if x_min is not None or x_max is not None:
        result.summary["Fit region"] = (
            f"{x_min if x_min is not None else '−∞'} ≤ x ≤ "
            f"{x_max if x_max is not None else '∞'}"
        )
    xs = np.linspace(x.min(), x.max(), 400)
    params = {name: fit.params[name].value for name in param_names}
    result.curves["Fit"] = (xs, func(xs, **params))
    # Confidence band (±1 sigma) when lmfit can provide the uncertainty.
    try:
        dely = fit.eval_uncertainty(x=xs, sigma=1.0)
        result.curves["Fit +1σ"] = (xs, func(xs, **params) + np.asarray(dely))
        result.curves["Fit -1σ"] = (xs, func(xs, **params) - np.asarray(dely))
    except Exception:  # noqa: BLE001 - uncertainty not available for all models
        pass
    result.curves["Residuals"] = (x, y - y_fit)
    result.notes = "Parameters: " + ", ".join(
        f"{p.name}={p.value:.5g}" + (f"±{p.error:.3g}" if p.error else "")
        for p in result.parameters
    )
    return result


def fit_custom(
    func: Callable[..., np.ndarray],
    param_names: Sequence[str],
    x: Sequence[float],
    y: Sequence[float],
    *,
    p0: dict[str, float] | None = None,
    x_min: float | None = None,
    x_max: float | None = None,
) -> AnalysisResult:
    """Fit a caller-supplied model function."""
    _MODEL_SPECS["__custom__"] = (func, list(param_names), [1.0] * len(param_names))
    try:
        return fit_model("__custom__", x, y, p0=p0, x_min=x_min, x_max=x_max)
    finally:
        _MODEL_SPECS.pop("__custom__", None)


__all__ = ["available_models", "fit_model", "fit_custom", "MODELS"]
MODELS = list(_MODEL_SPECS)
