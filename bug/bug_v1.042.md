# Bug Log — v1.042

## BUG-1: Step 3 (Review & Edit Names) collapses to a sliver on short displays
- **Reported by:** Nick, 2026-08-05, with screenshot ("บางคอมขยายสุดแล้วช่อง 3 เล็กไปมองไม่เห็น").
- **Symptom:** on short displays (e.g. 1366×768 laptops / ~620 px-tall windows) the
  maximized window shows Steps 1-2 and the Log at full size while Step 3 — the main
  review/edit work area — is squeezed to a few pixels and unusable.
- **Root cause:** `main.py _build_ui` packed `header → top_row → step3`. The top row
  stacked Step 1 over Step 2 next to the Log (~430 px natural height). tk `pack`
  grants earlier-packed widgets their requested height first, so the *last* packed
  widget (Step 3) absorbed the entire deficit on short screens.
- **Fix (main.py):**
  1. Top row re-arranged to 3 side-by-side columns (Step 1 | Step 2 | Log) — ~200 px.
  2. Step 3 packed `side="bottom"` *before* top_row → shrink priority reversed; the
     top row now absorbs any squeeze.
  3. `table_scroll` given `height=150` as a guaranteed minimum for the review table.
  4. Compaction: drop zone 96→64, log box `height=110` (no longer drives row
     height), source list max 3 lines, wraplength 520→280 for the narrower cards.
- **Verified:** 27/27 tests PASS; real launches at 960×621 (Nick's saved geometry)
  and force-resized 1000×600 physical — Step 3 full-size and usable in both.
