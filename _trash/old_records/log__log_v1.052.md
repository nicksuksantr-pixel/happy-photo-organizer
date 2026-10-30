# Log — v1.052 (2026-09-24)

## Entry 1 — "ขึ้นผิดพลาด": the date was the rule, not a fault

Nick sent three jobs from the phone in one afternoon. All three were filed
correctly, and the second and third came back with dates that looked wrong:

| sent | work date | filed as |
|---|---|---|
| 14:58 | 24-09-26 | `24-09-26 DG2 inspected & repaired wire...` |
| 15:17 | 24-09-26 | **`04-09-26`** Installed. Steering gear motor No.1 |
| 15:29 | 24-09-26 | **`18-09-26`** Inspected DG 3 |

That is `assign_unique_dates` doing exactly what it is told: **one day number
per folder, across the whole archive.** Job one took day 24; jobs two and three
were moved to the earliest free day numbers left in that destination.

The transfer itself was perfect, and the log shows the protocol working as
designed:

    GET /jobshot/v1/job/20260924-145745-42907a -> 404   (never sent before)
    POST /jobshot/v1/upload                    -> 200   (filed)
    GET /jobshot/v1/job/20260924-145745-42907a -> 200   (receipt confirms)

**Put to Nick, who confirmed the rule for the third time: day numbers stay
unique.** So nothing about the rule changed. What changed is that it no longer
looks like a fault:

- The **reply to the phone now carries `work_date`** alongside `date_shifted`,
  so JobShot can say *"filed as 18-09-26 - moved from 24-09-26"* instead of
  presenting a date the engineer knows is wrong with no explanation. Additive
  field: a reader that ignores unknown keys is unaffected, which is why this
  one did not need the phone to move first - unlike the reply-shape change that
  broke JobShot two days ago.
- The **PC log names both dates and the reason**: *"work done 2026-09-24 - that
  day number was already used in this folder, so it was filed under 18-09-26"*.
  It previously said "the day rule filed it on a different date", which sent
  Nick hunting for a bug three times in one afternoon.

Still to do on the other side: the phone's own message needs JobShot to render
the new field.

## Entry 2 — a silent fast path that never ran

Chasing the above, the receipt book (`~/.happy-photo-organizer/jobshot_filed.json`)
**did not exist anywhere on the machine**, after three successful filings by the
installed v1.051.

What is certain: §4 answered `200`, which it can only do from the index (absent)
or by scanning the archive - so the scan fallback carried it, and Nick lost
nothing. What I could not explain from outside the app: why neither `record()`
at filing time nor the backfill inside `lookup()` left a file, when the same
code writes that exact path correctly when run from source here.

The fix is not a guess at the cause. The call site was:

    except Exception:
        pass

so a failure had nowhere to appear. It now reports - a failed write adds a
warning naming the path, and an unavailable recorder reports the exception.
**A fast path that silently never runs is worse than one that fails loudly**,
and the next job Nick sends will say which of the two this is.

## Entry 3 — the same flaky test, one day later

`test_receiver_requires_the_paired_token` failed on unrelated work, exactly as
its sibling did yesterday: a "wrong token" built as `token[:-1] + "0"` **is**
the real token whenever it already ends in `0`, one run in sixteen.

I fixed that pattern yesterday in one test and did not look for others. The
lesson is small and repeatable: **when a bug is a pattern, grep for its
siblings before closing it.** The grep now returns nothing.

## Verification
`tests/test_core.py` **96/96**, run twice to catch the one-in-sixteen.
