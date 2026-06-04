# Happy Photo Organizer — Codey Onboarding

> Claude Code auto-loads this when you open this folder.

## 🚀 Quick start

1. Read [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) — full state, lessons, V2 plan
2. Read [GEMINI_LIMITS.md](GEMINI_LIMITS.md) — quota rules
3. Wait for Nick's instruction

## 🛑 Don't do (already decided in v1.024)

- ❌ Don't revert UI from English back to Thai (Nick wants pro)
- ❌ Don't put mascot in identity slots (camera = identity, robot = helper)
- ❌ Don't change default model from `gemini-3.1-flash-lite`
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
