# Log — v1.046 (2026-09-22)

## Entry 1 — HPO becomes the receiver for JobShot (phone), steps 1–3

The R&D Director session sent the brief: a Flutter app (`Projects\JobShot`) lets
Nick create a job at the machine, photograph it, tag each shot Before/After and
push it to the PC. It sends **originals** and does not name the folder —
everything after arrival is HPO's existing pipeline. Steps 1–3 of five are done
here; 4 (LAN receiver) and 5 (pairing + catalog) are not started.

### Checked the brief against the code before building
Three claims held, one was out of date, one contradicted the code.

- ✅ `scan_used_days` (`processor.py:216`) and the assigner (`assign_unique_dates`,
  line 329) read `dest_root`. A phone cannot see the archive, so the date rule
  has to stay on the PC. Correct.
- ✅ No AI naming pass: the name is in `job.json`, chosen from the catalog by the
  person at the machine.
- ✅ The v1.045 rename orphans `photos[].file`. **Worse than the brief said**:
  `rename_photos_for_folder` renamed *every* file in the folder, so a `job.json`
  placed there before the commit would itself have become
  `22-09-26 DG3 Turbo Inspection_003.json` — the marker destroyed, not just the
  references. The rename now skips anything that is not an image, and it returns
  the old→new mapping (kept on `JobAssignment.photo_renames`, and corrected
  again if a merge has to rename a file a second time).
- ⚠️ "Your grouper splits on a 90-minute gap" — **out of date since v1.044**.
  Grouping is by capture date; the gap only bridges midnight. The conclusion
  ("do not re-group") still holds but for the opposite reason: day-grouping
  would *merge two different jobs shot on the same day into one folder with one
  name*, and nothing downstream could notice.
- ❗ The date rule vs. `work_date` — put to Nick, because it is his rule.
  `assign_unique_dates` consolidates into the destination's dominant month and
  forces day numbers to be unique across the archive. Both exist because the
  card-reader path has no idea when a job was really done. JobShot supplies the
  truth, so applied blindly they would *falsify* it (a 22 Sep job landing in an
  August-dominated tree becomes August; two jobs really done on the same day get
  different dates). **Nick's call 2026-09-22: the archive rule wins, unchanged.**

### What that decision means in practice, and the one narrow exception
A JobShot job goes through the rule exactly like every other folder, so its date
can move. `work_date` is therefore left untouched in the manifest and a `filed`
block records where the job actually landed (`folder`, `folder_date`,
`date_shifted`, `merged_into_existing_folder`, `hpo_version`). The date is
adjusted, never silently.

The exception, which is the rule's own logic rather than a hole in it: if a
folder for **this job on this day** already exists, the job is merged into it
instead of being pushed to the earliest free day. Shifting would produce two
folders, two dates and one real job — and spend a second day number on the
duplicate. Merging keeps one folder and one day, which is what "one day = one
folder" asks for. It is also the two-engineers-on-one-job case, and it is
reported (`merged_into_existing`), never silent. **One line to reverse if Nick
disagrees** — `core/jobshot.py`, the `same_job_today` branch.

### Built
- `core/jobshot.py` — manifest read/validate (`job.json` is the completion
  marker; a folder without it is a transfer in flight and is left alone),
  `import_job()` headless path (resize → pending folder → date rule → commit →
  manifest written into the final folder with `photos[].file` rewritten), and
  `get_dest_root`/`remember_dest_root` per vessel (step 3, stored in the
  existing config via `auth.update_config`).
- A second manifest arriving into the same folder is written as
  `job-<job_id>.json`, never over the first one — overwriting would erase the
  first job's tags.
- Originals are never consumed or deleted; the phone's copy stays the backup.

### Verification
`tests/test_core.py` **52/52 PASS** (44 + 8). The contract test builds the
arrival folder by hand — no phone, no network — and asserts the whole chain:
`DD-MM-YY <Job Name>` folder, photos renamed and resized into the 10–25 KB band,
manifest present with `photos[].file` rewritten and tags intact, the day rule
applied. Plus: a folder with no manifest is refused and untouched, the manifest
is not renamed as a photo, a shifted date is recorded, a second job merging in
keeps the first manifest and continues the numbering, bad manifests are refused
with a plain reason, and the per-vessel folder memory round-trips.

Photo tests need Pillow (a hard dependency of the app); they print SKIP instead
of failing if it is ever absent.

### Not done / not shipped
- Steps 4 (LAN receiver, receive log, undo for a merge) and 5 (QR pairing,
  serving `job_catalog.json`) — not started.
- No UI entry point yet, so **no build and no GitHub Release**: an installer
  that looks identical to the user is not worth pushing through the
  auto-updater. The code is on `main` for the JobShot session to build against.
