# V-Log — Happy Photo Organizer (version timeline)

Full version history, oldest → newest. Detail per version lives in `CHANGELOG.md`,
`log/log_vX.md`, and `bug/bug_vX.md`. (Created 2026-06-04 per command_pattern #11.)

| Version | Date | Highlight |
|---------|------|-----------|
| v1.001–1.023 | 2026-05-17 → 05-21 | Initial build → iterate: drag-drop, resize 10-25KB, group-by-session, Gemini Vision tagging, catalog, rename pipeline |
| v1.024 | 2026-05-22 | Feature-freeze baseline (138 jobs, 14 formats, English UI, free-tier rate limiter) |
| v1.025 | 2026-05-22 | Auto-updater via GitHub Releases |
| v1.026 | 2026-05-22 | Smart date — consolidate to dominant month, unique days across months |
| v1.027 | 2026-05-22 | Window-state persist, dropzone border, layout refactor |
| v1.028 | 2026-05-22 | pystray + zero-click silent auto-update + single-instance |
| v1.029 | 2026-05-22 | Stale-mutex fallback, hide-to-tray on minimize, Range resume download; VERSION-file refactor |
| v1.030 | 2026-05-22 | Split main.py → core/ + ui/ |
| v1.031 | 2026-05-23 | Dark dialog backgrounds, unused-import cleanup |
| v1.032 | 2026-05-23 | UpdateWorker extracted to core/ |
| v1.033 | 2026-05-23 | Double-download race fix, startup installer-cache cleanup |
| v1.034 | 2026-05-23 | ETag + If-Range download integrity, debug-log rotation, requirements pins |
| v1.035 | 2026-05-23 | Round-5: async+throttled Thai→EN translate, catalog flush on destroy |
| v1.036 | 2026-05-24 | Round-6 Cos external review — 20 patches (5xx retry, traceback capture, disk pre-check, async thumbnails, keyboard shortcuts, minsize) |
| v1.037 | 2026-05-24 | Dark Windows title bar + per-Toplevel app icon (hotfix on v1.036) |
| v1.038 | 2026-05-25 | Settings dialog Save-button clipping hotfix (CRITICAL — key couldn't be saved) |
| v1.039 | 2026-05-25 | Round-7: 11-patch sprint (transient-error regex, fallback JPEG verify, async saves, thread-safe flags, mtime-guarded sweep) |
| v1.040 | 2026-05-25 | Round-8: Settings dialog UX polish (4 paper-cuts + Risk-B deferred-callback cancel) |
| **v1.041** | **2026-06-04** | **Tester round** — 3-agent full-system audit → 18 code fixes + all doc/code mismatches corrected; first real test suite (`tests/test_core.py`, 27 tests); midnight-grouping + full-month date-allocation bugs fixed; tier→model wiring; live AI smoke test green |
