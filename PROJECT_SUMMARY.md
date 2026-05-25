# 🎨 Happy Photo Organizer — Project Summary

**Status:** v1.038 (2026-05-25 — Settings dialog Save-button clipping hotfix)
**Author:** Nick (with Codey — Claude Code)
**Family:** Happy AI Family (siblings: HAPPY AI Agent)
**Last full review:** Cos external audit 2026-05-24 → v1.036 Round-6 (20 patches) → v1.037 hotfix → Cos re-test (67/67 PASS) → 11 new low-risk findings → v1.038 critical hotfix (Settings cavity clipping found via Nick's fresh-install repro 2026-05-25)

---

## 📋 What it does

AI-powered photo organizer for ship maintenance & repair work:
1. Drop folders/photos → auto-detect capture date
2. Resize to 10–25 KB (target for email attachments)
3. Group by day + AI tag job name (Gemini Vision)
4. Review & edit before commit
5. Rename folders as `DD-MM-YY <Job Name>`

---

## 🏗 Tech Stack

| Layer | Choice |
|---|---|
| GUI | customtkinter 5.2 + tkinterdnd2 |
| AI | google-genai (Gemini 3.1 Flash Lite default) |
| Image | Pillow + pillow-heif (HEIC/iOS support) |
| Distribution | PyInstaller (folder mode) + custom installer |
| Storage | JSON files + Windows registry |

---

## 📦 Current state (v1.037)

| Metric | Value |
|---|---|
| Python LOC | ~5,650 (32 .py files, excluding dist/) |
| Catalog jobs | 146 (138 bundled + 8 user-added) |
| Image formats | 14 (incl. HEIC/HEIF) |
| Audit rounds | 6 (round-6 = Cos external review, 20 patches applied) |
| Test status | 67/67 pure-Python unit + integration tests pass |
| Build artifact | `dist/HappyPhotoOrganizerSetup.exe` (~80 MB) |
| New modules in v1.036/v1.037 | `ui/win_chrome.py` (dark title bar + icon) |

---

## 🎯 Features delivered (cumulative through v1.037)

### Core workflow
- Drag-drop multi-source (folders + files)
- Recursive image collection (14 formats incl. HEIC)
- EXIF + filename + mtime date detection
- Resize 10-25 KB iterative quality with JPEG integrity verify (v1.036 R6-BUG-L7)
- Group by date + 90-min time gap
- Smart date allocation: consolidate to destination's dominant month, unique day numbers across all months, earliest-gap-first, clamp implausible years (>5y from now, v1.036 R6-BUG-M3)
- Disk-space pre-check at Phase 1 with 2× headroom (v1.036 R6-BUG-M2)
- Phase 4 rename retries 3× on transient PermissionError (v1.036 R6-BUG-L9)
- Auto-updater silent + zero-click via GitHub Releases API (since v1.025; v1.036 fixed parsed-version comparison)

### AI / Gemini
- Gemini Vision per-folder sampling (1-3 photos)
- Fuzzy match catalog (cutoff 0.85)
- Translate Thai → English job names (throttled + logged, v1.035 R5-BUG-1)
- Auto-add new names to catalog
- Rate limiter (tier presets + custom RPM/RPD + cancel-aware throttle sleep)
- Quota tracking with PT 00:00 reset
- Parallel Phase 2 (4 workers via ThreadPoolExecutor)
- **Transient-error retry** with 1s/2s/4s exponential backoff on 5xx + connection reset (v1.036 R6-AI-04)
- Stack-trace capture on Phase 2 worker errors (v1.036 R6-BUG-M4)

### UI
- Single-window 2-column layout (Step 1+2 stacked left, Log full-height right)
- Step status indicators (Pending/Ready/Running/Done) via Canvas oval
- Live log panel with realtime updates
- AI Health dialog (usage bars, 7-day history, recent calls, pre-flight calculator)
- Header badge with live RPM tracking (refresh every 2s)
- Camera icon = app identity / Robot mascot = guide character
- Clickable URLs to AI Studio
- UI Scale slider (0.7x – 1.3x)
- Pro English copy throughout
- **Async thumbnail loading** in Step 3 (v1.036 R6-BUG-M7)
- **Keyboard shortcuts** Ctrl+O / Ctrl+Enter / Esc / F5 (v1.036 R6-UI-03)
- **Minsize 960×600** (was 640×420, v1.036 R6-UI-13)
- **Dark Windows title bar** on main + dialogs via DWMWA_USE_IMMERSIVE_DARK_MODE (v1.037)
- **App icon on every Toplevel** via Tk class-level + per-window + Pillow fallback (v1.037)

### Reliability
- Atomic JSON writes (auth.json, usage_log.json, job_catalog.json) with quarantine on corrupt read
- **Retry 3× with backoff** in atomic_write_json — AV scanner lock recovery (v1.036 R6-BUG-L2)
- Stale-quarantine + tmp-orphan sweep on startup (v1.036 R6-BUG-L10)
- catalog.save() on destroy() wrapped in thread with 2s timeout (v1.036 R6-BUG-H1)
- paste_helper probes `_entry`/`entry`/`_input` instead of hard-coded internal (v1.036 R6-BUG-H3)
- Update poll logs state transitions only (v1.036 R6-BUG-M6)
- JPEG integrity verify after encode (v1.036 R6-BUG-L7)
- Cross-keyboard-layout Ctrl+V (keycode, not keysym)
- Cross-thread tray callbacks via host.after(0, ...)
- Single-instance Win32 named mutex + stale-mutex fallback

### Installer (creative)
- Single-page Hero design (no wizard nav)
- Animated gradient background + sparkles
- License + Tips panel during install
- Smooth progress (every file update, 0–100%)
- API key setup during install (optional)
- Desktop shortcut + Start Menu integration
- Uninstaller (uninstall.bat + HKCU registry)
- Add/Remove Programs entry

---

## ⚖ Cos audit (2026-05-24) — overall 7.9 / 10 → ~8.5 / 10 after v1.036+v1.037

| Category | Pre-v1.036 | Post-v1.037 | Δ |
|---|---|---|---|
| Layout / UI Structure | 8.5 A- | 9.0 A | +0.5 (keyboard shortcuts, minsize, dark chrome) |
| Visual Design / Typography | 7.0 B | 7.5 B+ | +0.5 (dark title bar; palette still pending) |
| Code Quality | 9.0 A | 9.5 A+ | +0.5 (20 patches closed) |
| Architecture / Modularity | 8.0 A- | 8.0 A- | 0 (main.py split deferred to V2) |
| AI / Gemini Integration | 9.0 A | 9.5 A+ | +0.5 (5xx retry, traceback capture) |
| Test Coverage | 4.0 D | 4.5 D+ | +0.5 (cleanup + verify helpers tested) |
| Documentation | 9.5 A+ | 9.7 A+ | +0.2 (audit log + round-6 detail) |
| Production Readiness | 8.5 A- | 9.0 A | +0.5 (more crash-safe paths) |
| **Overall** | **7.9 B+** | **~8.6 A-** | **+0.7** |

---

## 🐛 Round-7 follow-up — 11 new low-risk findings (Cos re-test 2026-05-24)

All discovered after Codey shipped v1.037. None block usage; bundle into next feature release per Nick's standing rule (round-6 pattern).

| ID | Sev | File | Issue |
|---|---|---|---|
| BUG-N1 | LOW | main.py:795-802 | `destroy()` has duplicate `after_cancel` block (dead code). |
| BUG-N2 | MED | core/analyzer.py:26-36 | `_is_transient_error` substring match: "500"/"502"/"503"/"504" tokens match anywhere in error string → false-positive retry. Use `\b` regex. |
| BUG-N3 | LOW | core/resizer.py:113-124 | Fallback path (lowest-quality save when target_kb_max exceeded) skips `_verify_jpeg_readable`. Could silently commit a corrupt JPEG. |
| BUG-N4 | LOW | main.py:770-786 | `_save_window_state` still synchronous after R6-BUG-H1 wrapped catalog.save() in timeout. Same hung-disk class. Wrap in same pattern. |
| BUG-N5 | LOW | core/processor.py | Year clamp (>5 from now) lives in `phase1_resize_and_group`, not in `detect_target_month`. Future callers don't get it. Move into function. |
| BUG-N6 | LOW | ui/win_chrome.py:135 | `apply_chrome` schedules `after(50, apply_dark_title_bar)` without tracking id. Dies early → "invalid command" warning. |
| BUG-N7 | LOW | main.py:_kbd_open / _kbd_run | Keyboard shortcut skip check uses `winfo_class()` string ("Entry"/"Text") — misses CTkEntry's outer-frame focus. Use `self.focus_get()` + isinstance check. |
| BUG-N8 | LOW | ui/dialogs/settings.py:_save | Calls `atomic_write_json` (retry up to 0.45s) on UI thread → potential 0.45s freeze under AV lock. Move to daemon thread with after(0,...) status. |
| BUG-N9 | LOW | core/update_worker.py | `self.in_progress` flag set in worker thread, read in Tk thread, no lock. Theoretical race → re-entry of `_begin_download`. |
| BUG-N10 | LOW | core/auth.py:cleanup_stale_quarantines | tmp-orphan sweep races with concurrent atomic_write_json tmp file. Add mtime > 5s check. |
| BUG-N11 | LOW | ui/win_chrome.py:120 | Same as BUG-N6 — `apply_icon_to_window` retry at +200ms not cancelled if window dies early. |

**Recommendation:** Codey can clear all 11 in one round-7 pass (~2 hours total — most are 5-15 min surgical patches). Bundle with v2 docx form filler or ship as v1.038 paper-cut release after V2 lands.

---

## 🟡 Known limitations / by-design tradeoffs

- **Phase 1 ช้ากว่า Nick_Resizer 5-10x** — iterative quality reduction (5-15 encode/รูป)
- **Installer size 80 MB** — Python + bundled libs (no-deps install in exchange)
- **AI accuracy depends on catalog completeness** — new jobs require manual entry first time
- **No undo Phase 4** — rename committed; revert manually. Deferred per Cos UI-04, still on the V2-or-later list
- **Mascot mild distortion** — CTkImage scaler trims arms slightly = signature of HAPPY mascot
- **Single-user mutex** — `Local\\` namespace; switching Windows users doesn't detect existing instance (by design)
- **No light/dark mode toggle** — hard-coded dark (UI-09 deferred)
- **Tests use stub `google.genai`** — real Gemini integration tested only via Nick's machine + production runs

---

## 🐛 Audit history (lessons learned)

### Round 6 (2026-05-24) — Cos external review pack, 20 patches
External world-class review by Cos (Claude in Cowork — sibling instance). Cos read all 26 .py / 5,481 LOC, ran static analysis, produced 7.9/10 / B+ / 3 HIGH + 8 MED + 10 LOW bugs + 15 UI + 7 architecture + 6 AI findings, each with file:line and concrete fix. Codey triaged + patched 20 source-only in two passes. Pattern proved: when self-audit cascade plateaus, switch *modality* (self → external) instead of doing another self-round.

### Round 5 (2026-05-23 #2) — 2 source patches, 2 deferred
- R5-BUG-1: `_translate_to_english` made async + throttled + logged
- R5-BUG-2: catalog flushed in `destroy()` to close in-memory-loss window

### Round 4 (2026-05-23 #1) — 0 findings (audit plateau signal)

### Round 3 (2026-05-23) — 7 source patches
JobCatalog atomic save, RLock for catalog mutation, dead param removed, Phase 4 progress fired after work, collision counter capped at 9999, empty-dest year defaults to now, wm_state alias unified.

### Round 2 (2026-05-22) — 2 findings (cleanup of dead webbrowser/get_model imports)

### Round 1 (2026-05-22) — 13 hidden bugs + 8 future risks, all addressed in v1.034
Atomic auth.json/usage_log.json, parsed-tag dropped fix, window-state withdrawn skip, cancel_event piped through Phase 2 worker, single-write tier change, tray-thread → Tk marshalling, etc.

### Per-version older highlights
- v1.034: ETag + If-Range download integrity, debug log rotation, requirements upper-bound pins
- v1.033: double-download race fix, startup installer cache cleanup
- v1.032: UpdateWorker extracted to core/
- v1.031: dark dialog backgrounds, unused-imports clean
- v1.030: main.py → core/ + ui/ split (1275 → 800 lines initially)
- v1.029: stale-mutex fallback, hide-to-tray on minimize, Range resume download
- v1.028: pystray + zero-click silent auto-update + single-instance
- v1.027: window state persist + dropzone subtle border + layout refactor
- v1.026: smart date — consolidate to dominant month, unique days across months
- v1.025: auto-updater via GitHub Releases
- v1.024: feature freeze baseline (138 jobs, 14 formats, English UI, free-tier rate limiter)

---

## 🎨 Icon vs Mascot (สำคัญ — อย่าสับสน)

| ของ | ใช้ที่ | ความหมาย |
|---|---|---|
| 📷 **Camera** (`happy_icon.ico`, `happy_logo*.png`) | • Windows taskbar / title bar (now ดำ in v1.037)<br>• Header logo ในแอป<br>• Installer.exe icon<br>• Desktop shortcut<br>• Toplevel dialog icons (v1.037) | **Identity** ของแอป Happy Photo Organizer |
| 🤖 **HAPPY robot** (`mascot.png`) | • Welcome screen ของ installer<br>• Drop zone (50% fade)<br>• ปุ่ม Start AI Tagging / Commit Rename | **Helper character** — guide การใช้งาน (มาตรฐาน Happy AI Family) |

**❌ อย่าใช้ mascot ในตำแหน่ง identity** — Desktop จะซ้ำกับ HAPPY AI Agent
**❌ อย่าใช้ camera ในตำแหน่ง helper** — เสีย branding ของ HAPPY family

---

## 🚀 V2 Roadmap (next session)

**Concept:** เอาชื่อโฟลเดอร์ (DD-MM-YY <Job>) + รายละเอียด → กรอก form เอกสารอัตโนมัติ

### Features ที่จะทำ V2
- [ ] อ่าน folder name → parse date + job name
- [ ] Match กับ form template ที่มีอยู่ (.doc / .docx)
- [ ] เติม fields: วันที่ / ชื่องาน / รายละเอียด (AI-generated) / ผู้ปฏิบัติงาน / เรือ / แผนก
- [ ] Batch generate หลาย form จากหลายโฟลเดอร์ทีเดียว
- [ ] Output: .docx ที่กรอกแล้ว + embed รูปลง form

### Dependencies ที่อาจต้องการ
- `python-docx` — read/write .docx
- `docxtpl` — Jinja-style templating
- AI ช่วยสรุป "รายละเอียดงาน" จากรูป
- F-04-TEC-03 Engine Maintenance Report template

### ความท้าทาย V2
- Template parsing (placeholders / merge fields)
- Embedding รูปลง .docx ตามขนาด/ตำแหน่ง
- Multi-language (TH report + EN folder name)

### Deferred design / refactor items (still standing per Cos review)
- UI-01: Inter/Aptos + JetBrains Mono typography pairing
- UI-02: Refined orange/pink palette (less saturated)
- UI-04: Undo Phase 4 (rename_history.json + revert button)
- UI-05: lucide PNG icons replacing OK/?/! text
- UI-06: Step 3 sort/filter toolbar
- UI-09: Light/Dark/System mode toggle
- ARCH-01: split MainWindow (1229 lines) into controllers
- ARCH-02: dependency-injection container
- ARCH-03: logging framework + rotating file log
- ARCH-06: gettext/i18n for TH UI
- Test infra: tests/ + fixtures + pytest + GitHub Actions CI + mypy
- AI-01: TPM enforcement in rate_limiter
- AI-02: smart catalog filtering for prompt size
- AI-03: AI response cache layer

---

## 📦 Build artifacts (v1.037)

```
Documents/Projects/Happy-Photo-Organizer/
├── main.py                                   (~1229 lines)
├── core/                                     (15 modules — added catalog/update_worker since v1.024)
├── ui/                                       (8 modules — win_chrome.py added v1.037)
├── data/job_catalog.json                     (146 jobs, growing)
├── VERSION                                   (1.037)
├── assets/                                   (camera icons + mascot)
├── installer/                                (creative single-page setup)
├── HappyPhotoOrganizer.spec
├── CHANGELOG.md                              (rounds 1-6 + unreleased)
└── dist/
    ├── HappyPhotoOrganizer/                  (120 MB folder mode)
    ├── HappyPhotoOrganizer.zip               (48 MB payload)
    └── HappyPhotoOrganizerSetup.exe          (80 MB ← share via GitHub Release)
```

---

## 🙏 Credits

**Made by Nick** (ENA Crystal AHTS DP2 Electrician — Suksan Trisaranasart)
**Coded with Codey** (Claude Code, in-project agent)
**Reviewed by Cos** (Claude in Cowork, sibling external agent)

Session date: 2026-05-17 → 2026-05-24 (8 days, v1.001 → v1.037)
Total iterations: 37 versions
Audit rounds: 6 + 1 follow-up
