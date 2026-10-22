"""Scripting: programmatic API, macro recording, batch processing."""

from .api import GraphMatrixAPI, make_namespace
from .record import MacroRecorder

__all__ = ["GraphMatrixAPI", "MacroRecorder", "make_namespace"]
