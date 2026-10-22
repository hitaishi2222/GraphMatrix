"""Track a running GraphMatrix GUI instance for coordination with MCP/agents."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from graphmatrix.log import get_logger

log = get_logger(__name__)


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


def _alive_on_windows(pid: int) -> bool:
    """Whether ``pid`` is running, through OpenProcess (never os.kill)."""
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def process_alive(pid: int) -> bool:
    """Is ``pid`` a running process?

    ``os.kill(pid, 0)`` is not a portable probe: on Windows signal 0 is
    ``CTRL_C_EVENT``, so it sends Ctrl+C to that process group instead of
    asking whether anything is there.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        return _alive_on_windows(pid)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True  # it exists, it is just not ours to signal
    except OSError:
        return False
    return True


def _read() -> dict[str, Any] | None:
    """The recorded payload, without checking whether its process is alive."""
    path = _state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a half-written file is no instance
        return None
    return data if isinstance(data.get("pid"), int) else None


def unregister(pid: int | None = None) -> None:
    """Remove the instance file, but only if it still describes ``pid``.

    Without the check, cleaning up *our* stale entry would delete the file a
    *newer* window just wrote and agents would lose the running window: the
    file is a single slot, so every removal has to name its owner.
    """
    try:
        if pid is not None:
            data = _read()
            if data is None or data.get("pid") != pid:
                return
        _state_path().unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001 - a stale file is not fatal
        log.warning("could not remove the instance file: %s", exc)


def get() -> dict[str, Any] | None:
    data = _read()
    if data is None:
        return None
    pid = data["pid"]
    if not process_alive(pid):
        unregister(pid)
        return None
    return data


__all__ = ["get", "process_alive", "register", "unregister"]
