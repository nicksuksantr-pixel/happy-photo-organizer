# CODE_REVIEW_RUBRIC.md — what to inspect, and how to score it

> **Volume 1 of 2.** This file = *what to look at*. `CODE_REVIEW_PROCEDURE.md` = *how to actually do it*.
> Loaded by the **`reviver`** trigger (command_pattern #26). Master copy:
> `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\CODE_REVIEW_RUBRIC.md` ·
> mirrored to every project as `memory/CODE_REVIEW_RUBRIC.md`.
> Records are English (#17); Nick reads the Thai illustrated version as an Artifact.

---

## 0. The thesis

A junior reviewer checks **whether the code is written nicely**.
A real reviewer checks two things:

1. **Does it do what it claims to do?**
2. **What happens when it doesn't?**

Item 2 matters more and is the one people skip. Most code is only ever checked along the
happy path — but nearly every bug that actually breaks a system in the field lives on the
failure path.

---

## 1. Reading order (the order is load-bearing)

Most reviewers open the diff and read top to bottom. That is the highest-miss method,
because **a diff hides the caller**. This order means you know what "correct" means
*before* you see the code.

| # | Step | Why this position |
|---|---|---|
| 1 | **Intent first** — task text / commit message / issue / spec / V-Log / added test names | If you can't say what "done" looks like, that is already finding #1 |
| 2 | **Tests second** | Tests are a confession of what the author *believes* correct means. Gaps in the tests = gaps in their thinking |
| 3 | **Walk the full code path**, entry point → real effect | The diff never tells you who calls this |
| 4 | **Then read the diff** | Now you have context, so each hunk reads as sensible or not |
| 5 | **Look for what is *missing*** | Hardest and highest-yield: absent tests, absent error handling, the other site that needs the same fix |

---

## 2. The ten dimensions (A–J)

Not a sequence — a **set**. Sweep all ten before scoring. **B** and **H** have the highest
yield per minute spent.

### A — Correctness
- Does the name / docstring match the actual behaviour? *A name that lies is itself a bug.*
- Boundary values: `0`, `1`, empty, null, negative, maximum, duplicates
- Off-by-one in loops and slices
- Numbers: rounding, float for money, divide-by-zero
- Time: timezone, DST, **clock moving backwards**, wall clock vs monotonic
- Encoding: UTF-8, BOM, cp1252
- Is it idempotent? Double-click / retry / duplicate message

### B — Failure behaviour ⭐
- **Fail-open or fail-closed** — when the check *cannot run*, does it allow or deny?
- Are errors swallowed silently (`except: pass`, bare catch)?
- **Does the user see the failure?** A log line alone does not count.
- Partial failure: state left half-written, no rollback
- Retry: infinite loop? retrying something that is not retryable?
- Cleanup on the error path: files, locks, sockets, threads

### C — Trust boundaries
- Where does data cross from untrusted to trusted?
- **Is identity taken from the trusted channel, or from the payload?**
- Injection sinks: SQL, shell strings, `innerHTML`, path traversal, format strings
- Is authorization checked at the right layer? Is there another entry point that bypasses it?
- **Does anything self-elevate its own privilege?**

### D — State and data
- Who owns this state — single source, or duplicated?
- Does it survive restart? Does it corrupt on power loss?
- What happens to old data / old versions (migration)?
- **Cache invalidation** — what is the cache keyed on?

### E — Interface / contract
- Backward compatibility: old clients, old files, old firmware
- **Is the default the safe choice?**
- Is the API easy to misuse (bare bool parameter, swappable argument order)?

### F — Tests
- Does it test behaviour, or implementation?
- **If you revert the fix, does the test go red?** If it stays green, the test is worthless.
- Are failure paths tested, not just the happy path?
- Is there a test pinning the existing behaviour this change might break?

### G — Readability / maintainability
- Do comments explain **why**, not *what*?
- Does it match the idiom of the surrounding code?
- Dead code, leftover TODO, stray debug print

### H — Consistency ⭐
- **Compare against the sibling.** If two functions do the same kind of thing and one has a
  guard the other lacks, one of them is wrong.
- Logic that used to be duplicated and has since diverged — one got the fix, the other didn't
- This is the fastest way to find bugs **without understanding the whole system**.

### I — Performance
- Only flag where it matters — but **anything unbounded** is always fair to flag
- Query inside a loop, heavy work under a lock, memory that grows without limit
- Slow API call on the UI thread

### J — What's missing
- A test for the bug just fixed
- Docs / CODEMAP / V-Log that should be updated
- Rollback / migration path
- **The other place that needs the same fix** — grep for the pattern; bugs are rarely alone

---

## 3. Scoring 1–5

**Iron rule: the score is the LOWEST dimension, not the average.** One security hole is not
offset by nine tidy dimensions. With a panel of reviewers, take the **lowest score in the group**
(this is the same rule Lucifer #12 uses).

| Score | Verdict | Means |
|---|---|---|
| **5** | Ship it | Does what it claims · failure paths handled **and visible to the user** · tests pin the behaviour · no sibling site left unfixed |
| **4** | Ship after small fixes | Correct, but a gap — one missing test, an ambiguous name, or a minor fail-open with limited blast radius |
| **3** | Needs another round | Happy path works, but a real failure case is unhandled or a trust boundary is loose |
| **2** | Design problem | Code is written correctly on the wrong shape — needs rework, not patches; patching further makes it worse |
| **1** | Do not merge | Breaks existing behaviour, or **the premise is wrong** — the more elegant the logic, the more dangerous |

---

## 4. Red flags — stop and look

Not all are bugs, but all are worth two minutes.

| Severity | Flag | Why |
|---|---|---|
| 🔴 | **A check that is skipped when its input is absent** | No hash → install anyway. No key → pass. This is fail-open and it is the most common real hole |
| 🔴 | **A command assembled by string concatenation** | shell, SQL, HTML — if an external variable flows in, treat it as injection until proven otherwise |
| 🔴 | **An executable invoked by bare name** | `powershell.exe` with no absolute path — if CWD is user-writable, someone can plant a replacement |
| 🔴 | **Identity read from the payload** | trusting a `device_id` in the message body instead of the verified channel |
| 🟠 | **A permissive default** | `require = False` — a security control you must switch on is a control that is off |
| 🟠 | **`except: pass` / bare catch** | swallows every error class, including the ones that must not be swallowed |
| 🟠 | **A comment saying "this can never happen"** | if it truly can't, why was the guard written? |
| 🟠 | **A function that grew from doing 1 thing to 2** | the old name starts lying, and existing callers get a side effect they never asked for |

---

## 5. What NOT to flag

This is where reviewer discipline lives. A review with 40 items of which 35 are taste
**causes the 5 that matter to be ignored**.

| Don't flag | Because |
|---|---|
| Style the formatter handles | Whitespace, line breaks, punctuation — machine's job |
| "I would have written it differently" | If you can't say when the existing form breaks, that's taste, not a finding |
| Re-litigating a settled decision | If the reason is written down, you need new information to reopen it |
| Speculative future needs | "What if we have 10 vessels one day" — deal with it then |
| Re-flagging something proven closed | Every unnecessary fix is free added risk. Dead ends must be written down as "checked, no action" |

> **The single filter that catches all of it:** every finding must name a **concrete failure
> scenario** — what input → what wrong result. If you cannot write that sentence, don't file it.

---

## 6. How to write a finding

**Fixed five-field shape:**

```
file:line · what is wrong (one sentence) · failure scenario (input → result)
         · severity · proposed fix + the blast radius of that fix
```

❌ **Useless:** "This is unsafe, permissions should be checked better here."

✅ **Actionable:**
> `src/core/bridge.py:706` **@ `eb989b8`** (SHIP-MONITORING v2.9.8) — **`link_drive` grants itself
> Engineer/admin and never checks `confirm`.**
> **Failure:** publish two forged `ship/state/<switch>` messages → a real relay actuates at
> admin authority, with the automation MASTER switch off.
> **Evidence:** the sibling `_fire_rule_relay` checks role *and* confirm — the two are inconsistent.

**Done when:** the reader can start fixing without asking you a question back.

> ⚠️ **Always pin the commit, not just the line.** This very example proves why: reviewed at
> `eb989b8` the self-elevation was on line **706**; the function has since moved to
> `bridge.py:1200` and the authority was lowered to `operator`. A bare `file:line` rots within
> days. Write `path:line @ <sha>` — and when you re-read a citation later, re-locate it by
> **symbol name**, not by line number.

### Severity — three levels, each tied to a decision

`severity` is a required field, so it needs one vocabulary (not three):

| Level | Means | Effect on the score |
|---|---|---|
| **BLOCKER** | Do not merge — breaks existing behaviour, loses data, or opens a hole | forces the overall score to ≤ 2 |
| **MAJOR** | Fix before shipping — real failure scenario, limited blast radius | caps the overall score at 3 |
| **MINOR** | Worth fixing, does not gate the ship | does not move the score by itself |

The `P0–P3` markers used by tooling map on as: `P0` = BLOCKER · `P1` = MAJOR · `P2`/`P3` = MINOR.

---

## 7. The eight techniques that find the most bugs fastest

1. **Compare against the sibling function** — two similar functions, one has a guard, one doesn't; one of them is wrong. Works without understanding the whole system.
2. **Follow the data from untrusted source to real effect** — trace it as a line, don't scan. The point where it turns from *data* into *a command* is the point that needs a guard.
3. **Ask "what if it runs twice / concurrently / after a restart"** — these three questions alone catch more than half of state bugs.
4. **Hunt fail-open: "what happens if the check can't run?"** — find every `if` where *no data* means *pass*.
5. **Read the tests first, then look for the gap** — what they didn't test is what they didn't think about.
6. **Grep for the same pattern elsewhere** — bugs are rarely alone; fixing one and leaving three is a failed review.
7. **Compare the name against the behaviour** — a `get_` that writes, a `verify_` that returns true when there is nothing to verify.
8. **Attack the premise, not just the logic ⭐** — the deepest one. The logic can be entirely correct while resting on something untrue. Always ask: *"is the sentence this code believes still true?"*

### Technique 8 in practice — two real cases

**SHIP-MONITORING `src/core/bridge.py:706` @ `eb989b8`** (function now at `bridge.py:1200`; the
authority was lowered to `operator` after this review). The code granted **Engineer** authority to
a wall-switch press, with a genuinely persuasive rationale in the docstring: *"physical access is
the highest authority there is — the app's roles guard the SCREEN, not the panel someone is
standing in front of."* Every sentence of the logic is right. **The premise is false:** it
believes a human is at the panel, while what actually wakes it is a network packet, which can be
forged. A review that checks logic passes it; a review that attacks the premise catches it.

**Coddy's own mistake, 2026-08-17.** Reported "the auth system was never enabled" after reading
`data/` inside the repo — but the **installed app reads a different path**, where everything was
switched on. Lesson: before concluding "it's absent", ask whether you are looking at **the right
instance**. Dev and production frequently read different locations.

---

## 8. Using this rubric

1. Sweep dimensions **A–J** in full (see the 4-pass batching in `CODE_REVIEW_PROCEDURE.md` §04)
2. Write each finding in the §6 shape
3. Score from the **lowest** dimension, and name which dimension held the score down
4. State explicitly what was **checked and needs no action**, and what was **not covered at all**
