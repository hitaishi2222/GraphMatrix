"""Application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from graphmatrix import __version__
from graphmatrix.log import configure, get_logger
from graphmatrix.ui.main_window import MainWindow
from graphmatrix.ui.theme import apply_theme, load_saved_preset

APP_NAME = "GraphMatrix"
ORG_NAME = "GraphMatrix"

log = get_logger(__name__)


def run(
    argv: list[str] | None = None,
    project_paths: list[str] | None = None,
    open_graph: str | None = None,
) -> int:
    argv = list(sys.argv if argv is None else argv)
    import os

    configure()

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
                if open_graph:
                    graph = w.project.graph(open_graph)
                    if graph is not None:
                        w._open_graph_tab(graph)
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the others
                log.warning("could not open %s: %s", path, exc)
            windows.append(w)
            w.show()
    # One IPC bridge per window so agents can drive the live GUI directly.
    from graphmatrix.core.ipc import IpcBridge

    app._graphmatrix_ipc = [IpcBridge(w) for w in windows]
    # Keep references alive for the lifetime of the event loop.
    app._graphmatrix_windows = windows
    # Announce this instance so agents can find the bridge even when the
    # window was started without a project file.
    from graphmatrix.core.instance import register as register_instance

    first = windows[0] if windows else None
    register_instance(first._path if first is not None else None)
    # Remove our entry on a clean quit; the pid guard keeps it from deleting a
    # newer window's file.
    import os

    from graphmatrix.core.instance import unregister as unregister_instance

    app.aboutToQuit.connect(lambda: unregister_instance(os.getpid()))
    return app.exec()
