"""
paste_helper.py — Cross-keyboard-layout copy/cut/paste/select-all.

Default Tk binds Ctrl+V by keysym 'v' — on a Thai keyboard layout that
becomes 'ฬ' so paste silently breaks. We bind via keycode (scancode)
instead, which is identical across layouts.

CTkEntry / CTkComboBox wrap a tk.Entry as `_entry`. We bind there to make
sure key events on the real entry trigger our handlers.
"""
from __future__ import annotations

import tkinter as tk

# Scancodes — identical across layouts on Windows
_KEYCODE_V = 86
_KEYCODE_C = 67
_KEYCODE_X = 88
_KEYCODE_A = 65


def enable_paste(widget) -> None:
    """Wire Ctrl+V/C/X/A + right-click context menu on widget."""
    target = getattr(widget, "_entry", widget)

    def do_paste(_e=None):
        try:
            text = target.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            target.delete("sel.first", "sel.last")
        except Exception:
            pass
        try:
            target.insert("insert", text)
        except Exception:
            pass
        return "break"

    def do_copy(_e=None):
        try:
            sel = target.selection_get()
            target.clipboard_clear()
            target.clipboard_append(sel)
        except Exception:
            pass
        return "break"

    def do_cut(_e=None):
        try:
            sel = target.selection_get()
            target.clipboard_clear()
            target.clipboard_append(sel)
            target.delete("sel.first", "sel.last")
        except Exception:
            pass
        return "break"

    def do_select_all(_e=None):
        try:
            target.select_range(0, "end")
            target.icursor("end")
        except Exception:
            pass
        return "break"

    def on_ctrl(e):
        kc = e.keycode
        if kc == _KEYCODE_V:
            return do_paste()
        if kc == _KEYCODE_C:
            return do_copy()
        if kc == _KEYCODE_X:
            return do_cut()
        if kc == _KEYCODE_A:
            return do_select_all()

    def show_menu(e):
        m = tk.Menu(target, tearoff=0)
        m.add_command(label="Cut", command=do_cut)
        m.add_command(label="Copy", command=do_copy)
        m.add_command(label="Paste", command=do_paste)
        m.add_separator()
        m.add_command(label="Select All", command=do_select_all)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    target.bind("<Control-Key>", on_ctrl)
    target.bind("<Button-3>", show_menu)
