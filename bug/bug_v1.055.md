# Bug Log — v1.055 on

A rolling file (#7). Bugs 1–5 each hold one version's bug log as it was written, with its own bug ids inside
(BUG-1, U1, K16 and so on). From Bug 6 on: one `## Bug N — date — v1.0xx — title` per bug. At 20 entries a new
`bug/bug_v1.0xx.md` starts; when a third file starts, the oldest leaves the repo.
Until 2026-11-05 each version had a file of its own. They were joined here unchanged apart from heading levels.

## Bug 1 — 2026-09-26 — v1.055 — BUG-1 to BUG-3: after a batch, only a restart could clear the job list (fixed in v1.056)

> **Status: FIXED in v1.056 (2026-09-26).** Nick read this brief and said
> *"แก้ทั้ง 3 ตัวพร้อมกันเลย"* — all three the same day. See `log/log_v1.056.md`
> for what shipped and for the two further rounds of review it took, and
> `CHANGELOG.md` [1.056]. The diagnosis below is left exactly as it was written,
> before any of it was fixed.
> Diagnosed read-only by three independent investigations; **nobody ran the app** —
> every claim below is from source, cited to `file:line`. Confirm against a running
> window before trusting the reproduction steps.

### BUG-1: after a batch is committed, nothing can clear the job list but a restart

- **Reported by:** Nick, 2026-09-26 — *"แอพเราเองเวลาสร้างงานเสร็จแล้วเคลียงานจากลิสเพื่อทำใหม่ไม่ได้นะ
  ต้องปิดโปรแกรมเปิดใหม่เท่านั้น"*
- **Severity:** daily friction, no data loss on this path. But see BUG-2 and BUG-3,
  which are the same root cause with teeth.
- **Root cause — the control does not exist.** All three investigations agree. The
  only code in the app that empties Step 3 is inside `_start_phase12`
  (`main.py:1473-1481`): `_rename_done = False`, `self.plan = None`, destroy every
  child of `self.table_scroll`. It is reachable **only** by pressing *Start AI
  Tagging* (`main.py:429`) or Ctrl+Enter. Clearing is a side effect of launching the
  next run, never an action Nick can take on its own. `grep -n "    def "` over
  `MainWindow` shows no `_clear_plan`, `_new_batch`, `_reset_all` or equivalent — so
  this is **not** the project's recurring "finished feature with no entry point"; the
  feature was never written.
- **Why the obvious button does not work.** The one control labelled **Clear**
  (`main.py:372`) calls `_clear_sources` (`main.py:1396-1401`), which clears
  `self.source_paths` and refreshes two labels. It never touches `self.plan`, the
  rows, `review_summary`, `_rename_done` or `phase4_btn`. Pressing it after a commit
  changes nothing visible in Step 3 — **that is the moment the app reads as broken.**
- **Why a restart is the only thing that works:** a restart re-runs `__init__`.
  State that survives a commit and is otherwise reset nowhere:

  | State | Set | Cleared only at |
  |---|---|---|
  | `self.plan` | `main.py:1514` | `main.py:1478` (inside `_start_phase12`) |
  | JobRow widgets in `table_scroll` | `main.py:1622-1628` | `main.py:1479`, `1598` |
  | `self._rename_done` | `main.py:1836` | `main.py:1473` — pins Step 3's badge to "done" |
  | `self.source_paths` | `main.py:1098`, `1390` | `main.py:1399` (the Clear button) |
  | `review_summary` text | `main.py:1620`, `1758` | never restored |
  | progress bar / text | `main.py:1849` (100 %, "Done") | `_set_progress` or restart |
  | `a.temp_folder` on each assignment | `core/processor.py:829` | never — points at a `__pending_NN` path that no longer exists |

- **The only way to empty the list today** is per-row **Delete**
  (`ui/job_row.py:239-240` → `_delete_assignment`, `main.py:1640`), which fires a
  separate `askyesno` per row (`main.py:1651-1658`) worded as deleting photos from
  disk. Twenty rows = twenty destructive-sounding modals. Restarting is faster and
  feels safer, which is exactly the workaround Nick found.

### BUG-2: "Commit Rename" stays armed on a plan that has already been committed

- **Not reported — found while diagnosing BUG-1.**
- `_reset_buttons` (`main.py:1868-1876`) re-enables `phase4_btn` whenever
  `self.plan` is truthy (`1871-1872`), and the commit never nulls the plan. So the
  button is live again on a batch whose folders have already been renamed away.
- Pressing it runs `_start_phase4` over stale assignments whose `temp_folder` no
  longer exists: `rename_photos_for_folder` fails its `iterdir`
  (`core/processor.py:112-115`), the merge branch then iterates a missing folder
  (`core/processor.py:793`) and raises `FileNotFoundError`, caught at
  `core/processor.py:854-855`. Outcome: **renamed 0, one error per row, and a second
  "All Done" box.** Nothing is destroyed, but the app reports a finished run that did
  nothing.

### BUG-3: a second batch re-ingests the first one unless Nick presses Clear

- **Not reported — found while diagnosing BUG-1. This is the one with a real cost.**
- The commit does not clear `self.source_paths`, and `_on_drop` (`main.py:1096-1099`)
  and the browse button (`main.py:1389-1390`) both **append**. Phase 1 copies rather
  than moves (`core/processor.py:431`, `519`), so the previous batch's originals are
  still on disk and still listed.
- Drop a new folder without first pressing Clear and the next run re-collects the
  previous batch's photos too: resized again, sent to Gemini again (quota), and filed
  again as new folders on new day numbers.
- Nick currently avoids this by accident — the restart he uses to clear the list also
  clears `source_paths`. **Fixing BUG-1 without fixing this would remove the accident
  and expose the defect.** They must ship together.

### The fix, when it is time

Both investigations that proposed one proposed the same thing:

1. Factor `main.py:1473-1481` out into `MainWindow._reset_batch()` and have
   `_start_phase12` call it, so the two paths cannot drift. It should restore what
   `__init__` would: `plan = None`, `source_paths.clear()`, `_rename_done = False`,
   destroy the rows, `review_summary` back to "Not yet analyzed",
   `_sync_flagged_button(0)`, `_set_progress(0, "Ready")`, `phase4_btn` disabled,
   `_phase_start = None`, then `_refresh_sources()` + `_refresh_step_states()`.
2. **Deliberately do not reset** `dest_root`, `catalog`, `receiver` or `usage_log` —
   Nick keeps the same destination between jobs.
3. Call it from `_on_rename_done` (`main.py:1835`) **only on a clean finish** —
   `result.errors` empty and `result.skipped == 0`. Rows that errored or were skipped
   still own live `__pending_` folders and must stay on screen.
4. Add the visible control next to *Commit Rename* ("Start a new batch"), because
   after a partial failure the automatic reset will not fire and Nick still needs a
   way out.
5. Guard it while a worker is alive (`self.worker.is_alive()`), or a running
   `_phase12_worker` will write `self.plan` back a moment later
   (`main.py:1514`).

**Blast radius:** `self.plan` is read at `main.py:563, 574, 1647, 1661, 1674,
1697-1723, 1731-1755, 1776-1792, 1817, 1871`. Every reader already handles `None`
(`if not self.plan: return`), so `None` itself is safe. The one human consequence:
nulling the plan flips Step 2 and Step 3 back to "pending" and erases the green
"done" badge Nick may read as his receipt — so the status line
(`main.py:1846-1849`, *"Renamed N folder(s)"*) must survive the reset.

**And it is a window change**, so per the v1.051 lesson it is not done until Nick has
sent a screenshot of it.

### What was not checked

- Nobody ran the app. No claim here is confirmed against live behaviour.
- `ui/dialogs/settings.py`, `pairing.py`, `ai_health.py` were only grepped for
  reset-like controls (none found), not read.
- `ui/job_row.py` was read for the delete path only; `_open_folder`
  (`ui/job_row.py:366`) was not verified.
- The JobShot/LAN import path files its jobs headlessly and does not use Step 3, so
  it was not examined for this defect.

## Bug 2 — 2026-10-30 — v1.058 to v1.065 — backfilled: ten bugs those versions fixed, and U1–U10 open against #28

*Was `bug/bug_v1.058-v1.065.md` ("Bug Log — v1.058 → v1.065") until 2026-11-05.*

**Backfilled on 2026-10-30** under rule #20.0. `bug/` had stopped at v1.055. One
entry per bug, with the version that fixed it. Detail in `log/log_v1.058-v1.065.md`,
`CHANGELOG.md` and the GitHub release notes.

### Fixed

| # | Fixed in | Bug | How it was found |
|---|---|---|---|
| 1 | v1.058 | A config or catalog file with a BOM read as corrupt: the API key, pairing token and destination were lost silently, and the catalog went to 0 jobs. v1.044's fix had reached only 3 of 5 readers. | Asking JobShot's "where else?" of my own code |
| 2 | v1.060 (pre-release) | The sidecar route wrote the manifest by truncate-in-place. An interruption made the job look unfiled, and the phone would re-upload every photo. | Three independent reviewers |
| 3 | v1.060 (pre-release) | A partial sidecar application reported as a total refusal, and `filed_at` was overwritten by the correction time. | Same review |
| 4 | v1.062 | A damaged job record gave the same 404 as a job never filed, so the phone would re-upload. | Chain checklist with JobShot |
| 5 | v1.062 | Three temp files left in the archive on failure paths. The third was found by the test for the first two. | Own tests |
| 6 | v1.063 | No network read as "Up to date": every check failure returned `None`, the value for "nothing newer". | SM's `not-known-is-not-no` lesson |
| 7 | v1.064 | A third arrival of one `job_id` overwrote the second arrival's `emr-<id>.json` and `job-<id>.json`. | EMR's second-`emr.json` question |
| 8 | v1.064 | With 4+ arrivals, the "first match in sort order" picked the wrong draft as the job's record. | Found while preparing v1.064 |
| 9 | v1.064 | A phone file named `report_history.json` would be filed, and a later correction could overwrite EMR's own history. | JobShot's proposal |
| 10 | v1.065 | **Duplicate jobs and two drafts.** The §4 probe answered 404 while a job was still being filed (14–21 s measured), and on a 404 the phone sent the whole job again. | Measured with a probe harness after JobShot's report |

### Open — found 2026-10-30 against rule #28 (`memory/UPDATE_DRILL.md`)

None of these has reached a user as a known failure, but none has ever been run end
to end either. The silent `--upgrade` path has no record of ever being run from an
old packaged build to a new one. **Fix planned as the v1.066 bridge** (`docs/PARKED.md`).

**2026-10-31: U1–U7, U9 and U10 are fixed in v1.066** (built, not yet released: it waits for its drill). U8 is
still open. Detail in `bug/bug_v1.066.md`.

| # | Where | Defect |
|---|---|---|
| U1 | `tests/` | No test touches `installer/` at all, not even `_merge_catalog`. |
| U2 | `core/updater.py:185-190` | No hash check, and a fallback to the first `.exe` asset. |
| U3 | `installer/installer.py:372-376` | Extract-over: files the old version shipped are never removed. |
| U4 | `installer/installer.py:987-996`, `:1001-1004` | `taskkill /F`, one 0.5 s wait, no retry. A failed extract returns 1 with no relaunch and no rollback, leaving a half-overwritten install. |
| U5 | `core/update_worker.py:307-313`, `main.py:666` | Zero-click install whenever no batch runs, so it can close an open dialog or a JobShot filing in flight. |
| U6 | `installer/installer.py:978-1005`, spec `console=False` | The install stage logs with `print()` into a windowed exe, so nothing is written anywhere. |
| U7 | `installer/installer.py:982` | `--upgrade` always re-creates the Desktop shortcut, even one the user deleted. |
| U8 | `core/catalog.py:14` | `data/job_catalog.json` is user data inside the install tree (§2). Its own drilled release, after v1.066. |
| U9 | `core/updater.py`, `main.py` | No §3 contract: no loopback feed override, no `update.log`, no `STARTED` line. |
| U10 | `tools/publish_release.py` | It does not call `node tools/release-gate.mjs --check --tag <tag> <assets>`, so the lock refuses to run it. |

## Bug 3 — 2026-10-31 — v1.066 — the update path: U1–U10, S1–S2, T1, D1, R1–R7, H1–H8

*Was `bug/bug_v1.066.md` ("Bug Log — v1.066 (built 2026-10-31, not released: waits for its drill, #28)") until 2026-11-05.*

### Fixed in v1.066 — the update-path defects found 2026-10-30 (`bug/bug_v1.058-v1.065.md`)

| # | Defect | Fix | Test |
|---|---|---|---|
| U1 | No test touched `installer/`. | Swap, rollback, recovery, pruning, payload shape, silent upgrade, `--fresh-into` and the catalog path are tested. | 9 installer/swap tests |
| U2 | No hash check; first-`.exe` fallback. | Exact asset name; GitHub `digest` required; download hashed; hashed again before it runs; refused tag+hash not fetched again; https only (loopback http in a drill). | `test_only_the_named_installer_is_ever_offered`, `…without_a_digest_is_refused…`, `…changed_after_it_was_verified_is_not_run`, `…does_not_match_its_digest…` |
| U3 | Extract-over: old files never removed. | Stage → swap → prune by the old manifest (or, on the bridge, the old tree minus the new files), inside the app folder only. | `test_an_update_replaces_the_tree_exactly_and_keeps_a_way_back`, `…did_not_put_there_is_never_pruned` |
| U4 | `taskkill /F`, one 0.5 s wait, no rollback, no relaunch. | Wait for the mutex (60 s); window still open → nothing changed; any failure → roll back and relaunch the old version; interrupted swap rolled back next run. | `…fails_half_way_puts_the_old_version_back`, `…interrupted_swap_is_rolled_back…`, `…damaged_payload_changes_nothing` |
| U5 | Zero-click install whenever no batch ran: could close a dialog or a phone filing. | `busy_reason()`: batch, phone upload from its first byte, unfiled Step 3, any dialog; retry every 60 s. | `test_an_update_waits_while_the_app_is_busy…`, `…install_button_refuses_while_busy…`, `test_a_phone_upload_counts_as_busy_from_its_first_byte` |
| U6 | Installer logged with `print()` into a windowed exe. | `update.log` stages from both the app and the installer. | `test_the_update_log_writes_one_parseable_line_per_stage` |
| U7 | `--upgrade` re-created a Desktop shortcut the user deleted. | Re-creates only shortcuts that exist. | `test_the_silent_upgrade_waits_keeps_deleted_shortcuts_deleted_and_comes_back` |
| U9 | No §3 drill contract. | Drill switch + loopback feed, `update.log` + `STARTED`, `--check-update-now`, `--fresh-into`. | `test_the_drill_feed_is_honoured_only_on_loopback_with_the_drill_switch`, `test_check_now_works_even_with_automatic_checks_off`, `test_fresh_into_is_refused_outside_a_drill` |
| U10 | Publish script did not ask the #28 lock. | Lock first (before any tag); digest + offer + re-download checked after publishing. | `test_publishing_asks_the_drill_lock_before_anything_is_tagged`, `…lock_that_cannot_run_refuses`, `…published_asset_with_the_wrong_digest_is_refused` |

### Still open

| # | Defect | Plan |
|---|---|---|
| U8 | `data/job_catalog.json` is user data inside the install tree (UPDATE_DRILL §2). The installer merges it, and the drill allowlists it. | Its own drilled release after v1.066: move it to `~/.happy-photo-organizer/`. |

### Found in development — v1.066's own defects, caught by the smoke test of the built installer

| # | Bug | Fix | Test |
|---|---|---|---|
| S1 | **A failed install was not remembered, so it looped.** The installer rolled back and relaunched the old build. That build found the same release, downloaded 90 MB and handed over again, every few minutes, on any PC where that install cannot succeed (path too long, a file held open, a full disk). The same happened when the installer never ran at all (blocked, crashed). | The app writes `logs/update-attempt.json` at HANDOVER. The next start settles it: the version asked for came up → cleared; anything else → failed (the installer adds its reason). A failed version is not downloaded or handed over again by itself. The button shows `Retry vX`, its dialog shows the reason, and a newer release is not held back. An app from before v1.066 cannot read the record, so after a failed install the installer relaunches it with `HAPPY_UPDATE_REPO` pointed nowhere for that one session. | `test_a_handover_that_does_not_come_up_is_recorded_once_as_failed`, `…came_up_or_a_newer_one_clears_the_attempt`, `test_a_failed_version_waits_for_retry_and_a_newer_one_does_not`, `…handover_writes_the_attempt_before_the_installer_runs`, `test_a_failed_silent_upgrade_says_why_and_never_hands_straight_back` |
| S2 | Staging past Windows' 259-character path limit failed with a `FileNotFoundError` naming a file that is plainly in the payload. Nothing was changed, but the log gave no reason. Measured: the smoke test's long scratch folder + `.update\new\` (12) + the payload's longest path (130). | `install_swap.too_long()` names it: "path is too long for this update: N characters … Windows allows 259". | `test_a_path_too_long_to_stage_is_named_as_such` |

Not covered by the drill (stated in `drills/drill.json` `not_covered`): S1's paths are unit-tested only, and the drill runs the success path.

### Found in development — the test suite ran the real installer over Nick's install

| # | Bug | Fix | Test |
|---|---|---|---|
| T1 | **The suite downloaded the published installer and ran it over Nick's real install.** `test_manual_check_marks_itself_as_checking` (since v1.050, 2026-09-24) builds a worker that says it is v1.049. It polled the **real** GitHub and found the published release. Its fake host runs callbacks inline, so the background thread went on: download 90 MB into `~/.happy-photo-organizer/updates` → run `--silent --upgrade`. The thread's `sys.exit(0)` ended only that thread, and the suite passed. Measured 2026-10-31 with a 200 ms process watcher: `HappyPhotoOrganizerSetup-v1.065.exe --silent --upgrade` started mid-suite, and Nick's running HPO was replaced by a fresh one 20 s later. The breadcrumb log shows real downloads from suite runs at 00:57, 06:37 and 06:47 that day. Any installer up to v1.065 does `taskkill /F`, so every networked suite run since v1.050 could kill Nick's running app and re-extract his install. Checked afterwards: v1.065 still installed (1,898 files), catalog 177 jobs (that installer merges it), pairing data untouched. The Desktop shortcut is present; U7 means any old installer would re-create it. | `tests/test_core.py` fences itself at import: `urlopen` reaches loopback only (the JobShot server tests need it), `updater.cache_dir()` is a temp folder, and `updater.launch_installer_and_exit` raises. A test that needs the real launch calls `_REAL_LAUNCH_INSTALLER` with `Popen` patched. | `test_the_suite_cannot_reach_the_internet_or_run_an_installer`; the suite re-run under the process watcher showed no new HPO process |

### Found by the first drill run (2026-10-31, v1.065 → v1.066, `drills/logs/1.066-run1.*`)

| # | Bug | Evidence | Fix |
|---|---|---|---|
| D1 | **An app that hands over never exits, so no update can happen.** `launch_installer_and_exit` starts the installer, then `sys.exit(0)` from a Tk callback, with the tray icon still running. pystray's `run_detached()` starts a **non-daemon** thread (`pystray/_win32.py:131`: `threading.Thread(target=lambda: self._run()).start()`). `core/tray.py`'s docstring says "a daemon thread"; it is not. Interpreter shutdown waits for it in `threading._shutdown` forever. The process keeps a frozen window, the tray icon, the phone receiver and the single-instance mutex. **Every installer up to v1.065 hid this with `taskkill /F`.** v1.066's waits for the app to let go (U4), then gives up after 60 s: "the app was still open after 60 s - nothing was changed". Both v1.065 (the bridge) and v1.066 (its own next update) have it. **In the field:** every v1.065 start would download v1.066, freeze about a minute later, and block the next start too (the frozen window holds the mutex), until Task Manager or a reboot. | The drill: the check reached the test repo at 10:05:50, the download succeeded at 10:07:03 (91,686,951 bytes), and the installer logged FAILED at 10:08:06. The process was still alive at 10:30: 5 threads, 0 ms CPU over 20 s. The main thread was waiting, and a GetMessage thread was running (the tray). Reproduced on Nick's PC with a 15-line script (Tk + pystray `run_detached` + `sys.exit(0)` in `after`): `faulthandler` shows the main thread in `threading._shutdown` and the pystray `_mainloop` thread alive. Exit 1 at the 8 s watchdog. With `icon.stop()` first: exit 0 in 3 s. | **Fixed (Nick agreed, 2026-10-31 ~10:56):** |

**D1 fixes:**
- **The bridge (`installer/installer.py`, `core/install_swap.py`).**
  - At the start of `--upgrade` the installer reads the process that started it: `handover_parent`, which walks up to
    3 hops because the one-file setup is a bootloader plus a child.
  - It counts only if its exe is the app being replaced (`os.path.samefile`) and it is older than the installer.
  - That process gets `HANDOVER_GRACE_S` (20 s) to exit. Then `end_handover_parent` ends exactly it, with
    `TerminateProcess` on that PID, and only while the PID still names the same exe started at the same moment.
  - It logs a `HANDOVER` line saying so. Any other HPO is still left alone ("still open", nothing changed).
- **v1.066 itself.**
  - `core/tray.py` runs pystray's `icon.run` on a daemon thread of its own.
  - `on_before_install` stops the tray and the phone receiver before the handover's `sys.exit`.

**Tests:**
- `test_the_tray_never_keeps_the_app_alive_after_sys_exit`: a real process.
  - It fails in 20 s with `run_detached()` put back (mutation check).
- `test_the_handover_stops_the_tray_and_the_receiver`
- `test_the_installer_ends_only_the_process_that_handed_over`: a real child process; a different creation time or exe is
  never ended.
- `test_the_installer_finds_the_app_that_started_it_up_the_chain`: a real child process.
- `test_the_silent_upgrade_ends_a_stuck_handover_and_nothing_else` |

**Ruled out on the way, by measurement:**
- *The disconnected session:* v1.065 checked, downloaded and launched the installer while the drill session was disconnected (10:06:30–10:08:03). The installer ran and logged there too.
- *The route:* `HAPPY_UPDATE_REPO` reaches the app through `Start-Process`, tested.

**What the harness did well:** the update.log `FAILED` line and the route-evidence breadcrumbs named the failure.
**What it did badly:** it waited the full 30 minutes after a terminal `FAILED` line for the TO version, and wrote nothing while it waited.

### reviver, round 1 (2026-10-31, `v1.065..c9c6802`, 3 firms, all 7 parts × 10 dimensions)

**Score: 1/5** (lowest dimension, A). All 3 firms gave 1 independently.
- No firm died, and none left gaps.
- The intents agree in substance: hand over, exit by itself, swap with rollback, verified bytes only.
- The "intents differ" flag is wording only.
- Verdict: **not a pass** (1 BLOCKER and 2 corroborated MAJOR). Every row below was checked by Coddy against the code or by running it.

| # | Sev | Firms | Finding | Checked by Coddy |
|---|---|---|---|---|
| R1 | BLOCKER | A B C | = **D1** above: the handing-over app never exits. | Drill run 1 + 15-line repro |
| R2 | MAJOR | A B C | `swap_in` calls `recover_interrupted` inside the staging `try`. When an interrupted swap's rollback is incomplete (a file still locked), its `OSError` lands in the staging `except`: it logs "staging failed, **nothing was changed**" and `_rmtree(ud)` deletes `.update\old` and the journal, the only way back. The tree stays mixed for good. Double fault: a cut mid-swap, then a lock that outlasts 30 s. | `core/install_swap.py:305-335`, `:280-284` |
| R3 | MAJOR | A B | `update_log.PAUSED_REPO = "update-paused/after-a-failed-install"` is a slug anyone can register. After a failed bridge install, v1.065 is relaunched pointed there. v1.065 has no digest check and falls back to any `.exe`, so whoever owns that name could run code as the user. | `gh api users/update-paused` → 404 (free to register) |
| R4 | MINOR | B C | `busy_reason()` sees only Tk `Toplevel`s. A native dialog (messagebox, file picker) does not count, yet Tk timers keep firing inside it. An install can close the app under an open "All Done" box or a folder picker. The log's "any dialog" claim is false. | Probe: 6 `after()` ticks fired inside an open `messagebox`, 0 Toplevel children |
| R5 | MINOR | C | The phone receiver has no socket timeout, and `do_POST` counts "receiving" before the token check. A stalled or half-open upload, from any LAN host and without the token, holds `any_filing()` True: the update waits "a phone job is arriving" for the rest of the session. | `core/jobshot_server.py:287-293`; `BaseHTTPRequestHandler.timeout` is None |
| R6 | MINOR | A | The drill's `waits_while_busy` passes without v1.066 coming back after its own handover (`$back` is not required), so D1 in v1.066 would pass it. | `drills/kit/Invoke-Drill.ps1:268-273` |
| R7 | MINOR | A B C | The harness waited 27 min after the installer's terminal `FAILED`, wrote nothing while it waited, and kept none of the FROM's breadcrumbs (`reset` deletes them). It marked `start_from_released_build` FAIL although the FROM hash was checked at the start. | Run 1 log + receipt |

**R2–R7 fixed (Nick: "Fix R2–R7 too", 2026-10-31):**

| # | Fix | Test (mutation-checked where noted) |
|---|---|---|
| R2 | `recover_interrupted` raises `InterruptedRollbackIncomplete` after logging "could not be rolled back yet … kept .update for the next run". `swap_in` returns before the staging `except`, so it never runs `_rmtree(ud)` and never logs "nothing was changed" for it. Every other failure is unchanged. | `test_a_recovery_that_cannot_finish_keeps_the_way_back`: a real locked file, the next run finishes the rollback (mutant killed: "the way back was deleted") |
| R3 | `PAUSED_REPO = "update paused/after a failed install"`. A space is not allowed in a GitHub name, and http.client refuses the URL before DNS or a connection. Measured on v1.065's own `updater.check_for_update` from the tag: `InvalidURL`, 0 network calls; its `_poll_github` catches it and shows "offline". | `test_the_paused_repo_names_no_repo_and_never_reaches_the_network`: GitHub's owner/name grammar (the old value matches it) plus sockets that fail if touched |
| R4 | `busy_reason()` also answers "a dialog box is open" while the Tk thread owns a visible `#32770` window (message box, file or folder picker). The Tk thread id is kept at start. | `test_a_native_dialog_counts_as_busy`: a real message box, closed by a helper thread: before False, inside True, after False |
| R5 | The receiver counts a POST as "receiving" only once it carries the token, and its socket reads time out after 60 s (per read, not per upload). A timed-out or vanished client ends its connection without a traceback. | `test_a_stalled_or_unpaired_upload_cannot_hold_an_update_off`: the real server, timeout 1 s (mutant `counted = True` killed) |
| R6 | `waits_while_busy` needs the app to come back after its own handover. | Scratch run of the harness pieces |
| R7 | The update wait writes a progress line every minute, quoting the FROM's own diagnostics (new optional adapter function `Get-FromDiagnostics`). It ends 2 min after a terminal `FAILED` for TO, copies the FROM's breadcrumbs to `out\logs\<ver>.from-*` before reset deletes them, and checks `start_from_released_build` where it is measured. `Collect-Drill` brings back every `<ver>.*` log. | `test_wait.ps1` 14/14 (parse ×6, early stop, progress, STARTED after a non-terminal FAILED, positional call, `Get-LastLine` ×4 including a file held open for writing); `test_stage.ps1` 31/31 |

**Cleared by the firms** (claims checked and found not to be bugs):
- the drill feed cannot be pointed off-machine;
- the bridge prune keeps the catalog;
- `filecmp` rollback of the `.exe`;
- a truncated download does not stick `in_progress`;
- `%z` in the log time;
- the drill's process filter does not touch Nick's HPO;
- the publish lock order;
- the suite's isolation of `update-attempt.json`;
- a refused release is not a pass at the publish gate.

**Noted, not filed:**
- the 90 MB re-hash and the `rmtree` of the cache run on the Tk thread (a pause of a few seconds at handover);
- `app_window_open()` does not check visibility;
- `publish_release.py`'s check writes CHECK/FOUND into the real update.log;
- some tests leave stubs on `core.install_swap`.

**Not covered:**
- the frozen v1.066 handover (the drill covers it once R1 is fixed);
- the RUN-ALL runner's deadline kill (outside this repo);
- `ui/dialogs`.

### Found in development — the drill harness's own bugs, caught by its tests before any run

| # | Bug | Found by |
|---|---|---|
| H1 | `return ,$out` pipes an array as one object: `Read-UpdateLog \| Where-Object` never matched, so every log-based check would fail. | The feed test (Start-FakeFeed never saw "listening") |
| H2 | `$m` (a regex match) overwrote `$M` (the manifest): PowerShell names are case-insensitive. The taskbar-pin fixture did nothing. | The adapter test |
| H3 | `auth.json` as a byte-identical sentinel: the app rewrites it (window position) on every start, so `user_data_intact` would always fail. | Reading `main.py` while writing the fixtures |
| H4 | A feed that failed to start stayed running and held the port; the next run failed with no reason. | The feed test's second run |
| H5 | Route evidence could take a `SUCCESS` line from an earlier, real-repo download. | The adapter test |
| H6 | Logs read with `File.ReadAllLines` throw a sharing violation while another process appends. | Code review of the reader during the H1 fix |
| H8 | **Drill run 2: the busy step raced the app.** The harness put N+1 on the feed, then restarted the app busy (Settings opens at start). The app checked at start, found N+1, fetched 91 MB from loopback in a second, and handed over at 12:06:36, 2 s after it started and before Settings was viewable. So `waits_while_busy` failed, though the app was right: it was not busy yet. Everything else in that run behaved: v1.066 exited by itself after the handover (no "ended it" line, D1's app-side fix working), and the fake N+1 was then not retried by itself (S1). Fixed: the app comes up busy with nothing newer on the feed; the harness waits for the busy window, then feeds N+1, and waits for the app's next periodic check (≤ 5 min, with progress lines). | `drills/logs/1.066-run2.*` (update.log 12:06:34–12:06:51) |
| H7 | `.gitignore`'s `*.log` hid `drills/logs/<ver>.log` and `<ver>.update.log`: the receipt would be committed without its `drill_log`, and the lock refuses that in every other checkout. Fixed with `!drills/logs/*.log`, and `Collect-Drill` now exits 1 naming any collected file git ignores. | JS, relayed by the Director (UPDATE_DRILL §5 step 6); the scratch test now covers it (22/22) |

## Bug 4 — 2026-10-31 — v1.067 — the built-in key and its drills: K1–K16

*Was `bug/bug_v1.067.md` ("Bug Log — v1.067 (built 2026-10-31, not released: waits for its drill, #28)") until 2026-11-05.*

### Fixed in v1.067

| # | Defect | Fix | Test |
|---|---|---|---|
| K1 | **A run where the AI never answered said "done".** With a refused key, a used-up quota or no network, every folder failed in its own row ("API key not valid…"), but Phase 2 logged "done — awaiting review" and showed no alert. `plan.ai_error` was set only when the client could not be created, and a dead key creates a client fine. Measured live with a well-formed fake key. Old since the alert was added (F7, 2026-06-04); it became serious in v1.067, because the key field is now hidden and the user has nowhere to look. | **KEY_EMBED point 4.** `analyzer.ai_down_fields` reads the FULL exception: 401/403/key-invalid = withdrawn; day quota (`PerDay` quota id, or the local daily cap) = used up for today; other 429 = busy right now. The row's 200-character cut loses the quota id, so this is read before the cut. Phase 2 names a key-level failure in one line even when other folders got through, with "N of M folders were not analyzed". A permanent failure stops the remaining calls; those rows read "skipped: AI unavailable". A non-key failure is flagged only when nothing got through. The alert is one line, and the folders can still be named by hand. | `test_ai_down_is_read_from_the_full_error`, `test_phase2_says_when_ai_is_unavailable_and_stops_calling_a_dead_key` (counts the calls). Each turned red when the classification was removed. |
| K2 | **Ctrl+Shift+K did not reveal the key field when tested with a key event.** A synthetic Tk key event on Windows arrives with keysym `??` and proves nothing. Rebinding on the K key's code fixed it, proven with a real key press. | **Superseded by KEY_EMBED:** the built-in key now wins, so a revealed field would save a key that is never used. The shortcut was removed. `_reveal_key` stays unbound until Nick decides on a "use my own key" option. | — |
| K3 | The installer showed "Saving API key..." on every install. The uninstaller asked "Also remove your config (API key)?". Both were leftovers of the key page. | The step shows only when a key is passed. The uninstaller now asks "Also remove your settings?". | Found by grep over every visible string; checked by picture. |
| K4 | **The v1.066 → v1.067 drill would have stopped at its busy step.** The kit runs `Set-AppBusy` on the CANDIDATE (`Invoke-Drill.ps1` ~l.281). HPO's adapter made the app busy by blanking the saved key, so the app opened Settings at start. From v1.067 the built-in key wins and Settings never opens by itself, so the kit would throw "could not make the app busy". Found by reading the kit before any drill ran. | `updater.take_drill_busy_marker`: in drill mode only, a `drill-open-settings` marker in the user data dir makes the next start open Settings once, and it is deleted. `hpo.ps1` `Set-AppBusy` drops it, and `Restore-AfterBusy` removes a leftover. | `test_drill_busy_marker_opens_settings_once_and_only_in_a_drill`. On the BUILT exe, with a temp profile and drill mode: the marker made Settings open and was consumed, and the next start without it did not open Settings. |
| K5 | The free-tier notice in Settings was cut off at the right edge. A `wraplength` is scaled with DPI × UI Scale while the dialog is not: 640 overflowed at 125 %, and 460 still overflowed at UI Scale 1.3. | Broken by hand into three short lines. | Pictures at UI Scale 0.7, 1.0 and 1.3. |

### Found by the independent review (3 read-only reviewers, 2026-10-31), all fixed before commit

| # | Defect | Fix | Test |
|---|---|---|---|
| K6 | **The HTTP-code regex in `ai_down_fields` held two BACKSPACE bytes** where `\b` belonged, written by a Python patch run through a Bash-tool heredoc, which turned a doubled backslash into a single one (the same heredoc turned this very sentence's example into nonsense the first time it was written). It never matched a code. The tests passed because "permission_denied", "unauthenticated" and "resource_exhausted" appeared in the same test messages. | Anchored to where google-genai puts the code: `^\s*(401\|403\|429)\s+<status>`. An `OSError` is never classified. The source guard now refuses control bytes in `.py/.spec/.json/.mjs/.js`. | Code-only cases ("403 Forbidden", "429 Too Many Requests"). Names holding 403/40317/429 are not key failures. |
| K7 | **The key guard read the working tree, not the index.** If a key was staged and then deleted (or edited out) on disk, the guard passed and the commit held the key. The hook also ran the guard inside the suite import, which skips on any import error (fail OPEN). Masked keys and commit messages were not looked at. | `tools/key_guard.py`: staged blobs via `git cat-file --batch`; both shapes, plus the registered key plain and masked; fails CLOSED. Run first and on its own by `pre-commit`, and by a new `commit-msg` hook. The build stages the masked copy outside the repo and removes it. `*.key` is ignored. Stale "secrets/" guidance removed. | `test_key_guard_reads_what_is_staged_and_fails_closed`; the real hooks were driven on the real index: a staged key that had been deleted gave exit 1, a key in the message gave exit 1, and clean input gave exit 0. |
| K8 | **A tier or model saved for an old paid key misfired on the free one.** A saved "paid" tier (no throttle) ran the shared free key unthrottled into per-minute 429s. A model with no free quota got 429 `limit: 0`, which was reported as "used up for today" every day. | While the built-in key is in use, any tier is held to the free limits, and AI Health says so. `limit: 0` reads "choose another model in Settings" (permanent). | `test_the_built_in_key_is_throttled_as_free_whatever_tier_was_saved`, plus the `limit: 0` case. |
| K9 | **The v1.066 → v1.067 drill would have failed `real_update_path`.** `Get-FromRouteEvidence` knew only v1.065's test-repo breadcrumbs. In drill mode v1.066 reads the loopback feed, so its breadcrumbs name 127.0.0.1. `drill.json` still named FROM v1.065 and route `repo-env`, and README step 2 still published to the test repo. | Feed patterns for route `feed`; `from` = v1.066 (sha256 `93c4d69c…`, the released asset); README updated. | Read against v1.066's `updater.py` and the kit. Proven only by the drill itself. |
| K10 | **A transient reason hid the permanent one.** Results arrive in completion order: a "busy right now" seen first was what the one-line message said, while "used up for today" was what stopped the run. | The permanent reason wins. | The phase-2 test's `[minute, day]` case. |
| K11 | VERSION was still 1.066, so the candidate would have called itself 1.066, and the kit would wait for 1.067 while the feed offered it again (a loop). | VERSION 1.067, and the bundle was rebuilt (its VERSION was checked). | — |
| K12 | The kept own-key path could not work: a key saved from the field would never be used, because the built-in key wins. | A key saved from the field sets `use_own_key`, which lets it win. An old key merely sitting in auth.json does not. | Cases in `test_api_key_is_the_built_in_one_then_the_saved_one`. |

### Realigned to the written house standard (memory/KEY_EMBED.md, synced d790295)

The Director's first note said "the built-in key wins" and asked for no visible own-key path. The written
standard says the opposite on both counts, and it also asks for the key in plain text. v1.067 now follows the
written standard:

- **The user's own saved key wins; the built-in key is the fallback (§4).** The `use_own_key` flag from K12 is
  gone: with saved-first it has no job.
- **Ctrl+Shift+K is back (§4 names it).** It uses the binding proven with a real key press under K2.
- **The key ships in PLAIN text (§1).** A masked key hides from the gate's byte scan, so a paid key masked in by
  mistake would pass. The mask and the guard's masked-key needle were removed.
- **The `AQ.` shape is matched from 30 characters, with the gate's lookbehind**, as `tools/release-gate.mjs`
  matches it.
- **The AI-down line says whose key failed** (`processor.ai_down_line`):
  - the built-in key: "update when a new version is out";
  - your own key: "press Ctrl+Shift+K in Settings";
  - no internet: said as such.
- **`drills/drill.json` sets `"embeds_key": true`**, so the gate refuses a receipt that does not prove the key.
- **The key is registered** (`tools/register-key.mjs free`, project `Happy-Photo-Organizer`, `--no-billing`).

### The house answer: the built-in key is the ONLY key (KEY_EMBED §4, Nick 2026-10-31)

Nick told the Director: no own-key field in any app. The built-in key is the only key, and every path that reads a
pasted or stored key goes. Asked in HPO's chat, he said not to use the key saved in the system at all, and to follow
the rule fully (it is the same account anyway). Removed:
- `auth.get_api_key()` returns the built-in key only. `get_saved_api_key`, the own-key fallback and the unused
  `save_config(api_key, …)` are gone.
- Settings has no key field, Paste/Show, Test button, Ctrl+Shift+K or "Enter a key first".
- `main` no longer opens Settings when no key is set (only for the drill's marker), and no longer blocks a run with
  "Open Settings to enter your key". A keyless test build sorts the photos, and Phase 2 says in one line that AI is
  unavailable.
- The phase-2 lines name only the shared built-in key. The own-key lines that pointed to Ctrl+Shift+K are gone.
- The installer's dead key-save block and its `api_key` attribute are gone.
- A guard, `test_no_key_entry_path_is_left_in_the_app`, was driven red on the previous settings.py.

Why it mattered for v1.067 itself: Nick's PC and the ship PC have an old `api_key` in auth.json from the old key page.
With own-key-first they would have kept spending that key, not the built-in one.

### The drills (process bugs, not app bugs)

- **K13 - Run 2's key check read as "key broken" when the PC had no internet.** The receipt said
  `embedded_key_works FAIL ... error: [Errno 11001] getaddrinfo failed`: the PC's Wi-Fi had dropped to the SSID "epsonCL", which
  had no internet at that moment, and the request never left the machine. The verdict was right (no proof, so no pass), but the line did not
  say why.
  - **Fix: in the master kit (a458b00, adopted).**
    - With `embeds_key`, `Test-ApiReachable` (DNS + TCP 443, 5 s) runs before anything is installed. A dead network
      throws "no network for embedded_key_works" in seconds instead of after nine minutes.
    - A network error in the evidence reads `could not check (no network): …` and still FAILs.
  - The adapter wording I added first (`could not reach Google (DNS)`, 901fe9e) was removed. The kit's wording matches
    the same error, so the receipt would have said it twice.
  - Tested in PS 5.1:
    - run 2's real evidence reads as no network;
    - a 403 and a pass do not;
    - the probe passes on this PC now and names DNS for a bad host.
  - Two gaps sent to the Director:
    - Windows socket errors (WinError 10060/10061) are not caught;
    - a 504 "timed out", where Google did answer, is.
- **K14 - My re-stage broke the running run 3.** Nick pressed RUN-ALL at 23:31:47. At about 23:33 I re-staged to ship
  the K13 adapter. My guard looked for the lock at `C:\Users\Public\Drills\drill-busy.txt`, but the house lock is
  `C:\Users\Public\drill-busy.txt`, so the guard saw nothing.
  - Stage-Drill's `Remove-Item -Recurse` deleted `from/`, `kit/`, `out/logs/` and `feed-state.json` from under the
    live run, and stopped only at the transcript, which the run held open. It was the second time today; at 21:5x
    it stopped harmlessly on its first file.
  - Run 3 went on (the transcript shows `embedded_key_works PASS`, status 200), but every log write failed.
    `no_update_loop` counted from a feed log I had deleted, so its PASS proves nothing.
  - **Run 3 is void as release evidence.** It needs a run 4.
  - **Rule from now on:** before any re-stage, the lock at `C:\Users\Public\drill-busy.txt` is free AND `HPO.cmd` is
    still waiting (a missing HPO.cmd means a run took it).
  - **The check is now executable:** Stage-Drill refuses while the house lock names this app with a live pid. That is
    the master at 2567c46, fixed at d12865e to read both lock line shapes; adopted.
  - Tested in PS 5.1 with the guard lifted from the file: it refused on the LIVE run-3 lock
    (`Happy Photo Organizer | pid 31716 | drill | ...`) and on the runner's form, and let a dead pid, another app or
    an empty lock through.
- **K15 - The publish gates wrote into Nick's real app logs (tooling, not shipped).** Publishing v1.067 (00:15)
  left `UPDATE CHECK 1.066 ...`, `UPDATE CHECK 0 ...` and FOUND lines in `~/.happy-photo-organizer/logs/update.log`.
  It also left the re-download's breadcrumbs in `%TEMP%\happy-photo-organizer-updater.log`, finishing at 00:29:30.
  - Those are the two files a person reads after a failed update. v1.066's publish did the same at 13:21.
  - The test suite also wrote the updater's breadcrumbs into that real `%TEMP%` file. Only `update.log` was
    redirected.
  - **Fix:** `tools/publish_release.py` wraps the two gates that run the app's updater in `app_logs_elsewhere()`.
    It turns off update.log lines (the switch the drill's reference install uses), sends the breadcrumbs to
    `%TEMP%\hpo-publish-gates.log`, and puts both back afterwards.
  - The suite redirects `updater._LOG_PATH` and the gate log to its temp dir.
  - **Proof:**
    - the new test `test_the_publish_gates_keep_the_apps_own_logs_clean` was red on the old script and is green
      now;
    - a live `--check 1.067 --previous 1.066` passed with 0 new lines in Nick's update.log or breadcrumbs, and 2
      in the gate log;
    - a full suite run added 0 lines to the real gate log.
- **K16 - I adopted master kits without running the HPO suite.** 80052c3 put an em dash (3 non-ASCII bytes) into
  `drills/kit/DrillKit.psm1:12`, and `test_the_drill_scripts_are_plain_ascii` has been red since 2ef2821.
  - I ran only PS 5.1 tests for 80052c3, ae8d478 and 51ddc0f. Run 4 passed on it, because it is a comment.
  - Sent to the Director for a master fix (master-first; drills/kit is not edited alone).
  - **Rule:** every kit adoption runs the full suite before its commit.

## Bug 5 — 2026-11-01 — v1.068 — L1 a burst across midnight, L2 a daily cap above 500 (fixed in v1.069)

*Was `bug/bug_v1.068.md` ("Bug Log — v1.068 (released 2026-11-01 08:46)") until 2026-11-05.*

v1.068 changed only the used-up-quota line (`log/log_v1.068.md`). K15, the publish gates writing into Nick's logs,
was fixed in `tools/` and is recorded in `bug/bug_v1.067.md`.

### Found 2026-11-01 by the README/CODEMAP accuracy check — FIXED in v1.069 (`log/log_v1.069.md`)

Nick, answering "Fix L1 and L2 as v1.069 with its drills?": "Fix as v1.069". Both are fixed red-first:
- `test_grouper_midnight_bridge_does_not_pull_the_next_day_in` for L1;
- the 15/5000 and 15/500/1M cases in `test_the_built_in_key_is_throttled_as_free_whatever_tier_was_saved` for L2.

The text below is as filed, when they were still open.

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

### Checked and cleared during the same pass

- **The frozen build carries `tzdata`** (`dist/HappyPhotoOrganizer/_internal/tzdata`). So `usage_log.PT_TZ` is the real
  America/Los_Angeles zone in the app, not its fixed UTC-8 fallback. The usage day and `processor.quota_back_at` agree
  on the reset hour.
