# Log — v1.054 (2026-09-26)

## Entry 1 — a work sheet found two bugs, one on each side

Nick ordered a single checklist for the whole chain, passed hand to hand:
JS → HPO → EMR → R&D Director, each one appending what it checked and
forwarding the whole text. His words, carried with the sheet:

> *"ทำใบงานเดียวแต่ส่งต่อสิ่งที่เช็คและที่อยากบอกลงไปส่งต่อไปเรื่อยๆ"*

Filling in §3 honestly is what produced this release. Two things that needed
fixing were only visible from inside the exercise of writing down what is true.

### What filling it in cost, and what it bought

Every tick in §3 was produced by running the released build, not by reading it:
the four steps HPO owns, the gate (`notes.txt`, `run.exe`, `photo.jpg.exe`,
traversal, device names, NUL, 4-deep paths — all still refused), copy-not-move,
and a forced copy failure proving `extras` stays empty when a copy fails.

JobShot's hardest question had no test at all: **what happens to a job carrying
`emr.json` whose `job.json` is rejected?** It now has three, one per way a
manifest can fail — refused by the gate, not valid JSON, and a version this
build cannot read. All three end the same way: **422, nothing filed, no orphan
draft anywhere on the PC, and no `extras` claim.** The draft stays on the phone,
which is the only acceptable answer: `extras` is what JobShot turns into *safe
to delete from the phone*.

## Entry 2 — the route that exists for a lost reply could not speak about the draft

`GET /jobshot/v1/job/<id>` answered `filed`, `folder`, `photos`, `filed_at` —
and nothing about the sidecar. That route exists for exactly one situation: the
§3 reply was lost. Which is exactly the situation in which the phone cannot tell
whether the report draft survived.

I raised it on the sheet rather than shipping it, because three parties were
checking against a wire that was already released, and **a deviation nobody
wrote down is a bug even when the code is better** (the v1.049 lesson). JobShot
voted yes, and their reply turned the request into something sharper than a
nicety: their `markFiled` had been **replacing** the stored extras with whatever
the latest receipt carried. A resend called §4 first, got a receipt with no
`extras`, and the empty list **overwrote a confirmation the PC had already
given** — a filed draft silently became "not confirmed" and the phone told Nick
to send it again. They have fixed that on their side (extras are added, never
replaced); this change removes the case their fix is papering over.

- `extras` is now in the §4 reply, same meaning as §3: **what is on disk, under
  the names it is on disk as.**
- It comes from the receipt book when that has it, and from the archived
  manifest's `filed.extras` when it does not — so it answers for jobs filed
  before this version existed.
- An index entry from v1.053 has **no `extras` key at all**, which is not the
  same as a job that filed none. Answering `[]` there would tell the phone a
  draft it is still holding was never confirmed, so a keyless entry falls
  through to the archive. Missing and empty are different facts.
- A merged folder gives each job its own answer: the second job's receipt names
  `emr-<job_id>.json`, because that is the file that belongs to it.

### The §4 shape was never actually frozen
The contract tests written in v1.049 pin the key set of §2 and §3. §4 was only
spot-checked — `filed` is a bool, `folder` is a non-empty string — so adding a
key to it broke nothing, which is the wrong kind of quiet. It is pinned now,
with `extras` in it, deliberately and on a recorded vote.

## Entry 3 — "not a job" was a sentence Nick would delete a job over

When the only job in an upload has no usable manifest, the per-folder line read
`"not a job"`. JobShot prints that reason **verbatim**, in this sentence:

> The PC skipped this job: *not a job*.

Which reads as final — nothing to be done. The truth is nearly always the
opposite: the manifest did not arrive, so send it again. Both strings now say
what to do: `"no job.json in it — send the job again"` and, at the top level,
`"no job.json in the upload — send the job again"`. JobShot confirmed they match
on no reason string anywhere and display it as written, so the wording is free
to be useful.

## Verification

- `tests/test_core.py` **105 → 109**. New: §4 names the draft after a lost
  reply · §4 answers for a job filed before v1.054 (index entry stripped of the
  key, archive consulted) · each merged job gets its own draft name · the skip
  reason says what to do. Plus the §4 key set, now frozen.
- The 4 tests added while filling in the sheet (a refused, corrupt, or
  too-new manifest takes its draft with it; any `*.json` rides along except
  `job-*.json`) all still pass.
- Not verified, and it is the same box as last release: **no real phone has sent
  an `emr.json` to this PC yet.**

## What is on the sheet for EMR

The sheet went to EMR with §3 filled and five questions aimed at their section —
chiefly: in a merged folder holding two drafts, which report does the form get,
and where does "the folder's date wins" actually read the date from. Both
answers change what gets printed on F-04-TEC/03.
