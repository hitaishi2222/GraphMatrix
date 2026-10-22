"""Logging: one configured logger, a file in the state dir, nothing on stdout."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import pytest

from graphmatrix import log as gm_log


@pytest.fixture()
def clean_logger(monkeypatch, tmp_path):
    """A fresh ``graphmatrix`` logger writing into a throwaway state dir."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    root = logging.getLogger(gm_log.ROOT)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    monkeypatch.setattr(gm_log, "_configured", False)
    yield root
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


def test_configure_writes_the_log_file_in_the_state_dir(clean_logger, tmp_path):
    path = gm_log.configure(level="DEBUG")
    assert path == tmp_path / "graphmatrix" / "graphmatrix.log"
    gm_log.get_logger("tests.demo").debug("hello %s", "file")
    for handler in clean_logger.handlers:
        handler.flush()
    content = path.read_text(encoding="utf-8")
    assert "hello file" in content
    assert "tests.demo" in content


def test_configure_is_idempotent(clean_logger):
    before = list(clean_logger.handlers)
    gm_log.configure()
    ours = [h for h in clean_logger.handlers if h not in before]
    # Exactly one file handler and one stderr handler, never a duplicate pair.
    assert len(ours) == 2, [type(h).__name__ for h in ours]
    assert any(isinstance(h, RotatingFileHandler) for h in ours)
    assert any(type(h) is logging.StreamHandler for h in ours)
    gm_log.configure()
    assert [h for h in clean_logger.handlers if h not in before] == ours


def test_loggers_are_namespaced_under_the_root():
    assert gm_log.get_logger("graphmatrix.core.io").name == "graphmatrix.core.io"
    assert gm_log.get_logger("core.io").name == "graphmatrix.core.io"
    assert gm_log.get_logger(gm_log.ROOT).name == gm_log.ROOT


def test_the_log_level_follows_the_environment(clean_logger, monkeypatch):
    monkeypatch.setenv("GRAPHMATRIX_LOG_LEVEL", "DEBUG")
    gm_log.configure()
    assert clean_logger.level == logging.DEBUG
