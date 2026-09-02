# Log — v1.045 (2026-09-02)

## Entry 1 — Every folder restarted at `img_001`, so moving photos meant renaming them
- Nick, with two Explorer windows side by side: `20-09-26 Repaired Vingtor
  marine intercom` held `img_001, img_002`, and `27-09-26 Repaired internal
  wiring of Vingtor` held `img_001 … img_010` — the same names again. His words:
  "ไฟล์รูปชื่อเหมือนกันมันย้ายลำบาก ต้องคอยเปลี่ยนชื่อมัน". His own workaround is
  visible in the screenshot: `img_0028` and `img_0077` are files he had already
  renamed by hand to get them into that folder.
- Cause: Phase 1 writes every resized photo as `img_{seq:03d}.jpg` into its
  temp folder ([core/processor.py](../core/processor.py) line 420) and the
  counter restarts at 1 for each group, so the names were only ever unique
  *within* one folder. Dragging a photo across folders always hit Windows'
  "a file with this name already exists".
- Decision (asked Nick, he picked the format): photos are named after the
  folder they belong to — `DD-MM-YY <Job>_001.jpg`. Uniqueness comes for free
  because a folder is one shooting day (v1.044) and `assign_unique_dates`
  never issues the same day twice. It also means a photo pasted into a report
  or an email still says which job it came from.
- Where the rename happens: Phase 4, not Phase 1. The final folder name is not
  known until the AI has named the job and Nick has reviewed it, and the folder
  date can still be shifted into the target month, so naming at resize time
  would have baked in a name the folder never ended up having. Files are
  renamed inside the temp folder immediately before it is renamed/merged into
  its final home.
- Numbering continues instead of colliding: merging into a folder that already
  holds `..._001/_002` starts at 003, so a second run into the same day no
  longer produces `..._001_2.jpg` via the collision-suffix fallback.
- Windows path limit: the folder name is now repeated inside every file name,
  so `photo_prefix()` trims it to whatever keeps the full path within 259
  characters (and 100 characters regardless, for readability). A destination so
  deep that even the folder alone busts the limit falls back to `img_NNN`.
- Non-fatal by construction: a failed rename leaves that one file under its old
  name and is reported through `CommitResult.errors`; the folder still commits.
  A filename must never cost Nick a commit.
- ❗ Old folders are untouched — Nick chose "leave them, new runs only", so the
  photos already filed as `img_001` stay as they are.

## Verification
- `tests/test_core.py` **43/43 PASS** (38 + 5: named-after-folder, no duplicate
  names across two folders — the actual complaint, merge continues numbering,
  path-limit trimming, and the pre-existing suite unchanged).
- Caught during the work, same family as v1.044's BOM bug: `Path.write_text()`
  on Windows translates every LF into CRLF, which put CRLF into `core/processor.py`.
  `test_no_source_file_carries_a_bom_or_cr` failed and the file was rewritten
  with `newline=""`. The guard added last version paid for itself one day later.
