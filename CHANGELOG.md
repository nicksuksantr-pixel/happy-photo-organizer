# Changelog

All notable changes to Happy Photo Organizer are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/). Latest on top.

## [Unreleased] — deferred items (will roll into V2 docx form filler)

Cosmetic / design / V2-scope items that survived round 6. All catalogued
in detail at the bottom of this file under "Round 6 deferred".

## [1.036] — 2026-05-24 — Cos external review pack (Round 6, 20 patches)

A non-paper-cut quality release. Trigger: Nick handed Codey
`Happy-Photo-Organizer-CodeReview.docx` from Cos (Claude in Cowork, sibling
instance, no in-flight context). Cos returned 7,000 words / 7.9 ÷ 10 / B+ /
3 HIGH + 8 MEDIUM + 10 LOW bug findings + 15 UI/UX + 7 architecture + 6 AI
integration notes, every one with file:line and a proposed fix.

Codey triaged across two passes (initial 9 patches + Nick "จัดให้หมด"
extension 11 more), patched 20 items source-only, rejected 2 reviewer
claims (Cos misread `raise SystemExit` vs `sys.exit` and a guarded
after-id), deferred ~25 design / V2 / test-infra items.

Pattern proved: when self-audit cascade plateaus (round 1-5 went
13→0→7→0→2 finds), switch *modality* (self → external review) instead
of doing another self-round. Round 6 reset the curve: 20 real patches.

### Round 6 extension (2026-05-24 #2 — Nick said "จัดให้หมด", surgical sweep)

After the first Round-6 pass shipped 9 surgical patches, Nick directed
Codey to clear every remaining Cos finding that wasn't a design decision
or V2-scope refactor. 11 more patches applied source-only.

**UI (low-risk power-user improvements)**
- **R6-UI-03: keyboard shortcuts.** `Ctrl+O` opens the file picker;
  `Ctrl+Enter` starts Phase 1+2 when source + dest are both set;
  `Esc` cancels a running phase; `F5` triggers a manual update check.
  Each handler ignores keypresses inside text entries (Settings dialog
  etc.) to avoid hijacking typing. (`main.py:_kbd_*`)
- **R6-UI-13: minsize 960×600.** Old 640×420 collapsed Step 3's
  4-column review table the moment Phase 2 produced rows. New floor
  fits the two-pane layout + log panel comfortably. (`main.py:85`)

**Low-risk bug patches**
- **R6-BUG-L1: catalog `_extract_keywords` stop list expanded** from
  11 to 30 common English prepositions/articles/copulas. Fuzzy match
  on job names like "Cleaned the cooler from main AC" was previously
  treating "the"/"from" as semantically meaningful tokens.
  (`core/catalog.py:_extract_keywords`)
- **R6-BUG-L3: `JobRow._open_folder` surfaces failures** via
  `messagebox.showwarning` / `showinfo` instead of silently swallowing.
  User now learns when the source folder has been moved/deleted
  since Phase 1, or when `os.startfile` refuses. (`ui/job_row.py:_open_folder`)
- **R6-BUG-L2: `atomic_write_json` retries 3× with 0.15s/0.30s backoff.**
  AV scanners holding a write lock for a tenth of a second were the
  common cause of silent setting-save losses. Split into
  `_atomic_write_json_once` + retry wrapper. (`core/auth.py:atomic_write_json`)
- **R6-BUG-L7: JPEG integrity verify after save.** New `_verify_jpeg_readable`
  re-opens the bytes Pillow just produced; if decode fails, fall through
  to the next attempt with smaller dim. Catches rare codec edge cases
  that produced silently-corrupt 0-byte outputs. (`core/resizer.py`)
- **R6-BUG-L8: `.gitattributes` added.** Normalize line endings: LF in
  the repo, native on checkout, never CRLF in `.py`/`.json`/`.md`.
  Binary lock on assets prevents PIL/installer artifacts from being
  text-munged. Prepares the repo for a non-Windows contributor.
- **R6-BUG-L9: Phase 4 rename retry.** `a.temp_folder.rename(target)`
  now retries up to 3× with 0.3s/0.9s backoff before raising. Covers
  the AV-scanner / network-share transient-PermissionError window.
  (`core/processor.py:phase4_rename_folders`)
