"""Application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from respot import __version__
from respot.ui.main_window import MainWindow
from respot.ui.theme import apply_theme, load_saved_preset

APP_NAME = "Respot"
ORG_NAME = "Respot"


def run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    apply_theme(app, preset=load_saved_preset())  # Dark ("classic-dark") by default

    window = MainWindow()
    window.show()
    return app.exec()
