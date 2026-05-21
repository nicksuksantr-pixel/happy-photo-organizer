"""
single_instance.py — Win32 named-mutex single-instance guard.

Confirms a real Tk window exists before declining the launch (stale-mutex
fallback). If the mutex exists but no live HPO window is found via
EnumWindows, treat it as stale and proceed as the first instance — a zombie
process holding the named mutex should never lock the user out forever.
"""
from __future__ import annotations

import sys

_MUTEX_HANDLE = None
APP_TITLE_PREFIX = "Happy Photo Organizer"
MUTEX_NAME = "Local\\HappyPhotoOrganizer-SingleInstance-a1b2c3d4"


def ensure_single_instance() -> bool:
    """Returns True if this is the first instance (proceed to launch the app).

    Returns False if another live HPO window exists and has been raised — the
    caller should exit silently.
    """
    global _MUTEX_HANDLE
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE

        _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        ERROR_ALREADY_EXISTS = 183
        SW_RESTORE = 9
        # CRITICAL: ctypes.get_last_error(), NOT kernel32.GetLastError() —
        # WinDLL(use_last_error=True) stashes the error in a ctypes slot.
        if ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
            return True

        # Mutex exists. Confirm a real Tk window before declining.
        Proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        found = [False]

        def _cb(hwnd, _lp):
            # Gate on window CLASS prefix "Tk" so an Explorer window whose
            # path matches our title doesn't false-match.
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if not cls.value.startswith("Tk"):
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            t = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, t, n + 1)
            if t.value.startswith(APP_TITLE_PREFIX):
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                found[0] = True
                return False
            return True

        cb = Proc(_cb)
        user32.EnumWindows(cb, 0)
        if found[0]:
            return False  # live instance raised → caller exits
        # Stale mutex (zombie process held it) — proceed as first instance
        return True
    except Exception:
        # Be permissive on any ctypes failure rather than locking the user out
        return True
