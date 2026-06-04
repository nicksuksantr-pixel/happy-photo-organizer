# Bug Log — v1.041 (Tester round, 2026-06-04)

Source: 3 parallel audit agents (functional gaps · code correctness · holistic + doc
accuracy). Every finding verified against real code before fixing. ~40 findings raised;
those below are the CONFIRMED + fixed ones. Severity: HIGH / MED / LOW.

> Entry cap per command_pattern #7 = 20. This file has 18 → still under cap.

| # | Sev | File:area | Bug | Fix | Status |
|---|-----|-----------|-----|-----|--------|
| 1 | HIGH | core/grouper.py:80-83 | Continuous burst crossing midnight (e.g. 23:59→00:01, <gap apart) split into 2 folders because `same_day` flipped. | Use `within_gap` alone; sorted items mean the only within-gap cross-day case is a near-midnight burst → one session. `representative_date`=min keeps the pre-midnight date. | ✅ fixed + test |
| 2 | HIGH | core/processor.py:264-272 | When target month full, every overflowing assignment set `new_day=last_day` → distinct jobs collapse to same date (and same-name ones merge). Broke unique-day intent. | `new_day = min(base.day, last_day)` — keep each photo's own EXIF day (clamped). Still flags `date_was_capped`. | ✅ fixed + test |
| 3 | MED | core/analyzer.py:_parse_json_response | Greedy `\{.*\}`+DOTALL matched first-`{`-to-last-`}` → invalid when model emits prose / two objects / extra braces → fell to error dict. | Rewrote with `json.JSONDecoder().raw_decode` scanning each candidate `{`/`[` — parses exactly one balanced value. | ✅ fixed + test |
| 4 | MED | core/processor.py:314-319 | A directly-dropped non-image file (.txt/.mp4) was appended unconditionally → inflated `total_images` + failed silently in resize. | Gate single files through `is_supported_image` (import added). | ✅ fixed |
| 5 | MED | core/processor.py:phase2 | `create_client()` failure set per-row reasoning but returned plan normally → UI logged "Phase 2 done". | Added `Plan.ai_error`; set on failure; main.py logs error + `messagebox.showerror`. | ✅ fixed |
| 6 | MED | ui/dialogs/settings.py | UI-scale slider applies live globally; Cancel/Escape/X left the preview applied until restart. | Capture `_original_scale`; `destroy()` reverts unless `_committed` (set True only on successful Save). | ✅ fixed |
| 7 | MED | ai_health.py:_apply_tier + rate_limiter | Tier preset `model` field was dead — picking "Free — 2.5 Flash" changed RPM/RPD but kept the old model; quota math vs model diverged. | `TierConfig` carries `model`; `_apply_tier` writes the preset's model (paid/custom leave Settings' model). | ✅ fixed + test |
| 8 | MED | core/updater.py:309 | Stale release-API `size` forced delete + 3× full re-download that never converged. | If transfer complete (actual==`expected_total` from Content-Length/Range), accept + log; only retry-fresh when no transfer signal. | ✅ fixed |
| 9 | MED | core/processor.py:368 | `source_label` picked the first image's label of a mixed-source group (arbitrary). | Use the majority source label among the group's images. | ✅ fixed |
| 10 | MED | main.py:_start_phase12 | Second batch left prior run's `self.plan` + Step-3 rows visible with "ready" while new analysis ran. | Clear `self.plan`, destroy table rows, set summary "Analyzing…" on start. | ✅ fixed |
| 11 | LOW | core/auth.py:get_api_key/get_model | `"api_key": null` → `dict.get(k,"")` returns None → `None.strip()` AttributeError crash. | `(load_config().get(k) or default).strip()`. | ✅ fixed + test |
| 12 | LOW | core/processor.py:_apply_result | `float(result["confidence"])` outside per-future try → a non-numeric value aborts the whole Phase 2 loop. | Wrapped in try/except → 0.0 on bad input. | ✅ fixed |
| 13 | LOW | core/rate_limiter.py:172 | Cancel during throttle sleep didn't roll back the claimed `_last_call_ts` → next worker over-waits. | Save prev ts; roll back on `_CancelledError` if not advanced. | ✅ fixed |
| 14 | LOW | ai_health.py:_render_history | `strptime(today_pt)` could raise on a malformed (non-None) string → refresh() swallowed it → blank dialog. | try/except → fall back to local today. | ✅ fixed |
| 15 | LOW | ai_health.py:_on_tier_radio | Radio selection gave no feedback until Apply → silent loss on close. | Apply button shows "• unsaved" when selection ≠ loaded tier. | ✅ fixed |
| 16 | LOW | core/catalog.py:179 | `dates_seen.sort()` lexicographic on "DD-MM-YY" → ordered by day-of-month, not chronological. | `_date_sort_key` parses to (yy,mm,dd). | ✅ fixed + test |
| 17 | LOW | core/processor.py:621 | `import time` inside Phase-4 retry loop + comment said "0.3s,0.9s" but actual 0.3/1.2/2.7s. | Hoisted `import time` to module top; corrected comment. | ✅ fixed |
| 18 | LOW | installer/installer.py:390 | `auth.json` written via plain `write_text` — non-atomic, world-readable; crash mid-write truncates prior config. | tmp + `os.replace` + `chmod 0600`, with last-resort fallback. | ✅ fixed |

## Verified-but-NOT-changed (intentional)
- **C7 dead `_plan_lock`**: removed the unused lock; `self.plan` is only ever assigned a
  fully-built object (atomic ref under GIL) — no partial state crosses threads. Not a bug.
- **F8 updater repo slug**: confirmed `nicksuksantr-pixel/happy-photo-organizer` matches the
  real GitHub repo (CHANGELOG release links + PR remote) → correct. Added a diagnostic log only.
- **F4 catalog `ships` dead**: left dormant — the pipeline has no reliable ship source;
  forcing `source_label` as ship would be wrong. Harmless schema for a future feature.
- **C11 exif `datetime.now()` last resort**: extremely rare (mtime almost always wins). Left.
- **B1 main.py god-object / perf triple `collect_images`**: deferred (ARCH-01 / V2), noted.

## Test result
`python tests/test_core.py` → **27/27 PASS**.
`python scripts/smoke_test.py` → **6/6 PASS** (live Gemini round-trip verified;
synthetic image used since the old D-drive samples are gone).
