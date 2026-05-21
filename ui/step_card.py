"""
step_card.py — Numbered step card with circle indicator + title + body slot.

Drop into a parent frame, build content into `card.body`, call
`card.set_status("ready"|"active"|"done")` as the workflow progresses.
"""
from __future__ import annotations

from tkinter import Canvas

import customtkinter as ctk

from ui.theme import (
    COLOR_BG_CARD,
    COLOR_TEXT,
    STEP_ACTIVE,
    STEP_DONE,
    STEP_PENDING,
    STEP_READY,
)


class StepCard(ctk.CTkFrame):
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

        # Header row
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 2))

        # Status circle — use raw tk.Canvas; CTkFrame corner_radius warps at small sizes
        SIZE = 30
        self.indicator = Canvas(
            header, width=SIZE, height=SIZE,
            bg=COLOR_BG_CARD, highlightthickness=0, bd=0,
        )
        self.indicator.pack(side="left", padx=(0, 8))
        self._indicator_size = SIZE
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
