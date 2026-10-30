# UPDATE_DRILL — no update drill, no release (command_pattern #28)

> **Master copy:** `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\UPDATE_DRILL.md`. Every repo gets a mirror at
> `memory/UPDATE_DRILL.md` through `sync-rules-to-projects.ps1`. Edit the master only.
> **The lock:** `tools/release-gate.mjs` (a PreToolUse hook on Bash/PowerShell) refuses to publish without a passing
> receipt. It reads the lists in this document from its own `PROFILES` table, so change both together.

## 0 · Why this exists

On 2026-10-30, EMR v0.5.3 went out as "the app updates itself". Its own release report said **"NOT done: a drill of the
packaged exe"**. That same evening the update did this on Nick's PC:
- it renamed his EMR folder on the Desktop to `…_previous`;
- the new build appeared as a **second folder**;
- the old folder kept the icon's place, and Nick opened the old build from it.

Nick: *"how can something this basic be missed — it looks unprofessional."*

It was not the first time. SHARED_LESSONS → *Build / Release / Auto-update* holds the same class, project after project:
- installers hoarded until the disk filled;
- an "applied" flag written before the install, which poisoned the updater for ever;
- comparators that left the whole fleet on "already up to date";
- builds merged to main that never reached a user.

**Every one of them broke at a step that nobody had run: the OLD, PACKAGED build updating ITSELF to the new one, on
a machine laid out the way the user's is.** Unit tests, source drills and "the zip's SHA matches" all pass while that
step is broken. So it is now a gate, not a sentence.

**Counted on 2026-10-30.** Three read-only agents went through every repo's records, git log and updater code.
- **75 update, install and release failures** across the house: SM 27, HPO 14, EMR 11, PLC 10, JobShot 5, and others.
- **47 reached users**, and **30 were found by Nick in the field**.
- **28 are still pinned by no test.**
- By stage: release-publish 12 · install 11 · data/settings 8 · old-version removal 6 · check 6 · version compare 5 ·
  download 5 · relaunch 4 · permissions 4 · single-instance 3 · file-lock 2 · verify 2 · bootstrap 2 · other 5.
- The recurring shapes are below.
  - **The old updater decides whether the new one arrives**, so every fix works only from the release after it.
  - **The old-process → installer → new-process handover is never tested end to end.**
  - **A silent install with no log makes busy, failed and never-ran look the same.**
  - **A guard is added on the path where the bug was seen, and the sibling path is left.**
  - **User data does not survive the update.**
  - **Leftovers are nobody's job.**
  - **Publishing is a manual shell ritual whose failures are swallowed.** Piping `gh` through `tail` reported an
    HTTP 408 as success.
  - **"Could not check" is reported as "up to date".**
  - **Four hand-made updaters, and no shared conformance test.**

What the code reading added:
- **Four apps update themselves, and the updater was hand-written four times.** SHIP-MONITORING uses Inno Setup.
  EMR uses a zip and a batch swap. HPO and PLC each have their own installer. No code is shared, so every fix
  learned in one is rediscovered, or not, in the others.
- **None of the four has ever had a test or scripted drill take an OLD packaged build and update it to a NEW one.**
  Every launch, relaunch, single-instance and leftover failure was found **in the field, after release**:
  - SM v1.531 (the installer died inside the app), v1.545–v1.547 (the relaunch quit at its own mutex), v1.564;
  - EMR v0.5.3 (the second folder; the swap batch writes no log);
  - PLC v0.1.12→v0.1.14 (mixed-version bytes, a silent exit) and v1.6.1 ("did not open by itself").
  - HPO has no record of its silent upgrade ever being run.
