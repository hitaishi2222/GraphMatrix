"""Analysis recipe + batch pipeline tests (M3/M5)."""

from __future__ import annotations

import numpy as np
import pytest

from respot.core.batch import run_recipe_over_files
from respot.core.io import importer
from respot.core.model import ColumnType, Worksheet
from respot.core.recipes import Recipe, load_recipe, run_recipe, save_recipe


def _decay(n: int = 200):
    x = np.linspace(0, 10, n)
    return x, 3.0 * np.exp(-x / 2.5) + 0.2


def test_recipe_runs_and_roundtrips(tmp_path):
    x, y = _decay()
    recipe = Recipe("fit", {"model": "Exponential Decay"}, label="exp")
    result = run_recipe(recipe, x, y)
    assert result.summary["R²"] > 0.99

    path = save_recipe(recipe, tmp_path / "r.json")
    loaded = load_recipe(path)
    assert loaded.operation == "fit"
    assert loaded.params["model"] == "Exponential Decay"
    assert loaded.name == "exp"


def test_recipe_signal_and_peaks():
    x, y = _decay()
    assert run_recipe(Recipe("signal", {"operation": "FFT Spectrum"}), x, y).kind == "fft"
    assert run_recipe(Recipe("descriptive"), x, y).summary["N"] == 200


def test_recipe_rejects_unknown_operation(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"format": "respot-recipe", "operation": "nonsense"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_recipe(path)


def test_batch_recipe_pipeline(tmp_path):
    x = np.linspace(0, 10, 150)
    reports = tmp_path / "reports"
    figures = tmp_path / "figs"
    for index in range(2):
        sheet = Worksheet("S")
        sheet.add_column("X1", ColumnType.X, x, units="s")
        sheet.add_column("Y1", ColumnType.Y, 3.0 * np.exp(-x / 2.5) + 0.1 * index)
        importer.export_delimited(sheet, tmp_path / f"f{index}.csv")

    recipe = Recipe("fit", {"model": "Exponential Decay"})
    items = run_recipe_over_files(
        [tmp_path / "f0.csv", tmp_path / "f1.csv", tmp_path / "missing.csv"],
        recipe, report_dir=reports, export_dir=figures,
    )

    assert items[0].ok and items[1].ok and not items[2].ok
    assert items[0].result.summary["R²"] > 0.99
    assert (reports / "f0.txt").exists()
    assert (figures / "f0.pdf").exists() and (figures / "f0.pdf").stat().st_size > 0
