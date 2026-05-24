"""
Happy Photo Organizer — main entry point.

Layout: this file holds the MainWindow class and the program entry point.
Reusable building blocks live in core/ (version, single_instance, tray, updater,
auth, catalog, processor, rate_limiter, usage_log) and ui/ (theme, paste_helper,
step_card, job_row, dialogs.settings, dialogs.ai_health).
"""
from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import tkinter as tk
from PIL import Image
from tkinterdnd2 import DND_FILES, TkinterDnD

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ─── core ──────────────────────────────────────────────────────
from core import auth
from core.catalog import JobCatalog
from core.image_io import (
    collect_images, format_summary, is_supported_image, SUPPORTED_EXTS,
)
from core.processor import (
    phase1_resize_and_group,
    phase2_ai_analyze,
    phase4_rename_folders,
    Plan,
)
from core.rate_limiter import (
    DEFAULT_TIER,
    get_rate_limiter,
    update_tier_from_config,
)
from core.single_instance import ensure_single_instance
from core.tray import HappyTray, pystray
from core.update_worker import UpdateWorker
from core.usage_log import get_usage_log
from core.version import APP_TITLE, APP_VERSION

# ─── ui ────────────────────────────────────────────────────────
from ui.dialogs.ai_health import AIHealthDialog
from ui.dialogs.settings import SettingsDialog
from ui.job_row import JobRow
from ui.paste_helper import enable_paste
from ui.step_card import StepCard
from ui.theme import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_BG_CARD,
    COLOR_BG_INPUT,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_OK,
    COLOR_PRIMARY,
    COLOR_TEXT,
    COLOR_WARN,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


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
        # Round-6 UI-13 (Cos review 2026-05-24): bump from 640×420 — too
        # narrow for Step 3's 4-column table once Phase 2 produces rows.
        # 960×600 = comfortable two-pane review with the log panel still visible.
        self.minsize(960, 600)
        self.configure(fg_color=COLOR_BG)

        # Restore window geometry from last session (size + position + maximized)
        self._restore_window_state()

        # Window icon (title bar + taskbar) + dark title bar.
        # v1.037: use ui.win_chrome.apply_chrome which (a) registers the
        # icon at Tk class level so every Toplevel inherits it, (b) forces
        # the OS title bar into dark mode via DWMWA_USE_IMMERSIVE_DARK_MODE.
        # Fixes white title bars on Settings / AI Health dialogs that Nick
        # reported in v1.036 screenshots.
        from ui.win_chrome import apply_chrome, register_default_icon
        icon_path = ROOT / "assets" / "happy_icon.ico"
        if icon_path.exists():
            register_default_icon(icon_path)
            apply_chrome(self, icon_path)
        self._icon_path = icon_path  # stash for dialogs to read

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

        # Auto-update — state owned by the worker; we hold a handle for shutdown
        self._batch_running = False  # True only between batch start and _reset_buttons()
        self.update_worker = UpdateWorker(self, APP_VERSION)
        # Window-state debounce
        self._geo_save_after_id: str | None = None
        # System tray
        self._tray = None
        self._real_quit_requested = False
        self._destroyed = False  # flips True in destroy(); late callbacks bail
        # Round-6 BUG-M8 (Cos review 2026-05-24): track <Unmap>'s deferred
        # withdraw so destroy() can cancel cleanly. Already guarded by
        # _destroyed checks in _safe_withdraw, but explicit cancel is
        # defense-in-depth + matches the _geo_save_after_id pattern.
        self._unmap_after_id: str | None = None

        self._build_ui()
        self._refresh_step_states()
        self._check_auth_on_start()
        self.update_worker.start()

        # Hide-to-tray on X button; real quit only via tray menu
        self.protocol("WM_DELETE_WINDOW", self._on_main_close)
        # Minimize button — also hide to tray (instead of staying in taskbar)
        self.bind("<Unmap>", self._on_window_unmap)
        # Persist geometry on every resize/move (debounced 600 ms)
        self.bind("<Configure>", self._on_window_configure)
        # Round-6 UI-03 (Cos review 2026-05-24): power-user keyboard shortcuts.
        # Ctrl+O   → open file/folder picker (same as drop-zone click)
        # Ctrl+Enter → start Phase 1+2 if both source + dest are set
        # Esc      → cancel running Phase worker (if any)
        # F5       → manually trigger update check (matches tray menu)
        self.bind("<Control-o>", self._kbd_open)
        self.bind("<Control-O>", self._kbd_open)
        self.bind("<Control-Return>", self._kbd_run)
        self.bind("<Escape>", self._kbd_cancel)
        self.bind("<F5>", self._kbd_check_update)
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

    # ─── UpdateWorker host contract ──────────────

    @property
    def is_batch_running(self) -> bool:
        """Host contract for UpdateWorker — gates downloads and installs."""
        return self._batch_running

    def log(self, msg: str, level: str = "ok") -> None:
        """Host contract for UpdateWorker — forwards to the in-window log."""
        self._log(msg, level)

    def on_before_install(self) -> None:
        """Host contract for UpdateWorker — flag teardown before installer runs."""
        self._real_quit_requested = True

    # Shim retained so HappyTray's "Check for updates now" callback keeps working
    # without having to know about the worker.
    def _update_check_tick(self) -> None:
        self.update_worker.manual_check()

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

    def _on_window_unmap(self, event):
        """Convert a minimize (—) into a hide-to-tray. <Unmap> also fires for
        withdraw() and for child widgets — filter to the root in iconic state.
        """
        if event.widget is not self:
            return
        if self._destroyed or self._real_quit_requested:
            return  # destroy() is in flight — don't schedule any more callbacks
        if self._tray is None or getattr(self._tray, "icon", None) is None:
            return  # no tray available → leave the default minimize behavior
        try:
            state = self.wm_state()
        except Exception:
            return
        if state == "iconic":
            # Defer the withdraw so Tk finishes the iconify transition first.
            # Track the id so destroy() can cancel (round-6 BUG-M8).
            if self._unmap_after_id is not None:
                try:
                    self.after_cancel(self._unmap_after_id)
                except Exception:
                    pass
            self._unmap_after_id = self.after(50, self._safe_withdraw)

    def _safe_withdraw(self):
        """Withdraw guarded against destruction — avoids 'invalid command'."""
        if self._destroyed or self._real_quit_requested:
            return
        try:
            self.withdraw()
        except Exception:
            pass

    def _real_quit(self):
        """Final exit path — call from tray Quit menu.

        Tray callbacks arrive on pystray's thread. We MUST NOT touch Tk widgets
        or call tray.stop() here directly — both can race with the Tk thread.
        Set the flag, signal in-flight workers to bail, and let destroy() (run
        on the Tk thread via after(0, ...)) own the actual teardown including
        tray.stop().
        """
        self._real_quit_requested = True
        try:
            self.cancel_event.set()
        except Exception:
            pass
        try:
            self.after(0, self.destroy)
        except Exception:
            # If after() fails (Tk already gone), fall through — process will
            # exit when daemon threads die. Don't call destroy() directly from
            # this off-Tk thread.
            pass

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
        # Mark destroyed so any late <Unmap> / debounced after() callbacks bail
        self._destroyed = True
        # Round-6 BUG-M8 (Cos review 2026-05-24): explicitly cancel the
        # deferred-withdraw after-id. Already guarded by _destroyed check
        # in _safe_withdraw, but cancelling avoids a wasted Tk dispatch.
        for _attr in ("_unmap_after_id", "_geo_save_after_id", "_poll_after_id"):
            _aid = getattr(self, _attr, None)
            if _aid is not None:
                try:
                    self.after_cancel(_aid)
                except Exception:
                    pass
                setattr(self, _attr, None)
        # Cancel any in-flight Phase worker so it stops burning quota / IO
        try:
            self.cancel_event.set()
        except Exception:
            pass
        # Flush in-memory catalog mutations before shutdown (round-5 BUG-2).
        # _refresh_summary calls catalog.add() during review without saving;
        # Phase 4 saves at the end. If the user closes the app between Phase 2
        # and Phase 4 (X button, tray Quit, auto-update installer kill), the
        # learned names never reach disk. Best-effort save here closes the gap.
        #
        # Round-6 BUG-H1 (Cos review 2026-05-24): wrap in a worker thread
        # with a 2s join timeout. If the disk is hanging (network drive,
        # antivirus lock, USB unplugged), the user's X-click should not be
        # held hostage waiting for save() to return. Data persists at next
        # Phase 4 if save here is dropped.
        try:
            if getattr(self, "catalog", None):
                _save_t = threading.Thread(
                    target=self.catalog.save, daemon=True, name="catalog-save-on-exit",
                )
                _save_t.start()
                _save_t.join(timeout=2.0)
        except Exception:
            pass
        # Final geometry save — but ONLY if window is in a real state.
        # Skipping iconic/withdrawn avoids persisting phantom geometry that
        # Tk reports after withdraw() (would open at -32000,-32000 next launch).
        try:
            st = self.wm_state()
        except Exception:
            st = "normal"
        if st not in ("iconic", "withdrawn"):
            try:
                self._save_window_state()
            except Exception:
                pass
        # Stop the auto-update worker (cancels its periodic after-callback)
        try:
            if getattr(self, "update_worker", None):
                self.update_worker.cancel()
        except Exception:
            pass
        # Stop tray icon (idempotent)
        try:
            if getattr(self, "_tray", None):
                self._tray.stop()
        except Exception:
            pass
        # Cancel pending after() callbacks to avoid "invalid command" warnings
        try:
            for attr in ("_poll_after_id", "_geo_save_after_id"):
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

    def _on_window_configure(self, event):
        """Debounced save on resize/move. <Configure> fires dozens of times per
        drag — coalesce to one save 600 ms after the last event.
        """
        if event.widget is not self:
            return  # bubbled from a child widget
        try:
            if self._geo_save_after_id is not None:
                self.after_cancel(self._geo_save_after_id)
        except Exception:
            pass
        self._geo_save_after_id = self.after(600, self._debounced_save_geometry)

    def _debounced_save_geometry(self):
        self._geo_save_after_id = None
        # Don't persist while iconic / withdrawn — those geometries aren't real
        try:
            st = self.wm_state()
            if st in ("iconic", "withdrawn"):
                return
        except Exception:
            return
        self._save_window_state()

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

    # ─── Round-6 UI-03 (Cos review 2026-05-24): keyboard shortcuts ───
    # Each handler is a no-op when the action is invalid (no source, batch
    # running, focus inside text entry, etc.) — Tk binds at root level fire
    # for every keypress and we don't want to surprise the user.

    def _kbd_open(self, event):
        # Don't hijack Ctrl+O inside text-entry widgets (Settings dialog etc.)
        if event and event.widget is not self:
            w = str(event.widget.winfo_class()) if hasattr(event.widget, "winfo_class") else ""
            if w in ("Entry", "CTkEntry", "Text", "CTkTextbox"):
                return
        self._on_drop_click(None)

    def _kbd_run(self, event):
        if event and event.widget is not self:
            w = str(event.widget.winfo_class()) if hasattr(event.widget, "winfo_class") else ""
            if w in ("Entry", "CTkEntry", "Text", "CTkTextbox"):
                return
        if not self.source_paths or not self.dest_root:
            return  # silent — Step 1+2 status already shows what's missing
        if getattr(self, "worker", None) and self.worker.is_alive():
            return  # batch in progress
        self._start_phase12()

    def _kbd_cancel(self, _event):
        # Esc anywhere — cancel a running phase. If no phase running, no-op.
        if getattr(self, "worker", None) and self.worker.is_alive():
            try:
                self._cancel()
            except Exception:
                pass

    def _kbd_check_update(self, _event):
        try:
            if getattr(self, "update_worker", None):
                self.update_worker.manual_check()
                self._log("Update check (F5) requested", "ok")
        except Exception:
            pass

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
            if plan.oversized_count:
                self.after(0, lambda n=plan.oversized_count: self._log(
                    f"  ⚠ {n} image(s) exceeded target_kb_max even at lowest quality — kept anyway, spot-check size",
                    "warn",
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
            self.update_worker.resume_deferred()
        except Exception:
            pass



def main() -> int:
    if not ensure_single_instance():
        return 0
    # Sweep cached installer .exe files from previous runs.
    # Failed-install leftovers used to accumulate at ~/.happy-photo-organizer/updates/
    # because launch_installer_and_exit only fires on the happy path.
    try:
        from core import updater
        updater.cleanup_old_installers()
    except Exception:
        pass
    # Round-6 BUG-L10 (Cos review 2026-05-24): sweep stale auth.corrupt-*.json
    # quarantines + any .tmp orphans left by atomic_write_json crashes
    # (closes round-5 R5-RISK-2 deferred item).
    try:
        auth.cleanup_stale_quarantines(max_age_days=30)
    except Exception:
        pass
    app = MainWindow()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
