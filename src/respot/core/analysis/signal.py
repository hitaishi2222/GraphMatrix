"""Signal processing: FFT, smoothing, filters, calculus, interpolation, baseline.

Each routine returns an :class:`AnalysisResult` whose ``curves`` are ``(x, y)``
pairs the UI can add back as worksheet columns or graph plots.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy import integrate as sci_integrate
from scipy import interpolate as sci_interp
from scipy import signal as sci_signal

from .result import AnalysisResult


def _clean(x: Sequence[float], y: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def fft_spectrum(x: Sequence[float], y: Sequence[float]) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="fft", title="FFT Spectrum")
    if x.size < 2:
        result.notes = "Not enough data."
        return result

    dx = float(np.mean(np.diff(x))) if x.size > 1 else 1.0
    fs = 1.0 / dx if dx else 1.0
    n = y.size
    y_detrended = y - np.mean(y)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    amplitude = 2.0 / n * np.abs(np.fft.rfft(y_detrended))
    peak = int(np.argmax(amplitude[1:]) + 1) if amplitude.size > 1 else 0
    result.curves["Spectrum"] = (freqs, amplitude)
    result.summary = {
        "N": float(n), "Sampling freq": fs,
        "Peak frequency": float(freqs[peak]) if freqs.size else float("nan"),
        "Peak amplitude": float(amplitude[peak]) if amplitude.size else float("nan"),
    }
    return result


def smooth_savgol(x: Sequence[float], y: Sequence[float], *, window: int = 11, order: int = 3) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="smooth", title="Savitzky-Golay Smoothing")
    window = min(window if window % 2 == 1 else window + 1, y.size if y.size % 2 == 1 else y.size - 1)
    if window < order + 2:
        result.notes = "Window too small for the polynomial order."
        return result
    smoothed = sci_signal.savgol_filter(y, window, order)
    result.curves["Smoothed"] = (x, smoothed)
    result.summary = {"Window": float(window), "Order": float(order), "N": float(y.size)}
    return result


def smooth_moving_average(x: Sequence[float], y: Sequence[float], *, window: int = 5) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="smooth", title="Moving Average")
    window = max(1, min(window, y.size))
    kernel = np.ones(window) / window
    smoothed = np.convolve(y, kernel, mode="same")
    result.curves["Smoothed"] = (x, smoothed)
    result.summary = {"Window": float(window), "N": float(y.size)}
    return result


def butter_filter(
    x: Sequence[float], y: Sequence[float], *,
    kind: str = "low", cutoff: float = 1.0, order: int = 4, fs: float | None = None,
) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="filter", title=f"Butterworth Filter ({kind})")
    if x.size < 3:
        result.notes = "Not enough data."
        return result
    dx = float(np.mean(np.diff(x))) if x.size > 1 else 1.0
    fs = fs or (1.0 / dx if dx else 1.0)
    nyq = 0.5 * fs
    normalized = cutoff / nyq
    if not 0 < normalized < 1:
        result.notes = f"Cutoff must be between 0 and {nyq:.6g} (Nyquist)."
        return result
    b, a = sci_signal.butter(order, normalized, btype=kind)
    try:
        filtered = sci_signal.filtfilt(b, a, y)
    except ValueError:
        filtered = sci_signal.lfilter(b, a, y)
    result.curves["Filtered"] = (x, filtered)
    result.summary = {"Order": float(order), "Cutoff": float(cutoff), "Fs": float(fs)}
    return result


def differentiate(x: Sequence[float], y: Sequence[float], *, order: int = 1) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="differentiate", title=f"Numerical Derivative (order {order})")
    if x.size < 2:
        result.notes = "Not enough data."
        return result
    derivative = np.gradient(y, x, edge_order=2 if x.size > 2 else 1)
    for _ in range(order - 1):
        derivative = np.gradient(derivative, x, edge_order=2 if x.size > 2 else 1)
    result.curves["Derivative"] = (x, derivative)
    result.summary = {"Order": float(order), "N": float(y.size)}
    return result


def integrate_curve(x: Sequence[float], y: Sequence[float]) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="integrate", title="Numerical Integration")
    if x.size < 2:
        result.notes = "Not enough data."
        return result
    cumulative = sci_integrate.cumulative_trapezoid(y, x, initial=0.0)
    result.curves["Cumulative"] = (x, cumulative)
    result.summary = {"Total area": float(cumulative[-1]), "N": float(y.size)}
    return result


def interpolate(x: Sequence[float], y: Sequence[float], *, num: int = 200, kind: str = "cubic") -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="interpolate", title=f"Interpolation ({kind})")
    if x.size < 2:
        result.notes = "Not enough data."
        return result
    order = np.argsort(x)
    x, y = x[order], y[order]
    xi = np.linspace(x.min(), x.max(), max(num, x.size))
    k = kind if kind in ("linear", "nearest", "zero", "slinear", "quadratic", "cubic") else "linear"
    if k in ("quadratic", "cubic") and x.size < 4:
        k = "linear"
    try:
        if k == "linear":
            f = sci_interp.interp1d(x, y, kind="linear")
        else:
            f = sci_interp.interp1d(x, y, kind=k)
        yi = f(xi)
    except Exception as exc:  # noqa: BLE001
        result.notes = f"Interpolation failed: {exc}"
        return result
    result.curves["Interpolated"] = (xi, yi)
    result.summary = {"Points": float(xi.size), "N": float(x.size)}
    return result


def baseline_polynomial(x: Sequence[float], y: Sequence[float], *, degree: int = 3) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="baseline", title=f"Polynomial Baseline (deg {degree})")
    if x.size <= degree:
        result.notes = "Not enough points."
        return result
    coeffs = np.polyfit(x, y, degree)
    baseline = np.polyval(coeffs, x)
    result.curves["Baseline"] = (x, baseline)
    result.curves["Corrected"] = (x, y - baseline)
    result.summary = {"Degree": float(degree), "N": float(y.size)}
    return result


_OPERATIONS = (
    "Smooth (Savitzky-Golay)", "Moving Average", "Low-pass Filter", "High-pass Filter",
    "FFT Spectrum", "Derivative", "Integrate", "Interpolate", "Baseline (polynomial)",
)


def operations() -> list[str]:
    return list(_OPERATIONS)


def run_operation(
    name: str,
    x: Sequence[float],
    y: Sequence[float],
    *,
    window: int = 11,
    order: int = 3,
    cutoff: float = 1.0,
    points: int = 200,
) -> AnalysisResult:
    """Dispatch a named signal operation (shared by the dialog and recipes)."""
    if name in ("Smooth (Savitzky-Golay)", "savgol"):
        return smooth_savgol(x, y, window=window, order=order)
    if name in ("Moving Average", "moving"):
        return smooth_moving_average(x, y, window=window)
    if name in ("Low-pass Filter", "low"):
        return butter_filter(x, y, kind="low", cutoff=cutoff, order=order)
    if name in ("High-pass Filter", "high"):
        return butter_filter(x, y, kind="high", cutoff=cutoff, order=order)
    if name in ("FFT Spectrum", "fft"):
        return fft_spectrum(x, y)
    if name in ("Derivative", "derivative"):
        return differentiate(x, y, order=order)
    if name in ("Integrate", "integrate"):
        return integrate_curve(x, y)
    if name in ("Interpolate", "interpolate"):
        return interpolate(x, y, num=points)
    return baseline_polynomial(x, y, degree=order)


__all__ = [
    "fft_spectrum", "smooth_savgol", "smooth_moving_average", "butter_filter",
    "differentiate", "integrate_curve", "interpolate", "baseline_polynomial",
    "run_operation", "operations",
]