- **R6-BUG-L10: stale quarantine + tmp-orphan sweep on startup.**
  New `auth.cleanup_stale_quarantines(max_age_days=30)` called from
  `main()` alongside `cleanup_old_installers()`. Removes
  `auth.corrupt-<ts>.json` older than 30 days AND any `<name>.<rand>.tmp`
  orphan from a crashed atomic write (closes round-5 R5-RISK-2 too).

**Medium upgrade**
- **R6-BUG-M7: async thumbnail loading in `JobRow`.** `Image.open` +
  `thumbnail` was running on the Tk thread during `_render_plan` — with
  50+ HEIC rows it visibly froze the UI for 1-2 s. Now spawned to a
  daemon thread, shows `...` placeholder, swaps in the real CTkImage
  via `after(0)`. Guards against row teardown via a `<Destroy>` marker.
  (`ui/job_row.py`)

**Defense-in-depth**
- **R6-BUG-M8: track `_on_window_unmap` after-id + cancel in `destroy()`.**
  Already guarded by `_destroyed` check in `_safe_withdraw`, but
  explicit cancel matches the existing `_geo_save_after_id` /
  `_poll_after_id` pattern and avoids a wasted Tk dispatch. The
  destroy() loop now cancels all three tracked after-ids in one block.
  (`main.py`)

### Round 6 (2026-05-24 — Cos external review, applied to source)

External world-class review by Cos (Claude in Cowork — sibling instance).
Cos read all 26 .py files (5,481 LOC) + ran static analysis + tested pure
logic. Codey triaged each finding against the round 1-5 audit and applied
8 low-risk surgical patches. UI/Theme/Typography/Architecture refactors and
test infrastructure deferred to V2 / Phase B work per Nick's standing rule.

**HIGH — patched in source**
- **R6-BUG-H1: `MainWindow.destroy()` could block on hung disk during
  catalog save.** Round-5 added `catalog.save()` to `destroy()` to close the
  in-memory-loss window, but a hung disk (network drive, AV lock, USB
  unplugged) would freeze the X-button click waiting for atomic-write to
  return. **Fix**: wrap `catalog.save()` in a daemon thread with
  `join(timeout=2.0)`. If the disk is unresponsive, drop the save and let
  the next Phase 4 persist. Idempotent + crash-safe. (`main.py:716-730`)
- **R6-BUG-H2: `update_worker._on_ready` version-compare on stripped tag,
  not parsed version.** Compared `pending_info.tag.lstrip("vV")` to the
  parsed `version` arg. Pre-release tags like `1.035-rc1` would strip to
  `1.035-rc1`, mismatch the parsed `1.035`, and re-enter the download
  branch — risk of redundant re-download loop. **Fix**: compare
  `pending_info.version` (parsed, already stripped) on both sides. Clean
  one-liner. (`core/update_worker.py:181-184`)
- **R6-BUG-H3: `paste_helper.enable_paste` hard-coded `widget._entry`
  internal.** A CTk upgrade that renames the inner Entry would silently
  break Ctrl+V/C/X/A on Thai keyboards (the whole point of this helper).
  **Fix**: probe candidate names (`_entry`, `entry`, `_input`) and verify
  the inner widget has `bind` + `insert` before binding. Falls back to the
  widget itself if no inner candidate matches. (`ui/paste_helper.py:22-37`)

**MEDIUM — patched in source**
- **R6-BUG-M2: No disk-space pre-check before Phase 1 resize.** Phase 1
  writes ~30KB per JPEG straight to dest_root — a full disk would error
  mid-batch and leave a half-built temp folder. **Fix**: `shutil.disk_usage`
  pre-check at the top of `phase1_resize_and_group` requiring 2× headroom
  (≈60KB per image). Raises before any work starts. Degrades gracefully on
  UNC paths that don't support `disk_usage`. (`core/processor.py:311-326`)
- **R6-BUG-M3: `detect_target_month` could inherit implausible year.** If
  the dest happened to have a stray folder dated 2050 (mistyped batch),
  the detector returned `(2050, 5)` and every new folder for the batch
  inherited year 2050. **Fix**: clamp detected year to ±5 of today; fall
  back to current year + detected month if out of range. (`core/processor.py`
  post-`detect_target_month` block)
- **R6-BUG-M4: Phase 2 worker error swallowed stack trace.** Caught with
  `reasoning: f"worker error: {str(e)[:200]}"` — UI got the message but the
  log lost file:line, so reproducing was painful. **Fix**: capture
  `traceback.format_exc()` and emit via `progress_cb` as a debug line.
  UI-facing message unchanged. (`core/processor.py:472-487`)
