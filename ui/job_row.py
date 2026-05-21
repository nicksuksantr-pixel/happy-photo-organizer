"""
job_row.py — One row in the Review & Edit pane.

Thumbnail + date label + name combobox (with TH→EN translate) + size info +
AI confidence indicator. Calls `on_change` whenever the user accepts a new name.
"""
from __future__ import annotations

import os

import customtkinter as ctk
from PIL import Image

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


class JobRow(ctk.CTkFrame):
    THUMB_SIZE = 64

    def __init__(self, master, assignment: JobAssignment, catalog: JobCatalog, on_change=None):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8)
        self.assignment = assignment
        self.catalog = catalog
        self.on_change = on_change
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
            self._thumb_ref = thumb

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

        if not assignment.job_name.strip():
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

        # ─── Col 3: Confidence ───
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

    # ─── Helpers ───

    def _make_thumbnail(self):
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
        folder = self.assignment.temp_folder
        if folder and folder.exists():
            try:
                os.startfile(folder)
            except Exception:
                pass
        else:
            pool = self.assignment.resized_paths or self.assignment.images
            if pool:
                try:
                    os.startfile(pool[0].parent)
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
        from core.auth import create_client, get_model
        from google.genai import types

        text = self.job_var.get().strip()
        if not text:
            return

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
