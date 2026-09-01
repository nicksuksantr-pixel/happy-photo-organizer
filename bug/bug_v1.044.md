# Bug Log — v1.044

## BUG-1: every update deleted the job names the user had taught the app
- **Severity:** silent data loss on every upgrade since v1.025.
- **Root cause:** `installer.py::install()` extracts the payload zip over the
  install directory unconditionally (`zf.extract` per member, no skip list).
  `data/job_catalog.json` ships inside that tree but is written at runtime
  whenever the app learns a job name — user data in an overwritten location.
  There was no reference to `job_catalog` anywhere in the installer.
- **Measured:** installed catalog 160 jobs (39 user-added) vs shipped 146 →
  installing v1.043 would have destroyed 14 of Nick's names.
- **Fix:** `_read_installed_catalog()` snapshots before extraction,
  `_merge_catalog()` unions the old entries back afterwards (by `normalized`,
  shipped wins on collision, add-only, all failures swallowed).
- **Verified:** simulated upgrade with the real installed + shipped catalogs →
  0 names lost, shipped set intact, no duplicates.

## BUG-2: one day's work was scattered across dates it was never shot on
- **Reported by:** Nick, 2026-09-02 — "มันไม่รวมรูปวันเดียวกันไว้ด้วยกัน ... ทีนี้มันกระจัดกระจายเลย".
- **Root cause (two mechanisms compounding):**
  1. `grouper.group_by_session` started a new group whenever the gap between
     consecutive photos exceeded 90 minutes — including *within* a single day,
     so one day's work became several groups.
  2. `assign_unique_dates` gives every folder a unique day number, so those
     same-day groups were then pushed onto different days entirely.
  Net effect on his run: 46 folders, **43 shifted**, 16 capped.
- **Fix:** group by calendar date. The gap now only bridges a burst crossing
  midnight (which preserves the v1.041 midnight-session fix); it never splits a
  day. `assign_unique_dates` needed no change — with one group per day there is
  nothing left for it to shift.
- **Verified** on a corpus shaped like the real run (241 photos / 12 days):
  48 folders → **12**, 29 shifted → **0**, 17 capped → **0**, and every folder
  date equals its shooting date.

## BUG-3: a UTF-8 BOM in VERSION made the app report itself as version 0.x
- **Introduced during this session** by `Set-Content -Encoding utf8` (Windows
  PowerShell 5.1 always writes a BOM), and **not caught by the test suite**
  because `test_version_file_matches_running` compares the file against a value
  read from that same file — the BOM cancelled out on both sides.
- **Effect:** `str.strip()` does not remove U+FEFF (not whitespace in Python),
  so `read_version()` returned `"﻿1.044"`; `updater._parse_version` finds
  no leading digit in `"﻿1"` and coerces it to 0, giving **(0, 44)**. The
  installed build would compare older than every published release, so the
  updater would keep offering the version already installed.
- **Fix:** VERSION rewritten without BOM (LF); `read_version()` now reads with
  `utf-8-sig` so a BOM can never reach the comparator again.
- **New tests:** VERSION has no BOM and no CR and parses with a non-zero major;
  and the reader survives a BOM-saved file.
