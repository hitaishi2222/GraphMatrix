"""Signal processing: FFT, smoothing, filters, calculus, interpolation, baseline.

Each routine returns an :class:`AnalysisResult` whose ``curves`` are ``(x, y)``
pairs the UI can add back as worksheet columns or graph plots.
"""

from __future__ import annotations

from collections.abc import Sequence

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
        "N": float(n),
        "Sampling freq": fs,
        "Peak frequency": float(freqs[peak]) if freqs.size else float("nan"),
        "Peak amplitude": float(amplitude[peak]) if amplitude.size else float("nan"),
    }
    return result


def smooth_savgol(
    x: Sequence[float], y: Sequence[float], *, window: int = 11, order: int = 3
) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="smooth", title="Savitzky-Golay Smoothing")
    window = min(
        window if window % 2 == 1 else window + 1,
        y.size if y.size % 2 == 1 else y.size - 1,
    )
    if window < order + 2:
        result.notes = "Window too small for the polynomial order."
        return result
    smoothed = sci_signal.savgol_filter(y, window, order)
    result.curves["Smoothed"] = (x, smoothed)
    result.summary = {
        "Window": float(window),
        "Order": float(order),
        "N": float(y.size),
    }
    return result


def smooth_moving_average(
    x: Sequence[float], y: Sequence[float], *, window: int = 5
) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="smooth", title="Moving Average")
    window = max(1, min(window, y.size))
    kernel = np.ones(window) / window
    smoothed = np.convolve(y, kernel, mode="same")
    result.curves["Smoothed"] = (x, smoothed)
    result.summary = {"Window": float(window), "N": float(y.size)}
    return result


