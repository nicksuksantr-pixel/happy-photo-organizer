# 🎨 Happy Photo Organizer — Project Summary

**Status:** v1.044 (2026-09-02 — **1 shooting day = 1 folder** (no more scattering) · **installer merges the job catalog** instead of deleting it · VERSION BOM fix · builds on v1.043: thumbnails fixed, Gemini 3.5 default, non-work detection, per-folder Delete · tests 38/38)
**Author:** Nick (with Codey — Claude Code)
**Family:** Happy AI Family (sibling: HAPPY AI Agent)
**Last full review:** Tester sprint 2026-06-04 (Codey, 3 parallel audit agents) — see "Audit history" below

> ⚠️ This file was rewritten on 2026-06-04 against the **actual code** (the prior
> version had drifted: claimed ~5,650 LOC / 32 files / "67/67 tests" / "138+8 jobs",
> none of which matched reality). Numbers below are measured, not remembered.

---

## 📋 What it does

AI-powered photo organizer for ship maintenance & repair work:
1. Drop folders/photos → auto-detect capture date (EXIF → filename → mtime)
2. Resize to 10–25 KB (email-attachment friendly)
3. Group by session (time-gap, default 90 min — bursts that cross midnight stay one folder)
4. AI-tag each group's job name (Gemini Vision), fuzzy-matched against the catalog
5. Review & edit names in Step 3
6. Rename folders as `DD-MM-YY <Job Name>`

---

## 🏗 Tech stack

| Layer | Choice |
|---|---|
| GUI | customtkinter 5.2.2 (pinned `>=5.2,<6.0`) + tkinterdnd2 |
| AI | google-genai 1.75.0 — **default model `gemini-3.1-flash-lite`** (AI Studio key only, never Vertex) |
| Image | Pillow + pillow-heif (HEIC/iOS) |
| Distribution | PyInstaller (folder mode) + custom single-page installer |
| Storage | JSON files (`auth.json`, `usage_log.json`, `job_catalog.json`) + HKCU registry |

---

## 📦 Current state (v1.041 — measured 2026-06-04)

| Metric | Value |
|---|---|
| Python source | **~7,000 LOC** across **32 `.py` files** (31 source + 1 test), excluding `dist/` |
| `core/` modules | **15** (+ `__init__`) |
| `ui/` modules | **7** (+ `__init__`): `theme`, `paste_helper`, `step_card`, `job_row`, `win_chrome`, `dialogs/ai_health`, `dialogs/settings` |
| `main.py` | **~1,245 lines** (single MainWindow class — split deferred to V2, ARCH-01) |
| Catalog jobs | **146** = **121 bundled + 25 user-added** |
| Image formats | **14** (incl. HEIC/HEIF) — verified against `SUPPORTED_EXTS` |
| Version source of truth | the **`VERSION`** file (`core/version.py` reads it; frozen-bundle aware) |
| **Tests** | `tests/test_core.py` — **27 pure-Python tests** (no key/network/photos), all pass · `scripts/smoke_test.py` — live Gemini smoke (6 sections), passes. *(There is no pytest/CI yet.)* |
| Build artifact | `dist/HappyPhotoOrganizerSetup.exe` (~80 MB, share via GitHub Release) |

---

## 🎯 Features delivered (cumulative)

### Core workflow
- Drag-drop multi-source (folders + files); single dropped files are now image-filtered
- Recursive image collection (14 formats incl. HEIC)
- EXIF → filename → mtime date detection
- Resize 10–25 KB iterative quality with JPEG integrity verify on **both** the normal and the fallback path
- Group by **time-gap session** (90 min); a continuous burst crossing midnight stays one folder (fixed v1.041)
- Smart date allocation: consolidate to destination's dominant month, unique day numbers across all months, earliest-gap-first; when a month is full, overflowing folders keep their **own** EXIF day (clamped) instead of all collapsing to the last day (fixed v1.041)
- Disk-space pre-check at Phase 1 (2× headroom)
- Phase 4 rename retries 3× on transient PermissionError; merge-on-collision with uuid fallback
- Auto-updater silent + zero-click via GitHub Releases API

### AI / Gemini
- Gemini Vision per-folder sampling (1–3 photos)
- Fuzzy catalog match (cutoff 0.85), auto-add new names
- Robust JSON-response parsing (handles code-fences / prose / extra braces via `raw_decode`)
- Rate limiter (tier presets + custom RPM/RPD + cancel-aware throttle + slot-rollback on cancel)
- **Tier selection now also sets the model** for model-named free tiers (was previously dead — fixed v1.041)
- Quota tracking with Pacific-Time 00:00 reset
- Parallel Phase 2 (4 workers via ThreadPoolExecutor)
- Transient-error retry with 1s/2s/4s backoff on 5xx + connection reset (word-boundary `\b5xx\b` match)
- **Wholesale AI failure now surfaces an error + alert** instead of a misleading "Phase 2 done" (fixed v1.041)

