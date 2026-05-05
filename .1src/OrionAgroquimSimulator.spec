# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

<<<<<<< HEAD
datas = [('D:\\GitHub\\Orion_Fert\\INSUMOS_IN39_2018.csv', '.'), ('D:\\GitHub\\Orion_Fert\\ADITIVOS_IN39_2018.csv', '.')]
=======
datas = [('C:\\Users\\orion\\Documents\\GitHub\\Orion_Fert-NTB\\INSUMOS_IN39_2018.csv', '.'), ('C:\\Users\\orion\\Documents\\GitHub\\Orion_Fert-NTB\\ADITIVOS_IN39_2018.csv', '.')]
>>>>>>> 719263f18fa5f1f6d8803061ff8917b3ff208def
binaries = []
hiddenimports = ['flet_desktop']
tmp_ret = collect_all('flet_desktop')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
<<<<<<< HEAD
    ['D:\\GitHub\\Orion_Fert\\.1src\\1.main.py'],
=======
    ['C:\\Users\\orion\\Documents\\GitHub\\Orion_Fert-NTB\\.1src\\1.main.py'],
>>>>>>> 719263f18fa5f1f6d8803061ff8917b3ff208def
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='OrionAgroquimSimulator',
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