def butter_filter(
    x: Sequence[float],
    y: Sequence[float],
    *,
    kind: str = "low",
    cutoff: float = 1.0,
    order: int = 4,
    fs: float | None = None,
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


def differentiate(
    x: Sequence[float], y: Sequence[float], *, order: int = 1
) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(
        kind="differentiate", title=f"Numerical Derivative (order {order})"
    )
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


def interpolate(
    x: Sequence[float], y: Sequence[float], *, num: int = 200, kind: str = "cubic"
) -> AnalysisResult:
    x, y = _clean(x, y)
    result = AnalysisResult(kind="interpolate", title=f"Interpolation ({kind})")
    if x.size < 2:
        result.notes = "Not enough data."
        return result
    order = np.argsort(x)
    x, y = x[order], y[order]
    xi = np.linspace(x.min(), x.max(), max(num, x.size))
    k = (
        kind
        if kind in ("linear", "nearest", "zero", "slinear", "quadratic", "cubic")
        else "linear"
    )
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


def baseline_polynomial(
    x: Sequence[float], y: Sequence[float], *, degree: int = 3
) -> AnalysisResult:
    x, y = _clean(x, y)
    if x.size <= degree:
        result = AnalysisResult(
            kind="baseline", title=f"Polynomial Baseline (deg {degree})"
        )
        result.notes = "Not enough points."
        return result
    coeffs = np.polyfit(x, y, degree)
    baseline = np.polyval(coeffs, x)
    return _baseline_result(
        x, y, baseline, f"Polynomial Baseline (deg {degree})", Degree=float(degree)
    )


def _baseline_result(
    x: np.ndarray, y: np.ndarray, baseline: np.ndarray, title: str, **summary: float
) -> AnalysisResult:
    """Package a fitted baseline + the corrected signal into an AnalysisResult."""
    result = AnalysisResult(kind="baseline", title=title)
    corrected = y - baseline
    result.curves["Baseline"] = (x, baseline)
    result.curves["Corrected"] = (x, corrected)
    result.summary = {
        **summary,
        "N": float(y.size),
        "Raw std": float(np.nanstd(y)),
        "Corrected std": float(np.nanstd(corrected)),
    }
    return result


def baseline_linear(x: Sequence[float], y: Sequence[float]) -> AnalysisResult:
    """Straight-line baseline (degree-1 polynomial, named for what it is)."""
    x, y = _clean(x, y)
    if x.size < 2:
        result = AnalysisResult(kind="baseline", title="Linear Baseline")
        result.notes = "Not enough points."
        return result
    coeffs = np.polyfit(x, y, 1)
    return _baseline_result(x, y, np.polyval(coeffs, x), "Linear Baseline")


def baseline_als(
    x: Sequence[float],
    y: Sequence[float],
    *,
    lam: float = 1e5,
    p: float = 0.01,
    niter: int = 10,
) -> AnalysisResult:
    """Asymmetric least squares baseline (Eilers & Boelens, 2005).

    ``lam`` sets smoothness (bigger = flatter), ``p`` the asymmetry (small = the
    baseline hugs the underside of the peaks). It is iterative, so keep ``niter``
    modest for interactive use.
    """
    from scipy import sparse
    from scipy.sparse.linalg import spsolve

    x, y = _clean(x, y)
    if x.size < 3:
        result = AnalysisResult(kind="baseline", title="Baseline (ALS)")
        result.notes = "Not enough points."
        return result

    n = y.size
    diff = sparse.diags([1.0, -2.0, 1.0], [0, -1, -2], shape=(n, n - 2))
    penalty = lam * diff.dot(diff.transpose())
    weights = np.ones(n)
    baseline = y.copy()
    for _ in range(max(1, niter)):
        weight_matrix = sparse.spdiags(weights, 0, n, n)
        baseline = spsolve((weight_matrix + penalty).tocsc(), weights * y)
        weights = p * (y > baseline) + (1.0 - p) * (y < baseline)
    return _baseline_result(
        x,
        y,
        np.asarray(baseline),
        "Baseline (ALS)",
        Lambda=float(lam),
        p=float(p),
        Iterations=float(niter),
    )


def baseline_rolling_ball(
    x: Sequence[float], y: Sequence[float], *, radius: int = 50
) -> AnalysisResult:
    """Morphological (grey-scale opening) baseline — a rolling ball under the signal."""
    from scipy import ndimage

    x, y = _clean(x, y)
    if x.size < 3:
        result = AnalysisResult(kind="baseline", title="Baseline (rolling ball)")
        result.notes = "Not enough points."
        return result
    size = max(3, int(2 * max(1, radius) + 1))
    if size % 2 == 0:
        size += 1
    baseline = ndimage.grey_opening(y, size=size)
    return _baseline_result(
        x, y, baseline, "Baseline (rolling ball)", Radius=float(radius)
    )


def baseline_rubber_band(x: Sequence[float], y: Sequence[float]) -> AnalysisResult:
    """Lower convex hull through the points (the "rubber band" baseline)."""
    x, y = _clean(x, y)
    if x.size < 3:
        result = AnalysisResult(kind="baseline", title="Baseline (rubber band)")
        result.notes = "Not enough points."
        return result
    order = np.argsort(x)
    xs, ys = x[order], y[order]
    hull_x, hull_y = _lower_hull(xs, ys)
    baseline = np.interp(xs, hull_x, hull_y)
    return _baseline_result(x, y, baseline, "Baseline (rubber band)")


def _lower_hull(xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Lower convex hull of a point set (Andrew's monotone chain)."""
    points = sorted(zip(xs.tolist(), ys.tolist(), strict=False))
    lower: list[tuple[float, float]] = []
    for point in points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    hull_x = np.array([p[0] for p in lower], dtype=float)
    hull_y = np.array([p[1] for p in lower], dtype=float)
    return hull_x, hull_y


def _cross(
    o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def baseline_median(
    x: Sequence[float], y: Sequence[float], *, window: int = 51
) -> AnalysisResult:
    """Median-filter baseline; robust to narrow peaks, so good for a first pass."""
    from scipy import signal as _signal

    x, y = _clean(x, y)
    if x.size < 3:
        result = AnalysisResult(kind="baseline", title="Baseline (median)")
        result.notes = "Not enough points."
        return result
    size = max(3, int(window))
    if size % 2 == 0:
        size += 1
    size = min(size, x.size if x.size % 2 == 1 else x.size - 1)
    baseline = _signal.medfilt(y, kernel_size=size)
    return _baseline_result(x, y, baseline, "Baseline (median)", Window=float(size))


#: Baseline methods accepted by :func:`baseline_correction`, in menu order.
BASELINE_METHODS = (
    "Polynomial",
    "Linear",
    "ALS",
    "Rolling ball",
    "Rubber band",
    "Median",
)


def baseline_correction(
    x: Sequence[float],
    y: Sequence[float],
    *,
    method: str = "Polynomial",
    degree: int = 3,
    lam: float = 1e5,
    p: float = 0.01,
    radius: int = 50,
    window: int = 51,
) -> AnalysisResult:
    """Dispatch to a named baseline method (shared by the dialog and recipes)."""
    key = (method or "Polynomial").strip().lower()
    if key in ("linear", "line"):
        return baseline_linear(x, y)
    if key in ("als", "asymmetric"):
        return baseline_als(x, y, lam=lam, p=p)
    if key in ("rolling ball", "rolling-ball", "rollingball", "morphological"):
        return baseline_rolling_ball(x, y, radius=radius)
    if key in ("rubber band", "rubber-band", "rubberband", "hull"):
        return baseline_rubber_band(x, y)
    if key in ("median", "median filter"):
        return baseline_median(x, y, window=window)
    return baseline_polynomial(x, y, degree=degree)


#: Maps the Signal dialog's operation names to baseline dispatcher methods.
_BASELINE_BY_OPERATION = {
    "Baseline (polynomial)": "Polynomial",
    "Baseline (linear)": "Linear",
    "Baseline (ALS)": "ALS",
    "Baseline (rolling ball)": "Rolling ball",
    "Baseline (rubber band)": "Rubber band",
    "Baseline (median)": "Median",
}

_OPERATIONS = (
    "Smooth (Savitzky-Golay)",
    "Moving Average",
    "Low-pass Filter",
    "High-pass Filter",
    "FFT Spectrum",
    "Derivative",
    "Integrate",
    "Interpolate",
    "Baseline (polynomial)",
    "Baseline (linear)",
    "Baseline (ALS)",
    "Baseline (rolling ball)",
    "Baseline (rubber band)",
    "Baseline (median)",
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
    lam: float = 1e5,
    baseline_method: str | None = None,
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
    if name in _BASELINE_BY_OPERATION or baseline_method is not None:
        method = baseline_method or _BASELINE_BY_OPERATION.get(name, name)
        return baseline_correction(
            x,
            y,
            method=method,
            degree=order,
            lam=lam,
            radius=window,
            window=window,
        )
    return baseline_polynomial(x, y, degree=order)


__all__ = [
    "BASELINE_METHODS",
    "baseline_als",
    "baseline_correction",
    "baseline_linear",
    "baseline_median",
    "baseline_polynomial",
    "baseline_rolling_ball",
    "baseline_rubber_band",
    "butter_filter",
    "differentiate",
    "fft_spectrum",
    "integrate_curve",
    "interpolate",
    "operations",
    "run_operation",
    "smooth_moving_average",
    "smooth_savgol",
]
