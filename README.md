# Respot

A cross-platform scientific data analysis and graphing GUI.

Respot aims to be a Python-first, open alternative to tools like OriginPro:
typed worksheet columns, publication-quality 2D graphs, a real analysis toolkit,
and scriptable automation. It targets Windows, macOS, and Linux from a single codebase.

> Status: **M0 (skeleton)**. The application shell, project model, command/undo
> system, plugin loader, and a minimal plot canvas are in place. Analysis and
> publication export land in later milestones — see [`PLAN.md`](PLAN.md).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# run the app
PYTHONPATH=src python -m respot

# run the tests (core only, no GUI required)
pytest
```

Or install as a package:

```bash
pip install -e ".[dev]"
respot
```

## Layout

```
src/respot/
  core/        Qt-free engine: data model, commands, project I/O (future: analysis)
  ui/          PySide6 views: main window, panels, plot canvas
  plugins/     Drop-in plugins discovered at startup
tests/         Core unit tests (headless)
```

The golden rule: **`core/` never imports PySide6.** That keeps the engine
testable, headless-batchable, and free to be accelerated later without touching the UI.

## Documentation

- [`PLAN.md`](PLAN.md) — architecture, decisions, milestones, risks.