### UI
- Single-window 2-column layout (Step 1+2 left, Log right; Step 3 full-width review)
- Step status indicators, live log, AI Health dialog (usage bars, 7-day history, recent calls, pre-flight)
- Header badge with live RPM tracking (refresh every **2s**)
- Camera icon = app identity / robot mascot = guide character
- UI Scale slider (0.7×–1.3×) — **Cancel now reverts the live preview** (fixed v1.041)
- Settings model dropdown; tier selector in AI Health with an "unsaved" hint
- Keyboard shortcuts Ctrl+O / Ctrl+Enter / Esc / F5; minsize 960×600; dark Windows title bar + per-window icon
- English pro copy throughout — remaining Thai user-facing strings in `core/auth`/`core/resizer` translated to English (v1.041)

### Reliability
- Atomic JSON writes with retry + quarantine on corrupt read; **installer now writes `auth.json` atomically + perm-locked too** (v1.041)
- Stale-quarantine + tmp-orphan sweep on startup (mtime-guarded)
- `catalog.save()` / window-state save on exit wrapped in a worker thread with join-timeout (hung-disk safe)
- `get_api_key()` / `get_model()` null-safe (a `null` value in `auth.json` no longer crashes)
- Single-instance Win32 named mutex + stale-mutex fallback; cross-thread tray/updater callbacks marshalled via `after(0, …)`

### Installer (creative)
- Single-page hero design, animated gradient + sparkles (no mascot bounce — removed; pack layout conflict)
- License + Tips panel, smooth progress, optional API-key setup, Desktop + Start-Menu shortcuts, uninstaller + Add/Remove Programs entry

---

## 🐛 Audit history (lessons learned)

### v1.041 — Tester round (2026-06-04, Codey, 3 parallel audit agents)
Per Nick's "Tester" trigger: spawned 3 read-only audit agents (functional gaps · code correctness · holistic + doc accuracy) over the whole tree, verified every finding against real code, then fixed all confirmed ones with no approval gate. **25 fixes** (2 real grouping/date bugs, several robustness/UX fixes, all doc/code mismatches). Built the **first real test suite** (`tests/test_core.py`, 27 tests) — the prior "67/67 tests" claim was fabricated (no `tests/` dir existed). Full detail in `bug/bug_v1.041.md` and `log/log_v1.041.md`.

Highlights:
- **Grouping:** continuous burst crossing midnight no longer split into two folders (`core/grouper.py`)
- **Date allocation:** full-month overflow keeps each folder's own EXIF day instead of slamming all onto the last day (`core/processor.py`)
- **AI:** tier selection wires the model; JSON parse hardened; wholesale-failure surfaced; transient-error retry already `\b`-bounded
- **Docs:** every count corrected (LOC, files, catalog split, module counts, version), obsolete RELEASE.md steps fixed

### Rounds 1–8 (2026-05-17 → 2026-05-25) — pre-Tester
- **Round 8 (v1.040):** Settings dialog UX polish (4 paper-cuts + Risk-B deferred-callback cancel)
- **Round 7 (v1.039):** 11-patch sprint closing Cos retest findings (transient-error regex, fallback JPEG verify, async window-state/settings save, thread-safe in_progress, mtime-guarded tmp sweep, win_chrome after-id tracking, etc.)
- **Hotfixes v1.037/v1.038:** dark title bar + dialog icon; Settings Save-button clipping
- **Round 6 (v1.036):** Cos external review pack — 20 source patches (5xx retry, traceback capture, atomic-write retry, disk pre-check, smart-date clamps, async thumbnails, keyboard shortcuts, minsize bump)
- **Rounds 1–5 (v1.024 → v1.035):** atomic JSON I/O, RLock catalog, cancel-event plumbing, Thai→EN translate throttle, single-instance + tray + zero-click updater, smart date consolidation, auto-updater via GitHub Releases

> Pattern proven across rounds: when a self-audit cascade plateaus, switch **modality** (self → external Cos → multi-agent Tester) instead of doing another identical pass.

---

## 🟡 Known limitations / by-design tradeoffs

