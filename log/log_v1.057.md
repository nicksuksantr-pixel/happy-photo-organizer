# Log — v1.057 on

A rolling file (#7): one `## Entry N — date — v1.0xx — title` per version (v1.057 has two). At 20 entries the
next version starts a new `log/log_v1.0xx.md`; when a third file starts, the oldest leaves the repo.
Until 2026-11-05 each version had a file of its own. They were joined here unchanged apart from their headings:
each version's own sections now sit one level down, under its entry.

## Entry 1 — 2026-09-26 — v1.057 — the folder it never remembered

Nick: *"เวลาเปิดปิดหรืออัพเดทโปรแกรม ช่องโฟเดอร์ที่เลือกไว้ไม่จำ เลยต้องเลือกใหม่ทุกครั้ง เลยทำให้งานๆอื่นๆงงไปด้วยว่าทำไมส่งไม่ได้"*
— close, reopen or update HPO and the destination box is empty again, which then
makes everything else look broken, the phone included.

Three places choose a destination: the Step 1 **Choose Destination** button, the
pairing dialog, and the drop-zone JobShot import. **Only the last two ever wrote
it down** — and nothing read it back. `__init__` set `self.dest_root = None` and
left it there.

The second half of his sentence is the expensive half. The LAN receiver is built
with `dest_root=lambda: self.dest_root`, so after every restart the phone was
told *"no destination folder chosen on the PC yet"* — an honest report of an
empty variable, about a folder that had never moved. That is why sending failed
for no visible reason, and why the fix belongs in the same release as the thing
it breaks.

### What shipped
- One `_set_dest()` that every picker calls, so all three remember.
- It writes **two** keys: the per-vessel `dest_roots[SHIP]` and a ship-independent
  `last_dest_root`. The second one is there because **Nick renamed his vessel
  today**, from "Nick" to "ENA Test" — with only the per-vessel key, renaming a
  ship loses a folder that never moved.
- `_restore_dest()` at startup: per-vessel first, then the PC-wide fallback,
  and **never a folder that is not there any more** — an unplugged drive says so
  on the label in amber rather than coming up "ready" and failing on the first job.

**The update case is safe**, and it was checked rather than assumed: the config
lives in `~/.happy-photo-organizer/auth.json` while the installer only extracts
into `%LOCALAPPDATA%\HappyPhotoOrganizer`. It is not in the blast radius that ate
14 job names in v1.044 — that was `job_catalog.json`, which sits inside the
install tree.

## Entry 2 — 2026-09-26 — v1.057 — the review, and the regression I had just written

Two of the three reviewers refused to ship it, and the first finding was mine,
one hour old.

**Restoring the destination broke the per-vessel destination.** `_jobshot_dest`
opens with `if self.dest_root: return self.dest_root`. That was harmless while
`dest_root` was None on every fresh start — the next line read the job's own
manifest and used *that vessel's* remembered folder. The moment startup began
restoring a value, the early return swallowed the lookup: a job handed over on a
USB stick from another vessel would have been filed into **this** PC's tree,
silently. The Wi-Fi path refuses a foreign ship outright (*"ship X — this PC
files for Y"*); the hand-drop path has no such guard, so the destination was the
only thing standing up. It now reads the job's vessel first, files into that
vessel's folder when it has one, says so, and **does not** adopt it as this PC's
destination.

**A save that fails now says so.** `auth.update_config` and
`jobshot.remember_dest_root` *return* failure — they do not raise it — so the
`try/except` I wrapped them in was dead code and both return values were
discarded. On a locked or read-only config the app would have logged a green
"Destination set" and forgotten it again: Nick's original bug, wearing a success
message.

**And the two tests I wrote first did not pin the wiring.** They call
`_restore_dest` and `_set_dest` directly, so deleting the call from `__init__`
brings his exact bug back with both green. The structural check is in now, over
`__init__` and both pickers.

### Verification
- `tests/test_core.py` **132 → 134**. Every new test proven **red** first: the
  remembered-destination pair against the old code (`KeyError 'dest_roots'` —
  nothing was ever written), and the foreign-vessel test against the ordering as
  it stood an hour ago (it filed ENA Challenger's job into this PC's folder).
- **Confirmed by Nick on his own machine, 2026-09-26: "จำค่าแล้วครับ"** — the
  destination survives a restart. That is the behaviour confirmed, in words.
  The window itself he has still not shown me: v1.056's "Start a new batch"
  button has never appeared in a screenshot, so by the v1.051 rule that change
  is still unfinished even though this one is done.

## Entry 3 — 2026-10-02 — v1.058 — a BOM no longer un-pairs the phone or forgets the folder

*Entries 3–10 were `log/log_v1.058-v1.065.md` ("Log — v1.058 → v1.065 (2026-10-02 → 2026-10-30)") until 2026-11-05.*

**Backfilled on 2026-10-30** under rule #20.0. `log/` had stopped at v1.057 while
seven more versions shipped. One short entry per version, written from git log,
the GitHub release notes and `CHANGELOG.md`. The detail lives in those, and in
`docs/CHAIN_CHECKLIST.md` and `docs/PARKED.md`.

- v1.044's BOM fix (`utf-8-sig`) had reached three readers and stopped there.
  `core/auth.py` and `core/catalog.py` still read a BOM file as corrupt and returned
  a default. The cost was silent: the API key, the pairing token and the remembered
  destination all lost, or a catalog of 0 jobs instead of 174.
- Found by asking JobShot's question of my own code: where else does this happen?
- Both readers fixed. Test red first. 137/137.

## Entry 4 — 2026-10-02 — v1.059 — a full month now says so
- `filed.date_was_capped` is `true` when every day of the month was taken and the job
  shares a day number. It is a notification only, on Nick's approval (*"แค่แจ้งเตือนเฉยๆทำได้เลย"*).
- The month length comes from `monthrange`. The frozen `filed` shape test fired, and
  EMR confirmed before the key existed. 138/138.

## Entry 5 — 2026-10-02 — v1.060 — correct a filed report without re-sending a photograph
- LAN_PROTOCOL v1.1, the sidecar route: `POST /jobshot/v1/sidecar` replaces a report
  draft on a filed job, in place. Re-uploading had turned 7 photos into 14.
- The gate: a name must be in that job's own `filed.extras`.
- Three-reviewer pass before release, 7 fixes, each red first. 157/157.

## Entry 6 — 2026-10-02 — v1.061 — never shipped
- Never published, and it has no tag. Commit `0cdcc14` ("v1.061 never shipped")
  records why. Its fixes went out in v1.062.

## Entry 7 — 2026-10-03 — v1.062 — interrupted writes and damaged records
- The manifest beside a draft is written temp + fsync + replace, like the draft.
- A damaged job record no longer answers exactly like a job never filed: the §4 404
  carries `unreadable_records`.
- Three temp-file leaks closed.
- First release through `tools/publish_release.py` (eight gates, each proven to refuse). 166/166.

## Entry 8 — 2026-10-23 — v1.063 — "offline" no longer reads "Up to date"
- `_fetch_latest_release` swallowed network errors into `None`, the same value as
  "nothing newer", so a PC with no internet said "Up to date (1.062)". Now it raises
  `UpdateCheckFailed`, and the button says "Updates: offline". 172/172.
- Found by applying SM's `not-known-is-not-no` lesson to this repo.

## Entry 9 — 2026-10-30 — v1.064 — a job sent twice no longer erases anything
- A resend never overwrites an earlier arrival's `emr-<id>.json` / `job-<id>.json`.
- The latest arrival is the job's record (arrival order read from the names).
- The sidecar route writes report drafts only, and an upload never files `report_history.json`.
- The §4 404 carries `unreadable_records`, which JobShot reads from v0.045.

## Entry 10 — 2026-10-30 — v1.065 — the "was this filed?" check waits for a job that is landing
- Root cause of duplicate jobs: the §4 probe answered 404 while a job was still being
  filed, and the phone re-sent it. Now the probe waits up to 20 s, then answers 200,
  or 404 if the filing failed, or 409 `receiving` if the job is still arriving.
- LAN_PROTOCOL v1.1.1: `X-JobShot-Job-Ids` holds the probe from the first byte. The
  header is a hint only and never a reason to refuse. 189/189.
- On the ship PC since 21:09 the same day (read from Nick's phone, JS `fb2d69f`).

## Entry 11 — 2026-10-31 — v1.066 — the bridge release: an update you can prove

*Was `log/log_v1.066.md` until 2026-11-05.*

**RELEASED 2026-10-31** (tag `v1.066` at `d31b5c7`), after drill run 3 passed every check (`drills/1.066.json`).
The drill updated the released v1.065 to these exact bytes, `93c4d69c9c2346882d8c38eb27051a269be23e1b4f2d387a68a5636328b0579b`.
Published through `tools/publish_release.py`: the lock passed, then the release was read back from outside. The
digest is the drilled file, a re-download hashes the same, and the app offers it to a v1.065 user.

**Asked:** *"Go. Start building v1.066 and the drill harness now. I'll set up the drill account, the scheduled
task and the test repo later."* (Nick, 2026-10-30.)

### What changed in the app (U1–U7, U9, U10 from `bug/bug_v1.058-v1.065.md`)

- **U2 — no installer runs unless its bytes are the published ones.** The app takes only the asset named
  `HappyPhotoOrganizerSetup.exe` (the first-`.exe` fallback is gone), refuses a release whose asset has no GitHub
  `digest`, hashes the download (`REFUSED` + delete on a mismatch, and that tag+hash is not fetched again), and
  hashes it once more right before running it. The download URL must be https on the real feed.
- **U5 — an update waits while the app is busy.** Busy = a batch running, a phone job arriving (from its first
  byte: `jobshot_server.do_POST` counts it), Step 3 holding folders that are not filed yet, or any dialog open (native message boxes and pickers too
  since R4: Tk keeps firing timers inside them).
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

### The drill harness (`drills/`, UPDATE_DRILL §5a)

- `drills/kit/` is generic (no HPO name): `Invoke-Drill.ps1` (runner + receipt), `FakeFeed.ps1` (loopback
  releases server: Range/206, faults `truncate`/`flip`/`500`/`drop`, JSONL access log), `DrillKit.psm1`,
  `Stage-Drill.ps1` / `Collect-Drill.ps1` (the Public exchange folder, with a secret scan).
- `drills/drill.json` + `drills/hpo.ps1` hold everything HPO-specific.
- Guards: refuses any account not named like `drill*`, an administrator, a FROM whose SHA-256 is not the
  released v1.065, an account that already has HPO; takes `C:\Users\Public\drill-busy.txt` (one drill at a time,
  UPDATE_DRILL 5.2, added by the Director the same night).

### How it was checked

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

### The drill, staged (2026-10-31, on Nick's go: "เอาเลย")

- **Test repo:** `nicksuksantr-pixel/hpo-update-drill` (public, created 10:00). Release `v1.066` "drill v1.066" carries
  the candidate as `HappyPhotoOrganizerSetup.exe`. Read back: `releases/latest` = v1.066, GitHub digest
  `sha256:bf7f2efd…c79a1`, and a re-download hashes the same. The candidate was not rebuilt: no app source is
  newer than the onedir build.
- **FROM:** v1.065 downloaded from the real release; sha256 `46902c79…bccb88` = `drill.json`'s `from.sha256`.
- **Staged** at 10:01:40 into `C:\Users\Public\HPO-drill`, with the launcher at `C:\Users\Public\Drills\HPO.cmd`.
  - The secret scan passed.
  - `drill` can write the stage: `INTERACTIVE` has Modify, inherited from `C:\Users\Public`.
  - The house runner was already running a pass inside `drill`: ShipMonitor's drill held the lock, and EMR had
    failed in 0.2 min. The runner rescans after each launcher, so HPO joins that pass and needs no new double-click.
- **If the candidate is rebuilt:** its sha256 changes, so replace the asset on the test repo and re-stage.
  Otherwise v1.065 downloads the old bytes, and the receipt cannot match the file being released.

### Drill run 1 (10:05–10:35): FAIL, and the bug it caught (D1)

**What ran and what failed:**
- **The route worked, all while the drill session was disconnected.** v1.065's own updater asked the test repo,
  downloaded v1.066 (91,686,951 bytes) and launched the installer.
- **v1.065 then never exited.** pystray's thread is not a daemon, so the handover's `sys.exit(0)` waits for ever in
  `threading._shutdown`.
- The v1.066 installer no longer force-kills (U4). It waited 60 s and logged `FAILED … still open`. Evidence:
  `drills/logs/1.066-run1.*`.
- **Every installer up to v1.065 hid this with `taskkill /F`.** Shipped as it was, v1.066 would freeze every v1.065
  install about a minute after each start.

**reviver round 1 on the same diff:** score 1, and all three firms found D1 independently. R2–R7 are in
`bug/bug_v1.066.md`; their fixes wait for Nick.

**D1 fixed (Nick agreed):**
- The silent upgrade ends exactly the process that started it, after a 20 s grace. It is matched by PID, exe path and
  creation time, and walks up through the one-file bootloader to find it.
- v1.066 runs the tray on a daemon thread of its own, and stops the tray and the receiver before handing over.
- **Five tests.** Two use real processes. The tray test fails in 20 s when `run_detached()` is put back (mutation check).

**Also, the coverage guard caught a gap.** `test_the_invisible_byte_guards_still_cover_every_kind_of_file_here` had
been red since `drills/` was committed: the earlier 220/220 run came before those files were tracked.
- `.ps1`/`.psm1` are now scanned by `test_the_drill_scripts_are_plain_ascii` (the kit's ASCII rule, measured: 6 files,
  0 non-ASCII bytes).
- `.log`/`.jsonl` (drill evidence) are exempt, with the measured reason.

**The rebuilt candidate, re-uploaded and re-staged (11:17):**
- 91,698,416 bytes, sha256 `ba55637f4fc58869e90f5c69ce489cf27e239ee8a2124bd5484e54c4fe355ed1`.
- Checked that the fix is inside the built archives (PyInstaller CArchive/PYZ read back):
  - the app's `core.tray` starts a `daemon` thread named `tray`, and `run_detached` is gone;
  - the setup carries `handover_parent`, `end_handover_parent` and `HANDOVER_GRACE_S`.
- `--fresh-into` a scratch folder: exit 0, 1,899 files, VERSION 1.066. Nick's registry entry stayed 1.065, and no
  `logs` folder appeared in his profile.
- Test repo asset replaced: `releases/latest` = v1.066, digest `sha256:ba55637f…`, and a re-download hashes the same.
- Staged into `C:\Users\Public\HPO-drill` + `Public\Drills\HPO.cmd`. The 09:57 runner pass is still open in `drill`, so
  it picks the launcher up after ShipMonitor and EMR.
- Suite: **226/226** under the process watcher: no HPO process started, and no `logs` folder in Nick's profile.

### Drill run 2 (11:57, the D1-only candidate `ba55637f`) and R2–R7

**Run 2:** the bridge went through for the first time.
- The installer logged `HANDOVER 1.066 the app that handed over (pid 31644) had not exited after 20 s; ended it`,
  then `STAGED`, `SWAPPED`, and `STARTED 1.066` at 12:05:28.
- Every check up to the busy step passed: `real_update_path`, `new_version_running`, `start_from_released_build`,
  `one_process`, `relaunched_itself`, `one_install`, `tree_matches_fresh_install` (1,899 files identical),
  `shortcuts_open_new`, `user_data_intact`, `no_update_loop`, `unknown_is_not_no`, `bad_download_refused`,
  `sees_next_release`.
- Its receipt pins `ba55637f`. That build will not ship (R2–R7 change the bytes), so the run is evidence only.
- **It ended at 12:38: 13 pass, 1 fail.** The fail is `waits_while_busy`, and the fault was the harness's, not the
  app's: H8 in `bug/bug_v1.066.md`. N+1 was on the feed before the app came up busy, so the app installed it 2 s after
  starting.
- Seen working in the same run:
  - v1.066's own handover ended by itself, with no "ended it" line;
  - the fake N+1 that came up as 1.066 was recorded once as FAILED and not retried (S1).
- Evidence: `drills/logs/1.066-run2.*`.

**Run 3 is staged with the R2–R7 build `93c4d69c` and the H8 harness.**

**R2–R7 (Nick: "Fix R2–R7 too"):** fixed as tabled in `bug/bug_v1.066.md`. Each has a test, and the app-side ones
were mutation-checked. The harness pieces were tested on scratch copies (14/14 + 31/31).

### Found by smoke-testing the built installer (before any release)

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

### The test suite ran the real installer (T1)

- While checking who started Nick's HPO at 06:39:07 (3 s after a suite run ended, launched by a parent that had
  exited), a re-run with a 200 ms process watcher caught it: `HappyPhotoOrganizerSetup-v1.065.exe --silent
  --upgrade` from Nick's real update cache, mid-suite. Its parent started Nick's HPO again 20 s later.
- The cause was `test_manual_check_marks_itself_as_checking`: a v1.049 worker polled the real GitHub, and the fake
  host ran the download and install inline on a background thread. Every networked run since v1.050 could
  `taskkill` Nick's running app and re-extract his install.
- Fixed in the tests, not the app: no internet (loopback only), a temp update cache, and launching an installer
  raises. Nick's install checked afterwards: v1.065, catalog 177 jobs, pairing data untouched.

### Harness bugs its own tests caught (none shipped)

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
- `*.log` in `.gitignore` hid the drill's own logs (H7, found by JS): `!drills/logs/*.log`, and `Collect-Drill`
  fails on any collected file git ignores.

### Not drilled (stated, not papered over)

- The "Install now" button: in v1.066 it matters only while busy, where it refuses (unit test).
- v1.066's own updater against real GitHub: every check on v1.066 uses the loopback feed; the publish script
  reads the real endpoint back after publishing.
- A failed install (S1): the attempt record, no automatic retry, the Retry button and the pre-v1.066 pause are
  unit-tested only. The drill runs the success path.

## Entry 12 — 2026-11-01 — v1.067 — No key to set up: the built-in free key is the only key

*Was `log/log_v1.067.md` until 2026-11-05.*

**RELEASED 2026-11-01 00:15** (tag `v1.067` at `6875f01`), after drill run 4 PASSED every check
(`drills/1.067.json`). The drill updated the released v1.066 (`93c4d69c...`) to these exact bytes,
`bf807b97243c71b3e3b72239e6275afdd1aab9b63b07eb7c32b87f545d429364`, and proved the built-in key works from the
updated build. It was published through `tools/publish_release.py`, and every gate passed:
- the lock passed;
- the draft was uploaded first, and its asset size was verified;
- after publishing, the copy re-downloaded from `latest` hashes to the drilled file.

**Not drilled, and live on Nick's PC: v1.065 → v1.067.** Nick's PC still ran v1.065, not v1.066. At 00:16 its old
updater found v1.067 and downloaded it, finishing at 00:28:54 (91,707,238 bytes). The drill proves the previous
release (v1.066) updating. A machine on v1.065 skips v1.066 and runs v1.065's old update path with v1.067's
installer. That path was drilled only to v1.066 (the bridge), never to these bytes. The ship PC is also on v1.065.

**It worked on Nick's PC.** Read-only, from his `update.log`:
- 00:29:54 HANDOVER: the stuck v1.065 (pid 12196) was ended after 20 s (D1);
- 00:30:02 STAGED;
- 00:30:10 SWAPPED, 1898 files;
- 00:30:15 STARTED 1.067;
- 00:30:20 "nothing newer";
- 00:30:28 CLEANED.

Afterwards:
- one process, one install folder, no `.update` left;
- both shortcuts point to the updated exe;
- `auth.json` keeps its model, its auto-update setting and the old `api_key` field, untouched and unread.

It is one real machine, not a drill receipt. The ship PC will take the same path.

**Asked:** build Nick's free Gemini key into the app and hide the key page (*"it is a free key"*). Then: the safest
way is that the key never enters git, test the failure cases hard, and send the tests to the Director. Then the
house answer: no own-key path at all (*"don't use the key saved in the system; it is the same account anyway"*).
Detail per change: `CHANGELOG.md` [1.067] · bugs and fixes: `bug/bug_v1.067.md` · day log: `chat_log/chat_2026-10-31.md`.

### What changed in the app

- **The built-in key is the only key** (house rule KEY_EMBED §4).
  - `auth.get_api_key()` returns the bundled key and nothing else.
  - A key an older version saved in `auth.json` is never read, and the file keeps it untouched.
- **No key field anywhere.** The installer, Settings, shortcuts and messages are all clean. A guard test scans every
  string in the app for a key-entry path; it was driven red on the old Settings.
- **Settings says what the free key means:** it is shared by all installs, Google may use the photos, and people
  at Google may look at them. The installer's licence text says the same.
- **AI-down is said in one line and the run goes on without AI.**
  - The cause is read from the full error, with the HTTP code anchored at the start: withdrawn, today's quota,
    busy, or a model with no free quota.
  - A permanent cause stops further calls.
  - No internet is said as such.
  - A local file error is never blamed on the key.
- **The free limits hold whatever tier was saved** while the built-in key is in use.
- **For the drill:** `--check-embedded-key` (drill mode only) writes status, model and fingerprint, never the key.
  The `drill-open-settings` marker makes the app busy.

### How the key is kept out of git

- **Where it lives:** only in `%USERPROFILE%\.embed-keys\Happy-Photo-Organizer.json`. It is registered (free, no
  billing, project Happy-Photo-Organizer), and the registry holds the fingerprint only: `e656add8f927...`.
- **The build:** the spec reads that file, writes the plain key to a temp folder for PyInstaller and cleans it up.
  It refuses to build without a key unless `HPO_ALLOW_NO_KEY=1`.
- **The hooks:** `tools/key_guard.py` reads the STAGED blobs (`git cat-file --batch`) and commit messages, matches
  both key shapes (`AIza`+35, `AQ.`+30) and the registered plaintext, and fails closed. It runs in pre-commit and
  commit-msg.
- **Checked at each build:**
  - the bundled key equals the registered one;
  - there is no plain key in `dist`'s files;
  - the gate's byte scan finds no key in the compressed installer;
  - git history has 0 key-shaped strings.

### How it was checked

- **Tests:** suite 243/243, with fake keys built at runtime.
- **Error cases:** both key shapes; the AI-down causes; a dead key stops calls; the drill marker fires once and only
  in a drill; `--check-embedded-key` is refused outside a drill.
- **The frozen exe under a temp `USERPROFILE`:** the key check gives status 200 and the model from the reply; the
  marker opens Settings once.
- **Settings captured with PrintWindow:** no key field and no Test button, even with an old key saved in the config.
- **An independent read-only review** found K1–K12, all fixed before the commit.

### The drills (v1.066 → v1.067 through the loopback feed)

| Run | Candidate | Result | Why |
|---|---|---|---|
| 1 | 71435e02 (old, own-key path) | 14/15 | `no_update_loop` counted FROM's own feed fetch (kit bug, fixed in master 746d323) |
| 2 | bf807b97 | 14/15 | `embedded_key_works`: `getaddrinfo failed`; the PC's Wi-Fi had dropped to the SSID "epsonCL", with no internet at that moment (K13) |
| 3 | bf807b97 | void | my re-stage deleted the running drill's logs and feed (K14); it hung and Nick ended it |
| 4 | bf807b97 | **15/15 PASS** | the API probe passed before the run; `embedded_key_works` status 200, fp e656add8f927 |

The kit gained these during the day, all landed in the master first and adopted by copy:
- the AQ. secret scan;
- the `embedded_key_works` call;
- the `no_update_loop` window;
- the pre-run API probe and the `could not check (no network)` wording (status-aware);
- Stage-Drill refusing under a live run of the same app;
- a run-level STOP file every wait polls.

### Not drilled (stated, not papered over)

- The real GitHub endpoint for the v1.066 → v1.067 offer: the drill uses the loopback feed. The publish script reads
  the real endpoint back after publishing.
- A real quota exhaustion or a withdrawn key on the shared key: unit-tested with fakes, never live.

## Entry 13 — 2026-11-01 — v1.068 — When the free AI is back

*Was `log/log_v1.068.md` until 2026-11-05.*

**Both field-version drills PASSED 15/15** (#28, UPDATE_DRILL step 1, v3.26): from v1.067 (`drills/1.068.json`) and from v1.065 (`drills/1.068.from-1.065.json`), on the same bytes, sha256 `4345dc38d0072c5128d257991ebeed23bfc30f2bc3280cb7d7130eaf3944ed28`. `release-gate --check --tag v1.068` passed.

**RELEASED 2026-11-01 08:46** (tag `v1.068` at `f482697`) through `tools/publish_release.py --previous 1.067`. Every gate passed: the lock, the draft upload with its size verified, then, read from outside after publishing, `latest` is v1.068, a v1.067 user is offered it, and the re-downloaded asset hashes to the drilled file.

**Asked:** Nick, in this chat, answering *"Build v1.068 so the quota message names the 15:00 reset time?"*: **"Build
v1.068"** (2026-11-01, about 01:15).

### What changed in the app

- **The used-up-quota line says when AI is back, on the PC's own clock.** v1.067 said "try again tomorrow". The free
  tier's daily quota resets at midnight US Pacific: 14:00 in Thailand under US daylight time, 15:00 otherwise. So a
  quota that runs out in a Thai morning is back the same afternoon. It now reads, for example, "AI is back after 14:00
  today".
- `processor.quota_back_at()` works out the next Pacific midnight by hand (the US daylight-time rule), so the app needs
  no tz database.

### Step 0 — the rubric walk before the first drill (0 agents)

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

### Field versions (drill.json `field_versions`)

| Version | Where | Read | Drill |
|---|---|---|---|
| 1.067 | Nick's PC | 2026-11-01, his update.log: STARTED 1.067 at 00:30:15 | `drills/drill.json`, the loopback feed, receipt `drills/1.068.json` |
| 1.065 | the ship PC | 2026-10-30, V-Log v1.065 (21:09) | `drills/drill.from-1.065.json`, repo-env via the test repo, receipt `drills/1.068.from-1.065.json` |

### The drills

| FROM | Route | Run | Result |
|---|---|---|---|
| 1.067 (`bf807b97...`) | loopback feed | 2026-11-01 01:39:42-01:49:19 | **15/15 PASS**, receipt `drills/1.068.json` |
| 1.065 (`46902c79...`), attempt 1 | repo-env, the test repo | 01:25:49-01:38:51 | 15/15, but filed under the FROM-1.067 log name, so not a receipt (the Director's ruling); kept as `drills/logs/1.068.from-1.065.run1.*` |
| 1.065, attempt 2 | repo-env | 02:00:10 | FAIL in 6 s at the pre-run probe: DNS could not resolve the Gemini host, nothing installed (`run2-no-network.runner.log`); the Director measured the network fine at 02:04, so a resolver blip |
| 1.065, attempt 3 | repo-env, kit fafc0e7, `-ReceiptName 1.068.from-1.065` | 08:31:30-08:43:13 (11.7 min) | **15/15 PASS**, receipt `drills/1.068.from-1.065.json` |

Attempt 3 was run on Nick's go ("Re-run it", 2026-11-01 about 08:30), after the lock, the stage, the runner and the test repo were checked:
- the test repo's latest was v1.068, `4345dc38`, 91,707,491 bytes;
- the drill lock was free and `HPO.cmd` was absent.

What it showed:
- v1.065's own updater fetched `api.github.com/repos/nicksuksantr-pixel/hpo-update-drill/releases/latest` at 08:32:01 and handed over;
- v1.068 started itself at 08:34:26, as one process in one install folder;
- the 1900 files are identical to a fresh install (allowlist: `uninstall.bat`, `job_catalog.json`);
- the shortcuts open the new exe;
- `auth.json` and the job data are unchanged;
- the built-in key answered 200, fp `e656add8f927`.

Every log is named by the receipt name, and the receipt's `drill_log` is `drills/logs/1.068.from-1.065.log`. No key shape appears in any receipt or log.

**Stale wording, not a defect of the run:** two `not_covered` lines in `drill.json` have named v1.066 since the bridge (ad00773), where they mean the version being drilled to: "v1.066's own updater against real GitHub: every check on v1.066 runs through the loopback feed" and "the 'Install now' button: in v1.066 ...". `drill.from-1.065.json` copied them. The receipts for v1.067 and v1.068 carry them as written and were not edited (#28). After the release, both manifests were reworded to "the updated version's own updater" and "since v1.066", so the next drills say it right. The Director then found the same old meaning in `drills/README.md` ("Not drilled here"), checked that no other repo or the master kit carried it, and the README was brought up to date: one drill per field version, the v1.065 route through the test repo, `embedded_key_works`, the `drill-open-settings` busy step, and commands that read the versions from `VERSION` and `drill.json`.

### In the field

**Nick's PC, v1.067 → v1.068, read-only from his `logs\update.log`:**
- 08:50:48 SWAPPED, 1898 files;
- 08:50:50 STARTED 1.068;
- 08:50:55 "nothing newer";
- 08:51:02 CLEANED (the rollback copy was removed).

It took four minutes after publishing and needed no click. This is the route drilled in `drills/1.068.json`. The ship
PC (v1.065) is not read yet; its route is the one drilled in `drills/1.068.from-1.065.json`.

### After the release: README + CODEMAP + a docs gate (rule #15; no version, no build, no drill)

**Asked:** Nick, in the Director chat (about 09:2x), after he asked "why is there no CODEMAP": "Both of them".
- **Item 1, here:** README, CODEMAP and a docs gate in HPO.
- **Item 2, the Director's:** the same check in the house release gate.

**Why it was missing:** GitHub history starts at v1.027 with no README. PROJECT_SUMMARY.md took the README's place,
and it froze at "v1.057" because nothing made it move. Rule #15 (2026-06-09) never reached this repo's records.

#### What was added

- **`README.md`** with the five #15.2 blocks:
  - the name and purpose;
  - the stack and `**Version: v1.068**`;
  - run, build, and the release order;
  - one line per feature;
  - the doc map.
- **`docs/CODEMAP.md`:**
  - layer A is hand-written: 61 rows of task → file → entry point;
  - layer B is generated: 41 modules with their public names and first docstring lines.
- **`tools/gen_codemap.py`**, a repo-local generator:
  - same markers and bullet shape as the house one, plus each module's first docstring line;
  - `--check` writes nothing and exits 1 with the command to run;
  - console output is ASCII;
  - why repo-local: the house generator maps only `features/` folders and would empty layer B here, and a gate must
    not read outside the repo (#22). The Director agreed.
- **57 one-line docstrings** where layer B found none (#15.4):
  - 52 were added by 3 agents, each on its own files, docstrings only;
  - 5 were mine, in `tools/publish_release.py`;
  - checked mechanically: every changed `.py` has an AST identical to HEAD once docstrings are removed, and the diff
    is added lines only;
  - one agent's edit had dropped a space in 5 code lines (AST-equal, so only the diff showed it); I restored them.
- **Gate 5 in `publish_release.local_gates()`**, after `gate_version_agrees`:
  - `gate_readme_names_this_version` refuses unless README.md has exactly one `**Version: vX.XXX**` line equal to
    `VERSION`, and names the line to fix;
  - `gate_codemap_is_fresh` loads the generator in-process, refuses a stale layer B or missing markers, names
    `python tools/gen_codemap.py`, and writes nothing.
- **`PROJECT_SUMMARY.md` stays as history,** with a "frozen 2026-11-01" banner pointing to README and CODEMAP.
  `RELEASE.md` got a banner too: its per-release steps are old notes.

#### How it was checked

- **Tests:**
  - `test_the_readme_gate_refuses_a_readme_still_on_the_previous_version` covers a previous version, no line, two
    lines, a missing file, and a BOM pass;
  - `test_the_codemap_gate_refuses_a_stale_map_and_names_the_command` covers stale → refused, fresh → passes, code
    moved → refused with the check writing nothing, and no markers → refused;
  - each test is red with its gate swapped for a no-op;
  - suite 247/247.
- **The house gate's view** (`release-gate --check --tag v1.068`, v3.27 docs check): exit 0.
- **An independent accuracy check:** 2 read-only agents tried to refute every README sentence (66 claims) and every
  CODEMAP layer A row (50). They found 29 problems, and all were fixed. Among them:
  - the build prerequisites (pyinstaller 6.20.0, pywin32, node, gh);
  - the release order;
  - stale doc pointers (RELEASE.md, GEMINI_LIMITS.md, log/ and bug/ coverage);
  - the update.log path;
  - "aims for" 10–25 KB;
  - rows pointing at a mechanism instead of the decision: digest verify in `update_worker`, install timing, where the
    10/25 numbers and the 90-min gap are really set, the prompt constant, `discard_assignment`, two Pacific-day
    computations, the installer's own colours and paste;
  - five missing rows: button states, the update button, the EN translate prompt, the pre-flight estimate, window
    state.
- **Two findings are app bugs:** L1 (a midnight burst pulls the next day in) and L2 (a custom RPD above 500 is not
  clamped with the built-in key). Both were reproduced and are filed OPEN in `bug/bug_v1.068.md`, not fixed here. The
  README names both.
- **Not done:** no build. `dist/` is now older than the docstring edits by mtime, so the next release rebuilds anyway.

## Entry 14 — 2026-11-01 — v1.069 — The next day keeps its own folder

*Was `log/log_v1.069.md` until 2026-11-05.*

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

### What changed in the app

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

### Step 0 — the rubric walk before the first drill (0 agents)

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

### The build

- `python -m PyInstaller HappyPhotoOrganizer.spec --noconfirm --clean`, then `python installer/build_installer.py`.
- The bundle's `VERSION` is 1.069.
- **The key:**
  - there is one bundled `gemini.key`, whose fingerprint `e656add8f927` equals the registered key;
  - no other file in the app folder holds the key or anything key-shaped;
  - the setup's bytes hold neither.

### Field versions (drill.json `field_versions`)

| Version | Where | Read | Drill |
|---|---|---|---|
| 1.068 | Nick's PC | 2026-11-01, his update.log: STARTED 1.068 at 08:50:50 | `drills/drill.json`, the loopback feed, receipt `drills/1.069.json` |
| 1.065 | the ship PC | 2026-10-30, V-Log v1.065 (21:09) | `drills/drill.from-1.065.json`, repo-env via the test repo, receipt `drills/1.069.from-1.065.json` |

### The drills

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

### In the field

**Nick's PC, v1.068 → v1.069, read-only from his `logs\update.log`:**
- 10:52:41 DOWNLOADED, then VERIFIED (sha256 `6cb565fc…`) and HANDOVER;
- 10:52:48 STAGED, 1898 files;
- 10:52:54 SWAPPED;
- 10:52:56 STARTED 1.069.

That is four minutes after publishing, with no click: the route drilled in `drills/1.069.json`. The ship PC (v1.065)
is not read; its route is the one drilled in `drills/1.069.from-1.065.json`.
