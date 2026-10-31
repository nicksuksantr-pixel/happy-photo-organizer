# TO_PROMOTE.md

When the next cross-project lesson turns up here: write it in this file, say so, and stop (#10.1). Write each one as
**one line in the registry form** (`- **slug** (source, date) — fact… **Rule:** …`), so the Director can take it
verbatim (Director, 2026-10-31).

## ⏳ WAITING

Nothing is waiting.

---

## ✅ CONSUMED — 2026-11-01

Promoted by the Director and read back in the mirror (`memory/SHARED_LESSONS.md`), so cleared here (#10.1):
- at sync `35c6344`: `counts-must-start-when-the-judged-thing-starts`,
  `a-built-in-key-breaks-a-busy-step-that-held-the-key-back` and `a-guard-must-read-the-lock-the-house-writes`;
- at sync `ae5275e`: `a-patch-script-loses-a-backslash-and-writes-a-control-byte`, at mirror line 226. The "amend `a-control-character-from-an-escape`" row named a slug that
exists nowhere (master, mirrors, other projects: grep, 2026-11-01). The lesson was never promoted under any name, so it
is rewritten above as one whole row with both events.

---

## ✅ CONSUMED — 2026-10-31

The three items from HPO's v1.066 drills were promoted by the Director, condensed to one line each. They came back
in the mirror at `2ad0818` and were read there, row by row:

| Item | Where it is now |
|---|---|
| `make-it-busy-before-you-feed-it` (H8) | `memory/SHARED_LESSONS.md:52`, plus UPDATE_DRILL §5 step 3 |
| `a-suite-pass-before-the-commit-is-not-a-pass-on-the-commit` | `memory/SHARED_LESSONS.md:98` |
| `read-a-stuck-process-from-outside-without-admin` (D1) | `memory/SHARED_LESSONS.md:202` |

**One word was wrong, and it was mine:** the third row says the red guard "was found two runs later". The record
says otherwise:
- no full suite ran between `ad00773` (06:57) and 11:04;
- the 11:04 run (224/225) was the first after the commit, and it found it.

So it was found on the **next** full run, about four hours later. Sent to the Director to correct the master row.

---

## ✅ CONSUMED — 2026-10-20

**All four items from the 2026-10-02/13 round were promoted** to the master
`SHARED_LESSONS.md` by the rules session (`cwd` `…\Projects\Director`) and came
back to this repo in the mirror at commit `e46ffd5` (master `507b664`,
`command_pattern` v3.19). Verified by reading each row at that commit, not on the
strength of the rules session's notice.

| Item | Where it is now |
|---|---|
| `an-absence-is-not-a-fact` — widened from reporting to inference, plus *"where else does this happen?"* | `memory/SHARED_LESSONS.md:228` |
| New row `a-true-fact-is-not-evidence-for-the-next-thing` | `memory/SHARED_LESSONS.md:231` |
| New row `the-unread-field` | `memory/SHARED_LESSONS.md:233` |
| New row `wanting-the-confirmation-is-not-the-user-needing-to-act` | `memory/SHARED_LESSONS.md:235` |

### ⚠ Correction — the first item was not an amendment

It was handed over as *"Amend `an-absence-is-not-a-fact`"*, opening with *"The
existing lesson is scoped to reporting"* — as if the 2026-09-26 row were already
in the master. **It never was**: not in the master, not in any mirror, not in this
repo's memory. It was written on 2026-09-26 and never handed over; the rules
session found that and landed it as one whole row (original + widening). The
premise came from remembering having written the row, not from reading the master.

The full hand-over text of this round is in git history
(`git show 44004af:memory/TO_PROMOTE.md`); the promoted rows carry the substance.

---

## ✅ CONSUMED — 2026-09-26

**Nothing from that round is still waiting.** Both amendments were promoted to the master
`SHARED_LESSONS.md` by the rules session and came back to this repo in the
mirror at commit `e35e2b3` (master: `command_pattern` v3.18).

The file is kept rather than deleted because it is the record of what this
session handed over, and because the promoting session deliberately did not
touch it — its first draft of the new sub-rule told the promoter to clear a
consumed `TO_PROMOTE.md`, which would have meant deleting a record another
session authored. It caught that while writing the rule the mistake belongs to,
and the correction is in the sub-rule.

## What landed

| Amendment | Where it is now |
|---|---|
| `a-pipeline-exit-code-belongs-to-the-last-stage` — recurrence + the reason the row failed as written | `memory/SHARED_LESSONS.md:118` |
| `promote-to-the-master-before-the-mirror-or-the-sync-eats-it` — recurrence + #10's procedure is unrunnable inside the boundary rule | same file |
| **New row** `an-executable-check-is-the-only-lesson-that-fires-unremembered` — written from both amendments together | `memory/SHARED_LESSONS.md:137` |

Both projects had reached the same two conclusions independently, in different
words, which is cited in the promoted row as the evidence that **the rule was
wrong rather than the sessions**.

## The procedure it established, for next time

**#10.1 — a project-scoped session may not promote.** It writes
`memory/TO_PROMOTE.md` and hands over; the rules session promotes to the master,
re-syncs, and reports back. **That hand-over is a completed action, not a
failure** — which is the answer to the tension this file was opened to name: the
master lives outside the project folder, and the boundary rule is absolute.

So when the next cross-project lesson turns up here: write it in this file,
say so, and stop. Do not reach for the master.
