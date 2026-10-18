#!/usr/bin/env bash
# Build a GraphMatrix bundle for the current platform with PyInstaller.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Installing build dependencies…"
python -m pip install --upgrade pip >/dev/null
python -m pip install -e ".[dev]" >/dev/null

echo "Running tests…"
QT_QPA_PLATFORM=offscreen python -m pytest -q

echo "Building bundle…"
python -m PyInstaller packaging/graphmatrix.spec --noconfirm --clean

echo
echo "Done. See dist/graphmatrix/ (or dist/GraphMatrix.app on macOS)."