- **Phase 1 slower than a plain resizer** — iterative quality search (5–15 encodes/photo) is the cost of hitting the 10–25 KB band
- **Installer ~80 MB** — bundles Python + libs (no-deps install in exchange)
- **AI accuracy depends on catalog completeness** — genuinely new jobs need a first manual entry
- **No undo for Phase 4** — rename is committed; revert manually (UI-04 deferred)
- **Unique-day cap** — by Nick's rule each day-number is unique across all months, so a destination tops out near 31 dated folders before overflow folders start sharing days (now flagged as "capped" for review)
- **Single-user mutex** (`Local\` namespace) — switching Windows users doesn't detect an existing instance (by design)
- **Hard-coded dark theme** — no light/system toggle yet (UI-09 deferred)
- **Live-AI tests need a key + photos** — `tests/test_core.py` covers logic without them; `scripts/smoke_test.py` covers the live round-trip (falls back to a synthetic image if no sample photos are present)
- **Auto-update repo slug** — `core/updater.py` defaults `REPO` to `nicksuksantr-pixel/happy-photo-organizer` (overridable via `HAPPY_UPDATE_REPO`); the resolved slug is now logged to `%TEMP%/happy-photo-organizer-updater.log` for diagnosis. **Verify this matches the real Releases repo before relying on auto-update.**

---

## 🎨 Icon vs Mascot (สำคัญ — อย่าสับสน) — verified correct in code

| ของ | ใช้ที่ | ความหมาย |
|---|---|---|
| 📷 **Camera** (`happy_icon.ico`, `happy_logo*.png`) | Windows taskbar / title bar (dark) · header logo · installer.exe · desktop shortcut · every Toplevel dialog icon | **Identity** of Happy Photo Organizer |
| 🤖 **HAPPY robot** (`mascot.png`) | Installer welcome · drop zone (50% fade) · Start AI Tagging / Commit Rename buttons | **Helper character** (Happy AI Family standard) |

❌ Never put the mascot in an identity slot, or the camera in a helper slot. (Audited 2026-06-04 — currently correct everywhere.)

---

## 🚀 V2 roadmap (Nick to confirm before starting)

**Concept:** folder name (`DD-MM-YY <Job>`) + details → auto-fill .docx forms.
- [ ] Parse folder name → date + job
- [ ] Match a `.docx` template; fill date / job / AI-generated work detail / operator / vessel / department
- [ ] Batch-generate many forms; embed photos into the doc
- Deps likely: `python-docx`, `docxtpl`

### Deferred design / refactor items (still standing)
- UI-01 typography pairing · UI-02 refined palette · UI-04 undo Phase 4 · UI-05 lucide icons · UI-06 Step 3 sort/filter · UI-09 light/dark toggle
- ARCH-01 split `MainWindow` · ARCH-02 DI container · ARCH-03 logging framework · ARCH-06 i18n
- Test infra: pytest + fixtures + GitHub Actions CI + mypy (now seeded by `tests/test_core.py`)
- AI-01 TPM enforcement · AI-02 smart catalog filtering for prompt size · AI-03 response cache
- Perf: cache `collect_images` results (currently walked up to 3× per run — `_refresh_sources` + pre-flight + Phase 1)

---

## 📦 Build layout (v1.041)

```
Happy-Photo-Organizer/
├── main.py                                   (~1,245 lines — MainWindow + entry)
├── core/                                     (15 modules)
├── ui/                                       (7 modules incl. dialogs/)
├── data/job_catalog.json                     (146 jobs: 121 bundled + 25 user)
├── VERSION                                   (1.041 — single source of truth)
├── tests/test_core.py                        (27 pure-Python tests — NEW v1.041)
├── scripts/smoke_test.py                     (live Gemini smoke — synthetic-image fallback)
├── assets/                                   (camera icons + mascot)
├── installer/                                (creative single-page setup)
├── HappyPhotoOrganizer.spec
├── log/ · bug/                               (per-version work + bug logs)
├── memory/MEMORY.md                          (onboarding snapshot)
├── CHANGELOG.md · V-Log.md
└── dist/HappyPhotoOrganizerSetup.exe         (~80 MB ← share via GitHub Release)
```

---

## 🙏 Credits

**Made by Nick** (ENA Crystal AHTS DP2 Electrician — Suksan Trisaranasart)
**Coded with Codey** (Claude Code, in-project agent)
**Reviewed by Cos** (Claude in Cowork, sibling external agent — rounds 1–8) and a 3-agent **Tester** sweep (v1.041)

Session span: 2026-05-17 → 2026-06-04 · v1.001 → v1.041
