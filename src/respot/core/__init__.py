"""Respot's Qt-free engine: data model, commands, project I/O.

Nothing in this package may import PySide6. That boundary keeps the engine
testable headlessly, usable for batch processing, and free to be accelerated
later (PyO3/Cython) without touching the UI.
"""
