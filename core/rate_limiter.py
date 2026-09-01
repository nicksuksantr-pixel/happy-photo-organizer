"""
rate_limiter.py — Thread-safe throttle + quota enforcement for Gemini calls

Usage:
    limiter = RateLimiter(rpm=15, rpd=500)
    with limiter:               # blocks if rate too high
        result = gemini_call()  # safe call
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .usage_log import UsageLog, get_usage_log


# ─── Tier presets (เปลี่ยนได้จาก Settings) ───
TIER_PRESETS: dict[str, dict] = {
    "free-3.5-flash-lite": {
        "label": "Free — Gemini 3.5 Flash Lite",
        "model": "gemini-3.5-flash-lite",
        "rpm": 15,
        "rpd": 500,
        "tpm": 250_000,
        "throttle": True,
    },
    "free-3.1-flash-lite": {
        "label": "Free — Gemini 3.1 Flash Lite",
        "model": "gemini-3.1-flash-lite",
        "rpm": 15,
        "rpd": 500,
        "tpm": 250_000,
        "throttle": True,
    },
    "free-2.5-flash": {
        "label": "Free — Gemini 2.5 Flash",
        "model": "gemini-2.5-flash",
        "rpm": 10,
        "rpd": 250,
        "tpm": 250_000,
        "throttle": True,
    },
    "free-2.5-flash-lite": {
        "label": "Free — Gemini 2.5 Flash Lite",
        "model": "gemini-2.5-flash-lite",
        "rpm": 15,
        "rpd": 1000,
        "tpm": 250_000,
        "throttle": True,
    },
    "paid": {
        "label": "Paid — no throttle",
        "model": None,           # ใช้ของจาก auth.get_model()
        "rpm": 0,                # 0 = ไม่ throttle
        "rpd": 0,                # 0 = ไม่ cap
        "tpm": 0,
        "throttle": False,
    },
}

DEFAULT_TIER = "free-3.5-flash-lite"


class QuotaExceededError(RuntimeError):
    """Raised เมื่อ daily quota ครบ"""
    pass


class _CancelledError(RuntimeError):
    """Internal — raised when cancel_event fires inside acquire().
    Callers catch this and convert to a cancelled-result dict.
    """
    pass


@dataclass
class TierConfig:
    name: str = DEFAULT_TIER
    label: str = ""
    rpm: int = 15
    rpd: int = 500
    tpm: int = 250_000
    throttle: bool = True
    # The Gemini model this tier implies (e.g. "gemini-2.5-flash"). None for
    # "paid"/"custom" tiers, which leave the model to the user's Settings
    # choice. Carried here so the source of truth is one place.
    model: str | None = None

    @classmethod
    def from_preset(cls, tier_name: str) -> "TierConfig":
        p = TIER_PRESETS.get(tier_name) or TIER_PRESETS[DEFAULT_TIER]
        return cls(
            name=tier_name,
            label=p.get("label", tier_name),
            rpm=int(p.get("rpm", 0) or 0),
            rpd=int(p.get("rpd", 0) or 0),
            tpm=int(p.get("tpm", 0) or 0),
            throttle=bool(p.get("throttle", True)),
            model=p.get("model"),
        )

    @classmethod
    def custom(cls, rpm: int, rpd: int, tpm: int = 250_000) -> "TierConfig":
        return cls(
            name="custom",
            label=f"Custom (RPM {rpm}, RPD {rpd})",
            rpm=int(rpm),
            rpd=int(rpd),
            tpm=int(tpm),
            throttle=rpm > 0 or rpd > 0,
            model=None,
        )

    @property
    def min_interval_sec(self) -> float:
        """ระยะเวลาขั้นต่ำระหว่าง call (วินาที)"""
        if not self.throttle or self.rpm <= 0:
            return 0.0
        return 60.0 / self.rpm


# ─── RateLimiter ──────────────────────────────────────


class RateLimiter:
    """
    Thread-safe — รองรับ parallel workers ผ่าน ThreadPoolExecutor
    Workflow:
        1. acquire() — block จน safe to call (sleep ถ้า RPM เต็ม)
        2. external code makes call
        3. record(call_type, duration, tokens, ok)
    หรือใช้ as context manager:
        with limiter.acquire_context() as r:
            result = call()
            r.tokens = result.tokens
    """

    def __init__(self, tier: TierConfig | None = None, usage_log: UsageLog | None = None):
        self.tier = tier or TierConfig.from_preset(DEFAULT_TIER)
        self.usage = usage_log or get_usage_log()
        self._lock = threading.Lock()
        self._last_call_ts: float = 0.0

    def update_tier(self, tier: TierConfig) -> None:
        with self._lock:
            self.tier = tier

    # ─── core gating ──────────────────────────────

    def check_quota(self) -> tuple[bool, str]:
        """เช็คว่ายังเหลือ daily quota มั้ย — ไม่ block, แค่บอก"""
        if not self.tier.throttle or self.tier.rpd <= 0:
            return True, "no daily cap"
        used = self.usage.today_count()
        if used >= self.tier.rpd:
            return False, f"Daily quota exceeded: {used}/{self.tier.rpd}"
        return True, f"{used}/{self.tier.rpd}"

    def acquire(self, cancel_event: threading.Event | None = None) -> None:
        """
        Block จน safe — sleep ถ้าจำเป็น
        Raise QuotaExceededError ถ้า daily limit เต็ม
        Raise CancelledError ถ้า cancel_event ถูก set ระหว่าง sleep
        """
        # 1. daily quota check
        ok, msg = self.check_quota()
        if not ok:
            raise QuotaExceededError(msg)

        if cancel_event is not None and cancel_event.is_set():
            raise _CancelledError("cancelled before acquire")

        # 2. RPM throttle (ใส่ delay ระหว่าง call)
        if not self.tier.throttle or self.tier.rpm <= 0:
            return
        with self._lock:
            min_interval = self.tier.min_interval_sec
            now = time.time()
            elapsed = now - self._last_call_ts
            if elapsed < min_interval:
                sleep_sec = min_interval - elapsed
            else:
                sleep_sec = 0
            # update last_call_ts BEFORE sleep (claim slot)
            prev_call_ts = self._last_call_ts
            claimed_ts = now + sleep_sec
            self._last_call_ts = claimed_ts
        if sleep_sec > 0:
            # Cancel-aware sleep — wake every 200 ms to honor cancel_event.
            # Without this, a 4 s throttle delay = 4 s of quota burn after Cancel.
            end = time.time() + sleep_sec
            while True:
                remaining = end - time.time()
                if remaining <= 0:
                    break
                if cancel_event is not None and cancel_event.is_set():
                    # Roll back the slot we claimed (only if no later call has
                    # advanced it) so the NEXT worker isn't penalised with an
                    # extra idle interval for our cancellation.
                    with self._lock:
                        if self._last_call_ts == claimed_ts:
                            self._last_call_ts = prev_call_ts
                    raise _CancelledError("cancelled during throttle")
                time.sleep(min(remaining, 0.2))

    def record(
        self,
        call_type: str = "analyze",
        duration_sec: float = 0.0,
        tokens: int = 0,
        ok: bool = True,
    ) -> None:
        """บันทึก call เข้า usage log (หลัง call เสร็จ)"""
        self.usage.record_call(
            call_type=call_type,
            duration_sec=duration_sec,
            tokens=tokens,
            ok=ok,
        )

    # ─── context manager — for clean usage ──────

    def call(self, call_type: str = "analyze", cancel_event: threading.Event | None = None):
        """
        Returns context manager:
            with limiter.call('analyze') as ctx:
                result = gemini_call()
                ctx.tokens = result.usage_metadata.total_token_count
                ctx.ok = True
        Pass `cancel_event` to make the throttle sleep interruptible.
        """
        return _CallContext(self, call_type, cancel_event=cancel_event)

    # ─── pre-flight estimate ─────────────────────

    def estimate_eta(self, n_calls: int) -> dict:
        """ประมาณการเวลาที่จะใช้สำหรับ n_calls — สำหรับแสดงก่อน start
        return: {"eta_sec", "rpm_cap", "fits_quota", "remaining", "warning"}
        """
        used = self.usage.today_count()
        remaining = max(self.tier.rpd - used, 0) if self.tier.rpd > 0 else None
        fits = (remaining is None) or (n_calls <= remaining)

        if not self.tier.throttle or self.tier.rpm <= 0:
            eta_sec = n_calls * 0.5  # rough no-throttle estimate
        else:
            eta_sec = n_calls * self.tier.min_interval_sec

        warning = None
        if not fits:
            warning = f"Will exceed daily quota — only {remaining} call(s) left"
        elif remaining is not None and (used + n_calls) > self.tier.rpd * 0.8:
            warning = f"Will use >80% of daily quota"

        return {
            "n_calls": n_calls,
            "eta_sec": int(eta_sec),
            "rpm_cap": self.tier.rpm,
            "rpd_used_after": used + n_calls if fits else used,
            "rpd_cap": self.tier.rpd,
            "remaining": remaining,
            "fits_quota": fits,
            "warning": warning,
        }


class _CallContext:
    """Context manager — acquire on enter, record on exit"""
    def __init__(
        self,
        limiter: RateLimiter,
        call_type: str,
        cancel_event: threading.Event | None = None,
    ):
        self.limiter = limiter
        self.call_type = call_type
        self.cancel_event = cancel_event
        self.tokens = 0
        self.ok = True
        self._start: float = 0.0
        self._acquired: bool = False

    def __enter__(self):
        self.limiter.acquire(cancel_event=self.cancel_event)
        self._acquired = True
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._acquired:
            # acquire() raised — no slot was claimed, nothing to record
            return False
        duration = time.time() - self._start
        self.limiter.record(
            call_type=self.call_type,
            duration_sec=duration,
            tokens=self.tokens,
            ok=(exc_type is None and self.ok),
        )
        return False  # don't suppress exceptions


# ─── App-wide singleton ───────────────────────────────


_default_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter()
    return _default_limiter


def update_tier_from_config(cfg: dict) -> RateLimiter:
    """โหลด tier จาก auth.json config → return limiter ที่ตั้งค่าใหม่"""
    tier_name = cfg.get("tier", DEFAULT_TIER)
    if tier_name == "custom":
        tier = TierConfig.custom(
            rpm=int(cfg.get("custom_rpm", 15)),
            rpd=int(cfg.get("custom_rpd", 500)),
            tpm=int(cfg.get("custom_tpm", 250_000)),
        )
    else:
        tier = TierConfig.from_preset(tier_name)
    limiter = get_rate_limiter()
    limiter.update_tier(tier)
    return limiter
