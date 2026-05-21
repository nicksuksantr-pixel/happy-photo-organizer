"""
Happy Photo Organizer — main GUI
v1.003 — thumbnail + click-to-open folder + size info + editable name
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import tkinter as tk
from PIL import Image
from tkinterdnd2 import DND_FILES, TkinterDnD

# pystray is optional — if it fails to import the app still runs (X = real exit)
try:
    import pystray
    from pystray import Menu as _TrayMenu, MenuItem as _TrayItem
except Exception:
    pystray = None
    _TrayMenu = None
    _TrayItem = None


def enable_paste(widget):
    """Make Ctrl+V / right-click → Paste work even on Thai keyboard layout.
    Default Tk binds Ctrl+V by keysym 'v' — on TH layout it becomes 'ฬ' → no paste.
    Solution: bind via keycode (scancode) — universal across layouts.

    CTkEntry/CTkComboBox wrap a tk.Entry as `_entry`. We bind there to make
    sure key events on the real entry trigger our handlers.
    """
    KEYCODE_V = 86
    KEYCODE_C = 67
    KEYCODE_X = 88
    KEYCODE_A = 65

    # CTkEntry/CTkComboBox → use internal tk.Entry; raw tk.Entry → use as-is
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
        if kc == KEYCODE_V:
            return do_paste()
        if kc == KEYCODE_C:
            return do_copy()
        if kc == KEYCODE_X:
            return do_cut()
        if kc == KEYCODE_A:
            return do_select_all()

    def show_menu(e):
        m = tk.Menu(target, tearoff=0)
        m.add_command(label="Cut",   command=do_cut)
        m.add_command(label="Copy",  command=do_copy)
        m.add_command(label="Paste", command=do_paste)
        m.add_separator()
        m.add_command(label="Select All", command=do_select_all)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    target.bind("<Control-Key>", on_ctrl)
    target.bind("<Button-3>", show_menu)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core import auth
from core.catalog import JobCatalog
from core.image_io import collect_images, format_summary, is_supported_image, SUPPORTED_EXTS
from core.processor import (
    phase1_resize_and_group,
    phase2_ai_analyze,
    phase4_rename_folders,
    Plan,
    JobAssignment,
)
from core.rate_limiter import (
    DEFAULT_TIER,
    TIER_PRESETS,
    TierConfig,
    get_rate_limiter,
    update_tier_from_config,
)
from core.usage_log import get_usage_log

# ─── Theme ─────────────────────────────────────────────────────
COLOR_PRIMARY = "#FB923C"    # ส้ม
COLOR_ACCENT = "#EC4899"     # ชมพู
COLOR_BG = "#0F172A"
COLOR_BG_CARD = "#1E293B"
COLOR_BG_INPUT = "#334155"   # สว่างกว่า card สำหรับปุ่ม secondary
COLOR_TEXT = "#F1F5F9"
COLOR_MUTED = "#94A3B8"
COLOR_OK = "#10B981"
COLOR_WARN = "#F59E0B"
COLOR_DANGER = "#EF4444"

# Step status colors
STEP_PENDING = "#475569"   # เทา
STEP_READY = COLOR_PRIMARY  # ส้ม
STEP_ACTIVE = COLOR_ACCENT  # ชมพู
STEP_DONE = COLOR_OK        # เขียว

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "Happy Photo Organizer"
APP_VERSION = "1.028"


# ─── Step Card ─────────────────────────────────────────────────


class StepCard(ctk.CTkFrame):
    """การ์ดของแต่ละ step — มี circle indicator + title + body slot"""

    STATUS_TEXT = {
        "pending": "Pending",
        "ready": "Ready",
        "active": "Running",
        "done": "Done",
    }
    STATUS_COLOR = {
        "pending": STEP_PENDING,
        "ready": STEP_READY,
        "active": STEP_ACTIVE,
        "done": STEP_DONE,
    }

    def __init__(self, master, step_num: int, title: str, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=10, **kwargs)
        self.step_num = step_num
        self.title = title
        self.status = "pending"

        # Header row (compact)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 2))

        # Status circle — ใช้ tk.Canvas วาดวงกลมแน่นอน (CTkFrame corner_radius ดูเบี้ยว)
        from tkinter import Canvas
        SIZE = 30
        self.indicator = Canvas(
            header, width=SIZE, height=SIZE,
            bg=COLOR_BG_CARD, highlightthickness=0, bd=0,
        )
        self.indicator.pack(side="left", padx=(0, 8))
        self._indicator_size = SIZE
        # draw oval (อยู่ใน bbox 1..SIZE-1 = วงกลมเต็มกรอบ)
        self._indicator_oval = self.indicator.create_oval(
            1, 1, SIZE - 1, SIZE - 1, fill=STEP_PENDING, outline="",
        )
        self._indicator_text = self.indicator.create_text(
            SIZE // 2, SIZE // 2, text=str(step_num),
            font=("Segoe UI", 13, "bold"), fill="white",
        )

        self.title_label = ctk.CTkLabel(
            header, text=title,
            font=("Segoe UI", 13, "bold"),
            text_color=COLOR_TEXT, anchor="w",
        )
        self.title_label.pack(side="left", fill="x", expand=True)

        self.status_label = ctk.CTkLabel(
            header, text=self.STATUS_TEXT["pending"],
            font=("Segoe UI", 10, "bold"),
            text_color=STEP_PENDING,
        )
        self.status_label.pack(side="right", padx=(8, 0))

        # Body slot
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=10, pady=(0, 8))

    def set_status(self, status: str) -> None:
        if status not in self.STATUS_COLOR:
            return
        self.status = status
        color = self.STATUS_COLOR[status]
        try:
            self.indicator.itemconfig(self._indicator_oval, fill=color)
        except Exception:
            pass
        self.status_label.configure(text=self.STATUS_TEXT[status], text_color=color)


# ─── Settings Dialog ───────────────────────────────────────────


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, on_save=None):
        super().__init__(master)
        self.title(f"Settings — {APP_TITLE}")
        self.geometry("560x460")
        self.transient(master)
        self.grab_set()
        self.on_save = on_save

        cfg = auth.load_config()

        ctk.CTkLabel(self, text="Gemini API Key", anchor="w",
                     font=("Segoe UI", 13, "bold")).pack(fill="x", padx=20, pady=(20, 4))
        # Clickable link to open AI Studio in browser
        link_row = ctk.CTkFrame(self, fg_color="transparent")
        link_row.pack(fill="x", padx=20)
        ctk.CTkLabel(
            link_row, text="Get one at  ", anchor="w",
            text_color=COLOR_MUTED, font=("Segoe UI", 11),
        ).pack(side="left")
        url_label = ctk.CTkLabel(
            link_row, text="aistudio.google.com/apikey  ↗",
            text_color="#7DD3FC",
            font=("Segoe UI", 11, "underline"),
            cursor="hand2",
        )
        url_label.pack(side="left")
        url_label.bind(
            "<Button-1>",
            lambda _e: webbrowser.open("https://aistudio.google.com/apikey"),
        )
        self.key_entry = ctk.CTkEntry(self, show="*", placeholder_text="AIzaSy...")
        self.key_entry.pack(fill="x", padx=20, pady=8)
        self.key_entry.insert(0, cfg.get("api_key", ""))
        enable_paste(self.key_entry)

        self.show_key = ctk.CTkCheckBox(self, text="Show key", command=self._toggle_show)
        self.show_key.pack(anchor="w", padx=20)

        ctk.CTkLabel(self, text="Model", anchor="w",
                     font=("Segoe UI", 13, "bold")).pack(fill="x", padx=20, pady=(20, 4))

        # Default values = fallback list (ครอบคลุม 3.x, 2.x)
        default_values = auth.list_vision_models(None) if False else [
            "gemini-3.1-pro-preview", "gemini-3.1-flash-lite",
            "gemini-3-pro-preview", "gemini-3-flash-preview",
            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
            "gemini-2.0-flash", "gemini-2.0-flash-lite",
        ]
        current = cfg.get("model", auth.DEFAULT_MODEL)
        if current and current not in default_values:
            default_values = [current] + default_values

        self.model_var = ctk.StringVar(value=current)
        self.model_menu = ctk.CTkOptionMenu(
            self, values=default_values, variable=self.model_var,
            fg_color=COLOR_PRIMARY, button_color=COLOR_ACCENT,
        )
        self.model_menu.pack(fill="x", padx=20, pady=8)

        ctk.CTkButton(
            self, text="Refresh models from API", height=32,
            fg_color=COLOR_BG_INPUT, hover_color="#475569",
            command=self._refresh_models,
        ).pack(fill="x", padx=20, pady=(0, 8))

        # UI Scale slider
        scale_label_row = ctk.CTkFrame(self, fg_color="transparent")
        scale_label_row.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(scale_label_row, text="UI Scale",
                     font=("Segoe UI", 13, "bold")).pack(side="left")
        self.scale_value_label = ctk.CTkLabel(
            scale_label_row, text="", font=("Segoe UI", 11), text_color=COLOR_MUTED,
        )
        self.scale_value_label.pack(side="right")

        self.scale_var = ctk.DoubleVar(value=float(cfg.get("ui_scale", 1.0)))
        self.scale_slider = ctk.CTkSlider(
            self, from_=0.7, to=1.3, number_of_steps=12,
            variable=self.scale_var, command=self._on_scale_change,
            progress_color=COLOR_PRIMARY, button_color=COLOR_ACCENT,
        )
        self.scale_slider.pack(fill="x", padx=20, pady=(0, 8))
        # init label only — don't trigger set_widget_scaling (causes flicker)
        self.scale_value_label.configure(text=f"{self.scale_var.get():.2f}x")

        # Auto-refresh ตอนเปิด — run in background thread (อย่า block UI)
        if cfg.get("api_key"):
            self.after(200, self._refresh_models_silent)

        # Updates section
        ctk.CTkLabel(self, text="Updates", anchor="w",
                     font=("Segoe UI", 13, "bold")).pack(fill="x", padx=20, pady=(16, 4))
        self.auto_update_var = ctk.BooleanVar(value=bool(cfg.get("auto_check_updates", True)))
        self.auto_update_cb = ctk.CTkCheckBox(
            self, text="Check for updates on startup",
            variable=self.auto_update_var,
        )
        self.auto_update_cb.pack(anchor="w", padx=20)

        self.status = ctk.CTkLabel(self, text="", text_color=COLOR_MUTED, anchor="w")
        self.status.pack(fill="x", padx=20, pady=10)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=20, side="bottom")
        ctk.CTkButton(row, text="Test", width=100, height=36,
                      fg_color=COLOR_BG_INPUT, hover_color="#475569",
                      command=self._test).pack(side="left")
        ctk.CTkButton(row, text="Cancel", width=100, height=36,
                      fg_color=COLOR_BG_INPUT, hover_color="#475569",
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(row, text="Save", width=120, height=36,
                      fg_color=COLOR_PRIMARY, hover_color=COLOR_ACCENT,
                      command=self._save).pack(side="right")

    def _toggle_show(self):
        self.key_entry.configure(show="" if self.show_key.get() else "*")

    def _test(self):
        key = self.key_entry.get().strip()
        if not key:
            self.status.configure(text="Enter a key first", text_color=COLOR_WARN); return
        self.status.configure(text="Testing...", text_color=COLOR_MUTED)
        threading.Thread(target=self._test_worker, args=(key,), daemon=True).start()

    def _test_worker(self, key: str):
        try:
            client, err = auth.create_client(key)
            if err:
                self.after(0, lambda: self.status.configure(text=err, text_color=COLOR_DANGER))
                return
            ok, msg = auth.test_connection(client)
            self.after(0, lambda: self.status.configure(
                text=msg, text_color=COLOR_OK if ok else COLOR_DANGER,
            ))
        except Exception as e:
            msg = str(e)[:200]
            self.after(0, lambda: self.status.configure(text=msg, text_color=COLOR_DANGER))

    def _refresh_models(self):
        key = self.key_entry.get().strip()
        if not key:
            self.status.configure(text="Enter a key first", text_color=COLOR_WARN); return
        self.status.configure(text="Loading models...", text_color=COLOR_MUTED)
        threading.Thread(
            target=self._refresh_models_worker,
            args=(key, False),
            daemon=True,
        ).start()

    def _refresh_models_silent(self):
        """โหลด models in background thread — ไม่ block UI"""
        key = self.key_entry.get().strip()
        if not key:
            return
        threading.Thread(
            target=self._refresh_models_worker,
            args=(key, True),
            daemon=True,
        ).start()

    def _refresh_models_worker(self, key: str, silent: bool):
        """Background worker — แล้ว apply ผ่าน self.after() → main thread"""
        try:
            client, err = auth.create_client(key)
            if err:
                if not silent:
                    self.after(0, lambda: self.status.configure(text=err, text_color=COLOR_DANGER))
                return
            models = auth.list_vision_models(client)
            if not models:
                if not silent:
                    self.after(0, lambda: self.status.configure(
                        text="Failed to load models", text_color=COLOR_DANGER,
                    ))
                return
            # apply on main thread
            self.after(0, lambda m=models: self._apply_refreshed_models(m, silent))
        except Exception as e:
            if not silent:
                msg = str(e)[:200]
                self.after(0, lambda: self.status.configure(text=msg, text_color=COLOR_DANGER))

    def _apply_refreshed_models(self, models: list, silent: bool):
        try:
            current = self.model_var.get()
            self.model_menu.configure(values=models)
            if current not in models:
                self.model_var.set(models[0])
            msg = (f"Found {len(models)} models (auto-loaded)" if silent
                   else f"Refreshed {len(models)} models")
            self.status.configure(text=msg, text_color=COLOR_OK)
        except Exception:
            pass

    def _on_scale_change(self, value):
        scale = float(value)
        self.scale_value_label.configure(text=f"{scale:.2f}x")
        try:
            ctk.set_widget_scaling(scale)
        except Exception:
            pass

    def _save(self):
        key = self.key_entry.get().strip()
        if not key:
            self.status.configure(text="Enter a key first", text_color=COLOR_WARN); return
        ok, msg = auth.save_config(key, self.model_var.get(), self.scale_var.get())
        if ok:
            # persist additional preferences via merge
            auth.update_config({"auto_check_updates": bool(self.auto_update_var.get())})
            if self.on_save:
                self.on_save()
            self.destroy()
        else:
            self.status.configure(text=msg, text_color=COLOR_DANGER)


# ─── AI Health Dialog ──────────────────────────────────────────


class AIHealthDialog(ctk.CTkToplevel):
    """Standalone window — Tier + Usage + History + Pre-flight + Recent calls"""

    def __init__(self, master, on_tier_change=None):
        super().__init__(master)
        self.title("AI Health & Quota")
        self.geometry("760x780")
        self.transient(master)
        self.on_tier_change = on_tier_change

        self.usage_log = get_usage_log()
        self.rate_limiter = get_rate_limiter()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Scrollable container
        container = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # ─── 1. Tier info ─────────────────────────────────
        tier_card = ctk.CTkFrame(container, fg_color=COLOR_BG_CARD, corner_radius=10)
        tier_card.pack(fill="x", pady=(0, 8))
        self.tier_title = ctk.CTkLabel(
            tier_card, text="", anchor="w",
            font=("Segoe UI", 14, "bold"), text_color=COLOR_PRIMARY,
        )
        self.tier_title.pack(fill="x", padx=12, pady=(10, 2))
        self.tier_detail = ctk.CTkLabel(
            tier_card, text="", anchor="w",
            font=("Segoe UI", 11), text_color=COLOR_MUTED, justify="left",
        )
        self.tier_detail.pack(fill="x", padx=12, pady=(0, 10))

        # ─── 2. Today's usage bars ────────────────────────
        usage_card = ctk.CTkFrame(container, fg_color=COLOR_BG_CARD, corner_radius=10)
        usage_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            usage_card, text="Today's Usage", anchor="w",
            font=("Segoe UI", 13, "bold"), text_color=COLOR_TEXT,
        ).pack(fill="x", padx=12, pady=(10, 4))

        self.rpd_label = ctk.CTkLabel(
            usage_card, text="", anchor="w",
            font=("Segoe UI", 11), text_color=COLOR_TEXT,
        )
        self.rpd_label.pack(fill="x", padx=12)
        self.rpd_bar = ctk.CTkProgressBar(usage_card, height=10, progress_color=COLOR_PRIMARY)
        self.rpd_bar.pack(fill="x", padx=12, pady=(2, 8))

        self.rpm_label = ctk.CTkLabel(
            usage_card, text="", anchor="w",
            font=("Segoe UI", 11), text_color=COLOR_TEXT,
        )
        self.rpm_label.pack(fill="x", padx=12)
        self.rpm_bar = ctk.CTkProgressBar(usage_card, height=10, progress_color=COLOR_ACCENT)
        self.rpm_bar.pack(fill="x", padx=12, pady=(2, 10))

        # ─── 3. Pre-flight calculator ─────────────────────
        preflight_card = ctk.CTkFrame(container, fg_color=COLOR_BG_CARD, corner_radius=10)
        preflight_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            preflight_card, text="Pre-flight Calculator", anchor="w",
            font=("Segoe UI", 13, "bold"), text_color=COLOR_TEXT,
        ).pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            preflight_card,
            text="Estimate how long N AI calls will take, and whether you'll fit within today's quota.",
            anchor="w", font=("Segoe UI", 10), text_color=COLOR_MUTED,
            wraplength=680, justify="left",
        ).pack(fill="x", padx=12)

        pf_row = ctk.CTkFrame(preflight_card, fg_color="transparent")
        pf_row.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(pf_row, text="If I run",
                     font=("Segoe UI", 11), text_color=COLOR_TEXT).pack(side="left")
        self.pf_entry = ctk.CTkEntry(pf_row, width=80, justify="center",
                                     placeholder_text="0")
        self.pf_entry.pack(side="left", padx=8)
        self.pf_entry.bind("<KeyRelease>", lambda _e: self._update_preflight())
        enable_paste(self.pf_entry)
        ctk.CTkLabel(pf_row, text="AI calls...",
                     font=("Segoe UI", 11), text_color=COLOR_TEXT).pack(side="left")

        self.pf_result = ctk.CTkLabel(
            preflight_card, text="", anchor="w",
            font=("Segoe UI", 11), text_color=COLOR_TEXT,
            wraplength=680, justify="left",
        )
        self.pf_result.pack(fill="x", padx=12, pady=(0, 10))

        # ─── 4. 7-day history ─────────────────────────────
        history_card = ctk.CTkFrame(container, fg_color=COLOR_BG_CARD, corner_radius=10)
        history_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            history_card, text="Last 7 Days", anchor="w",
            font=("Segoe UI", 13, "bold"), text_color=COLOR_TEXT,
        ).pack(fill="x", padx=12, pady=(10, 4))
        self.history_box = ctk.CTkTextbox(
            history_card, height=120,
            fg_color="#0A1220", text_color="#CBD5E1",
            font=("Consolas", 10), corner_radius=6,
        )
        self.history_box.pack(fill="x", padx=12, pady=(0, 10))
        self.history_box.configure(state="disabled")

        # ─── 5. Recent calls ──────────────────────────────
        recent_card = ctk.CTkFrame(container, fg_color=COLOR_BG_CARD, corner_radius=10)
        recent_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            recent_card, text="Recent Calls (last 10)", anchor="w",
            font=("Segoe UI", 13, "bold"), text_color=COLOR_TEXT,
        ).pack(fill="x", padx=12, pady=(10, 4))
        self.recent_box = ctk.CTkTextbox(
            recent_card, height=140,
            fg_color="#0A1220", text_color="#CBD5E1",
            font=("Consolas", 10), corner_radius=6,
        )
        self.recent_box.pack(fill="x", padx=12, pady=(0, 10))
        self.recent_box.configure(state="disabled")

        # ─── 6. Tier selector ─────────────────────────────
        tier_select = ctk.CTkFrame(container, fg_color=COLOR_BG_CARD, corner_radius=10)
        tier_select.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            tier_select, text="Change Tier", anchor="w",
            font=("Segoe UI", 13, "bold"), text_color=COLOR_TEXT,
        ).pack(fill="x", padx=12, pady=(10, 4))

        cfg = auth.load_config()
        current_tier_name = cfg.get("tier", DEFAULT_TIER)
        self.tier_var = ctk.StringVar(value=current_tier_name)

        for key, preset in TIER_PRESETS.items():
            rb = ctk.CTkRadioButton(
                tier_select,
                text=f"  {preset['label']}   (RPM {preset['rpm']}, RPD {preset['rpd']})",
                variable=self.tier_var, value=key,
                command=self._on_tier_radio,
                font=("Segoe UI", 11),
            )
            rb.pack(anchor="w", padx=16, pady=2)

        # Custom tier row
        custom_row = ctk.CTkFrame(tier_select, fg_color="transparent")
        custom_row.pack(fill="x", padx=16, pady=(4, 6))
        ctk.CTkRadioButton(
            custom_row, text="  Custom", variable=self.tier_var, value="custom",
            command=self._on_tier_radio, font=("Segoe UI", 11),
        ).pack(side="left")
        ctk.CTkLabel(custom_row, text="RPM:", font=("Segoe UI", 10),
                     text_color=COLOR_MUTED).pack(side="left", padx=(12, 4))
        self.custom_rpm = ctk.CTkEntry(custom_row, width=60, justify="center")
        self.custom_rpm.pack(side="left")
        self.custom_rpm.insert(0, str(cfg.get("custom_rpm", 15)))
        enable_paste(self.custom_rpm)
        ctk.CTkLabel(custom_row, text="RPD:", font=("Segoe UI", 10),
                     text_color=COLOR_MUTED).pack(side="left", padx=(12, 4))
        self.custom_rpd = ctk.CTkEntry(custom_row, width=70, justify="center")
        self.custom_rpd.pack(side="left")
        self.custom_rpd.insert(0, str(cfg.get("custom_rpd", 500)))
        enable_paste(self.custom_rpd)

        ctk.CTkButton(
            tier_select, text="Apply tier", height=30, width=120,
            fg_color=COLOR_PRIMARY, hover_color=COLOR_ACCENT,
            command=self._apply_tier,
        ).pack(padx=12, pady=(0, 10))

        # ─── 7. Bottom action row ─────────────────────────
        action_row = ctk.CTkFrame(container, fg_color="transparent")
        action_row.pack(fill="x", pady=8)
        ctk.CTkButton(
            action_row, text="Reset today's counter", height=30, width=180,
            fg_color=COLOR_BG_INPUT, hover_color="#475569",
            command=self._reset_today,
        ).pack(side="left")
        ctk.CTkButton(
            action_row, text="Close", height=30, width=80,
            fg_color=COLOR_BG_INPUT, hover_color="#475569",
            command=self.destroy,
        ).pack(side="right")

    # ─── refresh ──────────────────────────────────────────

    def refresh(self):
        try:
            tier = self.rate_limiter.tier
            snap = self.usage_log.snapshot()
            self._render_tier(tier, snap)
            self._render_usage(tier, snap)
            self._update_preflight()
            self._render_history(snap)
            self._render_recent(snap)
        except Exception:
            pass

    def _render_tier(self, tier, snap):
        self.tier_title.configure(text=tier.label)
        reset_sec = snap.get("seconds_until_reset", 0)
        hh = reset_sec // 3600
        mm = (reset_sec % 3600) // 60
        cap_rpd = "unlimited" if (not tier.throttle or tier.rpd <= 0) else f"{tier.rpd}/day"
        cap_rpm = "no cap" if (not tier.throttle or tier.rpm <= 0) else f"{tier.rpm}/min"
        self.tier_detail.configure(
            text=(
                f"Model alias: {tier.name}\n"
                f"Limits: RPM {cap_rpm}  •  RPD {cap_rpd}  •  TPM {tier.tpm:,}\n"
                f"Throttle: {'4.0s/call' if tier.min_interval_sec else 'disabled (paid)'}\n"
                f"Resets in: {hh}h {mm}m  (Pacific Time 00:00)"
            )
        )

    def _render_usage(self, tier, snap):
        count = snap.get("today_count", 0)
        tokens = snap.get("today_tokens", 0)
        rpm_now = snap.get("current_rpm", 0)

        if not tier.throttle or tier.rpd <= 0:
            self.rpd_label.configure(text=f"Requests today: {count}  •  Tokens: {tokens:,}  (no daily cap)")
            self.rpd_bar.set(0)
        else:
            pct = min(count / tier.rpd, 1.0) if tier.rpd else 0
            self.rpd_label.configure(text=f"Requests/Day: {count}/{tier.rpd}  ({int(pct*100)}%)  •  Tokens: {tokens:,}")
            self.rpd_bar.set(pct)

        if not tier.throttle or tier.rpm <= 0:
            self.rpm_label.configure(text=f"RPM (last 60s): {rpm_now}  (no cap)")
            self.rpm_bar.set(0)
        else:
            pct = min(rpm_now / tier.rpm, 1.0) if tier.rpm else 0
            self.rpm_label.configure(text=f"RPM (last 60s): {rpm_now}/{tier.rpm}")
            self.rpm_bar.set(pct)

    def _update_preflight(self):
        try:
            n = int(self.pf_entry.get().strip() or "0")
        except Exception:
            n = 0
        if n <= 0:
            self.pf_result.configure(
                text="Type a number to simulate — e.g. how many photos / folders you'll run AI on.",
                text_color=COLOR_MUTED,
            )
            return
        est = self.rate_limiter.estimate_eta(n)
        eta = est["eta_sec"]
        eta_str = f"{eta}s" if eta < 60 else f"{eta // 60}m {eta % 60}s"
        lines = [f"ETA: ~{eta_str} (throttle {self.rate_limiter.tier.min_interval_sec:.1f}s/call)"]
        if est["rpd_cap"]:
            lines.append(f"Quota after: {est['rpd_used_after']}/{est['rpd_cap']}")
        if est["remaining"] is not None:
            lines.append(f"Remaining today: {est['remaining']}")
        color = COLOR_OK
        if est["warning"]:
            lines.append(f"⚠ {est['warning']}")
            color = COLOR_WARN if est["fits_quota"] else COLOR_DANGER
        self.pf_result.configure(text="  •  ".join(lines), text_color=color)

    def _render_history(self, snap):
        history = snap.get("history_7d", {}) or {}
        # always show last 7 days including today
        from datetime import timedelta
        today = datetime.strptime(snap.get("today_pt"), "%Y-%m-%d").date() if snap.get("today_pt") else datetime.now().date()
        today_count = snap.get("today_count", 0)

        rows = []
        max_val = max([today_count] + list(history.values()) + [1])
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            k = d.strftime("%Y-%m-%d")
            v = today_count if i == 0 else history.get(k, 0)
            bar_len = int(min(v / max_val, 1.0) * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            marker = " ← today" if i == 0 else ""
            rows.append(f"{d.strftime('%a %d-%m')}  {bar}  {v}{marker}")

        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        self.history_box.insert("end", "\n".join(rows))
        self.history_box.configure(state="disabled")

    def _render_recent(self, snap):
        recent = snap.get("recent_calls", []) or []
        if not recent:
            text = "(no calls yet today)"
        else:
            lines = []
            for c in reversed(recent):
                ok_mark = "✓" if c.get("ok") else "✗"
                lines.append(
                    f"{c.get('ts','')}  {ok_mark} {c.get('type','call'):<14} "
                    f"{c.get('duration',0):.1f}s  {c.get('tokens',0):>5} tokens"
                )
            text = "\n".join(lines)
        self.recent_box.configure(state="normal")
        self.recent_box.delete("1.0", "end")
        self.recent_box.insert("end", text)
        self.recent_box.configure(state="disabled")

    # ─── tier change ─────────────────────────────────────

    def _on_tier_radio(self):
        # update preflight estimate when tier changes (preview only — apply on button)
        pass

    def _apply_tier(self):
        tier_name = self.tier_var.get()
        cfg = auth.load_config()
        cfg["tier"] = tier_name
        if tier_name == "custom":
            try:
                rpm = int(self.custom_rpm.get().strip())
                rpd = int(self.custom_rpd.get().strip())
                if rpm < 0 or rpd < 0:
                    raise ValueError("non-negative only")
            except Exception:
                messagebox.showwarning("Invalid input", "RPM and RPD must be non-negative integers")
                return
            cfg["custom_rpm"] = rpm
            cfg["custom_rpd"] = rpd
        # write full merged config
        try:
            import json as _json
            auth.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            auth.CONFIG_FILE.write_text(_json.dumps(cfg, indent=2), encoding="utf-8")
        except Exception as e:
            messagebox.showwarning("Save failed", f"Could not save tier:\n{e}")
            return
        update_tier_from_config(cfg)
        self.refresh()
        if self.on_tier_change:
            self.on_tier_change()

    def _reset_today(self):
        ok = messagebox.askyesno(
            "Reset today's counter",
            "Set today's request count to 0?\n(use only if you know what you're doing)",
        )
        if not ok:
            return
        self.usage_log.reset_today()
        self.refresh()
        if self.on_tier_change:
            self.on_tier_change()


# ─── Job Row ───────────────────────────────────────────────────


class JobRow(ctk.CTkFrame):
    """แถวของ 1 งาน — thumbnail + ชื่อ + ขนาด + AI reasoning"""

    THUMB_SIZE = 64

    def __init__(self, master, assignment: JobAssignment, catalog: JobCatalog, on_change=None):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8)
        self.assignment = assignment
        self.catalog = catalog
        self.on_change = on_change
        self._thumb_ref = None  # ป้องกัน GC

        self.grid_columnconfigure(2, weight=1)

        # ─── Col 0: Date + count ─────
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=8, sticky="nw")

        date_str = assignment.folder_date.strftime("%d-%m-%y")
        # ถ้าวันที่ถูก shift → สีเตือน + แสดงวันเดิม
        date_color = COLOR_WARN if assignment.date_shifted else COLOR_TEXT
        if assignment.date_was_capped:
            date_color = COLOR_DANGER
        ctk.CTkLabel(left, text=date_str,
                     font=("Segoe UI", 13, "bold"), text_color=date_color,
                     ).pack(anchor="w")
        if assignment.date_shifted and assignment.original_date:
            orig = assignment.original_date.strftime("%d-%m-%y")
            shift_text = f"(was {orig})"
            if assignment.date_was_capped:
                shift_text = f"(overflow — was {orig})"
            ctk.CTkLabel(left, text=shift_text,
                         font=("Segoe UI", 9, "italic"),
                         text_color=date_color,
                         ).pack(anchor="w")
        count = len(assignment.resized_paths) or len(assignment.images)
        ctk.CTkLabel(left, text=f"{count} photos",
                     font=("Segoe UI", 11), text_color=COLOR_MUTED,
                     ).pack(anchor="w")

        # ─── Col 1: Thumbnail (clickable → open folder) ─────
        thumb = self._make_thumbnail()
        thumb_text = "" if thumb else "(no\nimage)"
        self.thumb_btn = ctk.CTkButton(
            self,
            image=thumb,
            text=thumb_text,
            width=self.THUMB_SIZE + 8, height=self.THUMB_SIZE + 8,
            fg_color=COLOR_BG, hover_color=COLOR_BG_INPUT,
            text_color=COLOR_MUTED,
            font=("Segoe UI", 9),
            command=self._open_folder,
        )
        self.thumb_btn.grid(row=0, column=1, rowspan=2, padx=4, pady=6)
        if thumb:
            self._thumb_ref = thumb  # keep ref

        # ─── Col 2: Combobox + size info ─────
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=2, rowspan=2, padx=6, pady=6, sticky="nsew")
        center.grid_columnconfigure(0, weight=1)

        # Row of combobox + translate button
        combo_row = ctk.CTkFrame(center, fg_color="transparent")
        combo_row.grid(row=0, column=0, sticky="ew", pady=(2, 4))
        combo_row.grid_columnconfigure(0, weight=1)

        # Combobox — values ไม่มี placeholder text
        self._all_names = [""] + catalog.names()
        self.job_var = ctk.StringVar(value=assignment.job_name)
        empty_border = COLOR_WARN if not assignment.job_name.strip() else COLOR_BG_INPUT
        self.job_combo = ctk.CTkComboBox(
            combo_row,
            values=self._all_names,
            variable=self.job_var,
            command=self._on_job_change,
            border_color=empty_border, border_width=2,
            fg_color=COLOR_BG_INPUT,
        )
        self.job_combo.grid(row=0, column=0, sticky="ew")
        # bind events
        self.job_combo.bind("<Return>", self._on_typing_done)
        self.job_combo.bind("<FocusOut>", self._on_typing_done)
        self.job_combo.bind("<KeyRelease>", self._on_key_release)
        # enable Ctrl+V / right-click paste (works on Thai keyboard too)
        enable_paste(self.job_combo)

        # Translate button TH→EN
        self.translate_btn = ctk.CTkButton(
            combo_row, text="EN", width=44, height=26,
            font=("Segoe UI", 10, "bold"),
            fg_color=COLOR_ACCENT, hover_color=COLOR_PRIMARY,
            text_color="#FFFFFF",
            command=self._translate_to_english,
        )
        self.translate_btn.grid(row=0, column=1, padx=(4, 0))

        # Hint ถ้า empty
        if not assignment.job_name.strip():
            ctk.CTkLabel(
                center,
                text="Type a job name or pick from dropdown ▼",
                font=("Segoe UI", 10, "italic"),
                text_color=COLOR_WARN, anchor="w",
            ).grid(row=1, column=0, sticky="w", pady=(0, 2))

        # Size info
        size_info = self._calc_size_info()
        size_line = ctk.CTkLabel(
            center, text=size_info,
            font=("Segoe UI", 10),
            text_color=COLOR_MUTED, anchor="w", justify="left",
        )
        size_line.grid(row=2, column=0, sticky="w", pady=(2, 0))

        # AI reasoning
        if assignment.reasoning:
            ctk.CTkLabel(
                center,
                text=f"AI: {assignment.reasoning[:240]}",
                font=("Segoe UI", 10),
                text_color="#7DD3FC",  # cyan-ish
                wraplength=700, justify="left", anchor="w",
            ).grid(row=3, column=0, sticky="w", pady=(2, 0))

        # ─── Col 3: Confidence ─────
        conf = assignment.confidence
        if conf >= 0.8:
            conf_color, conf_icon = COLOR_OK, "OK"
        elif conf >= 0.5:
            conf_color, conf_icon = COLOR_WARN, "?"
        else:
            conf_color, conf_icon = COLOR_DANGER, "!"

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=3, rowspan=2, padx=(6, 10), pady=8, sticky="ne")

        conf_text = f"{conf_icon}\n{int(conf * 100)}%"
        ctk.CTkLabel(right, text=conf_text, width=70,
                     font=("Segoe UI", 13, "bold"),
                     text_color=conf_color, justify="center",
                     ).pack(anchor="ne")
        if assignment.is_new_suggestion and assignment.job_name.strip():
            ctk.CTkLabel(right, text="new",
                         font=("Segoe UI", 9, "italic"),
                         text_color=COLOR_ACCENT,
                         ).pack(anchor="ne")

    # ─── Helpers ──────────────────────────

    def _make_thumbnail(self):
        """โหลด thumbnail ของรูปแรกใน resized_paths (หรือ images)"""
        pool = self.assignment.resized_paths or self.assignment.images
        if not pool:
            return None
        try:
            with Image.open(pool[0]) as img:
                img.thumbnail((self.THUMB_SIZE * 2, self.THUMB_SIZE * 2))
                return ctk.CTkImage(
                    light_image=img.copy(), dark_image=img.copy(),
                    size=(self.THUMB_SIZE, self.THUMB_SIZE),
                )
        except Exception:
            return None

    def _calc_size_info(self) -> str:
        """คำนวณ size info — รวม / max / avg"""
        paths = self.assignment.resized_paths or self.assignment.images
        sizes = []
        for p in paths:
            try:
                sizes.append(p.stat().st_size)
            except Exception:
                pass
        if not sizes:
            return "ไม่มีข้อมูลขนาด"
        total_kb = sum(sizes) / 1024
        max_kb = max(sizes) / 1024
        avg_kb = total_kb / len(sizes)
        scope = "resized" if self.assignment.resized_paths else "original"
        return (
            f"📊 {len(sizes)} photos ({scope})  •  "
            f"total {total_kb:,.0f} KB  •  "
            f"max {max_kb:,.0f} KB  •  "
            f"avg {avg_kb:,.0f} KB"
        )

    def _open_folder(self):
        """คลิก thumbnail → เปิดโฟลเดอร์ใน File Explorer"""
        folder = self.assignment.temp_folder
        if folder and folder.exists():
            try:
                os.startfile(folder)
            except Exception:
                pass
        else:
            # fallback: เปิดโฟลเดอร์ของรูปต้นฉบับ
            pool = self.assignment.resized_paths or self.assignment.images
            if pool:
                try:
                    os.startfile(pool[0].parent)
                except Exception:
                    pass

    def _on_job_change(self, value):
        """combobox dropdown selection"""
        self.assignment.job_name = value
        self.assignment.is_new_suggestion = (
            self.catalog.find(value) is None and bool(value.strip())
        )
        self._update_border()
        if self.on_change:
            self.on_change()

    def _on_typing_done(self, _event):
        """user พิมพ์เอง + กด Enter/FocusOut → save"""
        value = self.job_var.get().strip()
        self.assignment.job_name = value
        self.assignment.is_new_suggestion = (
            self.catalog.find(value) is None and bool(value)
        )
        self._update_border()
        if self.on_change:
            self.on_change()

    def _update_border(self):
        color = COLOR_WARN if not self.assignment.job_name.strip() else COLOR_OK
        try:
            self.job_combo.configure(border_color=color)
        except Exception:
            pass

    def refresh_catalog_values(self):
        """อัพเดท dropdown list หลังมีการเพิ่มชื่อใหม่เข้า catalog"""
        current = self.job_var.get()
        self._all_names = [""] + self.catalog.names()
        try:
            self.job_combo.configure(values=self._all_names)
            self.job_var.set(current)  # คงค่าที่เลือกอยู่
        except Exception:
            pass

    def _on_key_release(self, event):
        """Autocomplete — filter dropdown ตามที่พิมพ์"""
        # ข้าม keys ที่เป็น navigation
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Tab", "Escape"):
            return
        typed = self.job_var.get().strip().lower()
        if not typed:
            filtered = self._all_names
        else:
            # match ชื่อที่มี substring ของ typed (case-insensitive)
            filtered = [n for n in self._all_names if n and typed in n.lower()]
            # ถ้าไม่ match อะไรเลย — แสดง list ทั้งหมด (กรณีพิมพ์ชื่อใหม่)
            if not filtered:
                filtered = self._all_names
        try:
            self.job_combo.configure(values=filtered)
        except Exception:
            pass

    def _translate_to_english(self):
        """แปลข้อความปัจจุบันใน combobox จากไทย → อังกฤษด้วย Gemini"""
        from core.auth import create_client, get_model
        from google.genai import types

        text = self.job_var.get().strip()
        if not text:
            return

        # disable button + show "..."
        original_text = self.translate_btn.cget("text")
        self.translate_btn.configure(text="...", state="disabled")
        self.update()

        def restore():
            try:
                self.translate_btn.configure(text=original_text, state="normal")
            except Exception:
                pass

        try:
            client, err = create_client()
            if err:
                restore()
                return

            prompt = (
                "แปลข้อความนี้เป็นภาษาอังกฤษสำหรับใช้เป็นชื่องานซ่อมบำรุงเรือ "
                "(ใช้คำศัพท์ทางเทคนิคที่เหมาะสม เช่น Cleaned/Repaired/Replaced/Inspected). "
                "ตอบกลับเฉพาะคำแปลภาษาอังกฤษ ไม่ต้องมีคำอธิบาย ไม่ต้องมี quotes:\n\n"
                f"{text}"
            )
            response = client.models.generate_content(
                model=get_model(),
                contents=[prompt],
                config=types.GenerateContentConfig(temperature=0.1),
            )
            translated = (response.text or "").strip().strip('"').strip("'")
            if translated:
                self.job_var.set(translated)
                self.assignment.job_name = translated
                self.assignment.is_new_suggestion = (
                    self.catalog.find(translated) is None
                )
                self._update_border()
                if self.on_change:
                    self.on_change()
        except Exception:
            pass
        finally:
            restore()


# ─── System Tray ───────────────────────────────────────────────


class HappyTray:
    """Wraps pystray.Icon. Runs detached so the Tk mainloop stays in the main thread."""

    def __init__(self, app):
        self.app = app
        self.icon = None
        self._image = self._load_icon_image()

    def _load_icon_image(self):
        icon_path = ROOT / "assets" / "happy_icon.ico"
        try:
            return Image.open(icon_path)
        except Exception:
            return Image.new("RGBA", (32, 32), (251, 146, 60, 255))

    def start(self):
        if pystray is None:
            return False
        self.icon = pystray.Icon(
            "HappyPhotoOrganizer",
            icon=self._image,
            title="Happy Photo Organizer",
            menu=_TrayMenu(
                _TrayItem("Show", self._on_show, default=True),
                _TrayItem("Check for updates now", self._on_check_update),
                _TrayMenu.SEPARATOR,
                _TrayItem("Quit", self._on_quit),
            ),
        )
        self.icon.run_detached()
        return True

    def stop(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None

    def _on_show(self, icon, item):
        try:
            self.app.after(0, self.app._show_window_from_tray)
        except Exception:
            pass

    def _on_check_update(self, icon, item):
        try:
            self.app.after(0, self.app._update_check_tick)
        except Exception:
            pass

    def _on_quit(self, icon, item):
        try:
            self.app.after(0, self.app._real_quit)
        except Exception:
            pass


# ─── Main Window ───────────────────────────────────────────────


class MainWindow(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        # Apply UI scale from config (ก่อนสร้าง widgets)
        scale = auth.load_config().get("ui_scale", 1.0)
        try:
            ctk.set_widget_scaling(float(scale))
        except Exception:
            pass

        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.minsize(640, 420)
        self.configure(fg_color=COLOR_BG)

        # Restore window geometry from last session (size + position + maximized)
        self._restore_window_state()

        # Window icon (title bar + taskbar)
        icon_path = ROOT / "assets" / "happy_icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        # ─── 2 ตัวแยกชัดเจน ───
        # A. App identity icon (camera) — สำหรับ header ของแอป
        # B. HAPPY mascot (robot) — สำหรับ guide / helper ที่ drop zone + buttons
        from PIL import Image as _PIL

        self._app_icon_header = None  # camera 56x56 (header logo)
        camera_png = ROOT / "assets" / "happy_logo_small.png"
        if camera_png.exists():
            try:
                camera_pil = _PIL.open(camera_png).convert("RGBA")
                camera_pil = camera_pil.resize((56, 56), _PIL.LANCZOS)
                self._app_icon_header = ctk.CTkImage(
                    light_image=camera_pil, dark_image=camera_pil,
                    size=(56, 56),
                )
            except Exception:
                pass

        self._mascot_pil = None
        self._mascot_drop_zone = None  # robot 52x52 (50% opacity)
        self._mascot_btn = None         # robot 22x22 (buttons)
        mascot_png = ROOT / "assets" / "mascot.png"
        if mascot_png.exists():
            try:
                self._mascot_pil = _PIL.open(mascot_png).convert("RGBA")
                # Pre-resize with LANCZOS (CTkImage runtime scaler clips arms)
                faded_full = self._mascot_pil.copy()
                r, g, b, a = faded_full.split()
                a = a.point(lambda x: int(x * 0.5))
                faded_full = _PIL.merge("RGBA", (r, g, b, a))

                drop_pil = faded_full.resize((52, 52), _PIL.LANCZOS)
                btn_pil = self._mascot_pil.resize((22, 22), _PIL.LANCZOS)

                self._mascot_drop_zone = ctk.CTkImage(
                    light_image=drop_pil, dark_image=drop_pil, size=(52, 52),
                )
                self._mascot_btn = ctk.CTkImage(
                    light_image=btn_pil, dark_image=btn_pil, size=(22, 22),
                )
            except Exception:
                pass

        self.source_paths: list[Path] = []
        self.dest_root: Path | None = None
        self.catalog = JobCatalog()
        self.plan: Plan | None = None
        self._plan_lock = threading.Lock()  # protect self.plan (worker vs UI)
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None

        # Apply tier from config → rate limiter
        cfg = auth.load_config()
        update_tier_from_config(cfg)
        self.usage_log = get_usage_log()
        self.rate_limiter = get_rate_limiter()
        self._ai_health_dialog: ctk.CTkToplevel | None = None

        self.target_kb_min = ctk.IntVar(value=10)
        self.target_kb_max = ctk.IntVar(value=25)

        # Update checker / installer state (auto-update — no UI button)
        self._pending_installer: Path | None = None
        self._pending_installer_version: str | None = None
        self._pending_update_info = None  # UpdateInfo found mid-batch (download deferred)
        self._update_after_id: str | None = None
        self._batch_running = False  # True only between batch start and _reset_buttons()
        # System tray
        self._tray = None
        self._real_quit_requested = False

        self._build_ui()
        self._refresh_step_states()
        self._check_auth_on_start()
        self._maybe_check_updates()

        # Hide-to-tray on X button; real quit only via tray menu
        self.protocol("WM_DELETE_WINDOW", self._on_main_close)
        self._start_tray()

    # ─── UI build ───────────────────────────────

    def _build_ui(self):
        # Header — taller to fit tier/quota badge + logo
        header = ctk.CTkFrame(self, fg_color=COLOR_BG_CARD, corner_radius=0, height=92)
        header.pack(fill="x")
        header.pack_propagate(False)

        # App icon (camera) — identity ของ Happy Photo Organizer
        if self._app_icon_header is not None:
            logo_label = ctk.CTkLabel(
                header, image=self._app_icon_header, text="",
                cursor="hand2",
            )
            logo_label.pack(side="left", padx=(16, 8), pady=12)
            logo_label.bind("<Button-1>", lambda _e: self._open_ai_health())

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=4, pady=8, fill="y")
        ctk.CTkLabel(
            title_frame, text=APP_TITLE,
            font=("Segoe UI", 20, "bold"), text_color=COLOR_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame,
            text=f"v{APP_VERSION}  •  {len(self.catalog.names())} jobs  •  {format_summary()}",
            font=("Segoe UI", 10), text_color=COLOR_MUTED,
        ).pack(anchor="w")

        # Tier + quota badge (clickable → AI Health) — wide enough not to clip
        self.tier_badge = ctk.CTkLabel(
            title_frame,
            text="",
            font=("Segoe UI", 11, "bold"),
            text_color=COLOR_PRIMARY,
            cursor="hand2",
            anchor="w",
            justify="left",
        )
        self.tier_badge.pack(anchor="w", pady=(3, 0), fill="x")
        self.tier_badge.bind("<Button-1>", lambda _e: self._open_ai_health())

        # Right side: action buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=20, pady=8)

        ctk.CTkButton(
            btn_frame, text="AI Health", width=100, height=30,
            fg_color=COLOR_BG_INPUT, hover_color="#475569",
            text_color=COLOR_TEXT,
            command=self._open_ai_health,
        ).pack(side="top", pady=(0, 4))
        ctk.CTkButton(
            btn_frame, text="Settings", width=100, height=30,
            fg_color=COLOR_BG_INPUT, hover_color="#475569",
            text_color=COLOR_TEXT,
            command=self._open_settings,
        ).pack(side="top")

        # Tier badge initial + start 2s poll loop (track id for cleanup)
        self._update_tier_badge()
        self._poll_after_id = self.after(1000, self._poll_quota_badge)

        # 2-column row: LEFT = Step 1 stacked on Step 2, RIGHT = Log (full height)
        self.top_row = ctk.CTkFrame(self, fg_color="transparent")
        self.top_row.pack(fill="x", padx=12, pady=(12, 6))
        self.top_row.grid_columnconfigure(0, weight=1, uniform="col")
        self.top_row.grid_columnconfigure(1, weight=1, uniform="col")
        self.top_row.grid_rowconfigure(0, weight=1)

        # Left column wrapper — holds Step 1 (top) and Step 2 (bottom)
        self.left_col = ctk.CTkFrame(self.top_row, fg_color="transparent")
        self.left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.left_col.grid_columnconfigure(0, weight=1)

        self._build_step1()
        self._build_step2()
        self._build_log()
        self._build_step3()

    # Step 1: Input (LEFT column, TOP — compact)
    def _build_step1(self):
        self.step1 = StepCard(self.left_col, 1, "Drop Photos or Folders")
        self.step1.grid(row=0, column=0, sticky="nsew", pady=(0, 3))

        body = self.step1.body

        # Drop zone (compact, taller to fit mascot)
        # Idle border is subtle grey — turns orange/pink only during drag interaction
        self.drop_zone = ctk.CTkFrame(
            body, fg_color="#1A2538",
            border_color=COLOR_BG_INPUT, border_width=2,
            corner_radius=10, height=96,
        )
        self.drop_zone.pack(fill="x", pady=(2, 6))
        self.drop_zone.pack_propagate(False)

        # Mascot label on left of hint text
        self.drop_hint = ctk.CTkLabel(
            self.drop_zone,
            text="  Drop photos or folders here\n  (or click to browse)",
            image=self._mascot_drop_zone,
            compound="left",
            font=("Segoe UI", 12),
            text_color=COLOR_MUTED, justify="left",
        )
        self.drop_hint.pack(expand=True)

        for widget in (self.drop_zone, self.drop_hint):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
            widget.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            widget.dnd_bind("<<DragLeave>>", self._on_drag_leave)
            widget.bind("<Button-1>", self._on_drop_click)

        # Control row (compact buttons)
        ctrl = ctk.CTkFrame(body, fg_color="transparent")
        ctrl.pack(fill="x", pady=(0, 2))

        ctk.CTkButton(
            ctrl, text="Clear", height=28, width=64,
            font=("Segoe UI", 11),
            fg_color=COLOR_BG_INPUT, hover_color="#475569",
            text_color=COLOR_TEXT,
            command=self._clear_sources,
        ).pack(side="left")

        self.dest_btn = ctk.CTkButton(
            ctrl, text="Choose Destination", height=28, width=140,
            font=("Segoe UI", 11, "bold"),
            fg_color=COLOR_PRIMARY, hover_color=COLOR_ACCENT,
            text_color="#FFFFFF",
            command=self._pick_dest,
        )
        self.dest_btn.pack(side="right")

        self.sources_label = ctk.CTkLabel(
            body, text="No source selected", anchor="w", justify="left",
            font=("Segoe UI", 10), text_color=COLOR_MUTED,
            wraplength=520,
        )
        self.sources_label.pack(fill="x", pady=(4, 0))

        self.dest_label = ctk.CTkLabel(
            body, text="Destination: —", anchor="w",
            font=("Segoe UI", 10), text_color=COLOR_MUTED,
            wraplength=520,
        )
        self.dest_label.pack(fill="x", pady=(2, 0))

    # Step 2: Workflow (LEFT column, BOTTOM — below Step 1)
    def _build_step2(self):
        self.step2 = StepCard(self.left_col, 2, "Workflow")
        self.step2.grid(row=1, column=0, sticky="nsew", pady=(3, 0))

        body = self.step2.body

        ctk.CTkLabel(
            body, text="① Resize & Group  →  ② AI Tagging  →  ③ Review  →  ④ Rename",
            font=("Segoe UI", 10), text_color=COLOR_MUTED, anchor="w",
        ).pack(fill="x", pady=(0, 6))

        # Action row (compact)
        action = ctk.CTkFrame(body, fg_color="transparent")
        action.pack(fill="x", pady=(0, 6))

        self.phase12_btn = ctk.CTkButton(
            action, text=" Start AI Tagging", height=36, width=180,
            font=("Segoe UI", 11, "bold"),
            fg_color=COLOR_PRIMARY, hover_color=COLOR_ACCENT,
            text_color="#FFFFFF",
            image=self._mascot_btn,
            compound="left",
            command=self._start_phase12,
        )
        self.phase12_btn.pack(side="left")

        self.cancel_btn = ctk.CTkButton(
            action, text="Cancel", height=32, width=70,
            font=("Segoe UI", 11),
            fg_color=COLOR_DANGER, hover_color="#B91C1C",
            text_color="#FFFFFF",
            state="disabled",
            command=self._cancel,
        )
        self.cancel_btn.pack(side="right")

        # Progress row
        progress_row = ctk.CTkFrame(body, fg_color="transparent")
        progress_row.pack(fill="x", pady=(4, 2))

        self.progress = ctk.CTkProgressBar(progress_row, height=10, progress_color=COLOR_PRIMARY)
        self.progress.pack(fill="x", side="left", expand=True, padx=(0, 8))
        self.progress.set(0)

        self.progress_text = ctk.CTkLabel(
            progress_row, text="0%", width=48,
            font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT,
        )
        self.progress_text.pack(side="right")

        self.status_detail = ctk.CTkLabel(
            body, text="Ready", anchor="w",
            font=("Segoe UI", 10), text_color=COLOR_MUTED,
            wraplength=520, justify="left",
        )
        self.status_detail.pack(fill="x", pady=(2, 0))

        # ETA tracking
        self._phase_start: float | None = None

    # Log Panel (RIGHT column — spans full height of Step 1 + Step 2)
    def _build_log(self):
        log_card = ctk.CTkFrame(self.top_row, fg_color=COLOR_BG_CARD, corner_radius=10)
        log_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            log_header, text="Log",
            font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT,
        ).pack(side="left")
        ctk.CTkButton(
            log_header, text="Clear log", height=22, width=70,
            font=("Segoe UI", 9),
            fg_color=COLOR_BG_INPUT, hover_color="#475569",
            command=self._clear_log,
        ).pack(side="right")

        self.log_box = ctk.CTkTextbox(
            log_card,
            fg_color="#0A1220",
            text_color="#CBD5E1",
            font=("Consolas", 10),
            corner_radius=6,
        )
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.log_box.configure(state="disabled")

    # Step 3: Review (full width, expand) — Commit Rename button on right
    def _build_step3(self):
        self.step3 = StepCard(self, 3, "Review & Edit Names")
        self.step3.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        body = self.step3.body

        # Header row: summary (left) + Commit Rename button (right)
        header_row = ctk.CTkFrame(body, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 6))

        self.review_summary = ctk.CTkLabel(
            header_row, text="Not yet analyzed",
            font=("Segoe UI", 11), text_color=COLOR_MUTED, anchor="w",
        )
        self.review_summary.pack(side="left", fill="x", expand=True)

        self.phase4_btn = ctk.CTkButton(
            header_row, text=" Commit Rename", height=36, width=170,
            font=("Segoe UI", 12, "bold"),
            fg_color=COLOR_OK, hover_color="#0EA371",
            text_color="#FFFFFF",
            image=self._mascot_btn,
            compound="left",
            state="disabled",
            command=self._start_phase4,
        )
        self.phase4_btn.pack(side="right")

        self.table_scroll = ctk.CTkScrollableFrame(body, fg_color=COLOR_BG, corner_radius=8)
        self.table_scroll.pack(fill="both", expand=True, pady=(0, 4))

    # ─── State / status ─────────────────────────

    def _refresh_step_states(self):
        # Step 1 — pending → ready เมื่อมี sources + dest
        if self.source_paths and self.dest_root:
            self.step1.set_status("ready")
        elif self.source_paths or self.dest_root:
            self.step1.set_status("pending")
        else:
            self.step1.set_status("pending")

        # Step 2 — ready ถ้า step1 ready, active ถ้ามี worker, done ถ้ามี plan
        if self.worker and self.worker.is_alive():
            self.step2.set_status("active")
        elif self.plan and self.plan.assignments:
            self.step2.set_status("done")
        elif self.source_paths and self.dest_root:
            self.step2.set_status("ready")
        else:
            self.step2.set_status("pending")

        # Step 3 — ready ถ้ามี plan, done หลัง rename, active ระหว่าง rename
        # ใช้ flag _rename_done
        if getattr(self, "_rename_done", False):
            self.step3.set_status("done")
        elif self.plan and self.plan.assignments:
            self.step3.set_status("ready")
        else:
            self.step3.set_status("pending")

    # ─── Log helpers ─────────────────────────────

    def _log(self, msg: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": " ", "ok": "+", "warn": "!", "err": "X"}.get(level, " ")
        line = f"[{ts}] {prefix} {msg}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _set_progress(self, ratio: float, label: str = ""):
        self.progress.set(min(max(ratio, 0), 1))
        self.progress_text.configure(text=f"{int(ratio * 100)}%")
        if label:
            self.status_detail.configure(text=label, text_color=COLOR_TEXT)

    def _eta(self, current: int, total: int) -> str:
        if not self._phase_start or current <= 0:
            return ""
        elapsed = time.time() - self._phase_start
        rate = current / elapsed if elapsed > 0 else 0
        if rate <= 0:
            return ""
        remaining = (total - current) / rate
        if remaining < 60:
            return f"~{int(remaining)}s left"
        return f"~{int(remaining / 60)}m left"

    # ─── Settings / auth ─────────────────────────

    def _check_auth_on_start(self):
        if not auth.get_api_key():
            self.after(300, self._open_settings)

    # ─── Auto-update (background, no UI button) ──

    UPDATE_INTERVAL_MS = 5 * 60 * 1000  # 5 minutes

    def _maybe_check_updates(self):
        """Schedule the first check after 3s; thereafter every 5 minutes.
        Runs even when the window is hidden in the tray.
        """
        cfg = auth.load_config()
        if not cfg.get("auto_check_updates", True):
            return
        # First check after 3s so first paint stays snappy
        self.after(3000, self._update_check_tick)

    # ─── System tray + window lifecycle ──────────

    def _start_tray(self):
        """Launch the tray icon in a detached thread. No-op if pystray missing."""
        if pystray is None:
            return
        try:
            self._tray = HappyTray(self)
            self._tray.start()
        except Exception:
            self._tray = None

    def _on_main_close(self):
        """X button: hide to tray if available, otherwise real quit."""
        if self._real_quit_requested:
            self.destroy()
            return
        if self._tray is not None and getattr(self._tray, "icon", None) is not None:
            # Save geometry now since we may stay alive a long time before real quit
            try:
                self._save_window_state()
            except Exception:
                pass
            self.withdraw()
            self._log(
                "Minimized to tray — right-click the icon (bottom-right) to restore or quit",
                "ok",
            )
        else:
            self.destroy()

    def _show_window_from_tray(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(150, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def _real_quit(self):
        """Final exit path — call from tray Quit menu."""
        self._real_quit_requested = True
        if self._tray:
            self._tray.stop()
        # Schedule on main thread (tray callbacks come from another thread)
        try:
            self.after(0, self.destroy)
        except Exception:
            try:
                self.destroy()
            except Exception:
                pass

    def _update_check_tick(self):
        """One tick of the periodic update worker."""
        threading.Thread(target=self._update_check_worker, daemon=True).start()
        # Reschedule whether or not this tick finds something
        self._update_after_id = self.after(self.UPDATE_INTERVAL_MS, self._update_check_tick)

    def _update_check_worker(self):
        try:
            from core import updater
            info = updater.check_for_update(APP_VERSION, timeout=5.0)
            if info is not None:
                self.after(0, lambda i=info: self._on_update_available(i))
        except Exception:
            pass

    def _on_update_available(self, info):
        """Update found. Refresh-only behaviour: if a batch is running, log the
        discovery and DEFER both download and install until the batch ends.
        Otherwise start a silent background download.
        """
        # Skip if we already know about this same version (avoid noisy re-logs)
        existing = getattr(self, "_pending_update_info", None)
        if existing is not None and existing.tag == info.tag:
            return
        if self._pending_installer and self._pending_installer_version == info.version:
            return

        self._log(f"Update available: v{info.version}", "ok")

        if self._batch_running:
            # Refresh-only while a batch is in progress — do NOT download or install
            self._pending_update_info = info
            self._log(
                f"  -> deferred — will download + install after the current batch finishes",
                "ok",
            )
            return

        self._begin_update_download(info)

    def _begin_update_download(self, info):
        """Kick off a silent background download of the installer."""
        self._log(f"Downloading v{info.version} in background...", "ok")

        def download_worker():
            from core import updater
            dest = updater.cache_dir() / f"HappyPhotoOrganizerSetup-v{info.version}.exe"
            ok, msg = updater.download_installer(info.download_url, dest)
            if ok:
                self.after(0, lambda d=dest, v=info.version: self._on_installer_ready(d, v))
            else:
                self.after(0, lambda m=msg: self._log(f"Update download failed: {m}", "warn"))

        threading.Thread(target=download_worker, daemon=True).start()

    def _on_installer_ready(self, installer_path: Path, version: str):
        """Installer downloaded — install + relaunch unless a batch is running."""
        self._pending_installer = installer_path
        self._pending_installer_version = version
        # Clear the lighter pending-info marker since we've graduated to a ready installer
        self._pending_update_info = None

        if self._batch_running:
            self._log(f"Update v{version} downloaded — will install after current batch", "ok")
            return
        self._install_pending_now(version)

    def _install_pending_now(self, version: str | None = None):
        """Launch installer (silent) and exit so files can be replaced.
        Guarded so it never fires mid-batch.
        """
        if self._batch_running:
            return
        if not self._pending_installer or not self._pending_installer.exists():
            return
        try:
            from core import updater
            self._log(f"Installing update{f' v{version}' if version else ''}...", "ok")
            # Tear down tray + after-loops cleanly before installer kills us
            self._real_quit_requested = True
            updater.launch_installer_and_exit(self._pending_installer, silent=True)
        except SystemExit:
            raise
        except Exception as e:
            self._log(f"Install failed: {str(e)[:120]}", "warn")

    def _resume_deferred_update(self):
        """Called once a batch finishes. Resume whichever stage was deferred.
        Case A: installer already downloaded → install now.
        Case B: only UpdateInfo was buffered → start the download now.
        """
        if self._batch_running:
            return  # safety — should not happen
        if self._pending_installer and self._pending_installer.exists():
            version = self._pending_installer_version or "?"
            self._log(f"Batch done — installing pending update v{version}", "ok")
            self._install_pending_now(version)
            return
        info = self._pending_update_info
        if info is not None:
            self._pending_update_info = None
            self._log(f"Batch done — resuming update v{info.version}", "ok")
            self._begin_update_download(info)

    def _open_settings(self):
        SettingsDialog(self, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        self._log("Settings saved", "ok")
        # reload tier (in case user changed it)
        cfg = auth.load_config()
        update_tier_from_config(cfg)
        self._update_tier_badge()

    def _open_ai_health(self):
        if self._ai_health_dialog is not None and self._ai_health_dialog.winfo_exists():
            self._ai_health_dialog.lift()
            self._ai_health_dialog.focus_force()
            return
        self._ai_health_dialog = AIHealthDialog(self, on_tier_change=self._on_tier_changed)

    def _on_tier_changed(self):
        self._update_tier_badge()
        cfg = auth.load_config()
        self._log(f"Tier changed: {cfg.get('tier', DEFAULT_TIER)}", "ok")

    def _update_tier_badge(self):
        """Refresh header badge — RPM realtime (RPD/quota ดูเต็มใน AI Health)"""
        try:
            tier = self.rate_limiter.tier
            rpm_now = self.usage_log.current_rpm()
            cap_rpm = tier.rpm
            if not tier.throttle or cap_rpm <= 0:
                # paid / no cap
                badge = f"Tier: {tier.label}  •  RPM: {rpm_now} (no cap)  ●"
                color = COLOR_OK
            else:
                pct = rpm_now / cap_rpm if cap_rpm else 0
                if pct >= 1.0:
                    icon, color = "🚫", COLOR_DANGER  # at limit
                elif pct >= 0.8:
                    icon, color = "⚠", "#F97316"     # near throttle
                elif pct >= 0.5:
                    icon, color = "▲", COLOR_WARN    # active
                elif rpm_now > 0:
                    icon, color = "▸", COLOR_OK      # running
                else:
                    icon, color = "●", COLOR_OK      # idle
                badge = f"Tier: {tier.label}  •  RPM: {rpm_now}/{cap_rpm}  {icon}"
            self.tier_badge.configure(text=badge, text_color=color)
        except Exception:
            pass

    def _poll_quota_badge(self):
        """Auto-refresh badge every 5s"""
        try:
            self._update_tier_badge()
            # also refresh AI Health dialog if open
            if self._ai_health_dialog and self._ai_health_dialog.winfo_exists():
                try:
                    self._ai_health_dialog.refresh()
                except Exception:
                    pass
        except Exception:
            pass
        # re-schedule every 2s (RPM is more dynamic than RPD)
        try:
            self._poll_after_id = self.after(2000, self._poll_quota_badge)
        except Exception:
            pass

    def destroy(self):
        """Override to cancel pending after() callbacks + stop tray cleanly."""
        # Save window geometry before tearing down — must happen while window is still valid
        self._save_window_state()
        # Stop tray icon (idempotent)
        try:
            if getattr(self, "_tray", None):
                self._tray.stop()
        except Exception:
            pass
        # Cancel pending after() callbacks to avoid "invalid command" warnings
        try:
            for attr in ("_poll_after_id", "_update_after_id"):
                aid = getattr(self, attr, None)
                if aid:
                    self.after_cancel(aid)
        except Exception:
            pass
        super().destroy()

    # ─── Window state persistence ────────────────
    def _restore_window_state(self):
        """Restore last geometry + maximized flag. Falls back to default 1280x780 centered."""
        ws = auth.load_config().get("window_state") or {}
        geom = (ws.get("geometry") or "").strip()
        maximized = bool(ws.get("maximized", False))

        # Validate geometry string roughly: "WxH+X+Y" or "WxH"
        if geom and self._is_geometry_onscreen(geom):
            self.geometry(geom)
        else:
            self.geometry("1280x780")

        if maximized:
            # On Windows the zoomed state must be set after the window is realized
            self.after(60, lambda: self._safe_state("zoomed"))

    def _save_window_state(self):
        """Persist current geometry + maximized flag to ~/.happy-photo-organizer/auth.json."""
        try:
            state = self.wm_state()
            is_maximized = state == "zoomed"
            # When zoomed, Tk reports the normal-state geometry — exactly what we want to restore
            geom = self.geometry()
            auth.update_config({
                "window_state": {
                    "geometry": geom,
                    "maximized": is_maximized,
                }
            })
        except Exception:
            pass

    def _safe_state(self, state: str):
        try:
            self.state(state)
        except Exception:
            pass

    def _is_geometry_onscreen(self, geom: str) -> bool:
        """Clamp check: rough sanity that the X,Y origin lies on some visible monitor.
        Tkinter only knows about the primary screen via winfo_screen*, so we use a wide tolerance.
        """
        import re
        m = re.match(r"^(\d+)x(\d+)(?:\+(-?\d+)\+(-?\d+))?$", geom)
        if not m:
            return False
        w, h = int(m.group(1)), int(m.group(2))
        if w < 400 or h < 300 or w > 8000 or h > 8000:
            return False
        if m.group(3) is None:
            return True  # size-only geometry is fine
        x, y = int(m.group(3)), int(m.group(4))
        # Allow positions up to a generous virtual-desktop bound (multi-monitor span)
        return -6000 <= x <= 12000 and -3000 <= y <= 6000

    # ─── Drop / sources ──────────────────────────

    def _on_drag_enter(self, _event):
        self.drop_zone.configure(border_color=COLOR_ACCENT, fg_color="#2D1B2E")
        self.drop_hint.configure(text="Drop here!", text_color=COLOR_ACCENT)

    def _on_drag_leave(self, _event):
        self.drop_zone.configure(border_color=COLOR_BG_INPUT, fg_color="#1A2538")
        self.drop_hint.configure(
            text="  Drop photos or folders here\n  (or click to browse)",
            text_color=COLOR_MUTED,
        )

    def _on_drop(self, event):
        raw_paths = self.tk.splitlist(event.data)
        added = 0
        for raw in raw_paths:
            p = Path(raw)
            if p.exists():
                self.source_paths.append(p)
                added += 1
        self._on_drag_leave(None)
        if added:
            self._log(f"Added {added} item(s) via drag-drop", "ok")
            self._refresh_sources()
            self._refresh_step_states()

    def _on_drop_click(self, _event):
        filter_str = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTS))
        files = filedialog.askopenfilenames(
            title="Select image files (or drag-drop instead)",
            filetypes=[("Images", filter_str), ("All", "*.*")],
        )
        for f in files:
            self.source_paths.append(Path(f))
        if files:
            self._log(f"Added {len(files)} file(s)", "ok")
            self._refresh_sources()
            self._refresh_step_states()

    def _clear_sources(self):
        if self.source_paths:
            self._log("Sources cleared", "info")
        self.source_paths.clear()
        self._refresh_sources()
        self._refresh_step_states()

    def _refresh_sources(self):
        if not self.source_paths:
            self.sources_label.configure(text="No source selected", text_color=COLOR_MUTED)
            return
        total = 0
        lines = []
        for p in self.source_paths:
            if p.is_dir():
                cnt = len(collect_images(p, recursive=True))
                total += cnt
                lines.append(f"[folder] {p.name}  →  {cnt} photos")
            elif p.is_file() and is_supported_image(p):
                total += 1
                lines.append(f"[file] {p.name}")
        header = f"{len(self.source_paths)} source(s)  •  {total} photos total"
        text = header + "\n" + "\n".join(lines[:6])
        if len(lines) > 6:
            text += f"\n   ... and {len(lines) - 6} more"
        self.sources_label.configure(text=text, text_color=COLOR_TEXT)

    def _pick_dest(self):
        folder = filedialog.askdirectory(title="Select destination folder")
        if folder:
            self.dest_root = Path(folder)
            self.dest_label.configure(text=f"Destination: {self.dest_root}", text_color=COLOR_TEXT)
            self._log(f"Destination set: {self.dest_root}", "ok")
            self._refresh_step_states()

    # ─── Phase 1+2 ───────────────────────────────

    def _start_phase12(self):
        if not self.source_paths:
            messagebox.showwarning("No source", "Drop photos or folders first")
            return
        if not self.dest_root:
            messagebox.showwarning("No destination", "Choose a destination folder first")
            return
        if not auth.get_api_key():
            messagebox.showwarning("API key missing", "Open Settings to enter your key")
            self._open_settings()
            return

        # Pre-flight: estimate # of folders ≈ rough heuristic, then check quota
        total_imgs = 0
        for p in self.source_paths:
            if p.is_file() and is_supported_image(p):
                total_imgs += 1
            elif p.is_dir():
                total_imgs += len(collect_images(p, recursive=True))
        if total_imgs == 0:
            messagebox.showwarning("No images", "No supported images found in sources")
            return
        # Rough estimate: 1 group ≈ 5-8 photos
        est_groups = max(1, total_imgs // 6)
        est = self.rate_limiter.estimate_eta(est_groups)
        # Show preflight summary in log + confirm if risky
        self._log(
            f"Pre-flight: ~{est_groups} folders estimated, "
            f"ETA ~{est['eta_sec']}s, quota {est.get('rpd_used_after', '?')}/{est.get('rpd_cap', '∞')}",
            "info",
        )
        if est.get("warning"):
            proceed = messagebox.askyesno(
                "Pre-flight warning",
                f"{est['warning']}\n\nProceed anyway? (Phase 2 may fail mid-way if quota runs out)",
            )
            if not proceed:
                self._log("Pre-flight: user cancelled", "warn")
                return

        self._rename_done = False
        self.phase12_btn.configure(state="disabled")
        self.phase4_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.cancel_event.clear()
        # Mark batch active — pauses any update download/install until _reset_buttons()
        self._batch_running = True
        self._log("Starting Phase 1+2", "ok")
        self._phase_start = time.time()

        self.worker = threading.Thread(target=self._phase12_worker, daemon=True)
        self.worker.start()
        self._refresh_step_states()

    def _phase12_worker(self):
        try:
            self.after(0, lambda: self._log("Phase 1: Collecting + Resizing + Grouping by date", "info"))
            self.after(0, lambda: self.status_detail.configure(
                text="Phase 1/2: Resizing & Grouping...", text_color=COLOR_PRIMARY,
            ))

            plan = phase1_resize_and_group(
                self.source_paths, self.dest_root,
                target_kb_min=self.target_kb_min.get(),
                target_kb_max=self.target_kb_max.get(),
                progress_cb=self._phase1_progress,
                cancel_event=self.cancel_event,
            )

            if self.cancel_event.is_set():
                self.after(0, lambda: self._log("Cancelled during Phase 1", "warn"))
                return

            self.plan = plan
            self.after(0, lambda: self._log(
                f"Phase 1 done: {len(plan.assignments)} folders, resized {plan.total_resized}/{plan.total_images}",
                "ok",
            ))
            # Report existing dates in destination + any shifts
            if plan.pre_existing_dates:
                self.after(0, lambda: self._log(
                    f"Found {len(plan.pre_existing_dates)} existing dates in destination — avoided collisions",
                    "info",
                ))
            if plan.shifted_count:
                msg = f"Shifted {plan.shifted_count} folder(s) to avoid date collision"
                if plan.capped_count:
                    msg += f" — {plan.capped_count} capped to last day of month (overflow)"
                self.after(0, lambda m=msg: self._log(m, "warn"))

            if not plan.assignments:
                self.after(0, lambda: self._log("No photos found in source", "warn"))
                return

            # Phase 2
            self._phase_start = time.time()
            self.after(0, lambda: self._log("Phase 2: AI tagging in progress", "info"))
            self.after(0, lambda: self.status_detail.configure(
                text="Phase 2/2: AI analyzing...", text_color=COLOR_PRIMARY,
            ))

            phase2_ai_analyze(
                plan, self.catalog,
                sample_size=3,
                progress_cb=self._phase2_progress,
                cancel_event=self.cancel_event,
            )

            if self.cancel_event.is_set():
                self.after(0, lambda: self._log("Cancelled during Phase 2", "warn"))
            else:
                self.after(0, lambda: self._log("Phase 2 done — awaiting review", "ok"))

            self.after(0, lambda: self._render_plan(plan))
        except Exception as e:
            err_msg = str(e)[:300]
            self.after(0, lambda: self._log(f"Error: {err_msg}", "err"))
        finally:
            self.after(0, self._reset_buttons)

    def _phase1_progress(self, current: int, total: int, msg: str):
        ratio = current / total if total else 0
        eta = self._eta(current, total)
        suffix = f"  •  {eta}" if eta else ""
        self.after(0, lambda: self._set_progress(
            ratio, f"[Phase 1] {current}/{total}  •  {msg}{suffix}",
        ))
        # log ทุกรูป — ให้นิกเห็นว่า realtime
        self.after(0, lambda: self._log(f"[{current}/{total}] {msg}", "info"))

    def _phase2_progress(self, current: int, total: int, msg: str):
        ratio = current / total if total else 0
        eta = self._eta(current, total)
        suffix = f"  •  {eta}" if eta else ""
        self.after(0, lambda: self._set_progress(
            ratio, f"[Phase 2] {current}/{total}  •  {msg}{suffix}",
        ))
        self.after(0, lambda: self._log(f"[{current}/{total}] {msg}", "info"))

    def _render_plan(self, plan: Plan):
        for w in self.table_scroll.winfo_children():
            w.destroy()

        if not plan.assignments:
            self.review_summary.configure(text="No photos found in source", text_color=COLOR_WARN)
            self._refresh_step_states()
            return

        need_review = sum(1 for a in plan.assignments if a.needs_review)
        summary = (
            f"{len(plan.assignments)} folders  •  "
            f"resized {plan.total_resized}/{plan.total_images}  •  "
            f"{need_review} need review"
        )
        if plan.shifted_count:
            summary += f"  •  {plan.shifted_count} shifted"
        if plan.capped_count:
            summary += f"  •  {plan.capped_count} capped"
        self.review_summary.configure(text=summary, text_color=COLOR_TEXT)

        for a in plan.assignments:
            row = JobRow(self.table_scroll, a, self.catalog, on_change=self._refresh_summary)
            row.pack(fill="x", padx=4, pady=4)

        self.phase4_btn.configure(state="normal")
        self.status_detail.configure(
            text="Analysis done — review the table then click 'Commit Rename'",
            text_color=COLOR_OK,
        )
        self._refresh_step_states()

    def _refresh_summary(self):
        if not self.plan:
            return
        # ดูชื่องานใหม่ที่ user พิมพ์ → เพิ่มเข้า catalog (in-memory) → refresh dropdowns
        added_any = False
        for a in self.plan.assignments:
            name = a.job_name.strip()
            if name and self.catalog.find(name) is None:
                ok, _ = self.catalog.add(name)
                if ok:
                    added_any = True
                    self._log(f"Learned new name: {name}", "ok")

        if added_any:
            # refresh dropdown ของทุก row
            for w in self.table_scroll.winfo_children():
                if isinstance(w, JobRow):
                    w.refresh_catalog_values()

        need = sum(1 for a in self.plan.assignments if a.needs_review)
        self.review_summary.configure(
            text=(
                f"{len(self.plan.assignments)} folders  •  "
                f"resized {self.plan.total_resized}/{self.plan.total_images}  •  "
                f"{need} need review"
            ),
        )

    # ─── Phase 4 ─────────────────────────────────

    def _start_phase4(self):
        if not self.plan:
            return
        unassigned = [a for a in self.plan.assignments if not a.job_name.strip()]
        if unassigned:
            ok = messagebox.askyesno(
                "Some folders have no name",
                f"{len(unassigned)} folder(s) without name — they'll keep temporary names (date-prefixed). Continue?",
            )
            if not ok:
                return

        self.phase12_btn.configure(state="disabled")
        self.phase4_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.cancel_event.clear()
        # Mark batch active — pauses any update download/install until _reset_buttons()
        self._batch_running = True
        self._log("Starting Phase 4: Rename folders", "ok")
        self._phase_start = time.time()
        self.step3.set_status("active")

        self.worker = threading.Thread(target=self._phase4_worker, daemon=True)
        self.worker.start()

    def _phase4_worker(self):
        try:
            result = phase4_rename_folders(
                self.plan,
                progress_cb=self._phase4_progress,
                cancel_event=self.cancel_event,
                catalog=self.catalog,
            )
            self.after(0, lambda: self._on_rename_done(result))
        except Exception as e:
            err_msg = str(e)[:300]
            self.after(0, lambda: self._log(f"Error: {err_msg}", "err"))
        finally:
            self.after(0, self._reset_buttons)

    def _phase4_progress(self, current: int, total: int, msg: str):
        ratio = current / total if total else 0
        self.after(0, lambda: self._set_progress(
            ratio, f"[Phase 4] {current}/{total}  •  {msg}",
        ))

    def _on_rename_done(self, result):
        self._rename_done = True
        self._log(
            f"Phase 4 done: renamed {result.renamed} folder(s)"
            + (f", skipped {result.skipped}" if result.skipped else "")
            + (f", errors {len(result.errors)}" if result.errors else ""),
            "ok" if not result.errors else "warn",
        )
        for err in result.errors[:5]:
            self._log(err, "err")

        self.status_detail.configure(
            text=f"Renamed {result.renamed} folder(s)",
            text_color=COLOR_OK if not result.errors else COLOR_WARN,
        )
        self._set_progress(1.0, "Done")
        self._refresh_step_states()

        detail = (
            f"Renamed: {result.renamed}\n"
            f"Skipped (no name): {result.skipped}\n"
            f"Errors: {len(result.errors)}\n\n"
            f"Output folders: {len(result.output_folders)}"
        )
        if result.errors:
            detail += "\n\nFirst errors:\n" + "\n".join(result.errors[:5])
        messagebox.showinfo("All Done", detail)

    def _cancel(self):
        self.cancel_event.set()
        self._log("Cancelling...", "warn")
        self.status_detail.configure(text="Cancelling...", text_color=COLOR_WARN)

    def _reset_buttons(self):
        self.phase12_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        if self.plan:
            self.phase4_btn.configure(state="normal")
        self._refresh_step_states()
        # Batch finished — release the update gate and resume anything that was deferred
        self._batch_running = False
        try:
            self._resume_deferred_update()
        except Exception:
            pass


def _acquire_single_instance() -> bool:
    """Win32 named mutex — returns True if this is the only running instance.
    On non-Windows or on failure, returns True (be permissive).
    """
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        # Per-session mutex (Local\\ prefix). UUID-like suffix avoids collisions.
        name = "Local\\HappyPhotoOrganizer-SingleInstance-a1b2c3d4"
        handle = kernel32.CreateMutexW(None, False, name)
        ERROR_ALREADY_EXISTS = 183
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            return False
        # Keep handle alive for process lifetime
        _acquire_single_instance._handle = handle  # type: ignore[attr-defined]
        return True
    except Exception:
        return True


def _focus_existing_instance() -> None:
    """Find the running HPO main window and bring it to the foreground."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value.startswith("Happy Photo Organizer"):
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    return False
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
    except Exception:
        pass


def main() -> int:
    if not _acquire_single_instance():
        _focus_existing_instance()
        return 0
    app = MainWindow()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
