# Log — v1.055 (2026-09-26)

## Entry 1 — three correct programs, one broken join

EMR built a folder the way HPO files it, ran its scanner against the draft, and
measured the result: **`MATCHES: []`**. Zero.

The chain is:

1. JobShot renumbers the photos of its own job from `0001.jpg` and writes
   `emr.json` naming them. **Correct** — those are the names in the folder the
   phone can see, the only folder it has.
2. HPO renames every photo on filing to `<folder name>_NNN.jpg` (v1.045, so
   Nick can move a photo between folders without a collision) and carries
   `emr.json` **byte-for-byte** (v1.053, so a draft is never altered in transit).
   **Both correct.**
3. EMR looks up each name from the draft in the folder. **Correct.**

Nothing in that list is a mistake, and the join between (1) and (3) does not
exist: the names in the draft are the phone's, the files on disk carry the
archive's. Worse, EMR's rule for a name it cannot find is to skip it **in
silence** — so a report would have printed with no photos at all while the
status line said the draft had been applied.

Nobody could have found this alone. It took the folder being built by the side
that reads it, which is the entire point of Nick's one-sheet chain.

## Entry 2 — the map existed, at the right moment, and was thrown away

`rename_photos_for_folder()` already returns `{phone name: archive name}`, and
`_file_group` already keeps it per arrival as `r.photo_renames`, corrected when
a folder is moved afterwards. It was live at filing time and dropped when the
function returned. This release is persistence, not computation.

### Why it goes in each job's own manifest and nowhere else

JobShot's warning was the sharp part of their report: **a flat map at folder
level collides on a merge.** Every phone numbers its own job from 1, so a merged
folder holds two different `0001.jpg`s, and a single `filed.renamed` would have
one slot for that key — pointing one job's report at the other job's pictures.
The same failure as two drafts overwriting each other, one layer down and just
as quiet.

Each job already writes its own manifest — `job.json` for the first, and
`job-<job_id>.json` for a job merging in behind it — so per-job storage needed
no new file and no new convention:

```json
"filed": {
  "extras":  ["emr.json"],
  "renamed": {"0001.jpg": "26-09-26 Pump Overhaul_001.jpg",
              "0002.jpg": "26-09-26 Pump Overhaul_002.jpg"}
}
```

Verified on a real merge: two jobs, both with a `0001.jpg`, two manifests, two
maps, **no shared value between them**.

It is deliberately **not** on the wire. JobShot said they would read it and
never use it — the phone has no business caring what the archive calls a file —
and EMR reads the folder, not the socket. Adding it to every LAN reply would be
payload with no reader.

## Entry 3 — the pairing rule JobShot proposed is wrong in one case, and I ran it

JobShot suggested EMR pair `emr-<job_id>.json` with `job-<job_id>.json` "by the
id already in both names". It holds for the ordinary merge, and it breaks here:

> **The first job files no draft. The second one does.**
> The second job's draft meets no collision, so it keeps the plain name
> `emr.json` — while its manifest, which does collide, is written as
> `job-<job_id>.json`.

Matching by filename would then hand `emr.json` to the first job and resolve its
photo names against the wrong half of the folder. Run, not reasoned:
`job.json` → `extras: []`, `job-20260926-110000-b.json` → `extras: ["emr.json"]`.

**The only correct link is `filed.extras`**: a manifest names the drafts that
job filed, so the manifest whose `extras` contains a draft is the manifest whose
`renamed` resolves it. That is why the two fields sit side by side, and there is
now a test whose name says it.

## Verification

- `tests/test_core.py` **109 → 112**: a draft resolved through the map to files
  that exist (and the draft still byte-identical) · a merged folder keeping two
  maps that share no value · the plain-`emr.json`-with-a-suffixed-manifest trap.
- The map is only ever read from the manifest, so nothing on the wire moved and
  no contract test needed changing.
- Still not verified, and still the same box: **no real phone has sent an
  `emr.json` to this PC yet.** EMR's measurement was on a folder built by hand.
