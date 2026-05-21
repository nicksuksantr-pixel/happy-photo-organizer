# ⚠️ Gemini Free Tier Limits

**หมายเหตุสำหรับโค้ดดี้และคอส** — นิกใช้ Gemini AI Studio key ฟรี ห้ามเกิน rate limit

## Model: `gemini-3.1-flash-lite` (Default)

| Metric | Free Limit |
|---|---|
| Requests per minute (RPM) | **15** |
| Tokens per minute (TPM) | **250,000** |
| Requests per day (RPD) | **500** |

## ✅ ก่อนทำงานที่ส่ง Gemini เยอะ ต้องถามนิก:

1. นี่จะ call Gemini กี่ครั้ง?
2. ใช้ free key หรือ paid key?
3. ถ้า free + เกิน 500 RPD → ต้อง throttle หรือ split

## ❌ อย่า hard-code ว่า "ห้ามใช้ paid model"

- Default ใน code = `gemini-3.1-flash-lite` (free-friendly)
- Settings ต้องให้นิกเลือก pro / paid model ได้เสมอ
- บางโปรเจคต้องใช้ pro/paid — อย่า fix free

## 📐 Throttle pattern (ถ้า batch ใหญ่)

```python
import time
# 15 RPM = 1 call ทุก 4 วินาที (safe)
MIN_INTERVAL = 4.0  # seconds
last_call = 0

for item in items:
    elapsed = time.time() - last_call
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    call_gemini(item)
    last_call = time.time()
```

## 🔗 อ้างอิง

- AI Studio key: https://aistudio.google.com/apikey
- Rate limits page: https://ai.google.dev/gemini-api/docs/rate-limits
- Memory: `~/.claude/projects/.../memory/reference_gemini_free_tier_limits.md`

---

**บันทึก:** 2026-05-17 โดยนิก ผ่านโค้ดดี้
