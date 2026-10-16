# -*- mode: python ; coding: utf-8 -*-
# Builds a single self-contained "Festival Extractor.exe" - icon, logo, keys.bin,
# the theme and the audio libraries are all inside it:
#
#     pip install -r requirements.txt pyinstaller
#     pyinstaller FFR.spec
#
# The exe is written to dist/
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['FFR.py'],
    datas=[
        ('media/icon.png', '.'),
        ('media/logo.png', '.'),
        ('alpha/keys.bin', '.'),
        *collect_data_files('sv_ttk'),
    ],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='Festival Extractor',
    icon='media/icon.png',
    console=False,
    upx=False,
)
