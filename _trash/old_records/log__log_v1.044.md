# Log — v1.044 (2026-09-02)

## Entry 1 — Installer was deleting the job names Nick had taught the app
- Found while checking whether junk names from the earlier run had polluted the
  catalog (they had not — the app only learns names the user edits, so the AI
  was never biased by "Browsing online shopping app on mobile").
- What turned up instead: `installer.py` extracts the payload zip over the
  install directory with no exceptions, and `data/job_catalog.json` lives
  inside that tree. It is user data — the app writes to it whenever a job name
  is learned — so **every update since v1.025 silently discarded it**.
  Measured on this machine: installed catalog 160 jobs vs shipped 146 = 14 of
  Nick's own names would have been lost by installing v1.043.
- Fix: snapshot the catalog before extraction, merge it back after. Union by
  `normalized`, shipped entry wins on collision, add-only — a failure can only
  mean "nothing was rescued", never "names were lost". Any failure is swallowed
  so it can never break an install.
- Verified against Nick's REAL catalogs (installed 160 + shipped): 0 names lost,
  all shipped names still present, no duplicates.
- Also folded every learned name back into the shipped catalog: 146 → **174**
  (14 from his install + 14 learned during tonight's test run, which lived only
  in `dist/` and would have died at the next `pyinstaller --clean`). Both
  catalogs were backed up to `Projects/Backups/` first.

## Entry 2 — Same-day photos were being scattered across different dates
- Nick: "มันไม่รวมรูปวันเดียวกันไว้ด้วยกัน ... ต้องเอาวันที่ถ่ายเป็นหลักในการจัดการโฟลเดอร์".
- Cause, and it was two mechanisms compounding:
  1. `grouper.group_by_session` split a day wherever the shooting gap exceeded
     90 minutes, so one day's work became several groups.
  2. `assign_unique_dates` then enforced a unique day number per folder, so
     those same-day groups were pushed onto *different days* — dates the photos
     were never taken on. His run: 46 folders, 43 shifted, 16 capped.
- Decision (asked Nick, he chose): **one folder per shooting day** — same day,
  different jobs, still merge into one folder — and **keep** consolidating into
  the target month.
- Fix in `grouper`: group by calendar date; the time gap now only bridges a
  burst that runs past midnight (23:59 → 00:01), which keeps the v1.041
  midnight fix intact. `assign_unique_dates` is untouched — with one group per
  day it simply has nothing left to shift.
- Simulated on a corpus shaped like his real run (241 photos, 12 shooting days):
  - OLD: 48 folders · 29 shifted · 17 capped · 29 dated a day they were not shot
  - NEW: **12 folders · 0 shifted · 0 capped · folder dates == shooting dates**

## Entry 3 — a BOM I introduced would have broken the auto-updater
- Bumping VERSION with PowerShell `Set-Content -Encoding utf8` wrote a UTF-8
  **BOM** (PS 5.1 always does). The test suite stayed green because
  `test_version_file_matches_running` compares the file against a value read
  from that same file, so the BOM cancelled out on both sides.
- Real effect: `str.strip()` does NOT remove U+FEFF (it is not whitespace in
  Python), so `read_version()` returned "﻿1.044" and
  `updater._parse_version` read it as **(0, 44) instead of (1, 44)** — the
  installed build would look older than every release and the updater would
  offer the same version forever.
- Fixed the file (no BOM, LF), hardened `read_version()` to `utf-8-sig`, and
  added two tests: VERSION has no BOM/CR and parses with a non-zero major, and
  the reader survives a BOM if some Windows tool re-saves the file.

## Verification
- `tests/test_core.py` **38/38 PASS** (36 + the two BOM guards; 35 → 36 was the
  new day-grouping test replacing the old "a gap splits a day" one, which
  asserted the behaviour Nick asked to remove).
- Installer merge proven against the real catalogs, not a synthetic pair.
- ❗ Not verified live: the AI's accuracy at flagging non-work photos — Nick was
  running v1.043 for exactly that when this work started, and has not reported
  back yet.
