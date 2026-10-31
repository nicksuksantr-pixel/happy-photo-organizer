# Happy Photo Organizer — update drills (#28)

No release ships until a drill has updated the **previous released build** to **the exact bytes** being released,
laid out the way users have it, and every check in `memory/UPDATE_DRILL.md` §4 passed.
`tools/release-gate.mjs` refuses `gh release` without a passing `drills/<version>.json` for those bytes.

| Path | What it is |
|---|---|
| `kit/` | The generic drill kit (no HPO names) — see [kit/README.md](kit/README.md). |
| `drill.json` | HPO's manifest: folders, shortcuts, user data, the released FROM and its SHA-256, the test repo. |
| `hpo.ps1` | HPO's adapter: how to install FROM, which user data to plant, how to make HPO busy. |
| `<version>.json` | A receipt, written only by the runner. |
| `logs/<version>.*` | The drill's own log, HPO's `update.log`, the fake feed's access log, the run transcript. |

## Nick's one-time setup

The account exists (Nick, 2026-10-31): `drill`, a standard user, profile `C:\Users\drill`, **no password**.
Measured by the Director: `LimitBlankPasswordUse = 1` and Remote Desktop off, so Windows lets it sign in only at
the keyboard. Every run is **Switch user**, done by Nick, never `runas` and never a scheduled task (UPDATE_DRILL 5.2).

1. **Read the ship PC:** its Windows username (spaces? Thai characters?), whether its Desktop is redirected to
   OneDrive, and the HPO version it runs. If the ship PC runs an older version than v1.065, the drill must also
   start from that version. If its username has a space or Thai characters, a second drill account with that kind
   of name is needed (UPDATE_DRILL 5.2): an ASCII `drill` cannot catch a quoting bug.
2. **How the run starts, as `drill`:** Switch user to `drill`, open Windows PowerShell (not as administrator), run
   `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Public\HPO-drill\run.ps1`, wait for it to end,
   switch back. HPO has a window and the busy check needs a desktop, so the run needs a signed-in session anyway.
3. **For the v1.066 bridge only, a public test repo** `nicksuksantr-pixel/hpo-update-drill` (the name is in
   `drill.json` as `drill_repo`; the lock lets a release go there and nowhere else without a receipt).
   v1.065 cannot read a drill feed, so its own updater must fetch the candidate from a real GitHub repo.
   From v1.066 on, the loopback feed is enough and this repo is not needed.

## Each drill (staged and collected from Nick's account; only the run itself is `drill`)

```powershell
# 1. the candidate, built; the FROM, downloaded from the real release
gh release download v1.065 --repo nicksuksantr-pixel/happy-photo-organizer -p HappyPhotoOrganizerSetup.exe -D "$env:TEMP\hpo-from"
# 2. bridge only, and only on Nick's go-ahead (it publishes the candidate publicly):
#    the candidate on the test repo, so v1.065's own updater can fetch it
gh release create v1.066 --repo nicksuksantr-pixel/hpo-update-drill --title "drill v1.066" --notes "update drill candidate" dist\HappyPhotoOrganizerSetup.exe
# 3. stage where the drill account can read it (no secrets are ever staged)
.\drills\kit\Stage-Drill.ps1 -Manifest .\drills\drill.json -FromSetup "$env:TEMP\hpo-from\HappyPhotoOrganizerSetup.exe" -ToSetup .\dist\HappyPhotoOrganizerSetup.exe -ToVersion 1.066
# 4. Nick starts the run as drill (2A or 2B above)
# 5. when C:\Users\Public\HPO-drill\out\exit-code.txt appears: receipt + logs into drills\, validated, stage removed
.\drills\kit\Collect-Drill.ps1 -Manifest .\drills\drill.json -ToVersion 1.066
```

- **One drill at a time on this PC** (UPDATE_DRILL 5.2): the runner takes `C:\Users\Public\drill-busy.txt` before
  it installs anything, waits (up to `timeouts.lock_wait_s`) while another app's drill holds it, and removes it at
  the end, pass or fail. It never removes a lock it did not take.
- Before the next drill, run `C:\Users\Public\HPO-drill\reset.ps1` **as `drill`** (it refuses in any other account).
- Windows may ask `drill` to allow network access for `HappyPhotoOrganizer.exe` (the phone receiver, because the
  fixture is paired). Cancel is fine: the drill never uses the LAN.

## What a run does

1. Installs v1.065 with its own released setup (`--silent`: default folder, Desktop + Start menu shortcuts,
   Uninstall entry), plants user data: settings with a placeholder key and a pairing token, a filed-jobs receipt,
   a job taught to the catalog, a taskbar pin.
2. Starts v1.065 with `HAPPY_UPDATE_REPO` = the test repo. v1.065 finds v1.066, downloads it and hands over; the
   v1.066 installer waits for v1.065 to exit, swaps the files with a way back, and relaunches.
3. Measures `one_process`, `relaunched_itself`, `one_install`, `tree_matches_fresh_install` (against
   `--fresh-into` of the same setup), `shortcuts_open_new`, `user_data_intact`, `no_update_loop`.
4. Through the loopback feed on v1.066: `unknown_is_not_no` (500 / 403 / dropped), `bad_download_refused`
   (one byte flipped), `sees_next_release` with **the app busy** (Settings open): it must wait, then install once
   the dialog closes (`waits_while_busy`).

## Not drilled here (say so in the release notes, do not paper over it)

- **The "Install now" button.** In v1.066 an update installs by itself once the app is idle; the button only
  matters while the app is busy, where it refuses and says why. That refusal is a unit test
  (`test_the_install_button_refuses_while_busy_and_says_why`), not a drill step.
- **v1.066's own updater against real GitHub.** Every check on v1.066 runs through the loopback feed; the real
  endpoint is read back by `tools/publish_release.py` after publishing (asset name, digest = the receipt's SHA-256,
  and a re-download hashed).
- **A failed install.** The attempt record (`logs/update-attempt.json`), no automatic retry of that version, the
  `Retry vX` button, and a pre-v1.066 app relaunched with its update checks paused for that session are unit tests
  (bug S1 in `bug/bug_v1.066.md`). The drill runs the success path.