- **R6-BUG-M5: `resizer` docstring contradicted code.** Doc said quality
  95→50, array was 90→20, target 20-50 KB, actual was 10-25 KB. Confused
  any maintainer. **Fix**: rewrite docstring to match constants exactly.
  (`core/resizer.py:1-7`)
- **R6-BUG-M6: `update_worker._poll_github` silent on every error.** Every
  poll while GitHub was unreachable failed silently — no telemetry, but
  also no signal to the user that "we tried, it's not us, it's GitHub".
  **Fix**: track `_last_poll_ok` and log only on state transitions
  (ok→fail = "GitHub unreachable", fail→ok = "GitHub reachable again").
  First poll outcome stays silent — avoids "warning" on cold start.
  (`core/update_worker.py:102-128`)

**LOW — patched in source**
- **R6-BUG-L6: `import uuid as _uuid` inside a Phase 4 function body.**
  Tiny code smell — runs on every collision cap. **Fix**: hoist to module
  top, kept the `_uuid` alias for call-site stability. (`core/processor.py`)

**AI — patched in source**
- **R6-AI-04: No exponential backoff on transient 5xx / network errors.**
  A 503 from Gemini surfaced immediately as `result.reasoning = "error: ..."`
  with no retry, even though the next request 1-2 s later usually
  succeeded. **Fix**: new `_generate_with_retry` wrapper in `analyzer.py`
  with 1s / 2s / 4s backoff. Retries on 500/502/503/504/timeout/connection-
  reset; does NOT retry quota / cancellation / 4xx (those are user/policy,
  not transient). Cancel-aware sleep so user cancel doesn't wait the full
  backoff. Wired into both `analyze_image` and `analyze_group`.
  (`core/analyzer.py` — new helper + 2 call sites)

### Round 6 deferred (Cos findings catalogued, not patched yet)

Reason for each defer: needs design decision (Nick), bigger-than-surgical
refactor (V2 scope), or test infrastructure work (Phase B per Cos's
roadmap).

- **UI-01 .. UI-15 (Cos)**: typography hierarchy, color-palette refine,
  keyboard shortcuts, undo-Phase-4, lucide icons, sort/filter in Step 3,
  drop-zone pulse, dark/light/system toggle, sparkline RPM badge, etc.
  These are visual design decisions and a multi-day rebuild of `ui/theme.py`
  + new `ui/typography.py` + `ui/spacing.py` + `ui/icons.py`. Defer to V2
  feature ship so the whole look-and-feel changes in one user-facing event.
- **BUG-M1**: `smoke_test.py` hard-coded `D:\+++++Nick folder+++++\…`
  paths. Replace by Phase B `tests/fixtures/` work — pytest + GitHub
  Actions CI is a separate effort and out of scope for round 6.
- **BUG-M7**: `JobRow._make_thumbnail` sync block on UI. Real but
  rewriting thumbnail loading to async with placeholder swap touches the
  CTkImage lifecycle — defer to V2 polish pass.
- **BUG-M8**: `_on_window_unmap` after-id not tracked + cancelled.
  Already guarded by `_destroyed` / `_real_quit_requested` checks in
  `_safe_withdraw`, so this is defense-in-depth, not a real bug.
- **BUG-L1 .. L10**: stop-word coverage, atomic-write retry, open-folder
  silent except, mutex namespace, raise SystemExit vs sys.exit (no
  observable difference — both trigger atexit), JPEG integrity verify,
  `.gitattributes`, Phase 4 rename retry, auth.corrupt sweep. All
  paper-cuts.
- **ARCH-01 .. 07**: split `main.py` controllers, DI container, logging
  framework, dry-run Phase 4, event bus, i18n, pydantic config schema.
  Each is a 1-2 day refactor that touches every module — wrong moment
  while V2 docx form filler design is still open. Catalogue and revisit
  during V2 scoping.
- **AI-01**: TPM enforcement (Gemini token-per-minute rate). Real risk
  but needs a new sliding-window data structure in `RateLimiter` + UI
  surface in AI Health. Defer to V2 — at current usage (single-user,
  free tier) RPM hits the cap first anyway.
- **AI-02**: Catalog filtering (send top-N relevant names per call).
  Optimization; deferred until catalog passes 500 entries (currently 146).
