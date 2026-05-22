"""
catalog.py — manage job_catalog.json
"""
from __future__ import annotations

import calendar
import json
import re
import threading
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "job_catalog.json"


def _normalize(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"no\.\s*(\d)", r"no.\1", s)
    s = re.sub(r"no\s+(\d)", r"no.\1", s)
    return s.rstrip(".")


def _extract_keywords(name: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z]+", name.lower())
    stop = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "at"}
    return [t for t in tokens if t not in stop and len(t) > 1]


class JobCatalog:
    """โหลด/อัพเดท job catalog — thread-safe.

    Reads (`names`, `find`, `find_fuzzy`) and writes (`add`, `record_usage`,
    `save`, `load`) are serialized through a single RLock. Phase 4 worker
    calls `record_usage` from a background thread while the Tk thread reads
    via `_refresh_summary`; without the lock, mutation during iteration of
    `_index` / `data["jobs"]` could raise `RuntimeError: dictionary changed
    size during iteration` (round-3 BUG-3-2).
    """

    def __init__(self, path: Path = DEFAULT_CATALOG_PATH):
        self.path = path
        self.data: dict = {"version": 1, "jobs": []}
        self._index: dict[str, int] = {}  # normalized → index ใน jobs
        # RLock so a write that internally calls find()/add() doesn't deadlock
        self._lock = threading.RLock()
        self.load()

    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self.data = {"version": 1, "jobs": []}
                self._rebuild_index()
                return
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                if "jobs" not in self.data:
                    self.data["jobs"] = []
            except Exception:
                self.data = {"version": 1, "jobs": []}
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        # Caller holds _lock
        self._index = {
            (job.get("normalized") or _normalize(job["name"])): i
            for i, job in enumerate(self.data.get("jobs", []))
        }

    def save(self) -> None:
        """Atomic write via auth.atomic_write_json — crash mid-save no longer
        truncates the catalog (round-3 BUG-3-1). Falls back to direct write
        only if the helper import fails (e.g. core/auth was renamed)."""
        with self._lock:
            self.data["generated_at"] = datetime.now().isoformat(timespec="seconds")
            try:
                from .auth import atomic_write_json
                atomic_write_json(self.path, self.data, lock_perms=False)
            except Exception:
                # Last-resort non-atomic write — better than dropping the data
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.path.write_text(
                        json.dumps(self.data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass

    def names(self) -> list[str]:
        """list ชื่องานทั้งหมด (display name)"""
        with self._lock:
            return [job["name"] for job in self.data.get("jobs", [])]

    def find(self, name: str) -> dict | None:
        """หา entry ตามชื่อ — exact normalized match"""
        with self._lock:
            idx = self._index.get(_normalize(name))
            if idx is None:
                return None
            return self.data["jobs"][idx]

    def find_fuzzy(self, name: str, cutoff: float = 0.85) -> tuple[dict | None, float]:
        """
        Exact match ก่อน — ถ้าไม่เจอ → fuzzy fallback
        Return (entry, similarity)  similarity ใน [0,1]
            - exact match → similarity = 1.0
            - fuzzy match → similarity = 0.85+
            - no match → (None, 0.0)
        cutoff สูง (0.85) เพื่อกัน false positive จากชื่อที่คล้ายแต่คนละงาน
        """
        if not name or not name.strip():
            return None, 0.0
        norm = _normalize(name)
        with self._lock:
            # 1) exact match
            idx = self._index.get(norm)
            if idx is not None:
                return self.data["jobs"][idx], 1.0
            # 2) fuzzy match — ใช้ get_close_matches กับ normalized keys
            keys = list(self._index.keys())
            candidates = get_close_matches(norm, keys, n=1, cutoff=cutoff)
            if not candidates:
                return None, 0.0
            # คำนวณ similarity แบบง่าย — get_close_matches ไม่ return score
            # ใช้ SequenceMatcher
            from difflib import SequenceMatcher
            matched_key = candidates[0]
            sim = SequenceMatcher(None, norm, matched_key).ratio()
            return self.data["jobs"][self._index[matched_key]], sim

    def add(self, name: str) -> tuple[bool, dict]:
        """เพิ่มชื่องานใหม่ — ถ้ามีอยู่แล้วจะคืน existing entry แทน"""
        name = name.strip()
        if not name:
            return False, {"error": "ชื่อว่าง"}
        norm = _normalize(name)
        with self._lock:
            if norm in self._index:
                return False, self.data["jobs"][self._index[norm]]
            entry = {
                "name": name,
                "normalized": norm,
                "occurrences": 0,
                "ships": [],
                "months_seen": [],
                "dates_seen": [],
                "variants": [name],
                "keywords": _extract_keywords(name),
                "user_added": True,
            }
            self.data["jobs"].append(entry)
            self._index[norm] = len(self.data["jobs"]) - 1
            return True, entry

    def record_usage(self, name: str, ship: str | None, date_str: str | None) -> None:
        """อัพเดท entry ตอนใช้งานจริง — เพิ่ม occurrences + tags + months_seen"""
        with self._lock:
            # find/add inside the same lock — RLock allows reentry
            entry = self.find(name)
            if entry is None:
                ok, entry = self.add(name)
                if not ok and "error" in entry:
                    return
            entry["occurrences"] = entry.get("occurrences", 0) + 1
            if ship and ship not in entry.get("ships", []):
                entry.setdefault("ships", []).append(ship)
                entry["ships"].sort()
            if date_str and date_str not in entry.get("dates_seen", []):
                entry.setdefault("dates_seen", []).append(date_str)
                entry["dates_seen"].sort()
            # populate months_seen (format: 'May 26' หรือ 'Conquest/May 26' ถ้ามี ship)
            month_label = self._format_month_label(date_str, ship)
            if month_label and month_label not in entry.get("months_seen", []):
                entry.setdefault("months_seen", []).append(month_label)
                entry["months_seen"].sort()

    @staticmethod
    def _format_month_label(date_str: str | None, ship: str | None) -> str | None:
        """แปลง 'DD-MM-YY' → 'May 26' (ถ้ามี ship ใส่ prefix 'Ship/May 26')"""
        if not date_str:
            return None
        try:
            parts = date_str.split("-")
            if len(parts) != 3:
                return None
            mm = int(parts[1])
            yy = parts[2]
            month_name = calendar.month_abbr[mm]
            label = f"{month_name} {yy}"
            if ship:
                label = f"{ship}/{label}"
            return label
        except Exception:
            return None
