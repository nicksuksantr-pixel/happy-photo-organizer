# Log — v1.068 (2026-11-01) — When the free AI is back

**Not released yet** (#28). It is drilled from every version still in the field (UPDATE_DRILL step 1, v3.26).

**Asked:** Nick, in this chat, answering *"Build v1.068 so the quota message names the 15:00 reset time?"*: **"Build
v1.068"** (2026-11-01, about 01:15).

## What changed in the app

- **The used-up-quota line says when AI is back, on the PC's own clock.** v1.067 said "try again tomorrow". The free
  tier's daily quota resets at midnight US Pacific: 14:00 in Thailand under US daylight time, 15:00 otherwise. So a
  quota that runs out in a Thai morning is back the same afternoon. It now reads, for example, "AI is back after 14:00
  today".
- `processor.quota_back_at()` works out the next Pacific midnight by hand (the US daylight-time rule), so the app needs
  no tz database.

## Step 0 — the rubric walk before the first drill (0 agents)

The candidate's app diff against v1.067 is `core/processor.py` only.
- **Correctness:**
  - the reset instant matched the tz database (`zoneinfo` + `tzdata`) at 105,168 instants, every hour and every
    hour + 59:59 from 2025 to 2030, with 0 mismatches;
  - at the exact reset instant, the next one is named;
  - the US daylight-time start and end days are tested.
- **Callers:** the skipped-row reasoning and `plan.ai_error` both call `ai_down_line(cause)`, and both get the same
  text. Every cause other than "day" is unchanged.
- **Tests:** the new test was red first (no `quota_back_at`) and is green now. It does not depend on the PC's zone:
  it passes Thai time explicitly, and the live-clock case only checks the shape. Suite 245/245.
- **Known fixes at this moment:**
  - K15 (the publish gates writing into Nick's logs) is fixed in `tools/`, not in the app bytes;
  - U8 (`job_catalog.json` inside the install tree) stays open by plan, as "its own drilled release"
    (log_v1.066).
  - No other known app fix is pending.

## Field versions (drill.json `field_versions`)

| Version | Where | Read | Drill |
|---|---|---|---|
| 1.067 | Nick's PC | 2026-11-01, his update.log: STARTED 1.067 at 00:30:15 | `drills/drill.json`, the loopback feed, receipt `drills/1.068.json` |
| 1.065 | the ship PC | 2026-10-30, V-Log v1.065 (21:09) | `drills/drill.from-1.065.json`, repo-env via the test repo, receipt `drills/1.068.from-1.065.json` |
