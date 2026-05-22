"""
usage_log.py — จัดการ usage tracking ของ Gemini API
เก็บที่ ~/.happy-photo-organizer/usage_log.json
Reset วันที่ตาม Pacific Time (Google's quota reset timezone)
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Pacific Time — Google's quota resets at PT 00:00
# PST = UTC-8, PDT = UTC-7. Use UTC-8 as conservative (covers DST).
# For accurate, use zoneinfo if available
try:
    from zoneinfo import ZoneInfo
    PT_TZ = ZoneInfo("America/Los_Angeles")
except Exception:
    PT_TZ = timezone(timedelta(hours=-8))

LOG_FILE = Path.home() / ".happy-photo-organizer" / "usage_log.json"
MAX_RECENT = 10        # last N calls
MAX_HISTORY_DAYS = 7   # rolling 7-day history


def _now_pt() -> datetime:
    return datetime.now(PT_TZ)


def _today_pt_str() -> str:
    return _now_pt().strftime("%Y-%m-%d")


def _seconds_until_pt_midnight() -> int:
    now = _now_pt()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds())


class UsageLog:
    """
    Thread-safe usage tracker — เก็บใน JSON file
    - daily counters (today_count, today_tokens) auto-reset at PT 00:00
    - rolling 7-day history
    - last 10 calls (timestamp, type, duration, tokens, ok)
    """

    def __init__(self, path: Path = LOG_FILE):
        self.path = path
        # ใช้ RLock เพราะ snapshot() ภายในเรียก current_rpm() ที่ acquire lock ซ้ำ
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {
            "today_pt": _today_pt_str(),
            "today_count": 0,
            "today_tokens": 0,
            "history_7d": {},     # {"YYYY-MM-DD": count}
            "recent_calls": [],   # list of {"ts", "type", "duration", "tokens", "ok"}
            "rpm_window": [],     # epoch seconds — used for live RPM tracking
        }
        self._load()
        self._roll_over_if_needed()

    # ─── persistence ────────────────────────

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open(encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                self._data.update(raw)
        except Exception:
            pass

    def _save(self) -> None:
        # Atomic write: crash mid-write would otherwise leave a truncated JSON
        # that _load() silently swallows → quota counters reset to 0.
        try:
            from .auth import atomic_write_json
            atomic_write_json(self.path, self._data, lock_perms=False)
        except Exception:
            # Last-resort fallback: direct write so a missing helper doesn't
            # break the app. Not atomic, but better than dropping the data.
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    # ─── day rollover ───────────────────────

    def _roll_over_if_needed(self) -> None:
        """ถ้าวันนี้ PT เปลี่ยน → archive today_count → history_7d → reset"""
        today = _today_pt_str()
        stored_day = self._data.get("today_pt")
        if stored_day == today:
            return
        # archive
        if stored_day and self._data.get("today_count", 0) > 0:
            history = self._data.setdefault("history_7d", {})
            history[stored_day] = int(self._data.get("today_count", 0))
            # prune history > 7 days
            cutoff = (_now_pt() - timedelta(days=MAX_HISTORY_DAYS)).strftime("%Y-%m-%d")
            for k in list(history.keys()):
                if k < cutoff:
                    history.pop(k, None)
        # reset day
        self._data["today_pt"] = today
        self._data["today_count"] = 0
        self._data["today_tokens"] = 0
        self._data["rpm_window"] = []
        self._save()

    # ─── recording ──────────────────────────

    def record_call(
        self,
        call_type: str = "analyze",
        duration_sec: float = 0.0,
        tokens: int = 0,
        ok: bool = True,
    ) -> None:
        """บันทึก 1 call — thread-safe"""
        with self._lock:
            self._roll_over_if_needed()
            now_ts = time.time()
            self._data["today_count"] = int(self._data.get("today_count", 0)) + 1
            self._data["today_tokens"] = int(self._data.get("today_tokens", 0)) + tokens

            # rpm_window: keep only last 60s
            window = [t for t in self._data.get("rpm_window", []) if now_ts - t < 60]
            window.append(now_ts)
            self._data["rpm_window"] = window

            # recent_calls
            recent = self._data.setdefault("recent_calls", [])
            recent.append({
                "ts": datetime.now().strftime("%H:%M:%S"),
                "type": call_type,
                "duration": round(duration_sec, 2),
                "tokens": int(tokens),
                "ok": bool(ok),
            })
            # cap to MAX_RECENT
            if len(recent) > MAX_RECENT:
                self._data["recent_calls"] = recent[-MAX_RECENT:]

            self._save()

    # ─── queries ────────────────────────────

    def today_count(self) -> int:
        with self._lock:
            self._roll_over_if_needed()
            return int(self._data.get("today_count", 0))

    def today_tokens(self) -> int:
        with self._lock:
            self._roll_over_if_needed()
            return int(self._data.get("today_tokens", 0))

    def current_rpm(self) -> int:
        """RPM ใน 60 วินาทีที่ผ่านมา"""
        with self._lock:
            now_ts = time.time()
            window = [t for t in self._data.get("rpm_window", []) if now_ts - t < 60]
            self._data["rpm_window"] = window
            return len(window)

    def history_7d(self) -> dict[str, int]:
        with self._lock:
            self._roll_over_if_needed()
            return dict(self._data.get("history_7d", {}))

    def recent_calls(self) -> list[dict]:
        with self._lock:
            return list(self._data.get("recent_calls", []))

    def seconds_until_reset(self) -> int:
        return _seconds_until_pt_midnight()

    def reset_today(self) -> None:
        """ใช้ตอนผู้ใช้ manual reset (ปุ่มใน AI Health page)"""
        with self._lock:
            self._data["today_count"] = 0
            self._data["today_tokens"] = 0
            self._data["rpm_window"] = []
            self._save()

    def snapshot(self) -> dict[str, Any]:
        """คืน data ทั้งหมดเป็น dict (สำหรับ UI render)"""
        with self._lock:
            self._roll_over_if_needed()
            return {
                "today_pt": self._data.get("today_pt"),
                "today_count": int(self._data.get("today_count", 0)),
                "today_tokens": int(self._data.get("today_tokens", 0)),
                "current_rpm": self.current_rpm(),
                "history_7d": dict(self._data.get("history_7d", {})),
                "recent_calls": list(self._data.get("recent_calls", [])),
                "seconds_until_reset": _seconds_until_pt_midnight(),
            }


# Singleton for app-wide use
_default_log: UsageLog | None = None


def get_usage_log() -> UsageLog:
    global _default_log
    if _default_log is None:
        _default_log = UsageLog()
    return _default_log
