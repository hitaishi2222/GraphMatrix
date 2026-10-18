"""Plugin discovery.

A plugin is any module under ``graphmatrix.plugins`` exposing ``register(context)``.
Failures are reported, never fatal, so a broken third-party plugin cannot stop
the app from starting.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any


@dataclass
class PluginContext:
    """The handles a plugin is given at registration time."""

    window: Any
    registry: Any
    commands: Any
    plugins_menu: Any


@dataclass
class LoadedPlugin:
    name: str
    ok: bool
    error: str | None = None


def load_plugins(
    context: PluginContext,
    package: str = "graphmatrix.plugins",
    *,
    exclude: tuple[str, ...] = ("loader",),
) -> list[LoadedPlugin]:
    results: list[LoadedPlugin] = []
    pkg = importlib.import_module(package)
    for modinfo in pkgutil.iter_modules(pkg.__path__):
        name = modinfo.name
        if name.startswith("_") or name in exclude:
            continue
        full = f"{package}.{name}"
        try:
            module = importlib.import_module(full)
        except Exception as exc:  # noqa: BLE001
            results.append(LoadedPlugin(name, False, f"import failed: {exc}"))
            continue
        register = getattr(module, "register", None)
        if not callable(register):
            continue
        try:
            register(context)
            results.append(LoadedPlugin(name, True))
        except Exception as exc:  # noqa: BLE001
            results.append(LoadedPlugin(name, False, f"{type(exc).__name__}: {exc}"))
    return results
