# CODE_REVIEW_PROCEDURE.md — how to actually run a review

> **Volume 2 of 2.** `CODE_REVIEW_RUBRIC.md` = *what to look at*. This file = *how to do it*:
> what to open first, what to write down, and how you know a step is finished.
> Loaded by the **`reviver`** trigger (command_pattern #26). Master copy:
> `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\CODE_REVIEW_PROCEDURE.md` ·
> mirrored to every project as `memory/CODE_REVIEW_PROCEDURE.md`.
> Every sub-step has three fields: **DO · WRITE · DONE WHEN** (some add **NEVER**).

---

## How the `reviver` trigger executes this procedure

`reviver` runs `reviver.js` through the Workflow tool: **exactly 3 review-only agents in parallel —
three independent review FIRMS.** The count is enforced by the script (agent cap #16).

> ⚠️ **They do not split the work.** Every firm gets the identical job and must walk **all 7 parts
> and score all 10 dimensions A–J itself**. (An earlier design gave each agent a third of the
> dimensions; Nick corrected it on 2026-08-26.) **Splitting the dimensions is distribution, not
> verification — nobody would be checking anybody.** A cross-check means several parties do the
> *same* work and you see whether the answers match.

**What gets compared afterwards** — this is why three is worth the cost:

| Signal | Reads as |
|---|---|
| **`scoreAgreement`** | All three scored the same → trustworthy. Differ by ≥2 → **someone missed something, or saw something the others didn't. Find out which.** |
| **`dimensionComparison`** | Per dimension, what each firm scored. A dimension they disagree on is where you open the code personally. |
| **`thoroughness`** | Catches a firm that worked sloppily — no `[TRACE]`, never found callers or siblings, never said which instance it read, left `[Q]` open, scored fewer than 10 dimensions. Its verdict then carries less weight, **and that must be said in the report.** |
| **`conflicts`** | One firm filed a bug where another filed a `cleared`. **Resolve by opening the real code, never by siding with a firm.** |
| **`corroborated` / `solo`** | Reached by 2+ firms independently = high confidence. Reached by one = verify before reporting. |
| **`intentAgreement`** | If the firms read the intent differently, the task text is ambiguous — every finding resting on it is suspect. |

The final score reported to Nick is **the lowest verified dimension**, never the average of the
three firms' scores.

**Running solo?** The same procedure applies — you own all ten dimensions either way; there is
simply no second opinion to compare against. The evidence gates in step 05 do not get cheaper.

**`reviver` never auto-fixes** (unlike Tester/supertester). It produces a graded review; fixing is a
separate decision.

---

## 00 — The review sheet (one artifact, used throughout)

Create one scratch note **before opening a single line of source**, then append to it at every
sub-step. Never rewrite it from memory.

**Iron rule: nothing appears in the final report that is not already on the sheet with either a
`file:line` or an *absence anchor*** — the path where the thing should exist but doesn't
(`tests/test_foo.py — no test for the reverted branch`). Dimension-J findings are about things
that are missing and have no line of their own; an absence anchor is their evidence.

Create all six sections, empty, up front:

```
[HEADER]  target · intent · in-scope · out-of-scope · depth · cut-reason
[MAP]     entry points · layer · callers · callees · siblings · instance
[TRACE]   the end-to-end walk, one line per hop
[Q]       open questions Q1..Qn (each: claim + status)
[DIM]     A..J, one line each: score | N/A + reason | evidence pointer
[DROP]    suspicions killed during step 05, one line each + why
```

**Why `[DROP]` matters:** what you checked and cleared is **worth as much as what you found**.
It stops the next round re-spending the time, and stops someone "fixing" what isn't broken —
every unnecessary fix is free added risk.

---

## 01 — SCOPE (before reading any source · ~10% of budget)

### 1.1 Pin the target as a real ref
- **DO:** Name the exact object under review as a **ref** — a commit range, a branch diff, a path
  list. **Never start from a prose description.** Pull the file list with added/removed line counts.
- **WRITE:** `[HEADER] target = <ref>` + a file table: `path | +N/-M | guessed role`
- **DONE WHEN:** the file count in your table matches the diff's file count. If they disagree you
  are looking at the wrong ref — resolve before continuing.

### 1.2 Establish intent
- **DO:** Read in this order and **stop at the first that gives a concrete statement**: task text →
  commit messages → issue/spec → V-Log / version-bump line → names of the added tests.
- **WRITE:** `[HEADER] intent = "after this change, X should Y"` — one sentence, tagged `STATED` or `INFERRED`
- **DONE WHEN:** exactly one sentence is on the sheet and it is **falsifiable** — you could point at
  a line and say "this fails to do it".

### 1.3 When no intent was stated
*Trigger: the commit says "fix stuff", or there is no description at all.*
- **DO:** Reconstruct mechanically — (a) list added public symbols and changed signatures;
  (b) list added test assertions; (c) write the shortest sentence covering both lists.
- **WRITE:** the assumed intent + `Q1: intent assumed as <...> — confirm`
- **NEVER:** review against a guessed intent silently. An `ASSUMED` intent is itself a review
  output, and any finding depending on it is reported conditionally ("if the intent was X, then…").

### 1.4 Draw the boundary — three buckets
- **DO:** Split by **rule, not by feel**:
  - **IN** — files in the diff, plus any file the diff calls into whose behaviour it depends on
  - **CONTEXT** — read-only: callers of the changed code, siblings used for comparison, the
    config/schema it reads. *You read these; you do not report defects in them unless this change
    makes them wrong.*
  - **OUT** — everything else: pre-existing defects in untouched code, format-only changes,
    generated files, lockfiles, vendored trees
- **WRITE:** `in-scope = <paths>` · `out-of-scope = <paths + one-word reason each>`
- **NOTE — this bucketing is provisional.** The IN definition needs the callee list and CONTEXT
  needs the caller and sibling lists, which step 02 produces. Bucket the diff's own files now, and
  **add callees/callers/siblings to the buckets as 2.3 and 2.4 surface them.**
- **DONE WHEN:** every file the diff itself touches lands in exactly one bucket (re-checked at the
  end of 02, when every file you have *touched* must also be in exactly one bucket).

### 1.5 Cut a huge change
*Trigger: >~800 changed lines, or >~15 files, or more than one distinct feature in one diff.*
> **Do 1.6 first if you have not.** You cut *against a budget*, so the depth and cap from 1.6 must
> exist before this step can decide anything. (Kept in this order because "is it too big?" is what
> makes you reach for a budget at all.)
- **DO:** Cut in this priority order, **stopping at the first cut that fits the budget**:
  1. **By risk tier** — keep files touching auth/permissions, money/quantities,
     persistence/migrations, external input parsing, concurrency. The rest becomes CONTEXT.
  2. **By call path** — keep one complete path from entry to effect; drop structurally identical
     parallel paths.
  3. **New vs moved** — pure moves/renames (confirm with a similarity check) get one line of
     review, not a read.
- **WRITE:** `cut-reason = <which rule · what was dropped · what would be needed to cover it>`
- **NEVER:** cut scope without declaring it. **An undeclared cut is a defect in the review** —
  the reader will believe everything was covered.

### 1.6 Declare depth and the stop rule
- **DO:** Pick one — **skim** (interface + diff only) · **standard** (full procedure) ·
  **deep** (standard + step 05 evidence on every dimension, not only on suspicions). Set a wall-clock cap.
- **WRITE:** `depth = <level>, cap = <minutes>`
- **DONE WHEN:** written. At the cap you **stop and report what was covered** — you never
  silently extend.

---

## 02 — RECON (map before reading · 10–15% of budget)

Breadth only. You are not evaluating anything yet.

### 2.1 Find the entry points
- **DO:** Find how execution reaches this code **from outside**: main/CLI, route or handler
  registration, event handler, scheduled job, UI action binding, test harness.
  **Search for the framework's registration idiom, not for the function name.**
- **WRITE:** `[MAP] entry: <file:line> → <name>` (max 3; if more, take the one the intent names)
- **DONE WHEN:** at least one entry point is a real `file:line`, not a guess.

### 2.2 Place each file on the map
- **DO:** Label every in-scope file with one word: `view | controller | service | model | infra | util | test | config`
- **WRITE:** `[MAP] <path> = <layer>`
- **DONE WHEN:** all in-scope files are labelled. **A file whose layer is ambiguous is itself a
  note** — log it as `Qn`.

### 2.3 Find who calls it
- **DO:** For every changed public symbol (function, class, constant, config key, route, schema
  field): search the exact name across the repo, **then search for it as a string as well** —
  dynamic dispatch, reflection, config, templates, serialized names.
- **WRITE:** `[MAP] callers of <symbol>: <file:line>, … (N)` · if `N=0` write
  `N=0 — dead code, or consumed externally?`
- **DONE WHEN:** every changed symbol has a caller count, **and the string search has actually been run**.

### 2.4 Find the siblings
- **DO:** Identify 1–2 pieces of existing code doing **the same kind of thing**: other handlers in
  the same folder, the previous migration, the adjacent service method, the other platform's
  implementation, the other writer that logs the same class of event.
- **WRITE:** `[MAP] sibling: <path:line> — peer of what`
- **DONE WHEN:** at least one sibling is named, or `sibling: none — first of its kind` is written
  (which **raises the bar** on dimensions E and H).

### 2.5 Identify the candidate instances
- **DO:** Work out how many copies could exist on a running machine: the working tree, the
  installed copy, build output (`dist/`, `build/`), a neighbouring worktree
  (e.g. `<project>-lucifer\`), and **the data folder** — dev and installed often read different ones.
- **WRITE:** `[MAP] instance: dev=<path> · installed=<path> · same/different`
- **DONE WHEN:** you know which copy you are about to read, and which one runs in production.

---

## 03 — THE READ (in this order only · ~35% of budget)

### 3.1 Read the tests first
- **DO:** Read only the tests **added or changed by this change**. Write out what the tests
  *believe* correct means. Do not yet judge whether they are good tests.
- **WRITE:** `[Q] tests cover: <...> · do not cover: <...>`
- **DONE WHEN:** you can name at least one thing they do not cover. **If you can't, you haven't
  read them closely enough.**

### 3.2 Walk the full path (not the diff)
- **DO:** Start at the entry point from 2.1 and walk to the **real effect** — a disk write, a
  command sent, a network call, a response to the user. One line per hop.
- **WRITE:** `[TRACE] file:line → file:line — what is passed on`
- **STOP DESCENDING WHEN** any of: (a) you reached the real effect; (b) you entered third-party
  library code; (c) you entered untouched code **whose contract is clear** — record that contract
  as a claim in `[Q]` and continue.
- **DONE WHEN:** the path is **unbroken** from entry to effect. A gap in the trace is a gap in the review.

### 3.3 Now read the diff
- **DO:** Read hunk by hunk, asking one question per hunk: **"does this make the intent from 1.2
  true, or does it just make the symptom go away?"**
- **WRITE:** any hunk you can't answer → straight into `[Q]`. Never skip one.
- **DONE WHEN:** every hunk is either *understood* or *in `[Q]`*. No hunk was merely glanced at.

### 3.4 Look for what is missing
- **DO:** Run five questions as a checklist — (1) is there a test for the bug just fixed?
  (2) are the error paths of the new code handled? (3) do docs / CODEMAP / V-Log need updating?
  (4) is there a rollback / migration path? (5) **is there another site needing the same fix?**
- **WRITE:** each one as `present` / `absent = finding` / `N/A + reason`
- **DONE WHEN:** question (5) is answered by **an actual search result**, not by feel.

---

## 04 — THE SWEEP (10 dimensions in 4 passes · ~25% of budget)

> **Budget shares across the whole review:** 01 SCOPE 10% · 02 RECON 10% · 03 READ 30% ·
> 04 SWEEP 25% · 05 EVIDENCE 15% · 06 WRITE 10% = **100%**. **07 CLOSE-OUT sits outside the cap** —
> it runs after the report is delivered. If you cannot measure wall-clock, use a proxy: the cap is
> spent when you have opened roughly as many files as the review is worth.

Do **not** run A–J as ten separate passes — it burns time and loses context. Batch by
**what kind of looking** each requires.

| Pass | Dimensions | Kind of looking | Share |
|---|---|---|---|
| **1 — Logic** | **A** correctness · **D** state | Slow line-by-line along the `[TRACE]` path: boundaries, duplicates, time, re-runs, who writes this state | ~40% |
| **2 — Failure** | **B** failure · **C** trust | Two sweeps: **(a)** read every `if` / `try` / early `return` branch; **(b)** then re-walk the `[TRACE]` happy path once asking only *"where should a check be that isn't?"* — **a fail-open has no branch to read, so sweep (a) alone cannot see it** | ~30% |
| **3 — Compare** | **H** consistency · **E** contract | Open the sibling from 2.4 **side by side** and diff them by eye — a guard one has and the other lacks | ~20% |
| **4 — Perimeter** | **F** tests · **G** readability · **I** perf · **J** missing | Fast sweep, leaning on tools (linter, grep) more than on eyes | ~10% |

### 4.x Dropping a dimension
- **DO:** A dimension may be dropped only if you can state **"this change touches nothing that
  gives this dimension meaning"** — e.g. a UI string change → dimension D is N/A.
- **WRITE:** `[DIM] D = N/A — string-only change, touches no state`
- **NEVER:** leave a dimension blank. **A blank reads as "checked and passed"** when it wasn't.

---

## 05 — EVIDENCE (prove it before writing it · ~15% of budget)

This is the step that separates a review people trust from a review that wastes their time.
**Every suspicion goes through all five gates** — but the gates do two different jobs, and
confusing them deletes real bugs.

### 05.0 — Resolve `[Q]` first
- **DO:** Every open question on the sheet gets a terminal status: `verified` · `became finding Fn`
  · `UNRESOLVED`. The claims you parked in 3.2 (the contracts of untouched code you chose not to
  descend into) are checked here — **R2 cases #4 and #6 both lived in exactly those claims**.
- **DONE WHEN:** no `Q` is left without a status.

### Drop gates — failing these means the suspicion is not real

| Gate | Do | Failing it means |
|---|---|---|
| **1. Open the real line** | Re-open the file and read the line with your eyes. Never cite from memory or from a search-result snippet. **Record `path:line @ <sha>`** — a bare line number rots | You may have misremembered, or missed the surrounding context |
| **2. Right instance?** | Confirm the file you opened is the one that actually runs — not a neighbouring worktree, a stale build, or the dev data folder | **The whole analysis is wrong** |
| **5. Write the failure scenario** | Write real input → real wrong result, as a sentence | **Can't write it = not a finding, it's taste** |

**Fails gate 1, 2 or 5 → `[DROP]`.** Only these three can kill a suspicion.

### Expand gates — failing these makes the finding BIGGER, never false

| Gate | Do | Failing it means |
|---|---|---|
| **3. Check the sibling** | Open the sibling and see how it handles the same concern | Two outcomes: the sibling has the guard → the finding stands (dimension **H**). The sibling has the *same* hole → **it is systemic, not idiom** — widen the finding to both sites |
| **4. Grep the repo** | Search for the same pattern elsewhere | The finding is **multi-site**: list every site found. One fixed and three left is a failed review |

> ⛔ **Never drop a finding for failing gate 3 or 4.** Rubric §2 H says it outright: if two
> functions do the same kind of thing and one lacks the guard, *one of them is wrong* — so "the
> sibling does it too" is evidence of a systemic bug, not an acquittal. R2 case #5 (8,600 log
> rows/day) and case #12 (a permanent-drop reject path repeated across sources) are exactly the
> bugs a uniform drop rule would have deleted.

---

## 06 — WRITE AND SCORE (~10% of budget)

### 6.1 Write each finding
- **DO:** Use the fixed five-field shape: `file:line` · what is wrong (one sentence) ·
  failure scenario (input → result) · severity · proposed fix **plus the blast radius of that fix**
- **DONE WHEN:** the reader can start fixing **without asking a question back**.

### 6.2 Score
- **DO:** Score each dimension first, then the overall score = **the lowest dimension**, never the
  average. With a panel, **the lowest score in the group**.
- **WRITE:** `[DIM]` complete for A–J, then `score = <n> (lowest, from dimension <X>)`
- **DONE WHEN:** you can name **which dimension held the score down**. If you can't, you are still averaging.

### 6.3 Report what needs no action
- **DO:** Promote `[DROP]` into a section of the report: "checked, already closed, do not fix",
  each with a one-line reason.
- **DONE WHEN:** the reader knows **what not to touch**. Every unnecessary change is free added risk.

### 6.4 State what was not covered
- **DO:** Lift `out-of-scope` + `cut-reason` + every `N/A` dimension **+ every `UNRESOLVED` Q from
  05.0** into the end of the report. An unresolved question is uncovered ground, not a loose end.
- **NEVER:** ship a report that **reads as complete** when half was cut. That is the worst defect a
  review can have.

---

## 07 — CLOSE OUT

### 7.1 Re-check after the fix
- **DO:** Read the **diff of the fix** — do not accept "fixed" as a claim. Ask two questions:
  (a) does it fix the cause or the symptom? (b) **does the fix introduce anything new?**
- **DONE WHEN:** the 6.1 failure scenario no longer reproduces, **and** a test exists that would go
  red if the fix were reverted.

### 7.2 Record the lesson if it crosses projects
- **DO:** Ask "could this class of bug bite another project?" If yes → one line in
  `memory/SHARED_LESSONS.md`: symptom → cause → prevention (rule #10).
- **DONE WHEN:** written and synced. **An unrecorded lesson gets re-learned at the same price.**

---

## 08 — Reviewing your own (or another model's) code

**Mandatory whenever author == reviewer** — which in these repos is the normal case: nearly every
diff is written by a Claude session and reviewed by one.

The failure mode is specific: you do not re-read the code, you re-read **your memory of your
intent**, and everything looks right because it matches what you meant. Countermeasures:

| # | Rule | Why |
|---|---|---|
| 8.1 | **Re-derive the intent from Nick's task text alone** — never from your own commit message | Your commit message describes what you *did*; the task says what was *wanted*. Reviewing your work against your own summary can only ever agree with itself |
| 8.2 | **Open every file fresh.** Do not review from the edit you remember making | The edit you remember is the edit you intended, not the bytes on disk |
| 8.3 | **Gate 2 is not optional for you.** Confirm which instance runs — dev path vs installed path, main vs a worktree | R2 #10 and #14 are both this. So was Coddy's own 2026-08-17 mistake |
| 8.4 | **Run the thing.** Tests, the linter, `node --check`, the actual button — not the library call the button is supposed to make. **Who runs what (split 2026-08-27):** a review firm under `reviver.js` may run **read-only** commands — `git diff/log/show/grep`, `ls`, `md5sum`, `node --check`, and **evaluating a function to see its real output** — and MUST use them rather than reasoning from source. ⛔ **But `import` is not read-only:** importing a module executes its top level, which can create directories, open files, connect to a DB or hit the network, so `python -c "from m import f"` is a state-changing act, not an inspection. Copy the function's body into a blank snippet and run that instead (`node -e "const f = (…pasted…); console.log(f('x'))"`); import the real module only after reading its top level and confirming it merely declares things. *(The first version of this rule shipped the unsafe `import` form as its example — corrected 2026-08-27.)* Running the **full suite / the app / a build** is Coddy's step after the review; a firm that needs it writes "must run X to confirm" into `notCovered` instead of guessing. *(Until 2026-08-27 the firms were granted Read/Grep/Glob only, so this step — and the command table below — were unreachable by the very agents the standard is executed by.)* | R2 #8: a live verification called `download()` directly while the button had been broken for a release · SHIP-MONITORING 2026-08-27: the real ACL-injection hole was found by **running** `build_acl_text(...)`; three firms reading the same file had all cleared it |
| 8.5 | **Write the failure scenario before deciding it's fine.** If you cannot write why it *would* break, you have not tested the belief that it won't | The five-gate rule applies to your own code hardest |
| 8.6 | **State that you are the author** in the report | The reader weighs a self-review differently, and is entitled to |

**When `reviver` runs its 3 lenses on code this session wrote, 8.1–8.5 bind the lenses too** — they
are told to derive intent from the task text and to re-open every file.

---

## R1 — Commands that actually work on Nick's machine

Verified individually against the real repos (Windows 11 / PowerShell).

### Git — scoping and comparing

| Use at | Command |
|---|---|
| 1.1 which files a commit touched | `git -C <repo> show --stat --oneline <sha>` |
| 1.1 changed file names | `git -C <repo> diff --name-only HEAD~1 HEAD` |
| 3.3 diff without CRLF noise — **required here**, `core.autocrlf=true` in all repos | `git -C <repo> diff -w --ignore-cr-at-eol HEAD~1 HEAD -- <path>` |
| 2.3 the commit that introduced/removed a symbol | `git -C <repo> log --oneline -S "<symbol>" -- <path>` |
| 3.2 full history of one function | `git -C <repo> log -L <start>,<end>:<file> --oneline` |
| 2.4 compare two sibling files | `git -C <repo> diff --no-index --stat -- <fileA> <fileB>` |
| 2.3 grep **tracked** files only — skips untracked/ignored output and never leaves the repo (so a sibling `*-lucifer` worktree can't pollute the result). ⚠️ It does **not** skip `_trash/` or `build/` where those are *tracked* — add `':!_trash' ':!build'` to the pathspec, since rule #6 forbids reading `_trash/` | `git -C <repo> grep -n "<pattern>" -- <pathspec> ':!_trash' ':!build'` |
| check for unpushed commits (repos auto-push per #20) | `git -C <repo> log --oneline origin/main..HEAD` |

### Running tests — **every repo is different, do not guess**

| Project | Command |
|---|---|
| HAPPY-Ai-Agent *(real pytest config)* | `python -m pytest -q` |
| SHIP-MONITORING | `python -m pytest -q tests` |
| Happy-Photo-Organizer *(plain script)* | `python tests\test_core.py` |
| Engine_Maintenance_Report *(unittest)* | `python -m unittest discover -s tests -v` |
| Happy-Ai-Trading — **own venv, no pytest installed** | `.venv\Scripts\python.exe -m unittest discover -s tests` |
| OCR-Agentic-Ai — **smoke scripts, not a unit suite** | `.venv\Scripts\python.exe tests\smoke_pipeline.py` |

### Checks that don't require running the app

| Use at | Command |
|---|---|
| 04 pass 4 — Python syntax across the tree | `python -m compileall -q src core ui tools tests` |
| syntax check writing **nothing** at all — **must exclude `.venv`**, or it walks ~7,600 site-packages files, takes minutes, and dies on one non-UTF-8 third-party file | `python -c "import ast,pathlib; [ast.parse(p.read_text(encoding='utf-8',errors='replace'),str(p)) for p in pathlib.Path('.').rglob('*.py') if not {'_trash','__pycache__','build','.venv','dist'} & set(p.parts)]"` |
| before claiming a JS edit is done | `node --check <file.js>` — ⚠️ **not** for the workflow scripts (`tools/*.js`): they run inside an async wrapper, so top-level `return` is legal there and `--check` reports a false error. Wrap the body in `async function(){…}` first |
| Flutter — **bare `flutter` is NOT on PATH here** (the machine's `C:\flutter\bin` entry is stale); Flutter is puro-managed | `puro flutter analyze` — or `& "C:\Users\NickSuksanTr\.puro\envs\stable\flutter\bin\flutter.bat" analyze` |

---

## R2 — Real cases: bugs that shipped, and the step that would have caught them

All from `bug/`, `V-Log.md` and `memory/SHARED_LESSONS.md` in Nick's own projects. Selected for
cases where **the code looked fine and/or the tests were green** — "read more carefully" does not
catch these; a specific step does.

| # | What shipped | The step that catches it | Source |
|---|---|---|---|
| 1 | **Six green tests, all blind.** An M15→H1 join keyed on the M15 bar's *open* time, feeding the H1 bar 15 minutes of its own future. Faked a passing gate (61.2% / PF 1.46 → 47.7% / PF 0.85 after the fix). One test asserted `m15_open <= h1_close`, **which the leaky code satisfies**; another asserted `staleness == 0`, **which is the leak's own signature written down as expected behaviour** | At every time-based join, read the right-hand key off the code and confirm it is the faster frame's **close** instant, not its label. Then name one concrete row ("the M15 bar opening exactly at the H1 close") and confirm it is excluded. **When a metric jumps after adding a data source, treat the number as a bug report until proven otherwise** | Happy-Ai-Trading `bug/bug_v0.0.8.md` |
| 2 | **Firmware-flash function callable by anyone.** A helper was inserted on the line under `@_gate(2)`, rebinding the decorator to the helper. Every flash test passed — **the tests exercised flashing, not authorization** | Read the permission level **off the function object at runtime** (have the decorator stamp an attribute, read it back) and diff against the intended permission table. **Never confirm a gate by reading the `@decorator` line above the def.** Doing this immediately exposed a second hole (an Operator could clear a winch STOP relay) | SHIP-MONITORING `V-Log.md` v1.3.1.9 |
| 3 | **62 tests asserting on source *text* instead of running code.** Burned the project three times: a dead feature stayed "tested" for three releases; a guard test **certified the very hole it existed to close**; an `os._exit` check passed on **prose in a comment** | Grep the suite for assertions that open a source file and match a string (`open(...).read()`, `in src`, regex over `.js`/`.py`). For each, ask: **would this still pass if the implementation were deleted and only a comment remained?** | SHIP-MONITORING `V-Log.md` v1.3.2.4–2.5 |
| 4 | **A "winch left running" alarm that could never fire.** `on_since` was documented as single-owner, but `set_relay` zeroed it a second after `set_latched` set it — so `since` was permanently 0. **It shipped with a comment claiming an earlier version had fixed exactly this.** Also recorded every press as two starts | For a field claimed to have one owner, **grep every assignment site** across the whole tree and lay the writers on the timeline of one real press. **A comment naming the owner is not evidence; the grep is** | SHIP-MONITORING `V-Log.md` v1.3.2.0 |
| 5 | **8,600 log rows per day per relay.** A retry loop wrote a row every 10 s. The rule log had had a first-failure-only guard since v2.8.5; **the command log — its sibling — never got one** | When code writes a row (or sends a notification) **inside a retry loop**, open the sibling writer for the same class of event and diff them line by line. Compute rows-per-day at the retry interval to size it | SHIP-MONITORING `V-Log.md` v1.3.2.1 |
| 6 | **A shipped security lock that engaged on no vessel.** It sat behind a "is the credential file new?" guard, but that file is created on first launch of every build since v2.9.9 with `require:false` already inside — so the guard read "not fresh" for ever. **Live in the code, inert in the field** | Evaluate a migration/first-run predicate against the **on-disk state of an existing install** (list the file, read its contents), not a clean machine. Ask: on a box that already ran the previous version, does this branch ever execute? | SHIP-MONITORING `V-Log.md` v1.3.1.9 |
| 7 | **An updater that deleted the install it had just made**, plus the rollback copy and every neighbouring file. The exe-finder returned the staging directory itself for a zip with the exe at the root — exactly what "select → Send to → compressed folder" produces, and what `validate_zip` accepted — so `rd /s /q` pointed one level too high. On a Desktop or USB root, that is the Desktop or the stick. **Every test used the nested layout the build script produces, so the branch was never entered** | For any path **derived from a discovered location and then passed to a delete/move**, construct the input the tests never build, print what the derived path resolves to, and assert it is strictly **below** the staging root and never an ancestor of the install | Engine_Maintenance_Report `bug/bug_v0.2.7.md` |
| 8 | **The update button had never worked since v0.2.6** — `updater` was imported only inside two other methods. **Third undefined-name bug in the same app.** A live verification an hour earlier had called `download()` directly, **which is not what the button does** | Run an undefined-name linter (pyflakes) over `src/` and treat every hit as a blocker — it kills this whole class in a second. Then verify a feature **by following the button's own call path**, not by calling the library function the button is supposed to call | Engine_Maintenance_Report `bug/bug_v0.2.7.md` |
| 9 | **A build gate that had never once run**, requiring an `_internal/google` folder PyInstaller never creates for pure-Python packages — so **no release could be cut**. Gate written 18:55, last build 18:16. **An unrun check is worse than none: it looks like protection** | Compare the gate's modification time against the last build's. **If the gate is newer, it has never run** — run the build once. Then check each asserted path against a real `dist/` tree | Engine_Maintenance_Report `memory/SHARED_LESSONS.md` |
| 10 | **Two data stores, one divergence, five different-looking complaints** (empty Library, scattered data, wrong counts, "deleted jobs come back"). `DATA_DIR` branched on `sys.frozen`: dev used `<project>\data`, the installed app `%LOCALAPPDATA%`. The UI showed one; "Open folder" opened the other | Resolve the data-directory expression **both with `sys.frozen` set and unset**, print both paths, list both on disk. If they differ, that is the bug regardless of what the UI shows. **When several "wrong/old data" symptoms arrive together, look for one shared-state divergence before chasing each symptom** | OCR-Agentic-Ai `bug/bug_v0.2.0.md` |
| 11 | **Two green smoke tests doing real damage.** One never scoped the queue, so it drained **every pending row in the real dev store** — 8 real sections were overwritten with a fake answer. The other had been sending ~24 **real** Gemini requests on every regression run since v0.0.3. **Because they were green, nobody asked what they were sending** | Per test, list the side effects it can reach: does it open the shared store? does it filter to rows it created? does any path reach the live sender? Force the API key to `None` and set a test data dir — **then confirm it still passes for the right reason** | OCR-Agentic-Ai `bug/bug_v0.1.1.md`, `bug_v0.0.8.md` |
| 12 | **One missing character silenced the whole system.** The first gate's regex accepted ฿/THB/บาท but not the SMS abbreviation **"บ"** that banks actually send. Every such notification became `skipped` and was **permanently removed from the queue** — no retry, no trace. It read as "the listener is dead" while permissions, battery and the service were all fine | Find every gate whose reject path is a **permanent drop**, and run the **real captured strings** for each supported source through it — not idealised fixtures. Then check the reject path leaves a recoverable trace: if "skipped" and "never arrived" look identical downstream, it cannot be debugged from the field | NotiWallet `bug/bug_2026-06-10.md` |
| 13 | **A button that filled the entire screen**, hiding the page list. Moving it into the `bottomNavigationBar` slot gave a `Container` with `alignment` a loose, screen-tall constraint. **Both a Tester and a Lucifer pass missed it because both read the code and never rendered the widget tree** | When a widget **moves to a different layout slot**, pump it in the real slot and assert a **measured dimension** (e.g. height < 120 px). For any `Container` carrying `alignment`, check whether its new parent passes loose or tight constraints | ScanDocs `V-Log.md` v0.2.3 |
| 14 | **Six rounds re-diagnosing a bug that was already fixed** — the fix lived in a Lucifer worktree that was never merged, so main stayed on the old version and the symptom never changed | Before concluding "fixed but still broken", confirm **the fixed code is in what is actually running**: compare the version the app reports against the branch you changed, and check for an unmerged worktree/branch. (This is gate 2 of step 05) | ScanDocs `V-Log.md` |

---

*Volume 2 of 2 · pairs with `CODE_REVIEW_RUBRIC.md` · trigger: `reviver` (command_pattern #26)*
