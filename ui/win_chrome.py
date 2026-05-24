"""
win_chrome.py — Windows title-bar chrome helpers.

Two concerns CTk doesn't handle on its own:

1. **Dark title bar.** CTk colors the *body* of a window, but the OS title
   bar (the strip with X / minimize / maximize) is rendered by DWM and stays
   white-mode unless you set `DWMWA_USE_IMMERSIVE_DARK_MODE`. On Win 10 1809+
   the attribute id is 20 (was 19 on the very first preview build).

2. **Icons on every Toplevel.** `iconbitmap(path)` is unreliable on
   CTkToplevel because the window can be realized before the call arrives.
   `iconbitmap(default=path)` registers the icon at the Tk *class* level, so
   every Toplevel created later inherits it. We also force a per-window
   `iconbitmap` + a deferred retry as belt-and-suspenders.

Both helpers are no-ops on non-Windows and silently degrade if the DWM /
icon call fails.

Round-6 v1.037 (2026-05-24) — pattern lifted from PLC Visual Logic Editor
v0.1.17. Same root cause, same fix.
"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

# DWM attribute ids — see Microsoft docs / dwmapi.h
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20         # Win 10 1809+ + Win 11
_DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19     # Win 10 1809 preview


def apply_dark_title_bar(window) -> None:
    """Switch the OS title bar of `window` to dark mode (Win 10/11 only).

    Safe to call from any thread. Silent on every failure. Call AFTER
    the window has a real HWND — i.e. after `update_idletasks()` or
    inside an `after(50, …)`.
    """
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()
        value = ctypes.c_int(1)
        size = ctypes.sizeof(value)
        DwmSetWindowAttribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        # Try the modern attribute first; if it returns non-zero (HRESULT
        # E_INVALIDARG on old builds), fall back to the preview-build id.
        res = DwmSetWindowAttribute(
            hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), size,
        )
        if res != 0:
            DwmSetWindowAttribute(
                hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
                ctypes.byref(value), size,
            )
    except Exception:
        pass


def register_default_icon(icon_path: Path) -> bool:
    """Register `icon_path` (.ico) as the Tk-class-level default icon so
    every Toplevel created afterward picks it up automatically. Returns
    True if the call succeeded.

    Call once at app start, before any Toplevel is created. Pair with
    `apply_icon_to_window` for windows already realized.
    """
    if not icon_path or not Path(icon_path).exists():
        return False
    try:
        # Tk's default-icon hook needs an HWND-bearing widget context.
        # We borrow the hidden root via the module-level Tcl interpreter.
        import tkinter as _tk
        root = _tk._default_root
        if root is not None:
            root.iconbitmap(default=str(icon_path))
            return True
    except Exception:
        pass
    return False


def apply_icon_to_window(window, icon_path: Path) -> None:
    """Force `icon_path` onto `window`'s title bar AND taskbar entry.

    CTkToplevel is realized fast enough that the first `iconbitmap(path)`
    call sometimes races the WM. We do three attempts on three channels:
      1. `iconbitmap(default=path)` — class-level (same as register).
      2. `iconbitmap(path)` — per-window.
      3. `iconphoto(False, PhotoImage)` via Pillow as a fallback for
         platforms where iconbitmap is unreliable.
    Plus a deferred retry at +200 ms in case the early attempts raced.
    """
    if not icon_path or not Path(icon_path).exists():
        return
    path_str = str(icon_path)

    def _attempt():
        try:
            window.iconbitmap(default=path_str)
        except Exception:
            pass
        try:
            window.iconbitmap(path_str)
        except Exception:
            pass
        try:
            from PIL import Image, ImageTk
            img = ImageTk.PhotoImage(Image.open(path_str))
            window.iconphoto(False, img)
            # Keep a ref on the window so GC doesn't drop it
            window._icon_ref = img  # type: ignore[attr-defined]
        except Exception:
            pass

    _attempt()
    try:
        window.after(200, _attempt)
    except Exception:
        pass


def apply_chrome(window, icon_path: Path) -> None:
    """Convenience: dark title bar + icon, in one call. Call from
    `__init__` AFTER `super().__init__` + `self.title(...)` are done.
    """
    apply_icon_to_window(window, icon_path)
    # Title-bar attr needs a real HWND. Defer slightly so geometry +
    # iconbitmap have settled.
    try:
        window.after(50, lambda: apply_dark_title_bar(window))
    except Exception:
        apply_dark_title_bar(window)
