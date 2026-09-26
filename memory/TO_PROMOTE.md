# TO_PROMOTE.md — consumed 2026-09-26

**Nothing is waiting here.** Both amendments were promoted to the master
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
