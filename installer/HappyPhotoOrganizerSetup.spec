# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Happy Photo Organizer Installer (one-file)
"""
from pathlib import Path

ROOT = Path.cwd()

a = Analysis(
    [str(ROOT / 'installer' / 'installer.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'dist' / 'HappyPhotoOrganizer.zip'), 'payload'),
        (str(ROOT / 'assets'), 'assets'),
    ],
    hiddenimports=['win32com.client', 'pythoncom'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'numpy.f2py', 'pytest', 'sphinx',
        'tkinterdnd2',  # installer doesn't need DnD
        'google.genai', 'pillow_heif',  # installer doesn't need either
    ],
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
    name='HappyPhotoOrganizerSetup',
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
    icon=str(ROOT / 'assets' / 'happy_icon.ico'),
)
