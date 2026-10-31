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

# The built-in Gemini key (Nick 2026-10-31, house rule KEY_EMBED): read from
# %USERPROFILE%\.embed-keys\Happy-Photo-Organizer.json - OUTSIDE the repo, which
# is public - and bundled as data/gemini.key, in plain text (KEY_EMBED §1).
# A build without it would ship an app whose key screen is hidden and that has
# no key, so it stops here instead. HPO_ALLOW_NO_KEY=1 builds one anyway (the
# Settings key field then shows, as before v1.067).
import os
sys.path.insert(0, SPECPATH)
from core import keymask

_key_src = keymask.embed_key_file()
_key = keymask.read_embed_key() or ''
_key_datas = []
if _key:
    # Plain text, by the house standard (KEY_EMBED §1, core/keymask.py). The
    # copy is staged in a temp folder OUTSIDE the repo and removed when the
    # build ends: a file left under build/ is one `git add -f` from public.
    import atexit, shutil, tempfile
    _key_dir = Path(tempfile.mkdtemp(prefix='hpo-key-'))
    atexit.register(shutil.rmtree, str(_key_dir), True)
    (_key_dir / keymask.BUNDLED_KEY_NAME).write_bytes(_key.encode('ascii'))
    _key_datas = [(str(_key_dir / keymask.BUNDLED_KEY_NAME), 'data')]
elif os.environ.get('HPO_ALLOW_NO_KEY') != '1':
    raise SystemExit(f'No built-in Gemini key: {_key_src} is missing, empty or not '
                     '{"GEMINI_KEY": "<key>"}. Put the key there, or set HPO_ALLOW_NO_KEY=1.')


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
    ] + _key_datas,
    hiddenimports=[
        'pillow_heif',
        'google.genai',
        'tkinterdnd2',
        'pystray',
        'pystray._win32',
        # qrcode is imported inside the pairing dialog's draw method. Static
        # analysis does follow function-level imports, but the failure mode if
        # it ever did not is "the QR silently will not draw in the frozen app
        # only", which is not a thing to discover on a vessel.
        'qrcode',
        'qrcode.image.pil',
        # core/ helpers — usually picked up by static analysis but kept here
        # in case any of them grow into dynamic-import users later.
        'core.keymask',
        'core.key_check',
        'core.updater',
        'core.update_worker',
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
        'ui.dialogs.pairing',
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
