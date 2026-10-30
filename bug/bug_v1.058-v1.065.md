# Bug Log — v1.058 → v1.065

**Backfilled on 2026-10-30** under rule #20.0. `bug/` had stopped at v1.055. One
entry per bug, with the version that fixed it. Detail in `log/log_v1.058-v1.065.md`,
`CHANGELOG.md` and the GitHub release notes.

## Fixed

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

## Open — found 2026-10-30 against rule #28 (`memory/UPDATE_DRILL.md`)

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
