# TO_PROMOTE.md

**Three items are waiting (2026-10-31, from HPO's v1.066 drills).** When the next cross-project lesson turns
up here: write it in this file, say so, and stop (#10.1).

## ⏳ WAITING — 2026-10-31

1. **make-it-busy-before-you-feed-it** (HPO drill run 2, H8).
   - With a loopback feed, a download takes about a second. An app that checks at start found N+1 and handed over
     2 s after starting, before its busy window (Settings) was even open, so `waits_while_busy` failed although
     the app was right.
   - **Rule:** in a busy test, start the app with nothing newer on the feed, wait until the busy window is really
     open, then feed N+1 and wait for the app's next periodic check.
   - This holds for any app whose updater checks at start. The shared kit's fix is in `Invoke-Drill.ps1`.
2. **read-a-stuck-process-from-outside-without-admin** (HPO drill run 1, D1).
   - The drill profile could not be read, and the harness only said "waiting". Three things answered it from Nick's
     account, with no admin and no agent:
     - WMI `Win32_Process` I/O counters: `WriteTransferCount` = 87.49 MB, so the 87.44 MB download had finished;
     - `Win32_Thread` wait reasons and CPU: the main thread was waiting at 0 ms CPU, and the GetMessage thread was
       alive;
     - the `TerminalServices-LocalSessionManager/Operational` log: the session connect and disconnect times, which
       ruled out "disconnected session" as the cause.
   - A 15-line repro then confirmed it.
   - **Rule:** when a run is a black box, measure the process from outside before theorising, and before waiting out
     a timeout.
3. **a-suite-pass-before-the-commit-is-not-a-pass-on-the-commit** (HPO v1.066).
   - `test_the_invisible_byte_guards_still_cover_every_kind_of_file_here` reads `git ls-files`.
   - 220/220 ran while `drills/` (`.ps1`, `.psm1`, `.log`, `.jsonl`) was still untracked. The guard went red only
     after the commit, and was found two runs later.
   - **Rule:** a test that reads the tracked tree must be run after the commit that adds new kinds of files, not
     before it.

Already in SHARED_LESSONS, not repeated: `a-non-daemon-thread-hangs-sys-exit-and-a-force-kill-hid-it` (D1).

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