- **Defects known today, each of which a drill catches on its first run:**
  - HPO and PLC verify no hash on some paths (PLC skips the SHA on an exact-size resume);
  - HPO and SM never delete files the old version shipped;
  - PLC deletes the old version before copying the new one, with no rollback;
  - PLC has no single-instance guard;
  - EMR's swap waits on a folder rename that Windows allows while the exe runs;
  - EMR cannot parse the compact `vX.NNN` shape at all, which needs a bridge (#14.7);
  - three apps write no log for the install stage.

## 1 · The rule in one paragraph

Before any build can reach a user, the **previous released build** must update **itself** to **exactly these bytes**.
Users are reached by: a GitHub release, an asset upload, a draft made public, or an `adb install` to a real phone.

The drill runs:
- from the real release file, installed the way users have it, with the shortcuts they have;
- through the **real update path**;
- with every check in §4 passing.

It writes `drills/<version>.json`, the receipt, with the SHA-256 of every published file, next to its own log. The lock
refuses `gh release create/upload/edit` and `adb install` for any file with no passing receipt **for those exact bytes**.
- A receipt for another build does not count.
- "I tested it from source" does not count.
- Only Nick can waive it, once per tag (§8).

## 2 · Install layout — what every desktop app must look like (#28.2)

Most of the field failures are layout failures: things that cannot happen if the app lives where Windows expects apps
to live.

| Rule | Why |
|---|---|
| **One fixed install folder per user**, e.g. `%LOCALAPPDATA%\Programs\<App>\`, created by an installer or by the app's first run. **Never run from the Desktop, Downloads, a USB stick or a folder whose name carries a version.** | A folder on the Desktop *is* the user's icon. Renaming it moves the icon, and so does a second folder. |
| **Shortcuts (Start menu, and Desktop if wanted) are made by the installer or first run and point at that fixed path.** An update never renames or moves the folder a shortcut points at. | A renamed folder takes the user's icon with it. Whether a `.lnk` follows a renamed target depends on the case (shell link tracking). EMR measured one that resolved to the original path, which held the new build. Never renaming the folder makes the question moot. |
| **An update replaces the app in place**: same folder, same exe name. A rollback copy, if kept, lives out of sight (`%LOCALAPPDATA%\<App>\rollback\`) and is deleted after the new build has started cleanly. | The user must never see two copies or have to choose between them. |
| **User data lives outside the install folder** (`%LOCALAPPDATA%\<App>\data\` or a folder the user chose), never inside it. | Replacing the app must not be able to touch the data. |
| **One download location**, swept on the ordinary start path (SHARED_LESSONS `an-updater-hoards-what-it-downloads`). | Disks fill on ships. |
| **Exactly one instance** (a named mutex). The updater waits for the app to exit; it never kills work in progress. | Two copies fight over files; a killed app loses typing. |
| **Moving an existing install into this layout is itself a release that must pass the drill FROM the old layout.** | The migration is where the mess happens. Users on the old layout must end with one app, working shortcuts and their data, through their own updater. |
| **A migration moves everything keyed to the old path, and retires the old folder last.** That covers Desktop and Start-menu shortcuts, taskbar pins, autostart entries and firewall rules, which are keyed to the exe path. It deletes the old folder only after two things hold. First, the new shortcut reads back to the fixed path. Second, no process runs from the old folder, checked by executable PATH, because the old and new copies share one exe name. Every step resumes on the next start, and the migration never overwrites a newer install. Files the app did not ship are never deleted, and the user is told, in plain words, which folder still holds them. | A half-done move is found by the user, weeks later, on a ship. A folder left behind without a word is the same "two folders" complaint. |

An installer (Inno Setup, per-user, no admin) is the simplest way to meet this table, but it is not required. A
self-updater that keeps the table is fine. What is required is the table.

## 3 · The updater contract — what the app must expose so a drill can run it

1. **A loopback feed override.** The updater reads its release feed from a local URL when both of these are set:
   - `HAPPY_UPDATE_DRILL=1`;
   - `HAPPY_UPDATE_FEED=http://127.0.0.1:<port>/…`, which **must be loopback**.

   The feed answers in the same shape as the real one (GitHub `releases/latest` JSON plus the asset). This lets the
   drill serve N, a corrupted N, and a fake N+1 without publishing anything. In any other case the override is ignored.
2. **A "check now" start.** For example, a `--check-update-now` argument, or the drill env above makes the first check
   happen at start, so the drill needs no clicks.
3. **An update log, one line per stage**, in a fixed file (`<data dir>\logs\update.log`):
   - `<ISO time> UPDATE <STAGE> <version> <detail>`, with STAGE in CHECK · FOUND · DOWNLOADED · VERIFIED · REFUSED · STAGED · HANDOVER · SWAPPED · CLEANED · FAILED;
   - and on **every** start: `<ISO time> STARTED <version> <exe path>`.

   The drill reads the version and every outcome from here, and so does Nick's next bug report.
4. **Version readable without the UI**: the `STARTED` line, or the exe's file-version resource.

## 4 · The checks — the receipt must carry every one for its profile

Each check is `{"result": "pass" | "fail" | "n/a", "evidence": "<what was measured, with the log line or listing>"}`.
- `pass` needs evidence.
- `n/a` needs a reason, and is refused outright for the checks marked ⛔.

| id | What must be true after the update | desktop-self-update | desktop-manual-install | android (adb or Play) |
|---|---|---|---|---|
| `start_from_released_build` | The drill began from the **real previous release file**, its SHA-256 recorded as `from_artifact_sha256`, installed the way users have it. | ⛔ | ⛔ | ⛔ |
| `real_update_path` | The update went through the path users take: the old build's own updater, the installer over the top, or `adb install -r`. Not a hand copy. | ⛔ | ⛔ | ⛔ |
| `new_version_running` | The running build reports the new version, from the `STARTED` line or versionCode. | ⛔ | ⛔ | ⛔ |
| `one_process` | Exactly one process of the app. | ✓ | ✓ | — |
| `one_install` | Exactly **one** copy on disk: no second folder, no visible `_previous`, no leftover versioned folder after the cleanup window. Exactly one Uninstall entry (HKCU + HKLM) if the app registers one. On Android, one package. | ⛔ | ⛔ | ⛔ |
| `tree_matches_fresh_install` | The updated install folder, hashed file by file, **equals a fresh install of N**, except for an allowlist (logs, caches). This is Mozilla's "update verify" method: it catches files the old version left behind, mixed-version trees, and user data written into the install folder. | ✓ | ✓ | — |
| `shortcuts_open_new` | **Every** shortcut the user had (Desktop, Start menu, pinned) resolves to the new exe and opens the new version. | ⛔ | ⛔ | — |
| `relaunched_itself` | The app came back without the user, in the intended mode (window or tray). | ✓ | — | — |
| `user_data_intact` | Settings and data are byte-identical (hash before and after), or a documented migration was verified field by field. | ⛔ | ⛔ | ⛔ |
| `no_update_loop` | The new build, fed itself again, is **not** offered an update. | ✓ | — | — |
| `sees_next_release` | The new build, fed a fake N+1, **is** offered it. The chain is not broken. | ⛔ | — | — |
| `bad_download_refused` | A corrupted or mismatched asset is refused (`REFUSED` logged), and the old build keeps running and stays usable. | ✓ | — | — |
| `unknown_is_not_no` | With the feed unreachable (or answering 403/500), the app says it **could not check**. It must never say "up to date". Three apps got this wrong. | ✓ | — | — |
| `same_signing_key` | The new APK is signed with the same certificate (`apksigner verify --print-certs`). | — | — | ⛔ |
| `version_code_increased` | versionCode is strictly greater than the previous release's. | — | — | ⛔ |

✓ = required, n/a allowed with a reason · ⛔ = required, never n/a · — = not in this profile.

Add a check when a new failure class appears. That means adding it here **and** in `release-gate.mjs` `PROFILES`.

## 5 · The drill, step by step

1. **FROM.** The version users actually run, normally the current Latest release. If the field may be older (a ship
   PC whose version nobody has read), find out first: Nick reads it from the app. Until then, also drill from the
   oldest version that could still be in use. An unknown field version is never assumed to be the Latest. Download
   its release file and record its SHA-256.
2. **A clean machine state.** Use a separate local **standard** (not admin) Windows user account named `drill`.
   - Windows 11 Home has no Sandbox and no Hyper-V.
   - A per-user install in another account cannot touch Nick's real one.
   - A standard account also proves the update needs no elevation; a hang at a UAC prompt is a fail.
   - Creating that account is Nick's one-time step: an account is not something Claude creates.
   - If a field PC's profile path has a space or non-ASCII (Thai) characters, give the drill account the same kind
     of name. An ASCII `drill` cannot catch a quoting bug in a swap script.
     Read the field PC's username (and its version, folder and whether its Desktop is redirected) BEFORE Nick
     creates the account, or it may have to be created twice.
   - **`drill` cannot read Nick's profile.** `C:\Users\NickSuksanTr` is open only to SYSTEM, Administrators and
     Nick, and that is where the repos, the release files and the per-user Python and node live (EMR measured,
     2026-10-30). So write the harness in PowerShell, or check first that its runtime is reachable from `drill`.
     Stage its inputs (FROM and TO release files, fixtures, the harness) in a folder `drill` can read, such as
     `C:\Users\Public\<App>-drill\`, and remove that folder afterwards. Every user on the PC can read it, so
     never stage a key, token or password there. Copy the results back into the repo from Nick's side.
   - For a per-machine app, or a release that changes the install mode, use a VirtualBox VM with a snapshot.

   ⚠ **Run the harness OUTSIDE the Claude desktop app.** Claude's shell runs inside an MSIX container that
   virtualises `%LOCALAPPDATA%`, so checks made from it can PASS on files that are not really there (memory note
   `msix-shadow-localappdata`). Start the harness as a scheduled task under the `drill` account, or from a plain
   PowerShell window, and read its result file back. Sanity check: write a marker from the harness and confirm it
   from a second, unpackaged shell.

    Install FROM exactly as
   users do, with the same shortcuts. Run it once, then load fixture data. Record:
   - the hashes of every data file;
   - every shortcut's target;
   - the install file list.
3. **Serve TO** through the loopback feed (§3.1) and trigger the update through FROM's own path. Drill **each** path
   the release enables: the automatic one and the button, and **every delivery route** the field uses. SM, for
   example, has two: the Server updates from GitHub, and every station updates from its Server. Each check's
   evidence names each route. A route that cannot be drilled yet blocks the release; it is not a footnote. For an auto-install, also drill it with the app busy (a
   dialog open, text typed). It must wait, not interrupt.
4. **Wait out the cleanup window**, then measure every check in §4 and copy the evidence lines into the log.
5. **Failure injection.**
   - Serve a corrupted TO: it is refused, and FROM keeps working.
   - Serve TO to TO: there is no offer.
   - Serve a fake TO+1: it is offered.
6. **Write the receipt** with the drill script, never by hand, as `drills/<version>.json`, with the log at
   `drills/logs/<version>.log`. Then run `node tools/release-gate.mjs --validate drills/<version>.json`. Commit both,
   then publish.
7. **Publish with the project's publish script, never by hand.** The script must do all of these:
   - call `node tools/release-gate.mjs --check --tag <tag> <assets>` first, and stop on a non-zero exit. With
     `--tag`, a bridge release can reach Nick's one-shot note (§8) through the script; the note is consumed right
     there, so a publish that then fails needs a new note;
   - check **every** exit code (never pipe `gh` through `tail`/`head`/`Select-Object`, which swallows the failure);
   - go draft → upload → publish;
   - read the release back through the same endpoint the field reads (`/releases/latest`) and assert it has exactly
     the drilled asset, re-downloaded, **with the receipt's SHA-256**. A release with no asset, or the wrong one,
     is a failed release.

**Android (`android`, sideloaded with adb or delivered by Play).** On the emulator:
- install the FROM APK (its release file) and create real jobs;
- `adb install -r` the TO APK;
- assert versionCode, job count and content, and the same signing certificate;
- launch, and check there is no FATAL in logcat.

Only then `adb install -r` the exact drilled file to Nick's phone, written literally, or run the Play upload.
Never `flutter install`, `flutter run --release` or `gradlew install…Release` to the phone: they rebuild, so the bytes
on the phone are not the drilled ones, and the lock refuses them. For Play, the FROM is the APK from the previous uploaded bundle (`bundletool build-apks --mode=universal`). The lock allows emulator installs, so the drill itself is never blocked.

## 5a · The shared harness — one drill kit, not four

Four hand-written updaters are why every lesson had to be learned four times, so the drill must not be four
hand-written scripts too.
- The house kit is: a loopback fake-releases server with Range support, fault switches (truncate, flip a byte,
  500, drop) and a JSONL access log as the oracle for "no loop" and "sees N+1"; plus one runner that reads a
  per-project `drills/drill.json` manifest and writes the receipt.
- The manifest holds: `exe_name`, `process_model` (pyinstaller onedir/onefile), `install_scope`, `install_dir`,
  `user_data_dir`, the sentinel files that must stay byte-identical, the expected shortcuts, the version probe, the
  relaunch expectation (window/tray), the update trigger, the tree-diff allowlist and the timeouts.
- Until the kit exists, a project's own drill script must produce the same receipt. The lock reads only the
  receipt.

## 6 · Receipt format — `drills/<version>.json`

```json
{
  "schema": "update-drill/1",
  "profile": "desktop-self-update",
  "app": "EngineMaintenanceReport",
  "from_version": "0.5.3",
  "from_artifact_sha256": "<64 hex: the previous release file>",
  "to_version": "0.5.4",
  "assets": [{ "name": "EngineMaintenanceReport_v0.5.4.zip", "sha256": "<64 hex: exactly what is published>" }],
  "drilled_at": "2026-10-31T09:00:00Z",
  "machine": "NICKSUKSANTR, Windows user 'drill'",
  "layout": "v0.5.3 installed at %LOCALAPPDATA%\\Programs\\EMR via its own zip/installer; Desktop + Start menu shortcuts",
  "drill_log": "drills/logs/0.5.4.log",
  "checks": { "one_install": { "result": "pass", "evidence": "dir listing: exactly 1 EngineMaintenance* folder; no _previous" } }
}
```

## 7 · Bootstrap — the one release that cannot be drilled before it ships

A drill serves N through the loopback feed override (§3.1). **No shipped build has that override today**, so N-1 cannot
yet be pointed at a candidate without publishing it. Do not redirect `api.github.com` with the hosts file: that needs
a trusted TLS certificate, which means installing a root CA, which is a system security change.

So each app crosses **once**, in this order:
1. A **bridge release** carries the smallest set that has to cross together: the §3 contract, the tolerant
   comparator if the version shape is changing, and whatever cannot ship separately without a second undrillable
   crossing. EMR's bridge, for example, also carries its in-place swap and the layout migration.
   **Before it ships, drill everything the OLD build can already reach through another real path.** For example,
   a folder/USB update road that runs the same install code, or an installer it can launch. That covers install,
   swap, migration, relaunch, shortcuts, data and tree. Only what no shipped path can reach (normally the check and
   the download) is left for the after-the-fact drill. A second delivery route counts too. SM's stations update
   from their own Server, not from GitHub. A released station pointed at a local candidate Server reaches the
   bridge before it is published.
2. It ships on **Nick's one-shot waiver**, with this written in its notes: *bridge, not drilled before release*.
3. Within the hour, it is **drilled after the fact**: a `drill` account on the previous release updates itself
   through the real channel, and every §4 check is recorded in `drills/<version>.json` with
   `"bootstrap": true`. A failure means the fix ships at once, on the same waiver road.
4. **From the next release on, every release is drilled before it ships, with no exceptions.**

If the app's updater already has an override that can point at a separate public test repo (HPO's
`HAPPY_UPDATE_REPO`), the bridge itself can be drilled first against that repo. Do that instead of the waiver.
Declare the repo in `drills/drill.json`, giving `"drill_repo": "<owner>/<name-with-drill>"` and
`"release_repo": "<the real one>"`. The lock then lets `gh release … --repo <drill_repo>` through without a
receipt, because that upload IS the drill. It refuses the same command against any other repo. It also refuses
a `drill_repo` whose name lacks "drill" or that equals the real repo.

## 8 · What the lock does, and does not, do

- **Blocks**:
  - `gh release create` with installable assets, or without assets on a non-draft;
  - `gh release upload` of an `.exe/.zip/.msi/.msix/.apk/.aab/.7z`, or of anything passed as a variable;
  - `gh release edit --draft=false | --latest | --prerelease=false`;
  - `gh api` POST/PATCH/PUT on releases;
  - `adb install` to anything but an emulator, also when adb or the APK is reached through a variable
    (`"$ADB" … install`, `adb install $APK`);
  - `flutter install`, `flutter run --release|--profile`, `gradlew install…Release` and `bundletool install-apks` to
    anything but an emulator: they put bytes on a phone that no receipt can be matched to;
  - a `*deploy*` / `*upload*` / `*promote*` script that calls the Play Developer API (`androidpublisher`);
  - a `*publish*` / `*release*` script that publishes (gh release, the releases API by hand, adb install, Play) but
    does not itself call `node tools/release-gate.mjs --check <assets>`.
- **Allows**:
  - drafts;
  - emulator installs;
  - reading releases;
  - editing notes;
  - a heredoc body or PowerShell here-string that only writes text, such as a chat_log entry that names
    `adb … install` in a table. A body fed to a shell or to `iex` is still read as commands.
- **Waiver: Nick's one-shot note.** `~/.claude/release-approval.json` holds `{"tag":"vX","reason":"…","expiresEpochMs":…}`
  and is consumed on use. Claude writes it only on Nick's explicit words for that tag. The hook reads it when the tag
  appears in the command. A publish script reads it through `--check --tag <tag> <assets>`.
- **What it cannot catch, stated rather than implied.** A receipt written by hand to get past it, which the rule
  forbids. And a release made outside Claude Code: GitHub's website, or a terminal Nick runs himself. The lock catches
  forgetting, not fraud. Like the agent-cap hook, it **fails open** if `node` cannot run. A debug `flutter run` or
  `gradlew installDebug` onto a phone also passes: that is development, not a release. It still replaces the app on
  that phone when the debug build shares the package name.
