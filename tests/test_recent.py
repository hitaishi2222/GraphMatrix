"""Recent projects: ordering, pruning, and the settings round trip."""

from __future__ import annotations

from graphmatrix.ui import recent


def test_remember_puts_the_newest_first_and_deduplicates():
    paths = ["/a.rsproj", "/b.rsproj", "/a.rsproj"]
    assert recent.remember(paths, "/a.rsproj") == ["/a.rsproj", "/b.rsproj"]
    assert recent.remember(paths, "/c.rsproj")[0] == "/c.rsproj"


def test_remember_caps_the_list():
    paths = [f"/p{i}.rsproj" for i in range(9)]
    assert recent.remember(paths, "/new.rsproj", limit=3) == [
        "/new.rsproj",
        "/p0.rsproj",
        "/p1.rsproj",
    ]


def test_prune_drops_files_that_are_gone(tmp_path):
    kept = tmp_path / "kept.rsproj"
    kept.write_text("{}")
    assert recent.prune([str(kept), str(tmp_path / "gone.rsproj")]) == [str(kept)]


def test_display_name_shows_the_file_then_its_folder(tmp_path):
    project = tmp_path / "work" / "spectra.rsproj"
    project.parent.mkdir()
    project.write_text("{}")
    text = recent.display_name(str(project))
    assert text.startswith("spectra.rsproj")
    assert "work" in text


def test_load_and_save_round_trip(monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path / "recent.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("graphmatrix.ui.settings.app_settings", lambda: settings)
    recent.save(["/one.rsproj", "/two.rsproj"])
    assert recent.load() == ["/one.rsproj", "/two.rsproj"]


def test_headless_app_has_no_settings(monkeypatch):
    monkeypatch.setattr("graphmatrix.ui.settings.app_settings", lambda: None)
    assert recent.load() == []
    recent.save(["/ignored.rsproj"])  # must not raise


def test_saving_an_empty_list_round_trips(monkeypatch, tmp_path):
    """QSettings turns an empty list into an absent key; loading must cope."""
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path / "empty.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("graphmatrix.ui.settings.app_settings", lambda: settings)
    recent.save([])
    assert recent.load() == []
    recent.save(["/one.rsproj"])
    recent.save([])
    assert recent.load() == []
