# Bug Log — v1.068 (released 2026-11-01 08:46)

v1.068 changed only the used-up-quota line (`log/log_v1.068.md`). K15, the publish gates writing into Nick's logs,
was fixed in `tools/` and is recorded in `bug/bug_v1.067.md`.

## Open — found 2026-11-01 by the README/CODEMAP accuracy check, not fixed here

Two read-only checkers compared the new README and CODEMAP with the code (rule #15 work, no version). Two of their
findings are app defects, not doc wording. I reproduced both on the dev PC.

They are **not fixed in the docs commit**:
- a change to app behaviour needs its own version and its own drill (#28);
- a bug found during other work is filed on its own, never folded into that work's diff.

| # | Defect | Reproduced | Fix to make (next version) |
|---|---|---|---|
| L1 | **A burst that crosses midnight pulls the whole next day into the earlier day's folder.** See the detail below. | `grouper.get_capture_date` stubbed; photos at 15-03 23:50, 16-03 00:10, 09:00, 15:00 and 17-03 10:00. Result: one folder dated 2026-03-15 holding a, b, c and d, and a second folder for 17-03 with e. | Bridge only the burst. A photo joins across midnight only while it is within the gap of the previous photo AND the group started on the previous day. Once the bridge ends, the next same-day photo starts a new group. Add the 5-photo case above as a test. Old since v1.044. |
| L2 | **A custom daily cap above the free 500 is kept while the built-in key is in use.** See the detail below. | `_builtin_key_in_use` patched to True; `update_tier_from_config({"tier": "custom", "custom_rpm": 15, "custom_rpd": 5000})` gave the tier `custom 15 5000`. | Clamp the RPD as well (`tier.rpd > free.rpd`), and add the 15/5000 case to `test_the_built_in_key_is_throttled_as_free_whatever_tier_was_saved`. TPM is stored but enforced nowhere. Either enforce it or stop showing it as a limit. |

**L1, how the chain happens.** `group_by_session` (`core/grouper.py`) compares each photo with the PREVIOUS photo:
- `same_day = dt.date() == last_dt.date()`
- `midnight_burst = (dt - last_dt) <= gap`

Once a 00:10 photo has joined the 23:50 group, `last_dt` is on the next day, so every later photo of that day joins
as `same_day`. The group is dated `min(dates)`, so a full day of work is filed under the day before. With a photo
near each midnight, the chain runs on through several days. The v1.044 rule (one shooting day = one folder; the gap
only bridges midnight) intended the opposite. The existing tests cover only a 2-photo burst.

**L2, why K8 missed it.** K8 (v1.067) said any tier is held to the free limits while the built-in key is in use.
`update_tier_from_config` (`core/rate_limiter.py`) replaces a custom tier only when:
- it is unthrottled; or
- its RPM is 0 or above the free 15; or
- its RPD is 0.

An RPD above 500 passes. The AI Health dialog accepts such a value. K8's test used custom 60/5000, which was replaced
because of its RPM, so the RPD clamp was never exercised. The effect is that the app's own day cap does not stop at
500, and Google's 429 is the first stop. The app then says "used up for today", so it is not silent.

## Checked and cleared during the same pass

- **The frozen build carries `tzdata`** (`dist/HappyPhotoOrganizer/_internal/tzdata`). So `usage_log.PT_TZ` is the real
  America/Los_Angeles zone in the app, not its fixed UTC-8 fallback. The usage day and `processor.quota_back_at` agree
  on the reset hour.
