# Log — v1.042 (2026-08-05)

## Entry 1 — Small-screen layout fix: Step 3 becomes the primary area
- Nick (Thai, with screenshot): Step 3 "Review & Edit Names" is the panel where the
  real work happens, but on some computers a maximized window leaves it too small to
  see. Fix requested.
- Root cause: root layout packed `header → top_row → step3`; the top row stacked
  Step 1 over Step 2 (~430 px natural height). tk `pack` satisfies earlier-packed
  widgets first, so on short displays the last-packed Step 3 absorbed the whole
  height deficit and collapsed to a sliver.
- Fix (main.py, UI-only — no core changes):
  1. Top row re-arranged to **3 side-by-side columns: Step 1 | Step 2 | Log**
     (uses spare width instead of scarce height; top row now ~200 px tall).
  2. **Pack priority flipped** — Step 3 packed `side="bottom"` *before* top_row,
     so a short window squeezes the top row, never Step 3.
  3. Review table requests a **150 px guaranteed minimum**; still expands to fill
     all remaining height (big screens now give Step 3 far more room).
  4. Compaction: drop zone 96→64 px, log box requests 110 px, source list capped
     at 3 lines (was 6), label wraplength 520→280, workflow caption shortened.
- Verified: `tests/test_core.py` 27/27 PASS · real app launched at Nick's saved
  960×621 geometry and force-resized to 1000×600 physical (harsher than the app's
  own 960×600 logical minsize) — Step 3 stays full-size and usable in both.
- Released v1.042 (commit + push + build + GitHub Release per standing
  authorization); Nick's saved window_state was backed up and restored after the
  visual test.
