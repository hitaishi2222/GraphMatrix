"""Analysis toolkit tests (M3)."""

from __future__ import annotations

import numpy as np

from respot.core.analysis import descriptive, fitting, peaks, regression, signal, statistics


def _exp_decay(n=200):
    x = np.linspace(0, 10, n)
    y = 3.0 * np.exp(-x / 2.5) + 0.2
    return x, y


def test_descriptive_stats():
    result = descriptive.summarize([1.0, 2.0, 3.0, 4.0, 5.0])
    assert result.summary["N"] == 5
    assert result.summary["Mean"] == 3.0
    assert result.summary["Median"] == 3.0


def test_linear_regression():
    x = np.arange(10.0)
    y = 2.0 * x + 1.0
    result = regression.linear_fit(x, y)
    assert abs(result.summary["R²"] - 1.0) < 1e-9
    assert abs(result.parameters[0].value - 2.0) < 1e-9
    assert "Fit" in result.curves


def test_polynomial_regression():
    x = np.linspace(-3, 3, 50)
    y = x ** 3 - 2 * x + 1
    result = regression.polynomial_fit(x, y, degree=3)
    assert result.summary["R²"] > 0.999


def test_nonlinear_fit_recovers_parameters():
    x, y = _exp_decay()
    result = fitting.fit_model("Exponential Decay", x, y)
    assert result.summary["R²"] > 0.999
    by_name = {p.name: p.value for p in result.parameters}
    assert abs(by_name["amplitude"] - 3.0) < 0.05
    assert abs(by_name["decay"] - 2.5) < 0.05


def test_fit_with_uncertainties():
    x, y = _exp_decay()
    yerr = np.full_like(y, 0.01)
    result = fitting.fit_model("Exponential Decay", x, y, yerr=yerr)
    assert all(p.error is not None for p in result.parameters)


def test_gaussian_fit():
    x = np.linspace(-5, 5, 400)
    y = 2.0 * np.exp(-((x - 1.0) ** 2) / (2 * 0.7 ** 2))
    result = fitting.fit_model("Gaussian", x, y)
    by_name = {p.name: p.value for p in result.parameters}
    assert abs(by_name["center"] - 1.0) < 0.05
    assert abs(by_name["sigma"] - 0.7) < 0.05


def test_peak_finding():
    x = np.linspace(-5, 5, 1001)
    y = np.exp(-(x ** 2) / 0.5) + np.exp(-((x - 2) ** 2) / 0.5)
    result = peaks.find_peaks_result(x, y)
    assert result.summary["Peaks"] == 2.0


def test_fft_finds_frequency():
    x = np.linspace(0, 1, 1000)
    y = np.sin(2 * np.pi * 5 * x)
    result = signal.fft_spectrum(x, y)
    assert abs(result.summary["Peak frequency"] - 5.0) < 0.2


def test_smoothing_and_derivative_and_integral():
    x, y = _exp_decay()
    assert "Smoothed" in signal.smooth_savgol(x, y).curves
    assert "Derivative" in signal.differentiate(x, y).curves
    assert "Interpolated" in signal.interpolate(x[:30], y[:30]).curves
    assert signal.integrate_curve(x, y).summary["Total area"] > 0


def test_statistics_suite():
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    b = np.array([2.0, 3.0, 4.0, 5.0, 6.0])
    assert statistics.ttest_ind(a, b).summary["N A"] == 5
    assert statistics.correlation(a, b).summary["r"] > 0.99
    assert "Histogram" in statistics.histogram(a, bins=3).curves
    assert statistics.anova_oneway([a, b, a + 1]).summary["Groups"] == 3
