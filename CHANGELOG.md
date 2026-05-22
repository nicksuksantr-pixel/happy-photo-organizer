# Changelog

All notable changes to Happy Photo Organizer are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/). Latest on top.

## [1.035] — 2026-05-23

### Fixed (round-3 audit pass — 7 new findings caught after v1.034, all closed)

**MED**
- **BUG-3-1: `JobCatalog.save()` non-atomic.** Same risk class as v1.034's
  `auth.json` / `usage_log.json` fix — `write_text` mid-save could corrupt
  the catalog (138 bundled jobs + every user addition). Now routes through
  `auth.atomic_write_json` (tempfile + fsync + os.replace) with a direct-write
  fallback if the import fails. Especially important during silent-upgrade:
  the installer's taskkill could race with the catalog write that fires after
  Phase 4.
- **BUG-3-2: `JobCatalog._data` mutated without lock.** Phase 4 worker thread
  calls `record_usage` while the Tk thread iterates `names()` / `find()` from
  `_refresh_summary`. RLock now wraps all reads and mutating writes; reentry
  is supported so `record_usage → find/add` doesn't deadlock.

**LOW**
- **BUG-3-3: `ship_label` parameter dropped.** `phase4_rename_folders` accepted
  it but `main.py` never passed it; removed the dead parameter (V2 can add it
  back with a proper Settings field if needed).
- **BUG-3-4: Phase 4 progress callback fired before the rename.** Bar reached
  100% while the last folder rename was still in-flight. Moved `progress_cb`
  to after the work; cosmetic on local disks, visible on network shares.
- **BUG-3-5: Phase 4 merge collision counter unbounded.** A target folder
  pre-populated with thousands of `img_NNN_M` files would force O(N) probes
  per file. Capped at 9999 with a UUID-suffix fallback.
- **BUG-3-6: Empty-destination smart-date allocation inherited EXIF year.**
  A camera with the clock wrong (e.g. year 2050) would produce folders named
  `01-05-50 …` because `detect_target_month` returned None and the assigner
  fell back to per-assignment EXIF year/month. Now defaults to current
  year/month when the destination is empty.
- **BUG-3-7: `_on_window_unmap` used `state()` while sibling methods used
  `wm_state()`.** Aliases in Tk, but mixing them obscured intent. Unified to
  `wm_state()`.

### Fixed (round-3 hygiene)

- **HYG-1: Installer license text said "no auto-update".** Stale since v1.027.
  Updated to reflect the silent zero-click auto-update flow and link the
  correct repo (`nicksuksantr-pixel/happy-photo-organizer`, not the typo
  variant the previous text had).
- **HYG-3: AI Health tier-detail throttle was hard-coded "4.0s/call".** Wrong
  for any tier other than RPM 15 (free Gemini 3.1 Flash Lite). Now uses
  `tier.min_interval_sec` so RPM 10 tiers show "6.0s/call" correctly.
- **HYG-4: Installer `DisplayIcon` registry write set twice unconditionally.**
  The .ico branch was dead. Cleaned to one conditional set.

### Also addressed
- Phase 4 catalog `record_usage` failures now surface via `result.errors`
  instead of silent skip.
- Phase 4 `temp_folder.rmdir()` failure (e.g. stray Thumbs.db created during
  the brief Phase 1→4 window) is now reported via `result.errors` instead of
  swallowed.

### Verified
- syntax-clean across all modified .py
- catalog concurrent-write stress: 5 threads × 30 `record_usage` calls (150
  ops) + interleaved `names()`/`find()` reads — 0 errors
- live launch v1.035: title intact, smoke + auto-update detection confirmed
- audit round 4 (post-fix): 0 regressions

Audit credit: Coddy round-3 independent agent (general-purpose subagent).

## [1.034] — 2026-05-23

### Fixed (deep audit pass — 13 hidden bugs + 8 future risks catalogued, all addressed)

**HIGH**
- **BUG-2 / RISK-4: Non-atomic `auth.json` + `usage_log.json` writes.** Crash
  or power-loss mid-write would corrupt the JSON and silently empty the user's
  api_key / tier / window_state / quota history (`_load()` swallowed
  `JSONDecodeError`). Added `core.auth.atomic_write_json` helper using
  temp-file + fsync + `os.replace` (ENA v2.6.7 pattern). All three callers
  (`save_config`, `update_config`, `usage_log._save`) now route through it.
  Corrupt reads are quarantined as `auth.corrupt-<ts>.json` so the next save
  doesn't overwrite the only forensic evidence. A module-level `_IO_LOCK`
  serializes concurrent writes from the window-state debounce, Settings save,
  and tier-change paths.
