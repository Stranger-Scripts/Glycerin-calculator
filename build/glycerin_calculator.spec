# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

# The .spec is executed from the project root by PyInstaller, but resolve
# paths relative to this file so the build works regardless of CWD.
SPECDIR = Path(SPECPATH)
PKG = SPECDIR.parent / "src" / "glycerin_calculator"

a = Analysis(
    ['launcher.py'],
    pathex=[str(SPECDIR.parent / "src")],
    binaries=[],
    datas=[
        (str(PKG / "static"), "glycerin_calculator/static"),
        (str(PKG / "templates"), "glycerin_calculator/templates"),
    ],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='glycerin-calculator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='glycerin-calculator',
)
