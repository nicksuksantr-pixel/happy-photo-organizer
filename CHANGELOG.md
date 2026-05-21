# Changelog

All notable changes to Happy Photo Organizer are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/). Latest on top.

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

[1.029]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.029
[1.028]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.028
[1.027]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.027
[1.026]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.026
[1.025]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.025
