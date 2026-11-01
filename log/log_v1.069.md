# Log — v1.069 (2026-11-01) — The next day keeps its own folder

**Both field-version drills PASSED 15/15** (#28): from v1.068 (`drills/1.069.json`) and from v1.065
(`drills/1.069.from-1.065.json`). `release-gate --check --tag v1.069` passed.

**RELEASED 2026-11-01 10:48** (tag `v1.069` at `785c494`) through `tools/publish_release.py --previous 1.068`.
Every gate passed: the local gates, including README v1.069 and a fresh CODEMAP; the lock; the draft upload with
its size verified; and, read from outside after publishing: `latest` is v1.069, a v1.068 user is offered it, and
the re-downloaded asset hashes to the drilled file.
 Candidate sha256 `6cb565fcfbcc3f741a650d53c3a806b825fbfb373203e0884eda21bd3e2258bf`,
91,709,120 bytes. It is drilled from every version in the field: v1.068 (Nick's PC) and v1.065 (the ship PC).

**Asked:** Nick, in this chat, answering "Fix L1 and L2 as v1.069 with its drills?": **"Fix as v1.069"**
(2026-11-01). The Director relayed the same answer from its own chat.

## What changed in the app

- **L1:** a burst across midnight no longer pulls the whole next day into the earlier day's folder.
  - `grouper.group_by_session` now reads "same day" against the group's first photo, not the previous photo.
  - The bridge still keeps 23:50 + 00:10 together, but it ends with the burst.
  - Wrong since v1.044. Found by the README/CODEMAP accuracy check (`bug/bug_v1.068.md`).
- **L2:** with the built-in key, a custom tier is held to every free limit, not only the per-minute one.
  - `rate_limiter.update_tier_from_config` now also replaces a custom tier whose RPD is above 500 or whose TPM is
    above 250k.
  - K8 (v1.067) clamped only RPM, and its test case 60/5000 was replaced for its RPM, so the day cap never ran.
  - TPM is still counted nowhere. At the clamped 15 RPM it would take more than 16k tokens a call to reach 250k a
    minute, and a call carries 1–3 photos plus the catalog names. It is clamped for what AI Health shows, not counted.
- Also in these bytes: the 57 one-line docstrings from the #15 docs work. The ASTs are identical without docstrings.

## Step 0 — the rubric walk before the first drill (0 agents)

- **The app diff against v1.068**, file by file, comparing syntax trees with the docstrings removed:
  - `core/grouper.py` and `core/rate_limiter.py` change behaviour;
  - 19 other app files change docstrings only;
  - `VERSION` is 1.069.
- **Callers:**
  - `group_by_session` has one caller, `processor.phase1_resize_and_group`;
  - `update_tier_from_config` is called by `main.py` at start and after Settings, and by `AIHealthDialog._apply_tier`;
  - the AI Health note ("a paid or faster tier is held to the free limits") is now true for the day cap too.
- **Tests:**
  - `test_grouper_midnight_bridge_does_not_pull_the_next_day_in` was red first (7 photos, 1 folder) and is green now;
  - the K8 test gained the 15/5000 and 15/500/1M cases and asserts `rpd <= 500` and `tpm <= 250k`; it was red first
    on 15/5000 and is green now;
  - suite 248/248.
- **Known fixes at this moment:** U8 (`job_catalog.json` inside the install tree) stays open by plan. No other known
  app fix is pending.

## The build

- `python -m PyInstaller HappyPhotoOrganizer.spec --noconfirm --clean`, then `python installer/build_installer.py`.
- The bundle's `VERSION` is 1.069.
- **The key:**
  - there is one bundled `gemini.key`, whose fingerprint `e656add8f927` equals the registered key;
  - no other file in the app folder holds the key or anything key-shaped;
  - the setup's bytes hold neither.

## Field versions (drill.json `field_versions`)

| Version | Where | Read | Drill |
|---|---|---|---|
| 1.068 | Nick's PC | 2026-11-01, his update.log: STARTED 1.068 at 08:50:50 | `drills/drill.json`, the loopback feed, receipt `drills/1.069.json` |
| 1.065 | the ship PC | 2026-10-30, V-Log v1.065 (21:09) | `drills/drill.from-1.065.json`, repo-env via the test repo, receipt `drills/1.069.from-1.065.json` |

## The drills

| FROM | Route | Run | Result |
|---|---|---|---|
| 1.068 (`4345dc38...`) | the loopback feed | 10:24:19-10:33:53 (9.6 min) | **15/15 PASS**, receipt `drills/1.069.json` |
| 1.065 (`46902c79...`) | repo-env, the test repo | 10:35:03-10:45:37 (10.6 min) | **15/15 PASS**, receipt `drills/1.069.from-1.065.json` |

**Before staging:**
- the lock was free and `HPO.cmd` was absent;
- the FROM setups hashed to the released files;
- the candidate went on the test repo draft-first (`drill v1.069`), and its public `releases/latest` read back as
  v1.069, 91,709,120 bytes, digest `6cb565fc…`.

**The FROM-1.068 run:**
- v1.068 fetched the loopback feed;
- v1.069 started itself at 10:25:09.

**The FROM-1.065 run:**
- v1.065's own updater fetched `api.github.com/repos/nicksuksantr-pixel/hpo-update-drill/releases/latest` at
  10:35:38;
- v1.069 started itself at 10:36:52.

**Both runs:**
- one process, one install folder;
- 1900 files identical to a fresh install;
- the shortcuts open the new exe;
- the user data is unchanged;
- `embedded_key_works` status 200, fp `e656add8f927`;
- no key shape in any receipt or log.

`release-gate --check --tag v1.069 dist/HappyPhotoOrganizerSetup.exe` exit 0. It reads both receipts, and the v3.27
docs check finds README naming v1.069 and a real CODEMAP. The publish script's local gates (`--dry-run`) passed
before the drills.

## In the field

**Nick's PC, v1.068 → v1.069, read-only from his `logs\update.log`:**
- 10:52:41 DOWNLOADED, then VERIFIED (sha256 `6cb565fc…`) and HANDOVER;
- 10:52:48 STAGED, 1898 files;
- 10:52:54 SWAPPED;
- 10:52:56 STARTED 1.069.

That is four minutes after publishing, with no click: the route drilled in `drills/1.069.json`. The ship PC (v1.065)
is not read; its route is the one drilled in `drills/1.069.from-1.065.json`.
