# Happy Photo Organizer — Codey Onboarding

> **🔗 Rules-in-repo bootstrap (command_pattern #22, added 2026-07-12).** Any instance — local Coddy OR cloud/GitHub — must follow this:
> **⚡ Session start → read `memory/MEMORY.md` + the newest `chat_log/` file, then `memory/nick-workflow.md` (the synced master-rule brief — currently command_pattern v3.12/24). Follow them.** · chat = **Thai** · records = **English** (#17).
> ⛔ **Agent cap (#16):** ≤3/round · max 5 · >5 STOP+ask · never self-start Tester/Lucifer/supertester (only on Nick's typed trigger) · FAIL = STOP (1 trigger = 1 launch, never blind-retry).
> 🔄 **Git (#20/#21):** session start → `git fetch`, `git pull --ff-only` if behind (diverged = STOP, never force-push) · task done → `git commit` + `git push` automatically (code **and** records).
> 🔐 **Security = approve-before-fix (#24):** the **"supertester security"** review audits **READ-ONLY** → presents a fix plan + per-fix blast-radius → **WAITS for Nick's approval** → fixes on a security branch (backup first) → **never auto-build/deploy**. ❌ Never auto-fix like Tester/supertester.

---

> Claude Code auto-loads this when you open this folder.

## 🚀 Quick start

1. Read [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) — full state, lessons, V2 plan
2. Read [GEMINI_LIMITS.md](GEMINI_LIMITS.md) — quota rules
3. Wait for Nick's instruction

## 🛑 Don't do (already decided in v1.024)

- ❌ Don't revert UI from English back to Thai (Nick wants pro)
- ❌ Don't put mascot in identity slots (camera = identity, robot = helper)
- ❌ Don't change default model from `gemini-3.5-flash-lite` (Nick moved it off
  3.1 on 2026-09-02 — same free limits; the old "keep 3.1" rule is retired)
- ❌ Don't print a model name in the header badge from a tier preset label —
  read `auth.get_model()`, or the badge starts lying again (v1.043 BUG-3)
- ❌ Don't add bounce animation to mascot (causes render artifacts)
- ❌ Don't remove uninstaller or registry registration
- ❌ Don't refactor Phase 2 to sequential (parallel = 4x faster)

## 🔀 Workflow (decided 2026-06-04 — Nick)

- ✅ **Work directly on `main`** — no feature branches, no PRs. The old
  `tester/* → PR → merge` flow is retired (PR #1 + its branch were cleaned up).
- ✅ **Commit, push, build, and publish GitHub Releases without asking.** Nick gave
  standing authorization ("อัพขึ้นเลยตามปกติ ไม่ต้องถาม"). Run the normal release
  flow (see [RELEASE.md](RELEASE.md)) and report what shipped at the end.
- Unchanged: bump version via the `VERSION` file only; tag `vX.XXX`; keep the asset
  named `HappyPhotoOrganizerSetup.exe` (the auto-updater depends on both).

## 📂 Key files

```
main.py                          ← GUI (MainWindow + entry, ~1,245 lines)
core/                            ← 15 modules: analyzer/catalog/processor/rate_limiter/etc.
ui/                              ← 7 modules: theme/job_row/step_card/dialogs/etc.
data/job_catalog.json            ← 146 jobs (121 bundled + 25 user-added)
tests/test_core.py               ← 27 pure-Python tests (run: python tests/test_core.py)
scripts/smoke_test.py            ← live Gemini smoke test (synthetic-image fallback)
assets/                          ← icons + mascot
installer/                       ← creative installer
HappyPhotoOrganizer.spec         ← PyInstaller spec
VERSION                          ← single source of truth (1.041); version.py reads it
dist/HappyPhotoOrganizerSetup.exe ← Final installer (share this)
```

> Version is bumped by editing the `VERSION` file ONLY — `main.py` and the
> installer read it at runtime (do not hunt for an `APP_VERSION = "..."` literal).

## 🎯 V2 roadmap (Nick to confirm before starting)

Fill .docx forms automatically from folder names + AI-generated work details.
See PROJECT_SUMMARY.md § "V2 Roadmap" for the brief.
