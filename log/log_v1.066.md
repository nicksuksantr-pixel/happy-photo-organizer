# Log — v1.066 (2026-10-31) — the bridge release: an update you can prove

**Built, not released.** Rule #28: it ships only after a drill has updated the released v1.065 to these exact
bytes and `drills/1.066.json` passes. Waiting on Nick for the run as `drill` and the public test repo.

**Asked:** *"Go. Start building v1.066 and the drill harness now. I'll set up the drill account, the scheduled
task and the test repo later."* (Nick, 2026-10-30.)

## What changed in the app (U1–U7, U9, U10 from `bug/bug_v1.058-v1.065.md`)

- **U2 — no installer runs unless its bytes are the published ones.** The app takes only the asset named
  `HappyPhotoOrganizerSetup.exe` (the first-`.exe` fallback is gone), refuses a release whose asset has no GitHub
  `digest`, hashes the download (`REFUSED` + delete on a mismatch, and that tag+hash is not fetched again), and
  hashes it once more right before running it. The download URL must be https on the real feed.
- **U5 — an update waits while the app is busy.** Busy = a batch running, a phone job arriving (from its first
  byte: `jobshot_server.do_POST` counts it), Step 3 holding folders that are not filed yet, or any dialog open.
  The worker re-checks every 60 s and installs on its own once idle. "Install now" refuses while busy and says why.
  The confirm dialog no longer promises that Step 3 survives an update.
- **U3, U4 — the installer replaces the app folder exactly, with a way back** (`core/install_swap.py`):
  wait for the app to exit (mutex, no `taskkill`) → check disk → stage the payload into `.update\new` (zip CRC
  checked) → journal → swap file by file, old files to `.update\old`, lock retries with back-off → prune what the
  old version shipped and the new one does not (only inside the app folder, never a file the installer did not
  put there) → read back → `installed-files.json` → `SWAPPED`. Any failure: roll back, `FAILED`, relaunch the old
  version. An interrupted swap is rolled back by the next run. The new app removes `.update` 10 s after it
  starts (`CLEANED`).
- **U4 — no kill.** The silent upgrade waits up to 60 s for the app to close. Still open with a window: nothing
  is changed. Holding the mutex with no window (a zombie): it goes on, and a locked file rolls it back.
- **U7 — a deleted shortcut stays deleted.** An upgrade re-creates only shortcuts that exist; the Desktop path is
  the shell's real Desktop (it can be redirected to OneDrive).
- **U6, U9 — the §3 contract.** `~/.happy-photo-organizer/logs/update.log`, one line per stage
  (`CHECK FOUND DOWNLOADED VERIFIED REFUSED HANDOVER SWAPPED FAILED CLEANED`) and `STARTED <version> <exe>` on
  every start; `HAPPY_UPDATE_DRILL=1` + a loopback `HAPPY_UPDATE_FEED`; `--check-update-now`;
  installer `--fresh-into <empty dir>` (refused outside a drill).
- **U10 — the publish script.** `tools/publish_release.py` asks `release-gate.mjs --check --tag` before anything
  is tagged (a lock that cannot run refuses), then after publishing checks that the asset's digest is the drilled
  SHA-256, that the app would offer it, and that a re-download hashes to it.
- **U1 — tests.** The installer and the swap are tested for the first time (see below).
- **U8 stays open** (`job_catalog.json` is user data inside the install tree): its own drilled release.

## The drill harness (`drills/`, UPDATE_DRILL §5a)

- `drills/kit/` is generic (no HPO name): `Invoke-Drill.ps1` (runner + receipt), `FakeFeed.ps1` (loopback
  releases server: Range/206, faults `truncate`/`flip`/`500`/`drop`, JSONL access log), `DrillKit.psm1`,
  `Stage-Drill.ps1` / `Collect-Drill.ps1` (the Public exchange folder, with a secret scan).
- `drills/drill.json` + `drills/hpo.ps1` hold everything HPO-specific.
- Guards: refuses any account not named like `drill*`, an administrator, a FROM whose SHA-256 is not the
  released v1.065, an account that already has HPO; takes `C:\Users\Public\drill-busy.txt` (one drill at a time,
  UPDATE_DRILL 5.2, added by the Director the same night).

## How it was checked

