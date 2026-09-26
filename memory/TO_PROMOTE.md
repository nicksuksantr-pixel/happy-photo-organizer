# TO_PROMOTE.md — cross-project amendments waiting on Nick

Two entries in the **master** `SHARED_LESSONS.md` need amending, not adding. Both
already existed. Both were hit again on 2026-09-26 — by the session that wrote
them. That is the finding.

**Why this file exists instead of the edit:** the master lives at
`Documents\Claude\Projects\Nick\SHARED_LESSONS.md`, outside this project folder.
Rule #10 says to add the row to the master, re-sync, then commit the mirrors —
but doing that means writing (and running `sync-rules-to-projects.ps1`) outside
the project, which the project-boundary rule forbids absolutely. The boundary
rule wins; **the promotion is Nick's to run or to authorise.** Editing this
project's `memory/SHARED_LESSONS.md` would be worse than doing nothing: it is a
mirror, and the next sync eats it — which is itself amendment 2 below.

EMR (`engine-maintenance-report-19`) reached the same conclusion independently
and is holding the same text on their side. One promotion covers both.

---

## Amendment 1 — `a-pipeline-exit-code-belongs-to-the-last-stage`

*(existing entry, written by Coddy 2026-09-05 — append this)*

> **RECURRENCE 2026-09-26, twice in one day, by the author.** Coddy ran
> `python tests/test_core.py 2>&1 | tail -4 && git commit …` as the gating
> command all day on Happy-Photo-Organizer; EMR committed over a red guard the
> same afternoon because the check and the commit were two statements on one
> shell line. Knowing the entry did not help either of us.
> **Why it failed as written:** it taught how to **detect** a lost exit code
> (capture `rc`, read `PIPESTATUS`) — a fact about a trap. But `| tail -N` is a
> **context-saving reflex**, typed without a decision, so detection never gets a
> chance to run. A fact about a trap does not change a habit.
> **Shaped as a habit instead:** *never pipe a command whose success gates the
> next step* — shorten the output after capturing the code, not before. And the
> sibling that is not about pipes at all: **two statements separated by `;` gate
> nothing; only `&&` gates.**
> **What actually fixed it:** an executable check, not the entry. An invisible
> failure class belongs in a test (and optionally a fast pre-commit hook); a
> lesson only fires if someone remembers to read it at the moment of typing.

## Amendment 2 — `promote-to-the-master-before-the-mirror-or-the-sync-eats-it`

*(existing entry, written by Coddy 2026-09-05 — append this)*

> **RECURRENCE 2026-09-26.** EMR wrote a new lesson straight into its project's
> `memory/SHARED_LESSONS.md`, committed and pushed — **while recording the
> recurrence of amendment 1 above.** Verified after the fact: master 0
> occurrences, mirror 1. Reverted, mirror byte-identical again.
> **The tension this exposes, which the entry does not mention:** rule #10's
> procedure (row into the master → re-sync → commit the mirrors) **cannot be
> executed by a project-scoped session at all** — the master is outside the
> project folder and the boundary rule is absolute. So the honest instruction
> for a session that finds a cross-project lesson is: **write it into your own
> project's memory, and hand the promotion to Nick.** Not "promote it yourself,
> carefully".

---

*Raised 2026-09-26 by the HPO session. Nothing here is urgent; both lessons are
already recorded in this project's own `memory/MEMORY.md`, where a session here
will read them. Promoting them is what makes them reach the other projects.*
