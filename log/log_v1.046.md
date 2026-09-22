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
reported (`merged_into_existing`), never silent. **Superseded the same day by
Entry 2** — that narrow check only held while the first arrival kept its own
day, so the `same_job_today` branch no longer exists; matching now runs on the
job's identity.

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

## Entry 2 — one real job = one folder, matched at arrival (same day, v1.046)

Nick's ruling on the date rule (Entry 1) has a consequence the R&D Director
spotted after sending the brief, and spotted correctly: **the unique-day rule
and merge-on-name-collision are in tension by construction.** If engineer A's
job is filed on day 22 and engineer B sends the same job, `scan_used_days`
reports 22 as taken, B is shifted to the earliest free day, the names never
collide — and one real job ends up owning two folders on two dates.

Entry 1's narrow fix (merge when `dest_root/<work_date> <job name>` exists)
closed that only while the first arrival kept its own day. The moment the rule
shifted the FIRST job as well — A filed on day 1 because day 22 was already
gone — B looked for `22-09-26 …`, found nothing, and got a third folder.

**Nick's call: go further — group at arrival on the job's own identity.**

- `find_filed_job(dest_root, ship, job_name, work_date)` reads the manifests HPO
  leaves in the filed folders and returns the folder this job already lives in,
  **whatever day the rule gave it**. Identity = ship + job_name + work_date,
  with job names normalised through the catalog's own `_normalize` (so
  "No. 3" and "No.3" are one job). A missing ship on either side does not block
  a match — it is metadata, not identity; only a genuine disagreement does.
- This is the second reason `job.json` is carried into the final folder: it is
  what lets a job arriving days later find its own folder.
- The name+date fallback is kept **only for folders that hold no manifest** —
  i.e. filed by the card-reader path, where there is nothing to match on. If a
  folder has a manifest and it did not match, that is an answer (a different
  vessel, a different work date), not a gap to paper over with the name.
- A folder renamed by hand after filing is followed, not duplicated: the job
  lives there now, so the arrival merges into it and says so in the warnings.
- The date rule itself is untouched. It still assigns the day for every job
  that is not already filed, and `work_date` never steers it.

### Verification
`tests/test_core.py` **56/56 PASS** (52 + 4): a job whose own folder was moved
by the day rule is still found; two different jobs on one day keep separate
folders; a folder renamed after filing is followed; two vessels sharing a job
name do not merge.

### Version
Still **v1.046** — it was committed but never built or released, so this is the
same unreleased version rather than a phantom v1.047.

## Entry 3 — the manifest shrinks, and the batch case (same day, v1.046)

Two more messages from the R&D Director, both landing on work that was already
finished. Taken in order of what they changed.

### The scope cut — `job.json` v1 loses its tags and notes
Nick: *"don't send before/after — EMR already does it"*, and the same reasoning
retires the notes and spare parts. JobShot now sends identity plus a file
manifest, and **EMR is out of the programme entirely**:

    { "jobshot": 1, "job_id", "job_name", "ship", "author", "created_at",
      "work_date", "photos": ["0001.jpg", "0002.jpg", ...] }

`photos[]` is now a list of plain file names. HPO reads **both shapes** — the
new list of names and the older `{"file": ...}` objects — and writes each
manifest back in the shape it arrived in. The phone and the PC ship separately,
so the reader has to tolerate both for as long as both exist.

What this does to the rename rewrite: its *purpose* changes, not its
correctness. It is no longer carrying tags for the report, so it is no longer
load-bearing; it stays because a manifest listing names that are not in the
folder is a trap for whoever reads it next, and because the receive log (step 4)
needs to say which sent file became which filed file. **The
`rename_photos_for_folder` fix that skips non-images is untouched and is not
optional** — that one protects the completion marker itself, and always did.

### `ship` comes out of the identity key
The Director's ruling: `dest_root` is per vessel, so two jobs reaching the same
destination are already on the same ship. Keeping `ship` in the key had a real
cost — a vessel name typed slightly differently on two phones ("ENA CRYSTAL" vs
"Ena Crystal AHTS") would split one real job into two folders. Identity is now
`job_name` + `work_date` only (`job_key()`), and the test that asserted two
vessels stay apart was **inverted**: it now pins that the ship field is ignored.
A test that documents a rule has to change when the rule does.

### The batch case — `import_batch()`
Nick approved arrival-time grouping as a **superset** of what shipped: keep the
match against already-filed folders, and add grouping for arrivals that land
*together*. Not theoretical, per the Director: Nick collects several jobs and
sends them in one sitting, and two engineers paired to one PC can interleave
their sends.

- `import_batch(folders, dest_root)` parses every arrival, groups them on
  `job_key`, and files each group as **one job** — one resize pass, one day
  assignment, one commit — so a pair gets one folder and one day instead of two.
- One result per input folder, in the input order, so a receive log can say what
  happened to each. An unreadable or still-arriving folder is reported and
  skipped; it never costs the rest of the send.
- Each sender keeps its own manifest (`job.json`, then `job-<job_id>.json`), and
  both record `grouped_with` so the pairing is visible afterwards.
- The old-to-new photo map is **per arrival**: two phones both send `0001.jpg`,
  and a single shared map would have one overwrite the other — a manifest
  pointing at someone else's photo. Pinned by a test.
- Group order: oldest `work_date` first, tie-broken by when the job was created
  on the phone. Jobs sharing a day cannot all keep it, and the one done first
  has a better claim to it than whichever name happens to sort lower.

`import_job()` is now `_file_group()` with a single arrival, so both paths run
the same code.

### Also — the suite was getting slow
The synthetic photos were built by a Python loop over ~2 million pixels each,
which had pushed the run past two minutes. `Image.frombytes` over `os.urandom`
does the same job in C: **39 s for the whole suite**. A suite nobody waits for
is a suite nobody runs.

### Verification
`tests/test_core.py` **61/61 PASS** (56 + 5, one inverted): plain-file-name
manifests file and round-trip, the ship field is ignored, a batch groups two
arrivals of one job into one folder, per-arrival photo names do not collide,
different jobs keep their own folders with the day rule deciding who keeps the
day, and a bad arrival does not drop the good one.

Still **v1.046**, still not built or released — no UI entry point.
