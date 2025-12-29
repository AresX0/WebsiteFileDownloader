# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['epstein_downloader_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('config.json', '.'), ('queue_state.json', '.'), ('assets', 'assets')],
    hiddenimports=['google', 'google.oauth2', 'googleapiclient', 'gdown', 'playwright'],
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
    name='EpsteinDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
