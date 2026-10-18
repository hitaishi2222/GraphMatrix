# Packaging & distribution

GraphMatrix ships as a frozen desktop bundle per platform. Freezing is set up from the
start (milestone M0) because Python desktop distribution is the classic place these
projects stall.

## Build locally

```bash
pip install -e ".[dev]"
python -m PyInstaller packaging/graphmatrix.spec --noconfirm --clean
```

Output:
- Linux/Windows: `dist/graphmatrix/` (a directory bundle; run `dist/graphmatrix/graphmatrix`)
- macOS: `dist/GraphMatrix.app`

`packaging/build.sh` does install → test → build in one step.

### One-directory vs one-file

The spec uses **one-directory** (`COLLECT`). It starts faster and triggers fewer
antivirus false positives than `--onefile`. If you need a single file, add
`--onefile`-style `EXE(..., a.binaries, a.datas, ...)`; expect slower cold start.

## Platform notes

### Windows
- Code-sign the executable with Authenticode (an EV certificate avoids SmartScreen
  warnings). `signtool sign /fd sha256 /tr <timestamp-url> /td sha256 dist\graphmatrix\graphmatrix.exe`.
- Build on the oldest Windows you intend to support.

### macOS
- The spec builds a `.app`. Notarize (not just sign) for Gatekeeper:
  `codesign --deep --force --options runtime --sign "Developer ID Application: …" dist/GraphMatrix.app`
  then `xcrun notarytool submit … --wait` and `xcrun stapler staple dist/GraphMatrix.app`.
- Build per-architecture (arm64, x86_64) or produce a universal2 build.

### Linux
- Bundle as AppImage or ship a `.deb`/`.rpm`. The frozen binary still needs system
  EGL/XKB libraries (the CI installs `libegl1 libxkbcommon0 libdbus-1-3 libglib2.0-0`).

## Qt plugin pitfalls

Frozen Qt apps most commonly fail because a platform plugin or image-format plugin
is missing. PyInstaller's PySide6 hooks usually handle this; if you hit
`could not load the Qt platform plugin "xcb"`, set `QT_DEBUG_PLUGINS=1` and confirm
`PySide6/plugins/platforms/` landed in the bundle.

## CI

`.github/workflows/ci.yml`:
- **test** job: matrix of Ubuntu / macOS / Windows × Python 3.11 / 3.13, runs the
  headless test suite (`QT_QPA_PLATFORM=offscreen`).
- **build** job: on `v*` tags, produces bundles for all three platforms as artifacts.

## Roadmap for shipping (M6 remaining)

- Installers: WiX/MSI (Windows), DMG (macOS), AppImage + deb (Linux).
- Auto-update channel.
- Opt-in crash reporting and telemetry.
- Versioned project-format stability guarantees.
