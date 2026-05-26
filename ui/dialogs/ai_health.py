"""
ai_health.py — AI Health & Quota dialog.

Tier + Usage + History + Pre-flight + Recent calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from tkinter import messagebox

import customtkinter as ctk

from core import auth
from core.rate_limiter import (
    DEFAULT_TIER,
    TIER_PRESETS,
    get_rate_limiter,
    update_tier_from_config,
)
from core.usage_log import get_usage_log
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


class AIHealthDialog(ctk.CTkToplevel):
    """Standalone window — Tier + Usage + History + Pre-flight + Recent calls"""

    def __init__(self, master, on_tier_change=None):
        # fg_color is REQUIRED — without it CTkToplevel uses the theme's
        # light-mode background even when set_appearance_mode("dark") is active.
        super().__init__(master, fg_color=COLOR_BG)
        self.title("AI Health & Quota")
        self.geometry("760x780")
        self.transient(master)
        self.on_tier_change = on_tier_change
        # v1.037: dark title bar + app icon (Nick screenshot — white bar +
        # missing icon on v1.036 dialogs).
        try:
            from ui.win_chrome import apply_chrome
            icon_path = getattr(master, "_icon_path", None)
            if icon_path:
                apply_chrome(self, icon_path)
        except Exception:
            pass

        self.usage_log = get_usage_log()
        self.rate_limiter = get_rate_limiter()
        self._build_ui()
        self.refresh()

    def destroy(self):
        """Round-7 BUG-N6/N11 (Cos retest 2026-05-24): cancel the
        win_chrome after-callbacks before Tk tears the window down.
        """
        try:
            from ui.win_chrome import cancel_chrome_callbacks
            cancel_chrome_callbacks(self)
        except Exception:
            pass
        super().destroy()

    def _build_ui(self):
        container = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # ─── 1. Tier info ───
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

        # ─── 2. Today's usage bars ───
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

        # ─── 3. Pre-flight calculator ───
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

        # ─── 4. 7-day history ───
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

        # ─── 5. Recent calls ───
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

        # ─── 6. Tier selector ───
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

        # ─── 7. Bottom action row ───
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

    # ─── refresh ───

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
        # Throttle string was previously hard-coded "4.0s/call" — wrong for any
        # tier other than RPM 15. Use the actual computed min_interval_sec.
        throttle_str = (
            f"{tier.min_interval_sec:.1f}s/call"
            if tier.min_interval_sec > 0 else "disabled (paid)"
        )
        self.tier_detail.configure(
            text=(
                f"Model alias: {tier.name}\n"
                f"Limits: RPM {cap_rpm}  •  RPD {cap_rpd}  •  TPM {tier.tpm:,}\n"
                f"Throttle: {throttle_str}\n"
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
        today = (
            datetime.strptime(snap.get("today_pt"), "%Y-%m-%d").date()
            if snap.get("today_pt") else datetime.now().date()
        )
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

    # ─── tier change ───

    def _on_tier_radio(self):
        # preview-only — actual apply is on the button
        pass

    def _apply_tier(self):
        tier_name = self.tier_var.get()
        updates: dict = {"tier": tier_name}
        if tier_name == "custom":
            try:
                rpm = int(self.custom_rpm.get().strip())
                rpd = int(self.custom_rpd.get().strip())
                if rpm < 0 or rpd < 0:
                    raise ValueError("non-negative only")
            except Exception:
                messagebox.showwarning("Invalid input", "RPM and RPD must be non-negative integers")
                return
            updates["custom_rpm"] = rpm
            updates["custom_rpd"] = rpd
        # Use update_config (atomic + serialized) so a concurrent window-state
        # debounce save doesn't lose the tier change in a read-modify-write race.
        if not auth.update_config(updates):
            messagebox.showwarning("Save failed", "Could not save tier (atomic write failed)")
            return
        # Reload the full config to pass to the rate limiter — update_config
        # has the latest tier + any custom_* values it just wrote.
        update_tier_from_config(auth.load_config())
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
