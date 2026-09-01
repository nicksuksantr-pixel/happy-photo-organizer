"""
job_row.py — One row in the Review & Edit pane.

Thumbnail + date label + name combobox (with TH→EN translate) + size info +
AI confidence indicator. Calls `on_change` whenever the user accepts a new name.
"""
from __future__ import annotations

import os
import queue
import threading

import customtkinter as ctk
from PIL import Image, ImageDraw

from core.catalog import JobCatalog
from core.processor import JobAssignment
from ui.paste_helper import enable_paste
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


def _make_tile(size: int, bg: str, text: str = "", fg: str = "#64748B") -> Image.Image:
    """Small flat tile used for the thumbnail's loading / unavailable states."""
    tile = Image.new("RGB", (size, size), bg)
    if text:
        draw = ImageDraw.Draw(tile)
        # default bitmap font — no font file to ship, legible at 64 px
        box = draw.multiline_textbbox((0, 0), text, align="center")
        x = (size - (box[2] - box[0])) // 2
        y = (size - (box[3] - box[1])) // 2
        draw.multiline_text((x, y), text, fill=fg, align="center")
    return tile


class JobRow(ctk.CTkFrame):
    THUMB_SIZE = 64
    THUMB_POLL_MS = 100   # Tk-thread poll for the decoded thumbnail

    # Source pixels for the two non-photo thumbnail states. Each row builds its
    # own CTkImage from these (a shared CTkImage would accumulate per-widget
    # configure callbacks from rows destroyed before their thumbnail lands).
    _TILE_LOADING = _make_tile(THUMB_SIZE, "#16213A")
    _TILE_MISSING = _make_tile(THUMB_SIZE, "#16213A", "no\npreview")

    def __init__(self, master, assignment: JobAssignment, catalog: JobCatalog,
                 on_change=None, on_delete=None):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8)
        self.assignment = assignment
        self.catalog = catalog
        self.on_change = on_change
        self.on_delete = on_delete
        if assignment.is_irrelevant:
            # AI says this is not vessel work — make it unmissable in a list of 46
            self.configure(border_color=COLOR_DANGER, border_width=2)
        self._thumb_ref = None  # keep a reference to defeat GC

        self.grid_columnconfigure(2, weight=1)

        # ─── Col 0: Date + count ───
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=8, sticky="nw")

        date_str = assignment.folder_date.strftime("%d-%m-%y")
        date_color = COLOR_WARN if assignment.date_shifted else COLOR_TEXT
        if assignment.date_was_capped:
            date_color = COLOR_DANGER
        ctk.CTkLabel(
            left, text=date_str,
            font=("Segoe UI", 13, "bold"), text_color=date_color,
        ).pack(anchor="w")
        if assignment.date_shifted and assignment.original_date:
            orig = assignment.original_date.strftime("%d-%m-%y")
            shift_text = f"(was {orig})"
            if assignment.date_was_capped:
                shift_text = f"(overflow — was {orig})"
            ctk.CTkLabel(
                left, text=shift_text,
                font=("Segoe UI", 9, "italic"), text_color=date_color,
            ).pack(anchor="w")
        count = len(assignment.resized_paths) or len(assignment.images)
        ctk.CTkLabel(
            left, text=f"{count} photos",
            font=("Segoe UI", 11), text_color=COLOR_MUTED,
        ).pack(anchor="w")

        # ─── Col 1: Thumbnail (clickable → open folder) ───
        # Round-6 BUG-M7 (Cos review 2026-05-24): defer thumbnail decode
        # to a daemon thread. With 50+ rows of HEIC the original sync path
        # froze the UI for 1-2 s while _render_plan iterated. Show a
        # placeholder immediately + swap in the real image via after(0)
        # when the worker completes.
        #
        # v1.043 BUG-1 — the placeholder MUST be a real image, not `image=None`.
        # CustomTkinter 5.2.2's CTkButton.configure(image=...) only calls
        # _update_image(), which is a no-op while the internal _image_label is
        # None; that label is created solely inside _draw(), and configure()
        # does not request a redraw for the "image" key (unlike "state" /
        # "compound" / "anchor"). So a button born with image=None can never
        # show a thumbnail assigned later — every row stayed an empty box.
        # Starting with a placeholder image creates the label up front.
        self._thumb_ref = self._tile_image(self._TILE_LOADING)
        self.thumb_btn = ctk.CTkButton(
            self,
            image=self._thumb_ref,
            text="",
            width=self.THUMB_SIZE + 8, height=self.THUMB_SIZE + 8,
            fg_color=COLOR_BG, hover_color=COLOR_BG_INPUT,
            text_color=COLOR_MUTED,
            font=("Segoe UI", 9),
            command=self._open_folder,
        )
        self.thumb_btn.grid(row=0, column=1, rowspan=2, padx=4, pady=6)
        self._destroyed = False
        self.bind("<Destroy>", self._on_destroy_marker, add="+")

        # v1.043 BUG-2 — the worker must NOT call self.after() itself.
        # Tkinter's after() is not thread-safe: a call issued from a worker
        # thread while the main thread has not yet entered mainloop (rows are
        # built as a batch, so the first row's decode finishes inside exactly
        # that window) is accepted and silently never fires — that row kept the
        # placeholder forever while later rows worked. Measured: row 1 reached
        # after() with no error and its callback never ran. So the worker only
        # fills a queue, and the Tk thread polls it.
        self._thumb_queue: queue.Queue = queue.Queue(maxsize=1)
        self._thumb_poll_id: str | None = None
        threading.Thread(target=self._load_thumbnail_async, daemon=True).start()
        self._schedule_thumb_poll()

        # ─── Col 2: Combobox + size info ───
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=2, rowspan=2, padx=6, pady=6, sticky="nsew")
        center.grid_columnconfigure(0, weight=1)

        combo_row = ctk.CTkFrame(center, fg_color="transparent")
        combo_row.grid(row=0, column=0, sticky="ew", pady=(2, 4))
        combo_row.grid_columnconfigure(0, weight=1)

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
        self.job_combo.bind("<Return>", self._on_typing_done)
        self.job_combo.bind("<FocusOut>", self._on_typing_done)
        self.job_combo.bind("<KeyRelease>", self._on_key_release)
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

        if assignment.is_irrelevant:
            ctk.CTkLabel(
                center,
                text="⛔ Not vessel work — delete it, or type a name to keep it",
                font=("Segoe UI", 10, "bold"),
                text_color=COLOR_DANGER, anchor="w",
            ).grid(row=1, column=0, sticky="w", pady=(0, 2))
        elif not assignment.job_name.strip():
            ctk.CTkLabel(
                center,
                text="Type a job name or pick from dropdown ▼",
                font=("Segoe UI", 10, "italic"),
                text_color=COLOR_WARN, anchor="w",
            ).grid(row=1, column=0, sticky="w", pady=(0, 2))

        size_info = self._calc_size_info()
        ctk.CTkLabel(
            center, text=size_info,
            font=("Segoe UI", 10),
            text_color=COLOR_MUTED, anchor="w", justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(2, 0))

        if assignment.reasoning:
            ctk.CTkLabel(
                center,
                text=f"AI: {assignment.reasoning[:240]}",
                font=("Segoe UI", 10),
                text_color="#7DD3FC",
                wraplength=700, justify="left", anchor="w",
            ).grid(row=3, column=0, sticky="w", pady=(2, 0))

        # ─── Col 3: Confidence + Delete ───
        conf = assignment.confidence
        if conf >= 0.8:
            conf_color, conf_icon = COLOR_OK, "OK"
        elif conf >= 0.5:
            conf_color, conf_icon = COLOR_WARN, "?"
        else:
            conf_color, conf_icon = COLOR_DANGER, "!"

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=3, rowspan=2, padx=(6, 10), pady=8, sticky="ne")

        if assignment.is_irrelevant:
            ctk.CTkLabel(
                right, text="NOT\nWORK", width=70,
                font=("Segoe UI", 12, "bold"),
                text_color=COLOR_DANGER, justify="center",
            ).pack(anchor="ne")
        else:
            conf_text = f"{conf_icon}\n{int(conf * 100)}%"
            ctk.CTkLabel(
                right, text=conf_text, width=70,
                font=("Segoe UI", 13, "bold"),
                text_color=conf_color, justify="center",
            ).pack(anchor="ne")
            if assignment.is_new_suggestion and assignment.job_name.strip():
                ctk.CTkLabel(
                    right, text="new",
                    font=("Segoe UI", 9, "italic"),
                    text_color=COLOR_ACCENT,
                ).pack(anchor="ne")

        self.delete_btn = ctk.CTkButton(
            right, text="🗑 Delete", width=70, height=26,
            font=("Segoe UI", 10, "bold"),
            fg_color=COLOR_DANGER if assignment.is_irrelevant else COLOR_BG_INPUT,
            hover_color="#B91C1C",
            text_color="#FFFFFF" if assignment.is_irrelevant else COLOR_MUTED,
            command=self._request_delete,
        )
        self.delete_btn.pack(anchor="ne", pady=(6, 0))

    # ─── Helpers ───

    def _on_destroy_marker(self, _event=None):
        # Round-6 BUG-M7: mark row destroyed so the async thumbnail
        # callback doesn't poke a tk widget that's no longer there
        # (re-render of plan during Phase 3 deletes + recreates rows).
        self._destroyed = True
        if getattr(self, "_thumb_poll_id", None) is not None:
            try:
                self.after_cancel(self._thumb_poll_id)
            except Exception:
                pass
            self._thumb_poll_id = None

    def _request_delete(self):
        """Hand the row up to the window, which owns the plan and the files."""
        if self.on_delete:
            self.on_delete(self.assignment, self)

    def _tile_image(self, pil_tile) -> ctk.CTkImage:
        return ctk.CTkImage(
            light_image=pil_tile, dark_image=pil_tile,
            size=(self.THUMB_SIZE, self.THUMB_SIZE),
        )

    def _load_thumbnail_async(self):
        """Worker thread — decode the first image, hand it to the Tk thread.

        Touches nothing but `_thumb_queue`: no Tk call may be made from here
        (see the BUG-2 note in __init__).
        """
        pool = self.assignment.resized_paths or self.assignment.images
        result: tuple[str, object] = ("missing", None)
        if pool:
            try:
                # Open + thumbnail on the worker thread (heavy IO + CPU).
                # CTkImage construction must happen on the Tk thread, so we
                # pass the resized PIL image over and build the CTkImage there.
                with Image.open(pool[0]) as raw:
                    raw.load()
                    pil = raw.copy()
                pil.thumbnail((self.THUMB_SIZE * 2, self.THUMB_SIZE * 2))
                result = ("photo", pil)
            except Exception:
                result = ("missing", None)
        try:
            self._thumb_queue.put_nowait(result)
        except Exception:
            pass

    def _schedule_thumb_poll(self):
        if self._destroyed:
            return
        try:
            self._thumb_poll_id = self.after(self.THUMB_POLL_MS, self._poll_thumbnail)
        except Exception:
            self._thumb_poll_id = None

    def _poll_thumbnail(self):
        """Tk thread — collect the worker's result once it lands."""
        self._thumb_poll_id = None
        if self._destroyed or not self.winfo_exists():
            return
        try:
            kind, payload = self._thumb_queue.get_nowait()
        except queue.Empty:
            self._schedule_thumb_poll()   # not ready yet — look again shortly
            return
        if kind == "photo":
            self._apply_thumbnail(payload)
        else:
            self._show_missing_thumbnail()

    def _apply_thumbnail(self, pil_image):
        if self._destroyed or not self.winfo_exists():
            return
        try:
            img = self._tile_image(pil_image)
            self.thumb_btn.configure(image=img)
            self._thumb_ref = img
        except Exception:
            self._show_missing_thumbnail()

    def _show_missing_thumbnail(self):
        """v1.043 BUG-1: a blank tile is indistinguishable from a bug — that is
        exactly how the broken thumbnails hid for so long. Say 'no preview'
        instead of leaving an empty box behind."""
        if self._destroyed or not self.winfo_exists():
            return
        try:
            img = self._tile_image(self._TILE_MISSING)
            self.thumb_btn.configure(image=img)
            self._thumb_ref = img
        except Exception:
            pass

    def _calc_size_info(self) -> str:
        paths = self.assignment.resized_paths or self.assignment.images
        sizes = []
        for p in paths:
            try:
                sizes.append(p.stat().st_size)
            except Exception:
                pass
        if not sizes:
            return "No size data"
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
        # Round-6 BUG-L3 (Cos review 2026-05-24): surface open failures
        # instead of silently swallowing — user has no other signal that
        # the click did anything when the folder is gone.
        target = None
        folder = self.assignment.temp_folder
        if folder and folder.exists():
            target = folder
        else:
            pool = self.assignment.resized_paths or self.assignment.images
            if pool and pool[0].parent.exists():
                target = pool[0].parent
        if target is None:
            try:
                from tkinter import messagebox
                messagebox.showinfo(
                    "Folder not available",
                    "The source folder has moved or been deleted since Phase 1.",
                )
            except Exception:
                pass
            return
        try:
            os.startfile(str(target))
        except Exception as e:
            try:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Could not open folder",
                    f"{type(e).__name__}: {e}\n\nPath:\n{target}",
                )
            except Exception:
                pass

    def _on_job_change(self, value):
        self.assignment.job_name = value
        self.assignment.is_new_suggestion = (
            self.catalog.find(value) is None and bool(value.strip())
        )
        self._update_border()
        if self.on_change:
            self.on_change()

    def _on_typing_done(self, _event):
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
        current = self.job_var.get()
        self._all_names = [""] + self.catalog.names()
        try:
            self.job_combo.configure(values=self._all_names)
            self.job_var.set(current)
        except Exception:
            pass

    def _on_key_release(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Tab", "Escape"):
            return
        typed = self.job_var.get().strip().lower()
        if not typed:
            filtered = self._all_names
        else:
            filtered = [n for n in self._all_names if n and typed in n.lower()]
            if not filtered:
                filtered = self._all_names
        try:
            self.job_combo.configure(values=filtered)
        except Exception:
            pass

    def _translate_to_english(self):
        """Translate Thai → English via Gemini.

        Round-5 fix (R5-BUG-1): the call used to run synchronously on the Tk
        thread, freezing the UI for 1-3 s per click, bypassing the rate limiter,
        and bypassing usage_log. The free-tier RPM counter and AI Health page
        were both blind to translate calls. Now: dispatched to a daemon thread,
        gated through `rate_limiter.call('translate')` so the throttle + usage
        log capture the call, and marshalled back to Tk via `after(0, ...)`.
        """
        import threading
        from core.auth import create_client, get_model
        from core.rate_limiter import (
            QuotaExceededError,
            _CancelledError,
            get_rate_limiter,
        )
        from google.genai import types

        text = self.job_var.get().strip()
        if not text:
            return

        original_text = self.translate_btn.cget("text")
        self.translate_btn.configure(text="...", state="disabled")

        def restore():
            try:
                self.translate_btn.configure(text=original_text, state="normal")
            except Exception:
                pass

        def apply_translation(translated: str):
            try:
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

        def worker():
            try:
                client, err = create_client()
                if err:
                    self.after(0, restore)
                    return

                prompt = (
                    "แปลข้อความนี้เป็นภาษาอังกฤษสำหรับใช้เป็นชื่องานซ่อมบำรุงเรือ "
                    "(ใช้คำศัพท์ทางเทคนิคที่เหมาะสม เช่น Cleaned/Repaired/Replaced/Inspected). "
                    "ตอบกลับเฉพาะคำแปลภาษาอังกฤษ ไม่ต้องมีคำอธิบาย ไม่ต้องมี quotes:\n\n"
                    f"{text}"
                )
                limiter = get_rate_limiter()
                try:
                    with limiter.call("translate") as ctx:
                        response = client.models.generate_content(
                            model=get_model(),
                            contents=[prompt],
                            config=types.GenerateContentConfig(temperature=0.1),
                        )
                        # Capture token usage so usage_log shows accurate totals
                        try:
                            meta = getattr(response, "usage_metadata", None)
                            ctx.tokens = int(getattr(meta, "total_token_count", 0) or 0)
                        except Exception:
                            pass
                except QuotaExceededError:
                    # Daily quota burned — silently give up; restore button
                    self.after(0, restore)
                    return
                except _CancelledError:
                    self.after(0, restore)
                    return

                translated = (response.text or "").strip().strip('"').strip("'")
                if translated:
                    self.after(0, lambda t=translated: apply_translation(t))
                else:
                    self.after(0, restore)
            except Exception:
                self.after(0, restore)

        threading.Thread(target=worker, daemon=True).start()