- Python suite: see the results line below.
- Harness, on Nick's PC with scratch folders (never `C:\Users\Public`, never Nick's data):
  - **the app's real `core/updater.py` against `FakeFeed.ps1`**: 18/18 — same version → nothing offered; N+1
    offered with its digest, downloaded, hash matches; flipped byte → hash differs; truncated → not accepted and
    the client resumed with Range (206); feed 500/403/drop → "could not check", never "up to date"; asset 500 →
    download fails; the kit parses the app's own `update.log` lines;
  - `hpo.ps1` on a fake layout: 21/21, including the app's own readers (`core.auth`, `core.catalog`,
    `core.jobshot_index`) on what it plants, and `Reset` refusing Nick's account;
  - `Stage-Drill` / `Collect-Drill` on a scratch copy: 19/19, including refusing a planted key;
  - the drill lock: 5/5; a dry run of the runner stops at preflight and the lock's `--validate` reads its receipt.
- The built candidate (`dist/HappyPhotoOrganizerSetup.exe`, 91,686,951 bytes, sha256
  `bf7f2efdf4b4cd08aa2a76bf9703c41c0911b2901c683c2ca10d5c9c202c79a1`; it changes with any rebuild, and the drill
  receipt pins the bytes that ship):
  - both frozen archives (the app and the setup) carry the new update code;
  - `--fresh-into` on a short path (`build\smoke\fresh`): exit 0, 1,899 files, no `.update` left. Nick's
    registry entry stayed 1.065, and no `logs` folder appeared in his profile;
  - **the bridge:** v1.066's payload swapped over a copy of Nick's installed v1.065 tree (1,898 files) →
    `STAGED`, `SWAPPED`, `CLEANED`, and the result is byte-identical to the fresh install (1,896 files compared;
    `uninstall.bat`, `installed-files.json` and the catalog excluded). This is the swap code on its own: the real
    run, through v1.065's updater and the silent installer, is the drill.

## Found by smoke-testing the built installer (before any release)

- **A failed install looped** (S1 in `bug/bug_v1.066.md`). Nothing recorded the failure, so the relaunched old
  build found the same release, downloaded it and handed over again, every few minutes, for good. Now
  `logs/update-attempt.json` is written at HANDOVER and settled by the next start. Failure is assumed until the
  asked-for version is seen running, so an installer that never ran counts too. A failed version waits for the
  `Retry vX` button, and a newer release is not held back. A pre-v1.066 app is relaunched with its update checks
  paused for that session, because it cannot remember a failure.
- **A path too long to stage was reported as a missing file** (S2). The swap already changed nothing; the log now
  says the path is too long, and by how much.
- Found because `--fresh-into` exit 1 in a long scratch folder was reproduced in Python rather than worked
  around: the MAX_PATH error led to the question "and what happens on the next start?".

## The test suite ran the real installer (T1)

- While checking who started Nick's HPO at 06:39:07 (3 s after a suite run ended, launched by a parent that had
  exited), a re-run with a 200 ms process watcher caught it: `HappyPhotoOrganizerSetup-v1.065.exe --silent
  --upgrade` from Nick's real update cache, mid-suite. Its parent started Nick's HPO again 20 s later.
- The cause was `test_manual_check_marks_itself_as_checking`: a v1.049 worker polled the real GitHub, and the fake
  host ran the download and install inline on a background thread. Every networked run since v1.050 could
  `taskkill` Nick's running app and re-extract his install.
- Fixed in the tests, not the app: no internet (loopback only), a temp update cache, and launching an installer
  raises. Nick's install checked afterwards: v1.065, catalog 177 jobs, pairing data untouched.

## Harness bugs its own tests caught (none shipped)

- `return ,$out` sends an array down a pipeline as ONE object: `Read-UpdateLog | Where-Object` never matched,
  so every log-based check would have failed. The readers now stream.
- PowerShell variables are case-insensitive: a `$m` regex match overwrote the manifest `$M`, and the taskbar-pin
  fixture silently did nothing.
- `auth.json` as a byte-identical sentinel would always fail: the app saves its window position into it on every
  start. It is now checked field by field (secrets shown only as a hash).
- A feed that failed to start was left running and held the port; `Start-FakeFeed` now kills it and names the
  cause (exit code, or which pid holds the port).
- Route evidence could take a `SUCCESS` line from an earlier real-repo download; it now requires ask → fetch →
  success in order, from the test repo.
- Not round-tripping the app's JSON through PowerShell 5.1's `ConvertTo-Json` (it can turn an array into
  `{"value": [...], "Count": n}`): fixtures and the busy step edit the text.

## Not drilled (stated, not papered over)

- The "Install now" button: in v1.066 it matters only while busy, where it refuses (unit test).
- v1.066's own updater against real GitHub: every check on v1.066 uses the loopback feed; the publish script
  reads the real endpoint back after publishing.
- A failed install (S1): the attempt record, no automatic retry, the Retry button and the pre-v1.066 pause are
  unit-tested only. The drill runs the success path.
