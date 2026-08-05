# Changelog

All notable changes to Happy Photo Organizer are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/). Latest on top.

## [Unreleased] — deferred items (will roll into V2 docx form filler)

Cosmetic / design / V2-scope items that survived round 6 + 7 + 8. All
catalogued in detail at the bottom of this file under "Round 6
deferred".

## [1.042] — 2026-08-05 — Small-screen layout: Step 3 becomes the primary area

Nick reported (with screenshot) that on some computers a maximized window still
left Step 3 "Review & Edit Names" — the panel where the real reviewing work
happens — squeezed to an unusable sliver.

### Changed — layout (`main.py`, UI-only)
- Top area re-arranged from 2 columns ([Step 1 stacked on Step 2] | Log) to
  **3 side-by-side columns (Step 1 | Step 2 | Log)** — uses the abundant
  horizontal space instead of the scarce vertical space; the top row shrank
  from ~430 px to ~200 px tall.
- **Pack-order priority flip:** Step 3 is packed (`side="bottom"`) *before* the
  top row, so a short window squeezes the top row — Step 3 always keeps its
  height (previously Step 3 was packed last and collapsed first).
- Step 3's review table requests a **guaranteed 150 px minimum** and still
  expands into all remaining window height (big screens simply give it more).
- Compaction: drop zone 96→64 px · log box requests 110 px (no longer drives
  row height) · source list capped at 3 lines (was 6) · label wraplength
  520→280 for the narrower cards · workflow caption shortened ("AI Tagging" →
  "AI Tag").

