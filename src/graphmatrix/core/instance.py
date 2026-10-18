"""Track a running GraphMatrix GUI instance for coordination with MCP/agents."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _state_dir() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    d = base / "graphmatrix"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path() -> Path:
    return _state_dir() / "instance.json"


def register(project_path: str | Path | None) -> None:
    payload = {
        "pid": os.getpid(),
        "project": str(project_path) if project_path else None,
    }
    _state_path().write_text(json.dumps(payload), encoding="utf-8")


def unregister() -> None:
    try:
        _state_path().unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


def get() -> dict[str, Any] | None:
    path = _state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    pid = data.get("pid")
    if not isinstance(pid, int):
        return None
    # Check if process is alive.
    try:
        os.kill(pid, 0)
    except OSError:
        unregister()
        return None
    return data