- **BUG-1: `_on_available` dropped a newer-tag update mid-download.** The
  v1.033 `in_progress` short-circuit overreached: if GitHub published a newer
  release while a download was running, the new tag was silently ignored. The
  dedup now runs first; a *different* tag arriving during download is stashed
  as `pending_info`. After the current download completes, `_on_ready` checks
  the stash, drops the stale installer, and starts fetching the newer one.

**MED**
- **BUG-3 / BUG-4: `_save_window_state` ran while window was withdrawn**, so
  the tray-Quit path overwrote the correct geometry with Tk's phantom
  withdrawn-state coordinates. Next launch could open at -32000,-32000.
  `destroy()` now skips the save when `wm_state()` is `iconic` or `withdrawn`.
- **BUG-7 / BUG-8: `cancel_event` was not honored by in-flight Phase 2
  workers.** Once `ThreadPoolExecutor.submit` queued a `_worker`, the cancel
  loop only marked pending futures cancelled — already-running calls
  continued through `analyze_group`, including the throttle sleep (up to
  4 s/call on free tier) and the actual Gemini API call. Now: `cancel_event`
  is piped through `analyze_group` → `analyze_image` →
  `RateLimiter.acquire(cancel_event=...)`, and the throttle sleep wakes every
  200 ms to check the flag. `_real_quit()` and `destroy()` both set
  `cancel_event` so quota stops burning the instant the user clicks Quit.
- **BUG-9: `_apply_tier` wrote `auth.json` directly**, bypassing
  `auth.update_config()` and racing with the window-state debounce save. Now
  uses `auth.update_config({...})` which acquires the IO lock and atomic-writes.
- **BUG-12: `_real_quit` called `tray.stop()` from pystray's thread**, racing
  with `_on_main_close` on the Tk thread. Now it only sets the quit flag and
  marshals teardown onto the Tk thread via `after(0, self.destroy)`; `destroy()`
  owns the actual tray cleanup.

**LOW**
- **BUG-5: Dead `webbrowser` import** in `main.py` removed (left over from
  v1.030 refactor).
- **BUG-6: Unused `get_model` import** in `core/processor.py` removed.
- **BUG-10: `<Unmap>` deferred `self.after(50, self.withdraw)` could fire
  after destroy** → "invalid command" warnings. New `_destroyed` flag is set
  at the top of `destroy()` and gates the late callback via `_safe_withdraw`.
- **BUG-11: Stale `core/processor.py.bak-v1.024`** deleted — 11 versions old,
  cluttered grep results and risked being bundled by PyInstaller.
- **BUG-13: Resizer fallback warning was never surfaced.** Images that exceeded
  `target_kb_max` even at lowest quality returned `ok=True` with a `warning`
  field that no caller read. `Plan.oversized_count` now tracks them and the
  UI log reports the count after Phase 1.

### Fixed (future risks — preempted before they could surface)
- **RISK-1 / RISK-2: Download integrity.** `download_installer` now captures
  `ETag` + `Last-Modified` from the first response and sends them as
  `If-Range` on each retry. If GitHub re-uploaded the asset between attempts,
  the server returns 200 instead of 206 → we restart from byte 0, eliminating
  the cross-version stitching corruption that hit ENA v2.6.5. Also accepts
  an `expected_size` from the release API and treats a final-size mismatch
  as a failure (with retry) even when `Content-Length` happened to match.
- **RISK-5: Debug log unbounded growth.** `_debug_log` now rolls over once
  the log exceeds 1 MB (single-generation rotation to `.1`). Months of idle
  periodic-check timeouts no longer accumulate.

### Housekeeping
- Bumped `requirements.txt` to include upper-bound version pins on every dep
  (`Pillow<12.0`, `google-genai<2.0`, `customtkinter<6.0`, …) so a downstream
  breaking change can't silently break a `pip install -r requirements.txt`.
- Removed 7 per-version files `release-notes-v1.027.md` … `v1.033.md` —
  duplicated `CHANGELOG.md` content.
- Bumped `VERSION` to 1.034.

