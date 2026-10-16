# -*- mode: python ; coding: utf-8 -*-
# Builds a self-contained Festival Extractor - icon, logo, keys.bin, the theme and
# the audio libraries are all inside it:
#
#     pip install -r requirements.txt pyinstaller
#     pyinstaller FFR.spec
#
# Output in dist/: "Festival Extractor.exe" on Windows, "Festival Extractor.app" on macOS,
# "Festival Extractor" on Linux.
import sys
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

if sys.platform == 'darwin':
    # macOS apps are folders (.app bundles), not single files
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Festival Extractor',
        icon='media/icon.png',
        console=False,
        upx=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name='Festival Extractor', upx=False)
    app = BUNDLE(
        coll,
        name='Festival Extractor.app',
        icon='media/icon.png',
        bundle_identifier='com.ilayezra.festivalextractor',
        info_plist={'NSHighResolutionCapable': True},
    )
else:
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
