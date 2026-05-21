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

## 📂 Key files

```
main.py                          ← GUI (v1.024)
core/                            ← analyzer/catalog/processor/rate_limiter/etc.
data/job_catalog.json            ← 138 jobs
assets/                          ← icons + mascot
installer/                       ← creative installer
HappyPhotoOrganizer.spec         ← PyInstaller spec
dist/HappyPhotoOrganizerSetup.exe ← Final installer (share this)
```

## 🎯 V2 roadmap (Nick to confirm before starting)

Fill .docx forms automatically from folder names + AI-generated work details.
See PROJECT_SUMMARY.md § "V2 Roadmap" for the brief.
