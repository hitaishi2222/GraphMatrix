"""Instance registration: one slot, and every removal names its owner."""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    return tmp_path / "graphmatrix"


def test_register_and_get_round_trip(state_dir, tmp_path):
    from graphmatrix.core import instance

    project = tmp_path / "demo.rsproj"
    instance.register(project)
    data = instance.get()
    assert data is not None
    assert data["project"] == str(project)
    assert data["pid"] > 0


def test_unregister_only_removes_its_own_file(state_dir):
    """A stale cleanup must never delete the file of a newer window."""
    from graphmatrix.core import instance

    instance.register(None)
    instance.unregister(instance.get()["pid"] + 999)
    assert (state_dir / "instance.json").exists()
    instance.unregister(instance.get()["pid"])
    assert not (state_dir / "instance.json").exists()


def test_get_drops_a_dead_process_entry(state_dir):
    from graphmatrix.core import instance

    path = state_dir / "instance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # PID 1 exists; use a pid the kernel cannot have, and check that the file
    # it belongs to is the one removed.
    path.write_text(json.dumps({"pid": 2**31 - 1, "project": None}))
    assert instance.get() is None
    assert not path.exists()
