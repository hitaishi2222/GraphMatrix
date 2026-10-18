"""Application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from graphmatrix import __version__
from graphmatrix.ui.main_window import MainWindow
from graphmatrix.ui.theme import apply_theme, load_saved_preset

APP_NAME = "GraphMatrix"
ORG_NAME = "GraphMatrix"


def run(argv: list[str] | None = None, project_paths: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    import os
    # On Wayland compositors (e.g. Hyprland) prefer the native wayland platform
    # plugin so windows tile instead of opening as floating XWayland windows.
    if "WAYLAND_DISPLAY" in os.environ:
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    # Hyprland (and other compositors) key window rules off the window's
    # application id / class. When running from a Python interpreter that id
    # defaults to "python3", which many user configs (including ours) float.
    # Pin it to the app name so the window is treated as a normal tiled app.
    app.setDesktopFileName("graphmatrix")
    apply_theme(app, preset=load_saved_preset())  # Dark ("classic-dark") by default

    windows: list[MainWindow] = []
    paths = list(project_paths or [])
    if not paths:
        window = MainWindow()
        windows.append(window)
        window.show()
    else:
        for path in paths:
            w = MainWindow()
            try:
                w._open_project_path(path)
            except Exception:  # noqa: BLE001
                pass
            windows.append(w)
            w.show()
    # Keep references alive for the lifetime of the event loop.
    app._graphmatrix_windows = windows
    return app.exec()