- **AI-03**: Response cache for re-runs. Useful for power users — design
  needed (cache invalidation rules, key hash, eviction).
- **AI-05**: Streaming response. Cos agrees defer — JSON payload is small.
- **AI-06**: Prompt versioning. Architecture decision; defer.

### Round 5 (2026-05-23 #2 — applied to source, awaiting next feature ship)

- **R5-BUG-1 (MED-LOW): `_translate_to_english` was synchronous + untracked.**
  The EN button on a JobRow called `client.models.generate_content()` directly
  on the Tk thread — froze the UI for 1-3 s per click, bypassed the rate
  limiter (no RPM throttle / no quota check), and bypassed `usage_log.record_call`
  so AI Health showed wrong call counts. **Fixed in source**: dispatched to a
  daemon thread, gated through `rate_limiter.call("translate")` so the call is
  throttled + logged like Phase 2 calls, and marshalled back to Tk via
  `after(0, …)`. Token usage is captured into the context so usage_log totals
  stay accurate. (`ui/job_row.py:274-322`)
- **R5-BUG-2 (LOW): catalog-learning persistence gap.** `_refresh_summary`
  calls `catalog.add()` in-memory only; `catalog.save()` only runs at the end
  of Phase 4. If the user edited names in review and then closed the app
  *without* running Phase 4 — X button → tray, tray Quit, auto-update
  installer killing the process between Phase 2 and Phase 4 — all the learned
  names were lost. **Fixed in source**: `MainWindow.destroy()` now best-effort
  calls `self.catalog.save()` before tearing down. Idempotent (Phase 4 still
  saves) and cheap (the catalog is small). (`main.py:_destroy_override`)

### Round 5 deferred (cosmetic / very low impact — not patched)

- **R5-RISK-1: `auto_check_updates` toggle is not live.** Toggling the Settings
  checkbox only takes effect on next launch; the running `UpdateWorker` keeps
  its scheduled `after` chain regardless. Cosmetic. (`ui/dialogs/settings.py`
  + `main.py:_on_settings_saved`)
- **R5-RISK-2: `.tmp` orphans in `~/.happy-photo-organizer/`.** If the process
  is killed mid-`atomic_write_json`, the `<file>.<rand>.tmp` is left behind.
  `cleanup_old_installers()` only sweeps `updates/`, not the parent config
  dir. < 1 KB per orphan, very rare. (`core/auth.atomic_write_json` +
  `core/updater.cleanup_old_installers`)

### Original deferred items (round 1-4 — still standing)

- **`auth.corrupt-<ts>.json` accumulates** — quarantine files from
  `_load_config_unlocked` are never cleaned. Add a sweep on app start that
  deletes quarantines older than 30 days. (`core/auth.py`)
- **`_load_config_unlocked` only quarantines `JSONDecodeError`** —
  `OSError` / `PermissionError` returns `{}` silently with no forensic copy.
  Inconsistent with design intent. (`core/auth.py`)
- **`manual_check` gives no immediate UI feedback** — tray "Check for updates
  now" relies on the log panel to show results, which the user may not see.
  Briefly disable the menu item or toast a status. (`core/update_worker.py`
  + `core/tray.py`)
- **`HappyTray._load_icon_image` fallback uses `print()`** — windowed exe
  has no stdout, so the "icon failed to load, using fallback" message goes
  nowhere. Route to `core.updater._debug_log` instead. (`core/tray.py`)
- **`_debug_log` rotate-fail edge case** — if the `.log.1` rename fails
  (file locked by another process), the log keeps appending past 1 MB.
  Acceptable as soft cap; flag if it ever shows up. (`core/updater.py`)
- **`_safe_withdraw` / `_safe_state` after-ids not tracked** — `destroy()`
  can't `after_cancel` them; Tk auto-cancels widget-bound callbacks so this
  is cosmetic. (`main.py`)
- **Phase worker `_reset_buttons` / `_on_rename_done` callbacks have no
  `_destroyed` guard** — predates v1.034, Tk auto-cancels so usually safe,
  but a deferred guard would be defense-in-depth. (`main.py`,
  `core/processor.py`)

All seven items collectively: cosmetic + edge-case + diminishing-returns. The
audit cascade (13 → 2 → 7 → 0) hit clear diminishing returns at round 4 — a
round-5 sweep would surface only HYG-tier polish.

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
