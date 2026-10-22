"""Recent projects: the short list the welcome page and File menu offer.

The list lives in ``QSettings`` beside the theme preset. Only files that still
exist are offered, so deleting a project never leaves a dead entry behind. The
list logic is pure so it can be tested without a window.
"""

from __future__ import annotations

from pathlib import Path

#: How many projects the welcome page and the menu show.
LIMIT = 5

SETTINGS_KEY = "files/recent"


def remember(paths: list[str], path: str | Path, limit: int = LIMIT) -> list[str]:
    """``path`` first, de-duplicated, capped at ``limit``."""
    text = str(path)
    rest = [other for other in paths if other != text]
    return [text, *rest][:limit]


def prune(paths: list[str]) -> list[str]:
    """Keep the entries whose file still exists, preserving order."""
    return [p for p in paths if Path(p).is_file()]


def display_name(path: str) -> str:
    """``analysis.rsproj — ~/work``: the name first, the folder for context."""
    location = Path(path)
    folder = location.parent
    try:
        folder_text = "~/" + str(folder.relative_to(Path.home()))
    except ValueError:
        folder_text = str(folder)
    return f"{location.name}  ·  {folder_text}"


def load() -> list[str]:
    from graphmatrix.ui.settings import app_settings

    settings = app_settings()
    if settings is None:
        return []
    value = settings.value(SETTINGS_KEY, [])
    if value is None:  # an empty list is stored as an absent key
        return []
    if isinstance(value, str):  # a one-entry list comes back as a bare string
        value = [value]
    return [str(item) for item in value]


def save(paths: list[str]) -> None:
    from graphmatrix.ui.settings import app_settings

    settings = app_settings()
    if settings is None:
        return
    if not paths:
        settings.remove(SETTINGS_KEY)  # an empty list round-trips as None
    else:
        settings.setValue(SETTINGS_KEY, list(paths))
    settings.sync()


__all__ = ["LIMIT", "SETTINGS_KEY", "display_name", "load", "prune", "remember", "save"]
