"""
pairing.py — the QR a phone scans to pair with this PC.

Nick's description of the flow is the whole specification: *turn the PC on,
open HPO, scan a code to confirm the pairing from the app, over Wi-Fi — send,
and carry straight on in HPO.* This dialog is the "scan a code" step, and it is
the only part of the LAN feature a person has to look at.

What is on screen is deliberately what someone in an engine room needs: the
code, the address it encodes, the vessel this PC files for, and whether the
receiver is actually listening. Nothing about tokens or ports unless it has
gone wrong.

The QR is built from the port the receiver **actually bound**, never from the
default — if 8765 was taken and the OS handed us another one, a QR carrying
8765 pairs the phone to nothing and the failure looks like a network fault.
"""
from __future__ import annotations

import json
from pathlib import Path

import customtkinter as ctk

from core import auth
from core import jobshot_receive as receive
from ui.paste_helper import enable_paste
from ui.theme import (
    COLOR_BG,
    COLOR_BG_CARD,
    COLOR_BG_INPUT,
    COLOR_MUTED,
    COLOR_OK,
    COLOR_PRIMARY,
    COLOR_TEXT,
    COLOR_WARN,
)


class PairingDialog(ctk.CTkToplevel):
    """Shows the pairing QR and what the receiver is doing."""

    def __init__(self, master, *, receiver, on_ship_change=None):
        # fg_color is REQUIRED — without it CTkToplevel uses the theme's
        super().__init__(master, fg_color=COLOR_BG)
        self.receiver = receiver
        self._on_ship_change = on_ship_change
        self._qr_image = None          # keep a reference or Tk drops it

        self.title("Pair your phone")
        self.geometry("460x620")
        self.minsize(420, 560)
        self.transient(master)

        try:
            self.after(200, lambda: self.iconbitmap(
                str(Path(__file__).resolve().parents[2] / "assets" / "icon.ico")))
        except Exception:
            pass

        self._build()
        self.after(120, self._refresh)

    # ─── layout ───

    def _build(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=16, pady=14)

        ctk.CTkLabel(
            wrap, text="Scan this with JobShot on your phone",
            font=("Segoe UI", 15, "bold"), text_color=COLOR_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            wrap, text="One scan is enough — the phone remembers this PC.",
            font=("Segoe UI", 11), text_color=COLOR_MUTED,
        ).pack(anchor="w", pady=(0, 10))

        # vessel — it is part of the code, because it is what stops a job from
        # one ship being filed into another ship's folders
        ship_row = ctk.CTkFrame(wrap, fg_color="transparent")
        ship_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(ship_row, text="This PC files for", font=("Segoe UI", 11),
                     text_color=COLOR_MUTED).pack(side="left", padx=(0, 8))
        self.ship_entry = ctk.CTkEntry(
            ship_row, height=30, font=("Segoe UI", 12),
            fg_color=COLOR_BG_INPUT, border_color=COLOR_BG_INPUT,
            text_color=COLOR_TEXT, placeholder_text="ENA CRYSTAL")
        self.ship_entry.pack(side="left", fill="x", expand=True)
        self.ship_entry.insert(0, current_ship())
        enable_paste(self.ship_entry)
        self.ship_entry.bind("<FocusOut>", lambda _e: self._save_ship())
        self.ship_entry.bind("<Return>", lambda _e: self._save_ship())

        self.qr_holder = ctk.CTkFrame(wrap, fg_color=COLOR_BG_CARD,
                                      corner_radius=10, height=300)
        self.qr_holder.pack(fill="x", pady=(0, 10))
        self.qr_holder.pack_propagate(False)
        self.qr_label = ctk.CTkLabel(self.qr_holder, text="", text_color=COLOR_TEXT)
        self.qr_label.pack(expand=True)

        self.address_label = ctk.CTkLabel(
            wrap, text="", font=("Consolas", 12), text_color=COLOR_TEXT)
        self.address_label.pack(anchor="w")

        self.status_label = ctk.CTkLabel(
            wrap, text="", font=("Segoe UI", 11), text_color=COLOR_MUTED,
            wraplength=410, justify="left")
        self.status_label.pack(anchor="w", pady=(6, 0))

        hint = ("Keep HPO open while you send. Photos land in the destination "
                "folder on the right, the same as a job you drop in by hand.\n"
                "The first time, Windows may ask whether to allow HPO on the "
                "network — say yes, or the phone cannot reach this PC.")
        ctk.CTkLabel(wrap, text=hint, font=("Segoe UI", 10),
                     text_color=COLOR_MUTED, wraplength=410,
                     justify="left").pack(anchor="w", pady=(10, 0))

        buttons = ctk.CTkFrame(wrap, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", pady=(12, 0))
        ctk.CTkButton(
            buttons, text="Copy address", height=32, width=120,
            font=("Segoe UI", 11), fg_color=COLOR_BG_INPUT,
            hover_color="#475569", text_color=COLOR_TEXT,
            command=self._copy_address,
        ).pack(side="left")
        ctk.CTkButton(
            buttons, text="Close", height=32, width=90,
            font=("Segoe UI", 11, "bold"), fg_color=COLOR_PRIMARY,
            text_color="#FFFFFF", command=self.destroy,
        ).pack(side="right")

    # ─── state ───

    def _save_ship(self):
        ship = self.ship_entry.get().strip()
        if ship == current_ship():
            return
        auth.update_config({"jobshot_ship": ship})
        if self._on_ship_change:
            try:
                self._on_ship_change(ship)
            except Exception:
                pass
        self._refresh()          # the ship is inside the QR, so it must redraw

    def _refresh(self):
        started, error = self.receiver.ensure_started()
        if not started:
            self.qr_label.configure(
                text="The receiver could not start,\nso there is nothing to "
                     "pair with yet.", font=("Segoe UI", 12))
            self.address_label.configure(text="")
            self.status_label.configure(text=error, text_color=COLOR_WARN)
            return

        payload = receive.qr_payload(current_ship(), port=self.receiver.port,
                                     host=self.receiver.host)
        self._draw_qr(json.dumps(payload, separators=(",", ":")))
        self.address_label.configure(
            text=f"http://{payload['host']}:{payload['port']}")
        self.status_label.configure(
            text=f"Listening for {payload['ship'] or 'any vessel'}. "
                 f"Leave HPO open while the phone sends.",
            text_color=COLOR_OK)

    def _draw_qr(self, text: str):
        try:
            import qrcode
            from PIL import Image  # noqa: F401  (CTkImage needs PIL present)

            img = qrcode.make(text).convert("RGB").resize((280, 280))
            self._qr_image = ctk.CTkImage(light_image=img, dark_image=img,
                                          size=(280, 280))
            # CTk 5.2.2: a button/label created with image=None never renders
            # one later (v1.043) — this label is configured while it is empty
            # of text, which is the supported path for labels.
            self.qr_label.configure(image=self._qr_image, text="")
        except Exception as e:
            self.qr_label.configure(
                image=None,
                text=f"Could not draw the code:\n{str(e)[:120]}\n\n"
                     f"Type the address into JobShot instead.",
                font=("Segoe UI", 11))

    def _copy_address(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.address_label.cget("text"))
        except Exception:
            pass


def current_ship() -> str:
    """The vessel this PC files for. Remembered, because it is asked once and
    then true for the life of the machine."""
    return str(auth.load_config().get("jobshot_ship", "") or "")
