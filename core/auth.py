"""
auth.py — Gemini API key + model management
เก็บที่ ~/.happy-photo-organizer/auth.json (เฉพาะ user ปัจจุบัน)
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import threading
import time
from pathlib import Path

from google import genai

CONFIG_DIR = Path.home() / ".happy-photo-organizer"
CONFIG_FILE = CONFIG_DIR / "auth.json"

DEFAULT_MODEL = "gemini-3.1-flash-lite"

# Serialize concurrent writes from multiple threads (window-state debounce vs
# settings save vs tier change). The OS handles tmp→replace atomicity, but two
# concurrent reads-then-writes can still lose data.
_IO_LOCK = threading.Lock()


def atomic_write_json(path: Path, data: dict, lock_perms: bool = True) -> bool:
    """Write `data` to `path` atomically. Returns success.

    Pattern from ENA v2.6.7: write to `<path>.tmp`, fsync, then `os.replace`.
    No half-written file can be observed after a crash. Best-effort on perms.

    Round-6 BUG-L2 (Cos review 2026-05-24): wrap in a 3-attempt retry with
    short backoff. AV scanners holding write locks for a tenth of a second
    are the usual cause of silent atomic_write_json failures; one retry
    almost always recovers and turns a "lost setting" into a no-op.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    for attempt in range(3):
        if _atomic_write_json_once(path, data, lock_perms):
            return True
        if attempt < 2:
            time.sleep(0.15 * (attempt + 1))
    return False


def _atomic_write_json_once(path: Path, data: dict, lock_perms: bool) -> bool:
    tmp_path: Path | None = None
    try:
        # NamedTemporaryFile keeps tmp in the same dir so os.replace is atomic
        # (cross-volume replace would degrade to copy + delete).
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8",
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp",
            delete=False,
        ) as f:
            tmp_path = Path(f.name)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(str(tmp_path), str(path))
        tmp_path = None  # ownership transferred
        if lock_perms:
            try:
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass
        return True
    except Exception:
        return False
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass


def cleanup_stale_quarantines(max_age_days: int = 30) -> int:
    """Round-6 BUG-L10 (Cos review 2026-05-24): sweep auth.corrupt-<ts>.json
    files older than `max_age_days`. Quarantines accumulate forever
    otherwise — most are useful for ~1 debugging session and then forgotten.

    Also sweeps any orphan `<file>.<rand>.tmp` in the config dir left by a
    crash mid-atomic-write (round-5 R5-RISK-2).

    Returns count of files removed. Silent on individual failures.
    """
    removed = 0
    try:
        if not CONFIG_DIR.exists():
            return 0
        cutoff = time.time() - (max_age_days * 86400)
        now_ts = time.time()
        # Round-7 BUG-N10 (Cos retest 2026-05-24): a previously aggressive
        # sweep deleted every .tmp it saw, including ones that another
        # thread had just opened mid-atomic_write_json. Require the tmp
        # to be at least 5 seconds old before considering it orphaned —
        # the atomic-write window is sub-millisecond on local disk and
        # sub-second even under AV lock, so 5 s is a wide safety margin
        # that still catches genuine crash leftovers.
        tmp_min_age_s = 5.0
        for entry in CONFIG_DIR.iterdir():
            try:
                name = entry.name
                is_quarantine = ".corrupt-" in name and name.endswith(".json")
                # tmp orphan: NamedTemporaryFile uses .<rand>.tmp suffix
                is_tmp_orphan = entry.suffix == ".tmp" and entry.is_file()
                if not (is_quarantine or is_tmp_orphan):
                    continue
                if is_tmp_orphan:
                    # Skip in-flight tmp files — the writer is still
                    # using the handle. Sweep on the next launch when
                    # the writer is definitely gone.
                    if (now_ts - entry.stat().st_mtime) < tmp_min_age_s:
                        continue
                    entry.unlink(missing_ok=True)
                    removed += 1
                elif entry.stat().st_mtime < cutoff:
                    entry.unlink(missing_ok=True)
                    removed += 1
            except Exception:
                pass
    except Exception:
        pass
    return removed


def save_config(api_key: str, model: str = DEFAULT_MODEL, ui_scale: float = 1.0) -> tuple[bool, str]:
    """Save API key + model + ui scale preference"""
    with _IO_LOCK:
        try:
            existing = _load_config_unlocked()
            existing.update({
                "api_key": api_key.strip(),
                "model": model.strip() or DEFAULT_MODEL,
                "ui_scale": float(ui_scale),
            })
            ok = atomic_write_json(CONFIG_FILE, existing)
            if not ok:
                return False, "บันทึกไม่ได้ (atomic write failed)"
            return True, "บันทึก config แล้ว"
        except Exception as e:
            return False, f"บันทึกไม่ได้: {str(e)[:200]}"


