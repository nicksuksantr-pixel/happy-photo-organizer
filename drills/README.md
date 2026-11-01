# Happy Photo Organizer — update drills (#28)

No release ships until a drill has updated the **previous released build** to **the exact bytes** being released,
laid out the way users have it, and every check in `memory/UPDATE_DRILL.md` §4 passed.
`tools/release-gate.mjs` refuses `gh release` without a passing `drills/<version>.json` for those bytes.

| Path | What it is |
|---|---|
| `kit/` | The generic drill kit (no HPO names) — see [kit/README.md](kit/README.md). |
| `drill.json` | HPO's manifest for the drill from the **previous release** (`from_route` kind `feed`): folders, shortcuts, user data, the released FROM and its SHA-256, the test repo, `field_versions`. |
| `drill.from-1.065.json` | The same manifest for an **older field version**, v1.065 (`from_route` kind `repo-env`: v1.065 has no drill feed, so its own updater fetches from the test repo). |
| `hpo.ps1` | HPO's adapter: how to install FROM, which user data to plant, how to make HPO busy. |
| `<version>.json` | The receipt from the previous release, written only by the runner. |
| `<version>.from-<from>.json` | A receipt from an older field version (`-ReceiptName`; UPDATE_DRILL step 1, v3.26). |
| `logs/<receipt name>.*` | The drill's own log, HPO's `update.log`, the fake feed's access log, the run transcript. |

## Nick's one-time setup

The account exists (Nick, 2026-10-31): `drill`, a standard user, profile `C:\Users\drill`, **no password**.
Measured by the Director: `LimitBlankPasswordUse = 1` and Remote Desktop off, so Windows lets it sign in only at
the keyboard. Every run is **Switch user**, done by Nick, never `runas` and never a scheduled task (UPDATE_DRILL 5.2).

1. **Read the ship PC:** its Windows username (spaces? Thai characters?), whether its Desktop is redirected to
   OneDrive, and the HPO version it runs. Every version still in the field gets its own drill and its own receipt
   (UPDATE_DRILL step 1, v3.26), listed in `drill.json` `field_versions`. If its username has a space or Thai
   characters, a second drill account with that kind of name is needed (UPDATE_DRILL 5.2): an ASCII `drill` cannot
   catch a quoting bug.