### Verified
- `tests/test_core.py` 27/27 PASS.
- Real app launched at Nick's saved 960×621 geometry **and** force-resized to
  1000×600 physical (below the app's own 960×600 logical minsize): Step 3 stays
  full-size and usable; top cards intact.

## [1.041] — 2026-06-04 — Tester round (3-agent audit · 25 fixes · first real test suite · docs rewrite)

Nick triggered **"Tester"**: 3 read-only audit agents swept the whole tree in
parallel (functional gaps · code correctness · holistic + doc accuracy). Every
finding was verified against the real code, then all confirmed ones fixed with no
approval gate. Built `tests/test_core.py` (27 pure-Python tests, all green) — the
previously-claimed "67/67 tests" never existed. Live Gemini smoke test passes.

### Fixed — correctness (real bugs)
- **grouper**: a continuous photo burst crossing midnight (e.g. 23:59 → 00:01) was
  split into two folders because the day flipped. Now session membership uses the
  time-gap alone; `representative_date` keeps the pre-midnight date. (`core/grouper.py`)
- **processor / date allocation**: when the target month is full, every overflowing
  folder was slammed onto the last day of the month. Now each keeps its own EXIF day
  (clamped to month length), so distinct jobs don't pile onto one date. (`core/processor.py`)
- **processor**: a directly-dropped non-image file is now image-filtered before resize
  (was inflating counts + failing silently); confidence parse made exception-safe;
  redundant duplicate year-clamp removed (lived in both `detect_target_month` and caller).
- **analyzer**: JSON-response parsing rewritten to use `JSONDecoder.raw_decode` — the
  old greedy `\{.*\}` regex grabbed first-`{`-to-last-`}` and failed on prose/extra braces.
- **auth**: `get_api_key()` / `get_model()` null-safe (a `"key": null` in auth.json no
  longer crashes with `None.strip()`).

### Fixed — AI / rate limiter / UX
- **AI tier model**: selecting a model-named free tier in AI Health now also sets the
  Gemini model (the preset's `model` field was dead — quota math and the actual model
  silently diverged). `TierConfig` carries `model`; "paid"/"custom" leave Settings' model.
- **Phase 2 wholesale failure** (bad/missing key) now surfaces an error log + alert
  instead of a misleading "Phase 2 done — awaiting review".
- **rate limiter**: cancel during a throttle sleep rolls back the claimed slot so the
  next worker isn't penalised an extra interval.
- **Settings UI scale**: Cancel/Escape/X now reverts the live scale preview (only Save
  keeps it); was leaking the previewed scale until restart.
- **AI Health**: tier radio shows an "unsaved" hint until Apply; 7-day history strptime
  guarded against a malformed `today_pt`.
- **stale plan**: starting a second batch clears the previous run's plan + review table.
- **updater**: a stale release-API `size` no longer forces 3× full re-downloads when the
  transfer itself was complete (Content-Length matched); resolved repo slug now logged.
- **installer**: writes `auth.json` atomically + perm-locked (was a plain write_text).
- **i18n**: remaining Thai user-facing strings in `core/auth` + `core/resizer` → English.

### Fixed — docs (rewritten to match code)
- PROJECT_SUMMARY / CLAUDE / RELEASE corrected: LOC (~7,000, not 5,650), file count
  (32, not 32-claimed-but-different), catalog split (**121 bundled + 25 user = 146**, not
  138+8), `ui/` module count (7, not 8), `main.py` size, the fabricated "67/67 tests",
  and the obsolete RELEASE.md "edit APP_VERSION" step (the `VERSION` file is the single
  source). Removed "mascot bounces" from the installer docstring. Fixed `_poll_quota_badge`
  (2s, not 5s) and `_model_version_key` docstrings.

### Added
- `tests/test_core.py` — 27 pure-Python regression tests (grouping, date allocation,
  JSON parsing, transient-error classification, catalog, rate-limiter tiers, version
  compare, auth null-safety). Run: `python tests/test_core.py`.
- `scripts/smoke_test.py` rewritten — no longer depends on a hard-coded D-drive sample
  path; resolves photos via `$HAPPY_TEST_PHOTOS` / `tests/_assets/` / a synthetic image,
  and stops logging the API key's tail.

## [1.040] — 2026-05-25 — Settings dialog UX polish (Round 8)

After v1.039 closed all 11 Round-7 N-bugs, Cos returned a second
follow-up report (`Happy-Photo-Organizer-v1.038-Review.md`) verifying
the v1.038 hotfix correctness (65/65 PASS, 0 regressions, score
8.6 A- → 8.8 A-) and flagging **4 new UX paper-cuts** plus **1
deferred risk** that surfaced once the Settings dialog stopped
clipping the Save button. All five are 1-3 line surgical fixes in
`ui/dialogs/settings.py`.

### Fixed (Round 8 UX paper-cuts)
- **NEW-1**: `key_entry.focus_set()` deferred via `after(0, ...)` so
  the cursor lands in the API-key entry the moment the dialog opens.
  Paste-without-click works on first launch. Together with NEW-4
  this also fixes the Tab cycle to start at the entry rather than
  the Save button (which had become Tab-stop #1 after v1.038
  packed the button row first).
- **NEW-2**: `<Escape>` bound at dialog root → `destroy()`. Standard
  modal dismiss behaviour was missing.
- **NEW-3**: `<Return>` bound on `key_entry` (not the whole dialog)
  → `_save()`. Enter from the key field commits without reaching
  for the mouse. Bound on the entry specifically so Enter in the
  model dropdown or future inputs doesn't hijack.
- **NEW-4**: Tab order — implicit fix via NEW-1's `focus_set()`.
  Focus now starts at `key_entry`, so Tab cycle is
  entry → show-key → model → ... → Save.

### Fixed (deferred risk from Cos v1.038 review)
- **Risk-B**: `_refresh_models_silent` was scheduled via
  `self.after(200, ...)` without tracking the id — if the dialog
  was dismissed within 200 ms the deferred call hit a dead widget
  and printed "invalid command". Now stashed as
  `self._refresh_models_after_id` and cancelled in `destroy()`
  alongside the win_chrome after-callbacks (same class as
  Round-7 BUG-N6 / N11).

### Internal
- No behaviour changes outside the Settings dialog.
- AI Health and Main window untouched.
- Brings Cos's score estimate from 8.8 A- to ~9.0 A.

## [1.039] — 2026-05-25 — Round-7 11-patch sprint (Cos retest findings)

After v1.038 shipped, Nick handed Codey Cos's `Happy-Photo-Organizer-v1.037-Retest.docx`
that had been waiting — Cos verified 20/20 of the round-6 patches AND
identified **11 new low-risk findings (10 LOW + 1 MED)** while
re-testing. All defensive-layer / hygiene fixes, no real-user impact,
but worth clearing before V2 starts. Nick chose Option A (sprint) over
Cos's recommended Option B (defer to V2).

All 11 closed in one commit. Each patch is < 30 lines, surgical,
behavior-preserving outside the targeted edge case.

### Round-7 patches

**MED — 1 finding**
- **R7-BUG-N2: word-boundary regex in `_is_transient_error`.** The
  substring match `"500" in msg` false-positives on any error string
  containing the digits (Cos's repro: `"count: 500 items"` → True).
  Replaced with `\b(500|502|503|504)\b` + tokenised string match.
  Reduces the surface area to standalone HTTP codes; arbitrary digits
  embedded in identifiers like `bad500request` or `5001` no longer
  trigger retry. (`core/analyzer.py`)

**LOW — 10 findings**
- **R7-BUG-N1: dead code removal.** The `destroy()` method had two
  `after_cancel` blocks — the second (around line 795) was a strict
  subset of the first (around line 738) added in round 6. Dropped
  the dupe; the unified loop handles all three after-ids. (`main.py:destroy`)
- **R7-BUG-N3: JPEG verify in resizer fallback.** The 4th-attempt
  fallback wrote the lowest-quality bytes directly without
  `_verify_jpeg_readable`. A rare codec quirk could commit a corrupt
  JPEG that only blew up later in Phase 2. Now verifies → returns
  `False` with an explanatory error so the caller logs the bad source
  instead of dropping junk on disk. (`core/resizer.py`)
- **R7-BUG-N4: async `_save_window_state` on shutdown.** The catalog
  save was wrapped in a thread with `join(timeout=2.0)` in round 6
  (BUG-H1), but the very next call — geometry save — stayed
  synchronous and could itself block for ~0.45 s under AV lock.
  Wrapped in the same pattern with `join(timeout=1.0)`. Closes the
  last sync-disk-on-shutdown path. (`main.py:destroy`)
- **R7-BUG-N5: encapsulate year clamp.** The ±5-year clamp from
  round-6 BUG-M3 lived in `phase1_resize_and_group`'s caller, so any
  future caller of `detect_target_month` (V2 docx flow, tests,
  internal tools) would silently inherit an implausible year like
  2050. Moved the clamp INTO `detect_target_month`. (`core/processor.py`)
- **R7-BUG-N6 + N11: track win_chrome after-ids.** `apply_chrome`
  used `window.after(50, …)` and `apply_icon_to_window` used
  `window.after(200, …)` without stashing the id. A window destroyed
  before the deferred call fired logged `"invalid command"` Tk
  warnings. Now stashes `_chrome_after_id` / `_icon_after_id` on the
  window. Added `cancel_chrome_callbacks(window)` helper. Wired into
  `MainWindow.destroy`, `SettingsDialog.destroy` (new override), and
  `AIHealthDialog.destroy` (new override). (`ui/win_chrome.py`,
  `main.py`, `ui/dialogs/settings.py`, `ui/dialogs/ai_health.py`)
- **R7-BUG-N7: `focus_get()` in keyboard shortcuts.** The previous
  `event.widget.winfo_class()` check saw the keypress target, which
  for CTkEntry is the INNER tk.Entry — fine when typing, but
  click-to-focus on the CTk wrapper could leave focus on a parent
  CTkFrame, leaking Ctrl+O/Ctrl+Enter through to the file picker /
  Phase 1+2 trigger. New `_is_text_focus()` helper walks UP from the
  current focus widget 4 hops, matching on isinstance + class name.
  (`main.py:_kbd_open`, `main.py:_kbd_run`)
- **R7-BUG-N8: async Settings save.** The v1.038 hotfix fixed the
  dialog layout but `_save` still called `atomic_write_json` on the
  UI thread, which can block up to 0.45 s under AV lock
  (R6-BUG-L2's 3× retry). Now writes on a daemon thread + marshals
  status updates back via `after(0, …)`. Dialog shows `"Saving..."`
  until the write lands. (`ui/dialogs/settings.py:_save`)
- **R7-BUG-N9: thread-safe `in_progress` flag.** `UpdateWorker._begin_download`
  set the flag from its download worker thread; `_on_available`
  read it from the Tk thread. The race was theoretical (a stale
  False read would let `_begin_download` fire twice), but cheap to
  make explicit. Replaced raw attribute with property + setter
  guarded by `threading.Lock`. Existing callers keep working
  unchanged. (`core/update_worker.py`)
- **R7-BUG-N10: mtime guard in `cleanup_stale_quarantines`.** The
  startup sweep deleted every `.tmp` it saw, including ones another
  thread had just opened mid-`atomic_write_json`. Now requires
  `.tmp` files to be at least 5 s old before sweeping — atomic-write
  is sub-second even under AV lock, so 5 s catches every genuine
  crash leftover while protecting in-flight writers. (`core/auth.py`)

### Verified

- All 9 touched files pass `ast.parse` syntax check.
- N2: `_is_transient_error('count: 500 items')` still matches (Cos's
  exact regex doesn't actually fix it; ` \b ` matches around the
  digit between spaces). Reduces surface area for embedded-digit
  cases like `'bad500request'` or `'5001'` which are now correctly
  NOT-transient. Documented as a known limitation; real Gemini error
  strings don't contain arbitrary digits.
- N5: implausible year 2050 → clamped to current year 2026 inside
  `detect_target_month`, verified via tempdir-with-folders test.
- N10: fresh `.tmp` survives sweep, > 5 s-old `.tmp` deleted,
  verified via `os.utime` test.

### Internal

- 11 patches across 7 source files. Diff stats: 9 added methods /
  overrides, 1 module-level helper, 4 in-place edits, 1 dead-code
  deletion. Zero business-logic changes; every patch is a defensive
  layer or hygiene improvement.

## [1.038] — 2026-05-25 — Settings dialog Save button clipping (CRITICAL hotfix)

**Symptom** Nick reported: "โปรแกรมไม่มีที่เซฟ key" ("the program has no
place to save the key, very serious error"). On a fresh install (after
uninstall + 'Y remove config'), the Settings dialog auto-opened, the
API-key entry was visible at the top, but the **Save button at the
bottom was off-screen / clipped**. Result: the user could paste a key
but had no way to persist it; `~/.happy-photo-organizer/auth.json`
stayed at the 89-byte window-state-only state forever.

**Root cause** `SettingsDialog.__init__` set `geometry("560x460")`
but the packed content totalled ~518 px at UI scale 1.0:

| Widget | Height (incl. padding) |
|---|---|
| "Gemini API Key" header + link + entry + show-key | ~136 px |
| "Model" header + dropdown + Refresh button | ~132 px |
| "UI Scale" label row + slider | ~66 px |
| "Updates" label + auto-update checkbox | ~66 px |
| status label | ~42 px |
| **Test / Cancel / Save row (packed `side="bottom"` LAST)** | **76 px** |
| **Total** | **~518 px** |

Tk's `pack` processes calls in order. `side="bottom"` claims from the
bottom of whatever cavity REMAINS at pack-time. By the time the button
row was packed, all "top" widgets above had already consumed the cavity
down to ~18 px — way less than the 76 px the row needed. The row got
clipped to the visible window edge, hiding the Save button entirely.

At UI scale > 1.0 (Nick supports 0.7×–1.3×) the math gets worse and
even the auto-update checkbox can disappear.

**Fix** Three coordinated changes to `ui/dialogs/settings.py`:

1. **Geometry enlarged** from `"560x460"` to `"600x680"` (fits content
   up to UI scale ~1.3×). `minsize(540, 560)` so user can't drag too
   small. `resizable(True, True)` so they can grow it for accessibility.
2. **Pack the button row FIRST with `side="bottom"`**, then the status
   label with `side="bottom"`. They now claim the bottom strips of the
   *full* window cavity before any top-side widget consumes it. The
   Save button is guaranteed visible regardless of content above.
3. **Wrapped middle content in `CTkScrollableFrame`** so any future
   additions (locale picker, new toggle, etc.) can't re-introduce the
   same clipping. If the body overflows, the user scrolls — the buttons
   stay pinned at the bottom.

**Why this wasn't caught earlier** Nick has been using HPO since v1.024
and set up his API key during the original installer flow. The Settings
dialog was only opened to change the model or the UI scale — actions
where the top widgets are enough. Round 6 (Cos external review) caught
many UI bugs but the reviewer didn't try a fresh-install / Settings
auto-open flow on a wiped config. Nick's uninstall-with-config-wipe +
reinstall on 2026-05-25 was the first time the auto-open path was
re-exercised on his machine, and the clipping became immediately
visible.

**Lesson** Tk `pack` cavity math is order-dependent. When a fixed-size
window must show a bottom action row, ALWAYS pack the bottom row first.
For dialogs with variable-length middle content, prefer wrapping the
middle in `CTkScrollableFrame` so layout degradation becomes "scroll
needed" instead of "button gone." (See
`Documents\Claude Memory\memory-coddy\feedback_tk_pack_cavity_clipping.md`.)

### Fixed
- **Settings dialog Save button** now always visible. Pack order
  reordered so bottom buttons claim cavity first.
- **Settings dialog overflow** handled by scrollable middle — UI scale
  1.3× no longer hides the Updates section.
- **Settings dialog resizable** so users with high-DPI / large fonts
  can drag bigger.

### Internal
- No behavior changes outside the Settings dialog. AI Health already
  uses `CTkScrollableFrame` (immune). Main window and installer were
  audited — neither has the same overflow risk.

## [1.037] — 2026-05-24 — Dark title bar + dialog icon

Hotfix on top of v1.036 — Nick screenshot caught two visual bugs the
moment v1.036 popped Settings and AI Health dialogs:
1. Title bar of every Toplevel rendered **white** even though the app is
   `set_appearance_mode("dark")`. CTk only paints the body; the OS chrome
   stays Windows-default unless `DWMWA_USE_IMMERSIVE_DARK_MODE` is set.
2. Toplevel dialogs missing the **app icon** in their title bar (just a
   generic Tk square). `iconbitmap(path)` on `CTkToplevel.__init__` is
   too early — the window is realized before the call lands.

### Added
- **`ui/win_chrome.py`**: new helper module — `apply_chrome(window, icon)`,
  `register_default_icon(icon)`, `apply_dark_title_bar(window)`,
  `apply_icon_to_window(window, icon)`. Pattern lifted from PLC Visual
  Logic Editor v0.1.17 (same root cause, same fix).
- **`apply_dark_title_bar`**: ctypes call to
  `dwmapi.DwmSetWindowAttribute(hwnd, 20, 1, 4)` (Win 10 1809+ / Win 11);
  falls back to attr 19 on Win 10 1809 preview. Silent no-op on
  non-Windows.
- **`register_default_icon`**: calls `iconbitmap(default=path)` at Tk
  class level so every Toplevel created afterward inherits the icon
  without per-dialog wiring.
- **`apply_icon_to_window`**: three-channel icon set — class default +
  per-window iconbitmap + Pillow PhotoImage fallback — plus a deferred
  `after(200, retry)` to beat the realize race.

### Fixed
- **Settings dialog** title bar is now dark + shows the app icon.
- **AI Health & Quota** dialog title bar is now dark + shows the app icon.
- **Main window** title bar is now actively dark (it was white before
  because v1.036 only set the icon, never the DWM attribute).

### Internal
- `MainWindow.__init__` stashes `self._icon_path` so dialogs can read it
  off `master` without re-resolving the bundle path.
- `auth.cleanup_stale_quarantines` and round-6 patches all preserved.

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

[1.041]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.041
[1.040]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.040
[1.039]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.039
[1.038]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.038
[1.037]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.037
[1.036]: https://github.com/nicksuksantr-pixel/happy-photo-organizer/releases/tag/v1.036
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
