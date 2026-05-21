"""
theme.py — Color palette + step status colors.

6-digit hex only — CustomTkinter rejects 8-digit (alpha) colors. Use a darker
solid color instead of transparency.
"""
from __future__ import annotations

# ─── Base palette ───
COLOR_PRIMARY = "#FB923C"    # orange
COLOR_ACCENT = "#EC4899"     # pink
COLOR_BG = "#0F172A"
COLOR_BG_CARD = "#1E293B"
COLOR_BG_INPUT = "#334155"   # lighter than card — secondary buttons
COLOR_TEXT = "#F1F5F9"
COLOR_MUTED = "#94A3B8"
COLOR_OK = "#10B981"
COLOR_WARN = "#F59E0B"
COLOR_DANGER = "#EF4444"

# ─── Step status colors ───
STEP_PENDING = "#475569"     # grey
STEP_READY = COLOR_PRIMARY   # orange
STEP_ACTIVE = COLOR_ACCENT   # pink
STEP_DONE = COLOR_OK         # green