### Audit credit
Audit performed by Coddy (general-purpose subagent) on 2026-05-23. Smoke test
+ live launch (process pid 28168) verified v1.033 ran clean before the fix
pass; post-fix verification follows in the next testing round.

## [1.033] — 2026-05-22

### Fixed
- **Double-download race in `UpdateWorker._on_available`.** Two rapid
  manual_check calls (or one tick + one tray "Check now" in flight) could
  both pass the dedup checks because `pending_installer` hadn't been set
  yet. Result: two background threads racing to write the same installer
  file. Added an `in_progress` short-circuit at the top of `_on_available`.
- **Installer cache cleanup never ran.** Failed downloads and aborted
  installs left `.exe` files at `~/.happy-photo-organizer/updates/` that
  no code path ever swept. `main()` now calls
  `updater.cleanup_old_installers()` once on launch.

### Found via post-release code review of v1.032 — both reported by Codey
during the regression hunt Nick requested. Both fixes are tiny (1 conditional
+ 1 function call). No behavior change for the happy path.

## [1.032] — 2026-05-22

### Changed
- **Extracted auto-update lifecycle to `core/update_worker.py`** (delegation
  pattern). The 8 update methods and 5 pieces of update state that used to
  live on `MainWindow` are now owned by an `UpdateWorker` instance. MainWindow
  exposes a small host contract — `after`, `after_cancel`, `log`,
  `is_batch_running`, `on_before_install` — and the worker handles everything
  else (periodic check, defer-during-batch, dedup, download, install hand-off).
- **Functionally identical** to v1.031 — same 5-min poll, same defer behavior,
  same tray "Check for updates now" path (kept via a one-line shim).

### Removed from `main.py` (1187 → 1057 lines)
- `_update_check_tick` body (kept as a 1-line shim → `update_worker.manual_check()`)
- `_update_check_worker`, `_on_update_available`, `_begin_update_download`,
  `_on_installer_ready`, `_install_pending_now`, `_resume_deferred_update`
- 5 update-state attributes from `__init__`: `_pending_installer`,
  `_pending_installer_version`, `_pending_update_info`, `_update_after_id`,
  `_update_in_progress`
- `UPDATE_INTERVAL_MS` class constant (now on `UpdateWorker`)

### Added
- `core/update_worker.py` — 174-line standalone worker, unit-testable with
  a mock host (covered: start scheduling, manual-check non-interference,
  cancel idempotency, batch defer, resume).
- `MainWindow.log()`, `MainWindow.is_batch_running` (property),
  `MainWindow.on_before_install()` — host contract surface.

## [1.031] — 2026-05-22

### Fixed
- **Settings dialog rendered with a white background** even when the rest of
  the app was in dark mode. `CTkToplevel` without an explicit `fg_color` falls
  back to the theme's light-mode default, regardless of
  `set_appearance_mode("dark")`. Both `SettingsDialog` and `AIHealthDialog`
  now pass `fg_color=COLOR_BG` to `super().__init__()`.
  This bug had been present since v1.027; the v1.030 refactor surfaced it
  because Nick noticed the contrast against the otherwise-dark layout.

### Changed
- **Cleaned 7 unused imports from `main.py`** left over from the v1.030 refactor:
  `JobAssignment`, `TIER_PRESETS`, `TierConfig`, and `STEP_ACTIVE/DONE/PENDING/READY`.

## [1.030] — 2026-05-22

### Changed
- **Refactor: `main.py` split into `core/` + `ui/` modules** per the
  reference desktop project playbook. `main.py` now 1275 lines (was 2478);
  the cut moved 1200 lines of widget/dialog code into focused modules:
  - `core/version.py` (VERSION reader, APP_TITLE)
  - `core/single_instance.py` (Win32 named-mutex guard + stale fallback)
  - `core/tray.py` (HappyTray wrapper around pystray)
  - `ui/theme.py` (COLOR_* + STEP_* palette)
  - `ui/paste_helper.py` (cross-keyboard-layout copy/cut/paste)
  - `ui/step_card.py` (StepCard widget)
  - `ui/job_row.py` (JobRow review widget)
  - `ui/dialogs/settings.py` (SettingsDialog)
  - `ui/dialogs/ai_health.py` (AIHealthDialog)
- `HappyPhotoOrganizer.spec`: added hidden imports for all `core.*` and
  `ui.*` modules so PyInstaller never misses one in static analysis.

