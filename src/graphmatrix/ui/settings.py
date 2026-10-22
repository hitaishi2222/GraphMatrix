"""QSettings access that stays quiet in headless tests.

A settings object bound to the named application, or ``None`` when there is
none: tests construct a bare ``QApplication`` and must not write to a stray
"Unknown Organization" file on the developer's machine.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication


def app_settings() -> QSettings | None:
    app = QApplication.instance()
    if app is None or not app.organizationName():
        return None
    return QSettings()


__all__ = ["app_settings"]
