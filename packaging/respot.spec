# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Respot.

Build with:  pyinstaller packaging/respot.spec --noconfirm
Produces a one-directory bundle under dist/respot/ (faster startup and fewer
antivirus false positives than --onefile).
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SRC = os.path.abspath(os.path.join(SPECPATH, "..", "src"))
ENTRY = os.path.join(SRC, "respot", "__main__.py")

hiddenimports = (
    collect_submodules("pyqtgraph")
    + collect_submodules("lmfit")
    + collect_submodules("openpyxl")
    + collect_submodules("pyarrow")
    + ["scipy.special._cdflib"]
)

datas = []
datas += collect_data_files("pyqtgraph")
datas += collect_data_files("matplotlib")

a = Analysis(
    [ENTRY],
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="respot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed app; use console=True for debugging
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="respot",
)

# macOS: build a .app bundle instead of a bare directory.
import sys  # noqa: E402

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Respot.app",
        icon=None,
        bundle_identifier="org.respot.app",
        info_plist={"NSHighResolutionCapable": True},
    )
