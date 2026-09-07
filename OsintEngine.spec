# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

PROJECT_ROOT = Path(SPECPATH).resolve()
ASSETS_DIR = PROJECT_ROOT / "assets"

maigret_datas, maigret_binaries, maigret_hiddenimports = collect_all("maigret")

a = Analysis(
    [str(PROJECT_ROOT / "app" / "main_flet.py")],
    pathex=[str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "app")],
    binaries=maigret_binaries,
    datas=[(str(ASSETS_DIR), "assets"), *maigret_datas],
    hiddenimports=maigret_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="OSINT_Engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
