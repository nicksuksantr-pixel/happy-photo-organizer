# Log — v1.053 (2026-09-25)

## Entry 1 — the report draft now rides along

JobShot asked three precise questions before building a feature on top of HPO,
and the honest answers required reading the code rather than remembering it.

**(a) Does the importer tolerate an entry that is neither a photo nor
`job.json`?** It did not refuse the job — which is what JobShot feared — but the
truth was worse in a quieter way: `_bad_entry()` allowed only
`^job(-…)?\.json$`, so `emr.json` was **dropped during extraction** with a
warning buried in `warnings[]`, and the job was filed without it.

**(b) Does it copy such a file into the archive folder?** No. Even had it been
extracted, `_read_arrival` builds its file list from `manifest["photos"]`, and
`photos[]` will never list the draft. JobShot guessed this exactly: *"if your
importer has an equivalent list somewhere, that is where the answer to (b)
lives."* It did, and it was.

**(c) Does the receipt say so?** No — and that is the part that could have cost
real work. `filed` is what the phone turns into *safe to delete from the phone*.
A draft dropped at (a) and unmentioned at (c) means Nick deletes the only copy
of something he typed.

### What changed
- The wire now accepts **images and JSON**, nothing else. `_SIDECAR_NAME_RE`
  replaces the job-manifest-only rule; a sidecar is data the PC never
  interprets, only carries. Everything else about the gate is untouched:
  traversal, absolute paths, device names, ratios, caps — `notes.txt`,
  `run.exe` and `photo.jpg.exe` are all still refused, and there is a test that
  says so, because widening a gate for a friend is exactly when a gate gets
  widened for everyone.
- `_copy_extras()` carries them into the filed folder **untouched, name
  intact** — copied, never moved: the arrival folder is the sender's, and this
  function must never be why a phone loses its only copy. A name already taken
  means another job merged in first, so the second keeps its own identity
  (`emr-<job_id>.json`) rather than overwriting a draft describing different
  work.
- The receipt gains `"extras": ["emr.json"]` per filed entry, and the `filed`
  block in the archived manifest records the same. **A file the reply does not
  mention must never be treated as filed** — so a copy that fails is a warning
  and is left out of `extras`, not quietly counted.

`emr.json` was the requested name and it is the one implemented; no sidecar
folder, no rename. JobShot can build against it now.

## Entry 2 — Nick's day rule, relayed twice and already true

Passed to me through EMR and then JobShot, in Nick's words: *a day may only be
reused once the month is FULL — 30 or 31 days. Fill the month before repeating
a day.*

**That is already exactly what the code does**, and has since v1.026:
`_find_free_day_earliest` returns the earliest free day and only returns `None`
— the signal to reuse the job's own day, flagged `date_was_capped` — when every
day in the month is taken. Verified by running it, not by reading it: with 1–29
occupied it answers 30; with 1–30 occupied it answers `None`.

No code change. What it did not have was a **test**, which for a rule stated
this deliberately is a gap: it is now pinned, including the end-to-end case of
four jobs on one real day fanning out to days 1–4. A rule nobody tests is a rule
waiting to be quietly optimised away.

Worth recording why it matters more than it used to: EMR now takes every
report's date from the folder name HPO chooses. This rule decides what the
entire archive is filed under.

## Verification
`tests/test_core.py` **101/101** (96 + 5): the draft reaches the folder
byte-identical and is named in the receipt, a job without one says `extras: []`
rather than inventing something, a second draft never overwrites the first, the
gate still refuses everything that is not an image or JSON, and the day rule
fills the month before repeating.
