"""
settings.py — Settings dialog (API key, model, UI scale, auto-update toggle).
"""
from __future__ import annotations

import threading
import webbrowser

import customtkinter as ctk

from core import auth
from core.version import APP_TITLE
from ui.paste_helper import enable_paste
from ui.theme import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_BG_INPUT,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_OK,
    COLOR_PRIMARY,
    COLOR_WARN,
)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, on_save=None):
        # fg_color is REQUIRED — without it CTkToplevel uses the theme's
        # light-mode background even when set_appearance_mode("dark") is active.
        super().__init__(master, fg_color=COLOR_BG)
        self.title(f"Settings — {APP_TITLE}")
        # v1.038: dialog was "560x460" but content (header + key + model +
        # refresh + scale + updates + status + button row) totals ~518 px at
        # UI scale 1.0 — pack `side="bottom"` ran out of cavity and CLIPPED
        # the Test/Cancel/Save row. Nick reported "no place to save key" on
        # a fresh install: dialog auto-opened, key entry was visible at top
        # but the Save button was off-screen, so the key never persisted.
        # Fix: enlarge to 600x680 (fits up to UI scale ~1.3x), make resizable,
        # and pack the button row FIRST with side="bottom" so it always
        # claims the bottom strip of the full cavity regardless of how much
        # content above grows.
        self.geometry("600x680")
        self.minsize(540, 560)
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        self.on_save = on_save
        # Round-8 NEW-2 (Cos v1.038 retest 2026-05-25): Escape closes
        # dialog — standard modal behaviour. Bound on root so it fires
        # regardless of which child widget has focus.
        self.bind("<Escape>", lambda _e: self.destroy())
        # Round-8 Risk-B: `_refresh_models_silent` is scheduled via
        # self.after(200, ...) below. Track the id so destroy() can
        # cancel it — otherwise the deferred call runs against a torn-
        # down widget and prints "invalid command". Same class as N6/N11.
        self._refresh_models_after_id: str | None = None
        # v1.037: dark title bar + app icon (Nick screenshot — white bar +
        # missing icon on v1.036 dialogs). win_chrome no-ops on non-Windows
        # and silently degrades if DWM / iconbitmap fails.
        try:
            from ui.win_chrome import apply_chrome
            icon_path = getattr(master, "_icon_path", None)
            if icon_path:
                apply_chrome(self, icon_path)
        except Exception:
            pass

        cfg = auth.load_config()

        # F3 (Tester 2026-06-04): the UI-scale slider applies globally LIVE via
        # _on_scale_change while dragging, but Cancel/Escape/X used to leave
        # that preview applied (only a restart reverted it). Remember the scale
        # we opened with and restore it on close UNLESS the user saved.
        self._original_scale = float(cfg.get("ui_scale", 1.0))
        self._committed = False

        # ─── v1.038: bottom button row packed FIRST + status above it ───
        # Tk pack processes calls in order. side="bottom" claims from the
        # bottom of whatever cavity remains at pack-time. By packing the
        # button row + status first, they get a guaranteed slice; the
        # scrollable middle takes whatever's left. Previously these were
        # packed last and got squeezed/clipped when content above exceeded
        # the dialog height.
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(8, 16), side="bottom")
        ctk.CTkButton(row, text="Test", width=100, height=36,
                      fg_color=COLOR_BG_INPUT, hover_color="#475569",
                      command=self._test).pack(side="left")
        ctk.CTkButton(row, text="Cancel", width=100, height=36,
                      fg_color=COLOR_BG_INPUT, hover_color="#475569",
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(row, text="Save", width=120, height=36,
                      fg_color=COLOR_PRIMARY, hover_color=COLOR_ACCENT,
                      command=self._save).pack(side="right")

        self.status = ctk.CTkLabel(self, text="", text_color=COLOR_MUTED, anchor="w")
        self.status.pack(fill="x", padx=20, pady=(0, 4), side="bottom")

        # ─── Scrollable middle so any future addition can't break layout ───
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=0, pady=(8, 0))

        ctk.CTkLabel(body, text="Gemini API Key", anchor="w",
                     font=("Segoe UI", 13, "bold")).pack(fill="x", padx=20, pady=(12, 4))
        link_row = ctk.CTkFrame(body, fg_color="transparent")
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
        self.key_entry = ctk.CTkEntry(body, show="*", placeholder_text="AIzaSy...")
        self.key_entry.pack(fill="x", padx=20, pady=8)
        self.key_entry.insert(0, cfg.get("api_key", ""))
        enable_paste(self.key_entry)
        # Round-8 NEW-3 (Cos v1.038 retest 2026-05-25): pressing Enter
        # in the key entry triggers Save — standard modal behaviour.
        # Bound here (not on the dialog) so Enter in other inputs
        # (model dropdown filter, etc.) doesn't hijack.
        self.key_entry.bind("<Return>", lambda _e: self._save())

        self.show_key = ctk.CTkCheckBox(body, text="Show key", command=self._toggle_show)
        self.show_key.pack(anchor="w", padx=20)

        ctk.CTkLabel(body, text="Model", anchor="w",
                     font=("Segoe UI", 13, "bold")).pack(fill="x", padx=20, pady=(20, 4))

        default_values = [
            "gemini-3.5-flash-lite",
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
            body, values=default_values, variable=self.model_var,
            fg_color=COLOR_PRIMARY, button_color=COLOR_ACCENT,
        )
        self.model_menu.pack(fill="x", padx=20, pady=8)

        ctk.CTkButton(
            body, text="Refresh models from API", height=32,
            fg_color=COLOR_BG_INPUT, hover_color="#475569",
            command=self._refresh_models,
        ).pack(fill="x", padx=20, pady=(0, 8))

        # UI Scale slider
        scale_label_row = ctk.CTkFrame(body, fg_color="transparent")
        scale_label_row.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(scale_label_row, text="UI Scale",
                     font=("Segoe UI", 13, "bold")).pack(side="left")
        self.scale_value_label = ctk.CTkLabel(
            scale_label_row, text="", font=("Segoe UI", 11), text_color=COLOR_MUTED,
        )
        self.scale_value_label.pack(side="right")

        self.scale_var = ctk.DoubleVar(value=float(cfg.get("ui_scale", 1.0)))
        self.scale_slider = ctk.CTkSlider(
            body, from_=0.7, to=1.3, number_of_steps=12,
            variable=self.scale_var, command=self._on_scale_change,
            progress_color=COLOR_PRIMARY, button_color=COLOR_ACCENT,
        )
        self.scale_slider.pack(fill="x", padx=20, pady=(0, 8))
        self.scale_value_label.configure(text=f"{self.scale_var.get():.2f}x")

        if cfg.get("api_key"):
            # Round-8 Risk-B: track the after-id so destroy() can cancel
            # before the +200 ms fires against a dead widget.
            self._refresh_models_after_id = self.after(
                200, self._refresh_models_silent,
            )

        # Updates section
        ctk.CTkLabel(body, text="Updates", anchor="w",
                     font=("Segoe UI", 13, "bold")).pack(fill="x", padx=20, pady=(16, 4))
        self.auto_update_var = ctk.BooleanVar(value=bool(cfg.get("auto_check_updates", True)))
        self.auto_update_cb = ctk.CTkCheckBox(
            body, text="Check for updates on startup",
            variable=self.auto_update_var,
        )
        self.auto_update_cb.pack(anchor="w", padx=20, pady=(0, 12))

        # Round-8 NEW-1 + NEW-4 (Cos v1.038 retest 2026-05-25):
        # because the button row is packed first (side="bottom"), Tab
        # focus naturally starts there — user sees the Save button as
        # the first focused widget instead of the API-key entry. Pull
        # focus to key_entry after the build is complete so:
        #   • Paste works without an explicit click (NEW-1)
        #   • Tab cycle starts at key_entry → show-key → model → ...
        #     → Save (NEW-4 implicit fix)
        # Deferred one tick so CTkEntry's inner Tk widget is fully
        # realised first.
        try:
            self.after(0, lambda: self.key_entry.focus_set())
        except Exception:
            pass

    def destroy(self):
        """Round-7 BUG-N6/N11 (Cos retest 2026-05-24): cancel the
        win_chrome after-callbacks before Tk tears the window down,
        otherwise the deferred +50/+200 ms tasks fire against a dead
        widget and log "invalid command" warnings.

        Round-8 Risk-B (Cos v1.038 retest 2026-05-25): also cancel the
        deferred `_refresh_models_silent` call. Same race class as
        N6/N11 — fires +200 ms after open, fails silently if dialog
        was dismissed in between (Escape, Cancel, X).
        """
        try:
            from ui.win_chrome import cancel_chrome_callbacks
            cancel_chrome_callbacks(self)
        except Exception:
            pass
        aid = getattr(self, "_refresh_models_after_id", None)
        if aid is not None:
            try:
                self.after_cancel(aid)
            except Exception:
                pass
            self._refresh_models_after_id = None
        # F3 (Tester 2026-06-04): revert the live UI-scale preview if the user
        # didn't save. On a successful save _committed is True and the new
        # scale (already applied live) must stick.
        if not getattr(self, "_committed", False):
            try:
                ctk.set_widget_scaling(self._original_scale)
            except Exception:
                pass
        super().destroy()

    def _toggle_show(self):
        self.key_entry.configure(show="" if self.show_key.get() else "*")

    def _test(self):
        key = self.key_entry.get().strip()
        if not key:
            self.status.configure(text="Enter a key first", text_color=COLOR_WARN)
            return
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
            self.status.configure(text="Enter a key first", text_color=COLOR_WARN)
            return
        self.status.configure(text="Loading models...", text_color=COLOR_MUTED)
        threading.Thread(
            target=self._refresh_models_worker,
            args=(key, False),
            daemon=True,
        ).start()

    def _refresh_models_silent(self):
        key = self.key_entry.get().strip()
        if not key:
            return
        threading.Thread(
            target=self._refresh_models_worker,
            args=(key, True),
            daemon=True,
        ).start()

    def _refresh_models_worker(self, key: str, silent: bool):
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
            self.status.configure(text="Enter a key first", text_color=COLOR_WARN)
            return
        # Round-7 BUG-N8 (Cos retest 2026-05-24): atomic_write_json can
        # block up to 0.45 s under AV lock (3× retry with 0.15s/0.30s
        # backoff per R6-BUG-L2). Running it on the UI thread froze the
        # dialog while Defender scanned auth.json on Nick's machine.
        # Move the write to a daemon thread + marshal status back via
        # after(0,...). The dialog stays interactive; user sees a
        # "Saving..." status until the write completes.
        updates = {
            "api_key": key,
            "model": (self.model_var.get() or auth.DEFAULT_MODEL).strip(),
            "ui_scale": float(self.scale_var.get()),
            "auto_check_updates": bool(self.auto_update_var.get()),
        }
        self.status.configure(text="Saving...", text_color=COLOR_MUTED)
        threading.Thread(
            target=self._save_worker, args=(updates,), daemon=True,
            name="settings-save",
        ).start()

    def _save_worker(self, updates: dict) -> None:
        ok = auth.update_config(updates)

        def done():
            if ok:
                # Mark committed so destroy() keeps the live UI-scale preview
                # (the saved value) instead of reverting it (F3).
                self._committed = True
                if self.on_save:
                    try:
                        self.on_save()
                    except Exception:
                        pass
                try:
                    self.destroy()
                except Exception:
                    pass
            else:
                try:
                    self.status.configure(
                        text="Could not save settings",
                        text_color=COLOR_DANGER,
                    )
                except Exception:
                    pass

        try:
            self.after(0, done)
        except Exception:
            # Window already destroyed — drop silently. Settings already
            # persisted on disk if ok=True.
            pass
