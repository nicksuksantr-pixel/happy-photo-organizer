# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Happy Photo Organizer
Build: pyinstaller HappyPhotoOrganizer.spec --noconfirm
"""
import sys
from pathlib import Path

# Allow access to customtkinter and tkinterdnd2 data
import customtkinter
import tkinterdnd2

ctk_path = Path(customtkinter.__file__).parent
tkdnd_path = Path(tkinterdnd2.__file__).parent


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Plain-text version file — read at runtime by main.py:_read_version
        ('VERSION', '.'),
        # bundled assets
        ('assets', 'assets'),
        ('data/job_catalog.json', 'data'),
        # CTk runtime resources
        (str(ctk_path), 'customtkinter'),
        # tkdnd2 native libs
        (str(tkdnd_path / 'tkdnd'), 'tkinterdnd2/tkdnd'),
    ],
    hiddenimports=[
        'pillow_heif',
        'google.genai',
        'tkinterdnd2',
        'pystray',
        'pystray._win32',
        # core/ helpers — usually picked up by static analysis but kept here
        # in case any of them grow into dynamic-import users later.
        'core.updater',
        'core.version',
        'core.single_instance',
        'core.tray',
        # ui/ widgets + dialogs
        'ui',
        'ui.theme',
        'ui.paste_helper',
        'ui.step_card',
        'ui.job_row',
        'ui.dialogs',
        'ui.dialogs.settings',
        'ui.dialogs.ai_health',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'numpy.f2py', 'IPython', 'jupyter', 'notebook',
        'pytest', 'sphinx', 'tornado',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HappyPhotoOrganizer',
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
    icon='assets/happy_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HappyPhotoOrganizer',
)
