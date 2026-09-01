"""
version.py — Single source of truth for APP_VERSION.

Reads the plain-text `VERSION` file (frozen-bundle aware via sys._MEIPASS).
Falls back to "0.0.0" if the file is missing — never raises.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def read_version() -> str:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "VERSION")
    candidates.append(_PROJECT_ROOT / "VERSION")
    for p in candidates:
        try:
            if p.exists():
                # utf-8-sig, not utf-8: a BOM is NOT stripped by str.strip()
                # (U+FEFF is not whitespace in Python), so a VERSION file saved
                # by a Windows tool would yield "﻿1.044" — and
                # updater._parse_version reads that as (0, 44) instead of
                # (1, 44), which makes every release look newer than the
                # installed build and re-offers an update forever.
                v = p.read_text(encoding="utf-8-sig").strip()
                if v:
                    return v
        except Exception:
            pass
    return "0.0.0"


APP_VERSION = read_version()
APP_TITLE = "Happy Photo Organizer"
