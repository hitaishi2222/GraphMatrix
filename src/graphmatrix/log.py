"""Logging for GraphMatrix: one rotating file, warnings on stderr.

Both entry points (the GUI in :mod:`graphmatrix.app` and the MCP server) call
:func:`configure` once at startup. Every other module gets its logger from
:func:`get_logger`, so a record always says which subsystem failed.

Several places in the UI deliberately swallow an exception — a canvas redraw
must not crash because one marker style is unsupported, for example. Those
guards log at DEBUG: invisible by default, and one environment variable away
when a redraw or an export misbehaves:

    GRAPHMATRIX_LOG_LEVEL=DEBUG graphmatrix

stderr is used, never stdout: the MCP server speaks JSON-RPC on stdout.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = "graphmatrix"

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s:%(funcName)s:%(lineno)d: %(message)s"

_configured = False


def state_dir() -> Path:
    """The platform state directory, shared with the instance/IPC files."""
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "graphmatrix"


def log_path() -> Path:
    return state_dir() / "graphmatrix.log"


def get_logger(name: str) -> logging.Logger:
    """The logger for ``name`` (``__name__`` works, short names are prefixed)."""
    if name != ROOT and not name.startswith(f"{ROOT}."):
        name = f"{ROOT}.{name}"
    return logging.getLogger(name)


def configure(level: str | int | None = None) -> Path | None:
    """Attach the file (and stderr) handler once. Returns the log file path.

    The file keeps INFO and above; stderr shows WARNING and above so a console
    launch stays quiet. ``level`` (or ``GRAPHMATRIX_LOG_LEVEL``) raises the file
    level, e.g. to ``DEBUG``. When the state directory is not writable the file
    handler is skipped and stderr still works.
    """
    global _configured
    root = logging.getLogger(ROOT)
    level = level or os.environ.get("GRAPHMATRIX_LOG_LEVEL") or logging.INFO
    root.setLevel(level)
    if _configured:
        return log_path()
    root.propagate = False

    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(console)

    path: Path | None = None
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
    except OSError:
        path = None  # read-only home: stderr is all we get
    _configured = True
    return path


__all__ = ["ROOT", "configure", "get_logger", "log_path", "state_dir"]
