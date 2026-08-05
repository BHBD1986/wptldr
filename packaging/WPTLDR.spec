# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the WP TLDR desktop app.

Build from the project root:
    pyinstaller packaging/WPTLDR.spec

Produces a onedir build under dist/WPTLDR (Windows) or dist/WPTLDR.app
(macOS). The AI model is intentionally NOT bundled — it is downloaded into
the user's app-data folder on first launch.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH).resolve().parents[0]

app_version = os.environ.get("WPTLDR_VERSION", "0.1.0")

datas = [(str(root / "frontend"), "frontend")]
binaries = []
hiddenimports = []

for pkg in ("llama_cpp", "uvicorn"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += collect_submodules("fastapi")

a = Analysis(
    [str(root / "backend" / "launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WPTLDR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    bundle_identifier="com.wptldr.app",
    info_plist={
        "CFBundleDisplayName": "WP TLDR",
        "CFBundleShortVersionString": app_version,
        "CFBundleVersion": app_version,
        "NSHighResolutionCapable": True,
    },
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="WPTLDR",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="WPTLDR.app",
        icon=None,
        bundle_identifier="com.wptldr.app",
        info_plist={
            "CFBundleDisplayName": "WP TLDR",
            "CFBundleShortVersionString": app_version,
            "CFBundleVersion": app_version,
            "NSHighResolutionCapable": True,
        },
    )
