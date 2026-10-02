# TO_PROMOTE.md

## ⏳ WAITING — 1 amendment, written 2026-10-02

### Amend `an-absence-is-not-a-fact` — it recurs in DESIGN, not only in reporting

**The existing lesson is scoped to reporting.** It was written on 2026-09-26 after
I told Nick *"no session is acting as Director"* when the evidence was only *"a
string was not in a list"* — the Director was present under a machine-generated
name. The lesson came out as: do not report an absence as a fact.

**It recurred on 2026-10-02 in a place the reporting wording does not reach: a
protocol design.** Designing the resend path (`docs/CHAIN_CHECKLIST.md` §3
addendum 8) I wrote a rule that **inferred a deletion from an absence** — a photo
missing from the upload meant *delete it from the archive*. JobShot found the cost:
their app tells the engineer a filed job is *"safe to delete"*, so a photo can be
absent from the phone **because the archive promised to hold it.** The design would
have destroyed the only remaining copy of a photograph, and neither HPO nor EMR
could see it — only the phone held the fact that made it dangerous.

**Why this is a widening and not a repeat of my forgetting:** the first instance
was a sentence I wrote and could have re-read. This one was a *rule I encoded*,
where the absence is evaluated later, by software, with no human in the moment to
notice. The same error class moves from "something I said" to "something that will
happen every time". The existing row could not have caught it, because nothing in
it is about design.

**Proposed amendment** — extend the row from *reporting* to *inference*:

> An absence is evidence of absence, never of intent. Do not report it as a fact,
> **and do not encode it as an instruction.** When a protocol or a function must
> act on something being missing, the actor that knows why it is missing has to
> say so explicitly — **ask for the field.** Two meanings that look identical on
> the wire need two different messages, not a guess chosen by whoever is reading.

**The executable form, per the row this project already promoted** (*an executable
check is the only lesson that fires unremembered*): in a review, any branch keyed
on a value being empty, missing or absent is a question — *"what are the two
reasons this could be empty, and does the code have to tell them apart?"* That is
checkable by reading a diff, which the prose version is not.

Cited evidence: `docs/CHAIN_CHECKLIST.md` §3 addenda 8 and 9 (HPO repo), and
JobShot's message of 2026-10-02 which is where the hazard was found.

**Handed over, not promoted** — #10.1: a project-scoped session may not reach the
master. This is the hand-over, and it is a completed action.

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
