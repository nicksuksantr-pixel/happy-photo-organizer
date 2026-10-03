# TO_PROMOTE.md

## ⏳ WAITING — 3 amendments, written 2026-10-02/03

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

**A second question, added 2026-10-02 after JobShot found the fifth instance in
their own code.** They had already solved *"a file name is not an identity"* for
spare-part photos — with a comment explaining the renumber and a test proving it —
and never asked where else the problem lived. **Nothing was wrong: the code was
correct, tested and documented. It stopped at the first instance.** So:

> **Where else does this same thing happen, and did I fix it there?**

**Both halves of the check have now paid out, in two repos, independently.**
JobShot cites three of their own (`equipment` read as null when absent, `.get()`
versus `in`, and a schema where an optional key let the model decline the work).
Asking the second question of HPO found a live bug within minutes: the v1.044
BOM lesson had reached three JSON readers and **not** the two holding the pairing
token, the remembered destination and all 174 catalog jobs — each of which
swallowed the failure and returned a default. Fixed in v1.058, test red first.
**Two projects reaching the same conclusion independently is the evidence that the
rule was too narrow rather than that either session forgot it** — the same
grounds on which this project's last cross-project row was promoted.

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

### New row — `a-true-fact-is-not-evidence-for-the-next-thing`

**Authored by JobShot, 2026-10-03, out of five corrections in one day across two
repos.** Their sentence, and it is better than anything I wrote during the day it
describes:

> **Every single one was a true statement about one thing offered as evidence
> about another.** The error was never the fact — it was the inference hanging
> off it, and that is not caught by measuring more carefully, only by asking
> **what else would produce this exact result**.

#### The five, because the row is only promotable with them attached

| The true fact | The false thing it was offered as evidence for |
|---|---|
| `extras` really does describe a list of sidecars on disk | …therefore it is **folder-scoped** (it is job-scoped) |
| EMR really refuses a folder holding two drafts | …therefore **two drafts** are what break them (two **manifests** are) |
| The hook really refused a literal array of ten | …therefore it **cross-checks the declaration** (it compares against `CAP = 5`) |
| My copy's refusal really said `has 10 items, over 5` | …therefore the two copies have **diverged** (the message depends on how the array is *spelled*) |
| The reply really carries the pre-correction `filed_at` | …therefore that PC **runs the fix** (every version does this; only the receipt differs) |

**Every left-hand column is true and was measured.** Every right-hand column is
an inference that happened to be wrong, and in four of the five cases the
inference was handed to another project as a fact — twice costing them work they
had already done correctly, once nearly adding a permanent field to their data
model, and once being relayed onward to Nick as proof.

#### Why "measure more carefully" is the wrong lesson

This is the part that makes it a new row rather than a restatement of
`an-absence-is-not-a-fact` or *name which side measured it*. **Both of those were
satisfied in all five cases.** The measurement was real, it was mine, and I named
myself as the measurer. **The rule that would have caught it is not about
provenance or rigour — it is about alternatives:**

> **What else would produce this exact result?**

Asked of the hook's refusal: *a cap of five would.* Asked of the two messages:
*one code path with two entry points would.* Asked of the preserved `filed_at`:
*reading the entry before the write would.* **Each answer was available at the
moment of the claim, cost nothing, and needed no new data.**

#### The executable form

Pairs with the row this project already promoted (*an executable check is the
only lesson that fires unremembered*):

> **When a measurement is about to become a claim about a MECHANISM, write down
> the second explanation before sending it.** If you cannot name one, say
> "consistent with" rather than "therefore". And when a result is handed to
> another project as grounds for them to change code, that sentence is required,
> not optional.

**The tell that it is happening:** the claim is one step larger than the thing
measured — *refused* becomes *cross-checks*, *carries a value* becomes *runs the
fix*, *differs* becomes *diverged*. **One verb of inflation, every time.**

#### Companion, same day, same pair

JobShot's other formulation, kept because it covers the reverse direction: **when
a failure's content is exactly what you intended to produce, suspect the thing
reporting it.** Seven freshly written gates all failing with the precise refusal
they asserted was a harness fault, not a gate fault — and the natural repair
(loosening the gates) would have produced a release tool that permits everything
behind a suite claiming it does not.

**Handed over, not promoted** — #10.1. The master lives outside the project
boundary.

---

### New row — `the-unread-field`

**Authored by JobShot, 2026-10-03.** Deliberately a separate row from
`a-true-fact-is-not-evidence-for-the-next-thing`, and the reason is the whole
point of having both.

**What happened:** HPO verified three properties of its own installation —
published, installed, running — handed JobShot the address, and spent hours with
them building a careful investigation of why a correction could not be found.
The answer was in the first line of HPO's own output, quoted to JobShot **twice**:

    200   v1.060, ship 'ENA Test', ready

**`ship 'ENA Test'`.** Every real job is `ENA CHALLENGER`. That machine was the
**test** installation, the real archive was never readable from it, and **nothing
either side could have searched would have found the folder.**

#### Why the other row cannot catch it

`a-true-fact-is-not-evidence…` is about **inference**: a true measurement
inflated by one verb, caught by asking *what else would produce this result*. Its
tell is that the claim is larger than the evidence.

**Here no claim was made.** The field was printed, accurate, and unread. There is
no inflated verb to notice, because there was no sentence. **The failure is
upstream of inference** — and a rule about the quality of conclusions cannot
reach a fact nobody turned into one.

#### The check

> **Does my evidence contain anything I have not accounted for?**
>
> Ask it of **identity fields first** — ship, host, version, id, path, account —
> because those answer *which thing am I even looking at*, and every other
> conclusion is conditional on that answer. A field you did not read is not
> neutral; it is a premise you adopted without noticing.

**Operationally:** when output is quoted into an argument, every field in the
quote is either used or explicitly dismissed. *"I pasted it and only looked at
the part I expected"* is the failure, and it is invisible precisely because the
output was correct.

#### The pairing that makes it general

**The same missing dimension appeared on both sides for opposite reasons:** HPO's
§2 ping prints a ship and no machine identity, and nobody read the ship;
JobShot's `Receipt` carries **no** PC identity at all, while every string in the
app says *"the PC"* as though there were one. **One printed it unread, one never
printed it.** Neither could answer *which machine*, and that is why two
installations on one LAN stayed invisible for hours.

Handed over, not promoted (#10.1).

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
