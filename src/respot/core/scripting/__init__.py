"""Scripting: programmatic API, macro recording, batch processing."""

from .api import RespotAPI, make_namespace
from .record import MacroRecorder

__all__ = ["RespotAPI", "make_namespace", "MacroRecorder"]
