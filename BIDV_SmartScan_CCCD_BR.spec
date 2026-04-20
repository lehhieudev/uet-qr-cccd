# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['doc_qr_cccd_desktop.py'],
    pathex=[],
    binaries=[('libs\\libzbar-64.dll', '.'), ('libs\\libiconv.dll', '.')],
    datas=[('models', 'models')],
    hiddenimports=['pyzbar', 'cv2'],
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
    name='BIDV_SmartScan_CCCD_BR',
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
    icon=['qr-code.ico'],
)
