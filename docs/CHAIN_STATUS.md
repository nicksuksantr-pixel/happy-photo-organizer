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

## 2. Multi-day jobs — ruled by Nick, and already what the code does

**Nick, 2026-09-26, verbatim:**

> *"ไอ้เรื่องที่ว่าเป็นช่วงเวลาวันทำงานน่ะ จริงๆก็คือถ้าส่งจากมือถืออ่ะมันก็เป็นไฟล์เดียวกันถูกไหม
> ก็อยากให้มองเป็นวันเดียวกัน คือเราก็มีหน้าที่แค่ดูวันที่ตามกฎเดิมเลยว่าอันไหนว่างก็ใส่เลยเป็นวันเดียวเลย
> แต่ถ้ามันเต็มแล้วก็ค่อยไปทับวันอื่นเอาอีกทีนึง เพราะยังไงชื่อก็ไม่ตรงกันอยู่แล้ว แค่ตรงแค่วันที่ ถูกไหม"*

In English: sent from the phone as one job means **one day**. Our only job is
the existing rule — take whichever day is free. **If the month is full, then go
ahead and reuse a day**, because the folder names differ anyway; only the date
would coincide.

**No code change. This is exactly what `assign_unique_dates` does**, verified by
running it rather than reading it:

| Situation | `_find_free_day_earliest` | Result |
|---|---|---|
| day 26 free | `26` | filed on its own day |
| days 1-26 taken | `27` | earliest free day |
| **every day 1-30 taken** | `None` | **reuse, flagged `date_was_capped`** |

**One nuance worth Nick's eye, because his words and the code could differ
here.** He said *"go and overlap another day"*; the code keeps **the job's own
real day** (clamped to the month length) rather than moving it to some other
day. That is deliberate and predates this conversation — `core/processor.py:388-399`:
a Tester round on 2026-06-04 found that slamming every overflowing job onto the
last day of the month collapsed different jobs onto one date and risked
same-name merges. Keeping each job's own day means **different work days stay on
different folder dates, and only genuinely same-day jobs share one** — which is
the same reasoning Nick gives for why sharing is safe at all. Flagged rather
than changed; one word from him settles it either way.

### The span: closing, on a measurement rather than on my argument
Whether the **span** should still be recorded — `filed.work_date_end` for EMR to
print "26-28 September" while the folder stays one day. I proposed it and argued
that an archive fact outlives whatever prints it. **Two independent lines now
close it, and the second is a measurement that beats the argument:**

1. Nick's *"อยากให้มองเป็นวันเดียวกัน"* — he wants it seen as one day.
2. **EMR measured the form.** `F-04-TEC-03_template.docx` has **exactly one date
   field** — no period of work, no from/to, no hours. A duration could only ever
   be prose somebody types into Troubleshooting. So `work_date_end` cannot reach
   the printed document by any route without changing the form itself.

My argument still stands on its own terms, which is why JobShot would not have
removed the control on EMR's measurement alone. What it does not survive is both
at once: **nobody can name a reader other than the form, and the form has no
slot.** Worth keeping as the lesson rather than the outcome — the question
"where would this fact be read?" was answerable by opening a .docx, and three
sessions had been reasoning about where it *belonged* instead.

**Still not settled by us.** It costs JobShot a control they shipped yesterday,
so it gets Nick's word rather than our agreement — they are asking him directly.
If he confirms: they remove the control and the field in one change, HPO writes
nothing, and my agreement is on the record rather than my silence.

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