def _load_config_unlocked() -> dict:
    """Internal — caller must hold _IO_LOCK. Quarantines corrupt files."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Quarantine the corrupt file so the next save doesn't overwrite the
        # only forensic evidence. The next call returns {} → user starts fresh.
        try:
            ts = time.strftime("%Y%m%d-%H%M%S")
            corrupt = CONFIG_FILE.with_suffix(f".corrupt-{ts}.json")
            shutil.copy2(str(CONFIG_FILE), str(corrupt))
        except Exception:
            pass
        return {}
    except Exception:
        return {}


def load_config() -> dict:
    """Load config — คืน dict ว่างถ้าไม่มีไฟล์
    On JSONDecodeError, the corrupt file is quarantined as auth.corrupt-<ts>.json
    so the next save doesn't overwrite the evidence.
    """
    with _IO_LOCK:
        return _load_config_unlocked()


def update_config(updates: dict) -> bool:
    """Merge `updates` into current config and persist. Returns success."""
    with _IO_LOCK:
        try:
            existing = _load_config_unlocked()
            existing.update(updates)
            return atomic_write_json(CONFIG_FILE, existing)
        except Exception:
            return False


def get_api_key() -> str | None:
    return load_config().get("api_key", "").strip() or None


def get_model() -> str:
    return load_config().get("model", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def create_client(api_key: str | None = None) -> tuple[object | None, str | None]:
    """สร้าง Gemini client — ใช้ key จาก param หรือจาก config"""
    key = (api_key or get_api_key() or "").strip()
    if not key:
        return None, "ยังไม่ได้ตั้ง API key"
    try:
        return genai.Client(api_key=key), None
    except Exception as e:
        return None, f"สร้าง client ไม่ได้: {str(e)[:200]}"


def test_connection(client) -> tuple[bool, str]:
    """ลอง list models เพื่อทดสอบว่า key ใช้ได้"""
    try:
        models = list(client.models.list())
        if not models:
            return False, "เชื่อมต่อได้ แต่ไม่เจอ model"
        return True, f"เชื่อมต่อสำเร็จ — เจอ {len(models)} models"
    except Exception as e:
        return False, f"เชื่อมต่อไม่ได้: {str(e)[:200]}"


def _model_version_key(name: str) -> tuple[int, int, int, str]:
    """
    Extract version จากชื่อ model เพื่อใช้เรียงลำดับ
    Return (major, minor, tier_rank, name) — ใหม่ก่อน, lite > flash > pro ในเวอร์ชันเดียวกัน
    tier_rank: pro=0, flash=1, flash-lite=2 (ใช้ negate ตอน sort)
    """
    import re
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
    if m:
        major = int(m.group(1))
        minor = int(m.group(2) or 0)
    else:
        major, minor = 0, 0

    # tier: pro ใหญ่กว่า flash, flash ใหญ่กว่า lite
    n_lower = name.lower()
    if "flash-lite" in n_lower or "flash_lite" in n_lower:
        tier = 1
    elif "flash" in n_lower:
        tier = 2
    elif "pro" in n_lower:
        tier = 3
    else:
        tier = 0
    return (major, minor, tier, name)


def list_vision_models(client) -> list[str]:
    """List Gemini models ที่ใช้ดูรูปได้ (vision / image understanding)"""
    # Filter ที่ตัดออก — ไม่ใช่ vision model
    EXCLUDE_KEYWORDS = (
        "embedding", "tts", "aqa",
        "robotics", "computer-use",
        "-image", "image-preview",  # image GENERATION models ตัด
        "customtools",                # tool-only variant
    )

    try:
        all_models = list(client.models.list())
        out = []
        seen = set()
        for m in all_models:
            name = getattr(m, "name", "").replace("models/", "")
            if not name or name in seen:
                continue
            if not name.startswith("gemini-"):
                continue
            n_lower = name.lower()
            if any(kw in n_lower for kw in EXCLUDE_KEYWORDS):
                continue
            actions = getattr(m, "supported_actions", None) or []
            # บาง model ไม่ list actions — ก็ให้ผ่าน
            if actions and "generateContent" not in actions:
                continue
            seen.add(name)
            out.append(name)

        # Sort: ใหม่ก่อน → (major desc, minor desc, tier desc, name)
        out.sort(key=lambda n: _model_version_key(n), reverse=True)
        return out
    except Exception:
        # fallback list — ครอบคลุม Gemini 3.x, 2.5, 2.0
        return [
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-lite",
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-pro-latest",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
        ]