### No behavioral changes
- Visual layout, keybindings, batch processing, auto-update, tray, single-
  instance lock, window state persistence, debug log, and download retry
  all behave exactly as in v1.029.

## [1.029] — 2026-05-22

### Fixed
- **Stale-mutex fallback**: single-instance lock now confirms a real Tk window
  via `EnumWindows` (class prefix `Tk` + title prefix `Happy Photo Organizer`)
  before declining the launch. A zombie process holding the mutex no longer
  locks the user out of the app forever.
- **Minimize (—) now hides to tray** like the X button. `<Unmap>` event detects
  the iconic state and routes to `withdraw()`.
- **Download retry + HTTP Range resume**: `download_installer` now retries up
  to 3 times with 300 s timeout each, asking GitHub for `Range: bytes=<size>-`
  on each retry so partial downloads aren't thrown away. Final size verified
  against `Content-Length`. Survives flaky networks.

### Added
- **Debug log breadcrumbs** at `%TEMP%/happy-photo-organizer-updater.log`.
  Windowed exe has no stderr; on-disk logs are how silent crashes get diagnosed.
- **`<Configure>` debounced geometry save** (600 ms). Window size/position now
  survives an app crash before `destroy()` would have fired.
- **`_update_in_progress` flag** — tracks an active download. Reserved for
  future flows that need to keep the app alive specifically because an update
  is mid-flight.
- **`VERSION` plain-text file** — single source of truth. `main.py` and
  `installer/installer.py` read it at runtime (frozen-bundle aware).
- **CHANGELOG.md** (this file).

### Changed
- Multi-resolution `assets/happy_icon.ico` verified: 16/24/32/48/64/128/256.

## [1.028] — 2026-05-22

### Added
- **System tray** (pystray) with **Show / Check for updates now / Quit** menu.
- **Hide-to-tray on X** — closing the window only hides; real quit goes via
  the tray menu.
- **Zero-click background auto-update**: removed the visible "Update" button.
  Updates now download + install + relaunch silently. Check every 5 minutes
  even while the window is hidden.
- **Single-instance lock** via Win32 named mutex. Second launch raises the
  existing window from the tray instead of starting a duplicate process.
- **Batch-aware deferred update** *(bug fix)*: while a photo-tagging batch is
  running, refresh during the batch only logs the discovery — no download,
  no install. The deferred install fires automatically when the batch finishes.

### Fixed
- `_batch_running` flag is now actually written (previously declared but never
  set, so the defer guard had no effect).
- Duplicate update events while deferred are deduplicated by tag/version.

## [1.027] — 2026-05-21

### Added
- **Window state persistence** (geometry + position + maximized) across
  sessions. Saved in `~/.happy-photo-organizer/auth.json` under `window_state`.

### Changed
- **Layout refactor**: Log panel moved to the right column (full height),
  Step 1 + Step 2 stacked vertically on the left.
- **Drop-zone idle border softened to subtle grey.** Orange/pink only on
  drag-over (previously always orange — looked like a stuck focus indicator).
- Date bumped to 2026-05-21.

### Infrastructure
- **First end-to-end auto-update smoke test** — verified the v1.025+ updater
  flow works in production by shipping a real release.

## [1.026] — 2026-05-18

### Changed
- Smart date allocation reworked: consolidate every assignment to the
  destination's dominant month, unique day numbers across months,
  earliest-gap-first using EXIF day when available, range pattern
  `DD-DD.MM.YY`, cap last day when full.

## [1.025] — 2026-05-18

### Added
- **Auto-updater** — silent startup check via GitHub Releases API +
  in-app download progress + silent install + relaunch.
- `GitHub Releases` integration in `core/updater.py`.
- `RELEASE.md` release process doc.

## [1.024] — 2026-05-18

### Status
- 138-job catalog.
- 14 image formats including HEIC.
- Free-tier rate limiter (RPM 15 / TPM 250 k / RPD 500) for
  `gemini-3.1-flash-lite`.
- English UI, dark theme, drag-drop sources + destination picker.
- Three-phase workflow: resize+group, AI tagging, rename.

[1.035]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.035
[1.034]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.034
[1.033]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.033
[1.032]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.032
[1.031]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.031
[1.030]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.030
[1.029]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.029
[1.028]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.028
[1.027]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.027
[1.026]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.026
[1.025]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.025
