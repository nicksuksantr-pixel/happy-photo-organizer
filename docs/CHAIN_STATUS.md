# Chain status — phone → HPO → EMR

> Written for the Director and for Nick, in the repo rather than in a message:
> **seven messages were sent to the rules session today by four projects and one
> arrived.** Git is the channel that works. This file and the commit messages
> are where HPO reports from now on.
>
> Last updated 2026-09-26, HPO v1.057.

## 1. Is there a step where a human retypes something?

**Not in HPO's segment. Phone → archive is hands-off, and that is measured, not
assumed** — the real job at 14:18:55 today went from the phone to
`26-09-26 Inspected and Serviced FloodLight` with nobody touching the PC:

| Step | Who | Retyping? |
|---|---|---|
| job, report draft, photos | phone | the engineer types the report once, which is the point |
| send over Wi-Fi | phone → HPO | none |
| accept, gate, extract | HPO | none |
| **decide the folder name and date** | HPO | none — the archive's own day rule |
| resize + rename the photos | HPO | none |
| carry `emr.json` in untouched | HPO | none |
| write `filed.renamed` (phone name → archive name) | HPO | none |
| receipt to the phone (`extras`, `folder`, `work_date`) | HPO | none |

**The one thing a person must still do on the PC is choose the destination
folder — once.** Before v1.057 it was once *per app start*, which is what made
the phone say "no destination folder chosen on the PC yet" at random and is why
this was worth a release.

**What I cannot certify from here:** EMR's segment. JS reports that EMR has
printed an F-04-TEC/03 from a phone job and that their reader's `equipment` bug
was fixed in v0.3.5, but I have not watched that run and I am not going to
report another project's state as fact. **Nick: for the EMR half, ask EMR.**
What I can say is that everything EMR needs from me arrives without a human:
the draft, the photos under their archive names, and the map between the two.

## 2. Multi-day jobs — Nick's ruling, and the one thing it leaves open

**Nick's ruling: photos sent together are one job and get one date.** That
removes the work that was queued rather than answering it — no consecutive-day
reservation, no full-month rule for a range, and his day-uniqueness rule is
untouched. `assign_unique_dates` stays exactly as it is.

**The folder NAME must not carry a range, and that is now settled between HPO
and JobShot.** Naming a folder `26-28.09.26` while the allocator reserved one
day would claim days 27 and 28 that nothing reserved — `scan_used_days` expands
a range on the next scan and would mark them used, and worse, inside a single
batch `assign_unique_dates` could hand day 27 to another folder in the same
pass. The reader and the writer would disagree with each other in the same run.

**Open, and deliberately not decided here: whether the span is recorded at all.
Both sides now agree on the option; what is open is whether Nick wants it.**
JobShot first held that the range had nowhere to appear and offered to remove
the `work_date_end` control rather than leave Nick filling a box nothing prints.
They have since withdrawn that and the control stays while this is open (their
`3b39e3c`). The home neither side had looked at:
**`job.json`'s `filed` block** (`core/jobshot.py:709-718`), the archive's own
record, which already carries `work_date` beside `folder_date` for exactly this
class of problem — where the job went versus when the work was done.

That would keep EMR's rule intact rather than bending it. *The folder decides
the date* exists to stop `emr.json` — a draft the engineer can still edit — from
overriding the archive. `filed.work_date_end` is not the draft; it is HPO's own
record, written once at filing time and never edited, and already what EMR reads
for `renamed` and `extras`.

Cost if it is taken: `work_date_end` added to `job.json` on the phone side
(additive — tested against the current reader, which accepts it, so `"jobshot"`
does not move), copied into `filed.work_date_end` here, and EMR printing a span
when it is present and later than `work_date`. **No folder naming change, no
day-rule change, no allocator change.**

**Neither side is building it**, by agreement: the chain has stopped to test,
and a fourth change shipped on a day with five releases in it is how the next
silent defect gets in. JobShot is also deliberately NOT adding `work_date_end`
to the manifest yet — if the option is taken it is one line and a test on their
side, and if it is dropped nothing was shipped that has to be unshipped.

Recorded as an option beside "remove the control" so whoever closes it is
choosing rather than discovering. If it closes the other way that decision gets
written here too, with agreement on the record rather than silence.

## 3. The `.part` question, answered and then made moot

Asked three times by the Director; answered twice into a channel that did not
deliver. The measurement:

- `download_installer` writes **straight to `dest`**, always
  `…/updates/HappyPhotoOrganizerSetup-vX.XXX.exe` (`core/update_worker.py:247`),
  and resumes by reading `dest.stat().st_size` (`core/updater.py:224`). There is
  no staging file, so a stranded partial **is** an `.exe`.
- Exhausted retries delete it explicitly (`core/updater.py:351-355`).
- Grepped `.part`, `mkdtemp`, `tempfile`, `open(..., "wb")`: the module's only
  `tempfile` use is the debug log.
- Measured on Nick's machine: `~/.happy-photo-organizer/updates` held 87.4 MB
  when the Director looked and **0 entries, 0.0 MB** when I did — v1.057 was
  installed and restarted in between, and startup reclaimed it. Not the function
  existing; the bytes gone.

**And the filter is gone anyway.** "It cannot happen today" is a sentence, and
the lesson this chain promoted to the master this afternoon is that a sentence
is not a fix: `cleanup_old_installers` now sweeps **every file** in the cache
except the one being kept, so a `.part`, a `.tmp` or anything else a future
refactor invents is reclaimed without anybody remembering to widen a filter.
Pinned by a test proven red against the old suffix check.

One bounded second location, for completeness:
`%TEMP%\happy-photo-organizer-updater.log`, outside `cache_dir()` and outside the
sweep — 129.2 KB, rotating at a 1 MB cap keeping one generation, so 1.9 MB
worst case, forever.

## 4. Not yet proven against the machine

**The vessel fix in v1.057 has never run on a real restart.** I caught it in
review: `_jobshot_dest` returns early when a destination is already set, which
was harmless while that was `None` on every fresh start — **the restore added in
v1.057 is what made it dangerous.** 134 tests are green and one of them builds
exactly that state, but a fixture chooses its own state and the bug existed
because of a state only a real restart produces.

What would settle it: **one real job from the phone after a genuine app restart,
checked on disk for which vessel's folder it landed in.** Asked of Nick
2026-09-26; this line gets updated with the result, either way.
