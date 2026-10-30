# Log — v1.043 (2026-09-02)

## Entry 1 — "รูปตัวอย่างไม่ขึ้น" (thumbnails never showed)
- Nick, with a screenshot of Step 3: every row had an empty box where the photo
  preview should be.
- `ui/job_row.py` was untouched since v1.036, so this was NOT caused by the
  v1.042 layout change — it had been broken all along.
- Both silent `except Exception: pass` layers meant nothing was ever reported.
  Built a standalone 3-variant repro to locate it instead of guessing, then a
  JobRow harness that classifies the tile actually bound to each button
  (photo / loading / missing) by comparing pixels — eyeballing a screenshot
  could not tell a dark placeholder from a dark empty box.
- Found **two** independent bugs (see bug/bug_v1.043.md): a CustomTkinter 5.2.2
  defect in `configure(image=...)`, and a thread-unsafe `after()` call that
  silently dropped the first row's thumbnail. Fixed both; the harness now
  reports all four cases correct, delivered on the first 100 ms poll.

## Entry 2 — Gemini 3.5 as the default + the badge that lied
- Nick: "เลือก 3.5 เป็นเริ่มต้นเลยนะตอนนี้ และเลือก 3.5 แต่หัวบนทำงาน 3.1 อยู่เลย".
- Default moved to `gemini-3.5-flash-lite` in `core/auth.py` (DEFAULT_MODEL),
  a new `free-3.5-flash-lite` tier preset (now DEFAULT_TIER, same free limits:
  RPM 15 / RPD 500 / TPM 250k), the Settings dropdown, the API-list fallback,
  and the installer's config seeding. The 3.1 preset stays for existing configs.
- The header badge was only ever printing the tier preset's hard-coded label, so
  it could never track the Settings model. API calls were already using the right
  model — the badge alone was wrong. It now reads `auth.get_model()`.
- ⚠️ `CLAUDE.md` said "don't change the default model from 3.1"; that line was
  written before Nick's move to 3.5 and is now updated, not silently ignored.

## Entry 3 — Tell work photos from screenshots / people / food, and delete the rest
- Nick: the AI should distinguish screenshots, photos of people and food — those
  are not jobs — and each folder needs a Delete button that also removes the
  photos and the folder the app created.
- The analyzer already *described* these correctly ("unrelated to ship
  engineering maintenance") but the prompt gave it no way out: rule 2 forced a
  job title for every image. Added an explicit `irrelevant` verdict to the prompt
  and schema, with examples and an explicit carve-out so PPE-wearing workers on
  equipment still count as real work. A flagged result is stripped of any name in
  both `analyzer` and `processor` — a self-contradicting reply can't sneak a job
  title through, and it can't reach the fuzzy catalog matcher either.
- Review rows: flagged ones get a red border, a "NOT WORK" marker and a red
  Delete button; every row now has a Delete button; a "🗑 Delete not-work (N)"
  bulk button appears in the Step 3 header only while something is flagged.
  Phase 4 asks separately before renaming anything still flagged.
- Delete removes only what Phase 1 created — the `__pending_` folder under the
  destination and the resized copies in it. `discard_assignment` refuses any
  folder outside the destination or without the pending marker, so a bad
  `temp_folder` fails loudly instead of deleting a real folder. Nick's originals
  are never touched, and the confirm dialog says so.

## Entry 4 — hazard caught while wiring the bulk delete
- The row tells the user "type a name to keep it", but the first version of
  "Delete not-work (N)" selected on `is_irrelevant` alone — so naming a flagged
  row to keep it and then clicking the bulk button would have deleted it anyway.
- Bulk delete, the header counter and the Phase 4 warning now all go through one
  predicate, `MainWindow._is_discardable` = flagged **and still unnamed**, so the
  number on the button is always exactly what the button deletes.
- (Per-row Delete is unaffected — that one is an explicit choice about one row.)

## Verification
- `tests/test_core.py` **35/35 PASS** (27 existing + 8 new: `_as_bool`,
  irrelevant-never-named, flag-cleared, and 4 `discard_assignment` guard tests
  incl. "refuses outside destination" and "refuses a folder we did not create").
- Thumbnail harness: 4/4 rows bind the correct tile (photo/photo/missing/missing).
- Row UI rendered and screenshotted: photo visible, flagged rows marked red.
- ❗ Not verified live: the AI's actual irrelevant/relevant accuracy needs a real
  key + Nick's real photos — the prompt change is the deliverable, the hit rate
  is his to judge on the next run.