2. **How the run starts: one double-click** (Nick, via the Director, 2026-10-31; UPDATE_DRILL 5.2). Switch user to
   `drill`, double-click **Run update drills** (`C:\Users\Public\Drills\RUN-ALL.cmd`), switch back. The very first
   time the button is not there yet: Win+R, that path, Enter, and that run creates it.
   - The house runner runs every launcher waiting there with no keyboard and a deadline, and writes PASS or FAIL to
     `C:\Users\Public\Drills\results.txt`.
   - HPO's launcher is `HPO.cmd`, written by `Stage-Drill`. It runs `reset.ps1`, then `run.ps1`, by absolute path,
     and passes the harness's exit code on (0 only on a pass).
   - It asks nothing of Nick (no `DRILL-NEEDS-NICK`): the fixtures write a placeholder key for a FROM that still
     reads one, and the busy step opens and closes Settings itself (from v1.067 through the `drill-open-settings`
     marker, because the built-in key is the only key).
   - **WATCH mode (Director, on Nick's word, 2026-11-01):** once Nick has started "Run update drills" in `drill`, it
     stays open and runs every launcher the moment it is staged. A Startup shortcut restarts it when `drill` logs
     in, and `C:\Users\Public\Drills\STOP-WATCH` stops it. So **staging IS starting a run**: do not ask Nick to
     click. If `results.txt` shows nothing 2 minutes after staging, tell the Director (the watcher may not be
     running). Re-staging while a run is going is refused by Stage-Drill's lock guard. A wrong stage still runs at
     once, so stage only what should be drilled.
   - Nick switches back while it runs, so the drill runs in a disconnected session. The harness uses no input and
     no screen capture, only `EnumWindows` and `PostMessage`, which work there. That is read from the code; the
     first run's result is the proof.
3. **For a FROM older than v1.066, a public test repo** `nicksuksantr-pixel/hpo-update-drill` (created 2026-10-31
   on Nick's go; the name is in `drill.json` as `drill_repo`; the lock lets a release go there and nowhere else
   without a receipt).
   v1.065 cannot read a drill feed, so its own updater must fetch the candidate from a real GitHub repo. The repo
   served the v1.066 bridge, and since v3.26 it serves every drill from v1.065 while v1.065 is in the field (the
   ship PC). A FROM of v1.066 or later uses the kit's loopback feed and needs no test repo.

## Each drill (staged and collected from Nick's account; only the run itself is `drill`)

```powershell
# 0. the candidate, built; drill.json `from` re-pointed to the previous release (version + SHA-256)
$to = (Get-Content .\VERSION -Raw).Trim()
$prev = (Get-Content .\drills\drill.json -Raw -Encoding UTF8 | ConvertFrom-Json).from.version
# 1. from the previous release, through the loopback feed: the FROM, downloaded from the real release
gh release download "v$prev" --repo nicksuksantr-pixel/happy-photo-organizer -p HappyPhotoOrganizerSetup.exe -D "$env:TEMP\hpo-from"
# 2. stage where the drill account can read it (no secrets are ever staged); also writes C:\Users\Public\Drills\HPO.cmd
.\drills\kit\Stage-Drill.ps1 -Manifest .\drills\drill.json -FromSetup "$env:TEMP\hpo-from\HappyPhotoOrganizerSetup.exe" -ToSetup .\dist\HappyPhotoOrganizerSetup.exe -ToVersion $to
# 3. the WATCH-mode runner starts it by itself; watch results.txt (nothing within 2 min = tell the Director)
# 4. when results.txt has the HPO line: receipt + logs into drills\, validated, stage removed
.\drills\kit\Collect-Drill.ps1 -Manifest .\drills\drill.json -ToVersion $to
# 5. then, one at a time, from each older field version (`field_versions`; here v1.065, through the test repo):
#    publish the candidate on drill_repo as its latest release and read its digest back first
gh release download v1.065 --repo nicksuksantr-pixel/happy-photo-organizer -p HappyPhotoOrganizerSetup.exe -D "$env:TEMP\hpo-from-1.065"
.\drills\kit\Stage-Drill.ps1 -Manifest .\drills\drill.from-1.065.json -FromSetup "$env:TEMP\hpo-from-1.065\HappyPhotoOrganizerSetup.exe" -ToSetup .\dist\HappyPhotoOrganizerSetup.exe -ToVersion $to -ReceiptName "$to.from-1.065"
.\drills\kit\Collect-Drill.ps1 -Manifest .\drills\drill.from-1.065.json -ToVersion $to -ReceiptName "$to.from-1.065"
```

- **One drill at a time on this PC** (UPDATE_DRILL 5.2): the runner takes `C:\Users\Public\drill-busy.txt` before
  it installs anything, waits (up to `timeouts.lock_wait_s`) while another app's drill holds it, and removes it at
  the end, pass or fail. It never removes a lock it did not take.
- The launcher resets the `drill` account before every run (`reset.ps1` refuses in any other account), so a
  failed run never blocks the next one.
- Windows may ask `drill` to allow network access for `HappyPhotoOrganizer.exe` (the phone receiver, because the
  fixture is paired). Cancel is fine: the drill never uses the LAN.

## What a run does

1. Installs FROM (the previous release, or an older field version) with its own released setup (`--silent`:
   default folder, Desktop + Start menu shortcuts, Uninstall entry), plants user data: settings with a placeholder
   key and a pairing token, a filed-jobs receipt, a job taught to the catalog, a taskbar pin.
2. Starts FROM. Its own updater finds the candidate, through the kit's loopback feed (FROM v1.066 on) or the test
   repo (`HAPPY_UPDATE_REPO`, FROM v1.065), downloads it and hands over; the candidate's installer waits for FROM
   to exit, swaps the files with a way back, and relaunches.
3. Measures `one_process`, `relaunched_itself`, `one_install`, `tree_matches_fresh_install` (against
   `--fresh-into` of the same setup), `shortcuts_open_new`, `user_data_intact`, `no_update_loop`, and
   `embedded_key_works` (the updated app makes one real AI call with the built-in key and writes status, model and
   fingerprint, never the key).
4. Through the loopback feed on the updated version: `unknown_is_not_no` (500 / 403 / dropped),
   `bad_download_refused` (one byte flipped), `sees_next_release` with **the app busy** (Settings open): it must
   wait, then install once the dialog closes (`waits_while_busy`).

## Not drilled here (say so in the release notes, do not paper over it)

- **The "Install now" button.** Since v1.066 an update installs by itself once the app is idle; the button only
  matters while the app is busy, where it refuses and says why. That refusal is a unit test
  (`test_the_install_button_refuses_while_busy_and_says_why`), not a drill step.
- **The updated version's own updater against real GitHub.** Every check made on the updated version runs through
  the loopback feed; the real endpoint is read back by `tools/publish_release.py` after publishing (asset name,
  digest = the receipt's SHA-256, and a re-download hashed). A v1.065 FROM's updater does reach real GitHub, but
  the test repo, not the release repo.
- **A failed install.** The attempt record (`logs/update-attempt.json`), no automatic retry of that version, the
  `Retry vX` button, and a pre-v1.066 app relaunched with its update checks paused for that session are unit tests
  (bug S1 in `bug/bug_v1.066.md`). The drill runs the success path.
