# Bug Log — v1.066 (built 2026-10-31, not released: waits for its drill, #28)

## Fixed in v1.066 — the update-path defects found 2026-10-30 (`bug/bug_v1.058-v1.065.md`)

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

## Still open

| # | Defect | Plan |
|---|---|---|
| U8 | `data/job_catalog.json` is user data inside the install tree (UPDATE_DRILL §2). The installer merges it, and the drill allowlists it. | Its own drilled release after v1.066: move it to `~/.happy-photo-organizer/`. |

## Found in development — v1.066's own defects, caught by the smoke test of the built installer

| # | Bug | Fix | Test |
|---|---|---|---|
| S1 | **A failed install was not remembered, so it looped.** The installer rolled back and relaunched the old build. That build found the same release, downloaded 90 MB and handed over again, every few minutes, on any PC where that install cannot succeed (path too long, a file held open, a full disk). The same happened when the installer never ran at all (blocked, crashed). | The app writes `logs/update-attempt.json` at HANDOVER. The next start settles it: the version asked for came up → cleared; anything else → failed (the installer adds its reason). A failed version is not downloaded or handed over again by itself. The button shows `Retry vX`, its dialog shows the reason, and a newer release is not held back. An app from before v1.066 cannot read the record, so after a failed install the installer relaunches it with `HAPPY_UPDATE_REPO` pointed nowhere for that one session. | `test_a_handover_that_does_not_come_up_is_recorded_once_as_failed`, `…came_up_or_a_newer_one_clears_the_attempt`, `test_a_failed_version_waits_for_retry_and_a_newer_one_does_not`, `…handover_writes_the_attempt_before_the_installer_runs`, `test_a_failed_silent_upgrade_says_why_and_never_hands_straight_back` |
| S2 | Staging past Windows' 259-character path limit failed with a `FileNotFoundError` naming a file that is plainly in the payload. Nothing was changed, but the log gave no reason. Measured: the smoke test's long scratch folder + `.update\new\` (12) + the payload's longest path (130). | `install_swap.too_long()` names it: "path is too long for this update: N characters … Windows allows 259". | `test_a_path_too_long_to_stage_is_named_as_such` |

Not covered by the drill (stated in `drills/drill.json` `not_covered`): S1's paths are unit-tested only, and the drill runs the success path.

## Found in development — the test suite ran the real installer over Nick's install

| # | Bug | Fix | Test |
|---|---|---|---|
| T1 | **The suite downloaded the published installer and ran it over Nick's real install.** `test_manual_check_marks_itself_as_checking` (since v1.050, 2026-09-24) builds a worker that says it is v1.049. It polled the **real** GitHub and found the published release. Its fake host runs callbacks inline, so the background thread went on: download 90 MB into `~/.happy-photo-organizer/updates` → run `--silent --upgrade`. The thread's `sys.exit(0)` ended only that thread, and the suite passed. Measured 2026-10-31 with a 200 ms process watcher: `HappyPhotoOrganizerSetup-v1.065.exe --silent --upgrade` started mid-suite, and Nick's running HPO was replaced by a fresh one 20 s later. The breadcrumb log shows real downloads from suite runs at 00:57, 06:37 and 06:47 that day. Any installer up to v1.065 does `taskkill /F`, so every networked suite run since v1.050 could kill Nick's running app and re-extract his install. Checked afterwards: v1.065 still installed (1,898 files), catalog 177 jobs (that installer merges it), pairing data untouched. The Desktop shortcut is present; U7 means any old installer would re-create it. | `tests/test_core.py` fences itself at import: `urlopen` reaches loopback only (the JobShot server tests need it), `updater.cache_dir()` is a temp folder, and `updater.launch_installer_and_exit` raises. A test that needs the real launch calls `_REAL_LAUNCH_INSTALLER` with `Popen` patched. | `test_the_suite_cannot_reach_the_internet_or_run_an_installer`; the suite re-run under the process watcher showed no new HPO process |

## Found in development — the drill harness's own bugs, caught by its tests before any run

| # | Bug | Found by |
|---|---|---|
| H1 | `return ,$out` pipes an array as one object: `Read-UpdateLog \| Where-Object` never matched, so every log-based check would fail. | The feed test (Start-FakeFeed never saw "listening") |
| H2 | `$m` (a regex match) overwrote `$M` (the manifest): PowerShell names are case-insensitive. The taskbar-pin fixture did nothing. | The adapter test |
| H3 | `auth.json` as a byte-identical sentinel: the app rewrites it (window position) on every start, so `user_data_intact` would always fail. | Reading `main.py` while writing the fixtures |
| H4 | A feed that failed to start stayed running and held the port; the next run failed with no reason. | The feed test's second run |
| H5 | Route evidence could take a `SUCCESS` line from an earlier, real-repo download. | The adapter test |
| H6 | Logs read with `File.ReadAllLines` throw a sharing violation while another process appends. | Code review of the reader during the H1 fix |
| H7 | `.gitignore`'s `*.log` hid `drills/logs/<ver>.log` and `<ver>.update.log`: the receipt would be committed without its `drill_log`, and the lock refuses that in every other checkout. Fixed with `!drills/logs/*.log`, and `Collect-Drill` now exits 1 naming any collected file git ignores. | JS, relayed by the Director (UPDATE_DRILL §5 step 6); the scratch test now covers it (22/22) |
