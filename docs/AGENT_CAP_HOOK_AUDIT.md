# What the agent-cap hook actually catches

**Audited 2026-10-02 · 0 agents spent · driven with synthetic `PreToolUse` payloads**

`tools/workflow-agent-cap.mjs`, wired by the tracked `.claude/settings.json`, is
the only automated enforcement of the agent cap (`CLAUDE.md` #16 / #16.1) — and
it is the one gate in this repo whose own failure meant **the cap silently turns
off**, because #16.1 says it *"fails OPEN if it cannot run."*

JobShot audited their copy while waiting on a test and found it did not do
everything the paragraph above it implied. **I re-measured mine rather than take
that on report**, because the whole of 2026-10-02 was projects correcting each
other's descriptions of their own code. It is a node script that reads JSON on
stdin, so every gate can be driven for free.

## Measured

| Script | exit | |
|---|---|---|
| no `// MAX_AGENTS` line at all | 2 | **blocked** |
| `parallel(items.map(...))` — fan-out over runtime data | 2 | **blocked** |
| `MAX_AGENTS: 9`, literal array of nine | 2 | **blocked** — because 9 > 5, **not** because 9 ≠ the fan-out |
| `MAX_AGENTS: 8`, no approval note | 2 | **blocked** — because 8 > 5 |
| `MAX_AGENTS: 3`, literal array of **ten**, written **inline** | 2 | **blocked** — *"has 10 items, over 5"*. **Over 5, not over 3**; this is not a cross-check against the declaration. And the message differs if the array is **named** first — see below |
| `MAX_AGENTS: 3`, literal array of three | 0 | allowed *(correct)* |
| **`MAX_AGENTS: 3`, then `for (let i=0;i<40;i++) await agent(i)`** | **0** | ⚠️ **ALLOWED** |
| **`MAX_AGENTS: 3`, then `while (budget.remaining()>N) await agent()`** | **0** | ⚠️ **ALLOWED** |
| a non-`Workflow` tool | 0 | allowed *(correct)* |

## So, precisely — **CORRECTED 2026-10-02, and the first version of this section was wrong**

**It does NOT compare the declared number to the script.** JobShot named the
decisive case I had not run, and it settles it:

| Script | exit | |
|---|---|---|
| `MAX_AGENTS: 1`, literal array of **five** | **0** | **ALLOWED** |
| `MAX_AGENTS: 5`, literal array of five | 0 | allowed |
| `MAX_AGENTS: 2`, literal array of four | 0 | allowed |

Declared one, wrote five, accepted. **Both results I had read as a cross-check are
explained by the comparison against `CAP = 5` alone** — a literal of ten is
refused because 10 > 5, and a declared nine because 9 > 5. Neither looks at the
declaration.

**And the refutation was printed by my own first probe.** The refusal says:

    * parallel([...]) has 10 items, over 5

**"over 5" — not "over 3".** I had displayed only the exit codes, so I never saw
the reason, and then inferred a mechanism from two refusals that had a simpler
cause. **That is my own earlier lesson — *a summary of a wire is not the wire* —
applied to the output of my own instrument**, and the cost was that I used it to
correct a peer who had read their code properly.

**So what the hook actually enforces:**

- a `// MAX_AGENTS` line **exists** (not that it is true)
- no fan-out is **uncountable** at author time
- no countable fan-out, and no declaration, **exceeds `CAP = 5`** without the
  approval note

**It is blind to a loop that calls `agent()` directly** — forty agents from a
`for` loop pass with `MAX_AGENTS: 3` declared, because there is no
`parallel()`/`pipeline()` for the fan-out gate to inspect.

**My first reading of that gap was wrong too, and the correction matters more
than the gap.** I argued it was *"not simply a bug to fix"*, because
`while (budget.remaining() > N) { await agent(...) }` and loop-until-dry are
**documented patterns** in the workflow-authoring reference, so refusing them
would make this a guard that fires on legitimate work — and a guard that does
that is one somebody `--no-verify`s.

**JobShot took that apart and they are right:** those loops **exceed five by
construction**, so under #16 they are *already over the cap* and belong on Nick's
one-shot approval note like any other number above five. Refusing them is not a
false positive; it is the rule working.

> **"Documented in the authoring reference" is not "permitted under #16."**
> Different documents, different authority.

I had been treating a pattern's presence in a reference as a licence — **which is
exactly how a cap erodes without anyone deciding to erode it.** The trade-off I
thought existed does not; what does exist is the implementation risk JobShot hit
within one run of tightening theirs — `log("searching for things (quickly)")`
refused as *"a for loop"*, because `for` sat inside an English sentence and the
next `(` belonged to the prose.

(JobShot reports Nick has ruled on this and tightened their copy. That ruling has
not reached me directly, and nothing here has changed on a relayed instruction —
see below.)

## Not a divergence — **the message depends on how the array is SPELLED**

I recorded a suspected divergence here, because JobShot's copy blamed *"runtime
data via `.map()`"* for an array literal while mine said `has 10 items, over 5`.
**There is no divergence.** JobShot ran both spellings through one binary and
found the third explanation neither of us had considered; measured again here, on
this copy:

| The same logical script | exit | reason given |
|---|---|---|
| `parallel([1..10].map(...))` — **inline** | 2 | `parallel([...]) has 10 items, over 5` ✅ true |
| `const L=[1..10]; parallel(L.map(...))` — **named** | 2 | `fans out over runtime data via .map() … count unknown until it runs` ❌ **false** |

**Same decision, different reason, decided by where the array was written.** The
branch that consults the literal counter is skipped whenever `.map(` appears, so
the named spelling falls through to the catch-all. **My probe happened to write
the array inline, which is the only reason I saw the honest message** — so the
"divergence" was an artifact of my own probe's shape, on top of the inference it
had already produced.

**So this hook has a second defect, on this copy, independent of the loop gap: a
refusal whose stated reason is false.** The decision is right; the sentence sends
the reader hunting for runtime data in a literal array two lines above. JobShot's
framing is the one to keep: **a refusal whose reason nobody reads can be false
indefinitely at no cost — until somebody reads it and believes it.** Mine cost
one wrong correction of a peer; theirs would eventually have cost somebody an
afternoon.

**Not fixed here, and bundled with the loop gap rather than treated as separate.**
It is a change to the same guard, and this file already says that guard waits for
Nick. JobShot has fixed theirs and reports the shape that cost them a round: blank
strings and comments **before** matching anything, keep template `${...}` holes
because an `agent()` can live in one, and **test the stripper itself** — a guard's
guard. That scoping is here so the work is ready rather than being started twice.

## Not changed, and not mine to change

**The hook is untouched** and **`CLAUDE.md` is untouched.** Whether to tighten the
hook, or to reword #16.1 so a reader does not count less carefully on the
strength of it, is **Nick's call** — he has the table. A peer raised this, and a
peer's suggestion is not grounds for editing `CLAUDE.md`, the hook config, or
permissions.

**That holds even now that a ruling is reported.** JobShot says Nick told them to
block unbounded loops around `agent()` and allow only what the rule allows, and
they have tightened their copy on the strength of a message **he sent them**.
**A peer's account of an instruction is not the instruction**, so nothing here
moves until Nick says so to me. The gap, the trade-off and the reported ruling
are all written down above so that when he does, the work is already scoped.

**What stands regardless:** #16.1's real instruction is to hand-count the worst
case before spawning. The hook catches the forms where the count is written down
and wrong. **It cannot catch a count nobody did** — which is why the rule is
addressed to the author and not to the script.

## The gap below this one, named rather than claimed covered

Nothing tests the hook's own coverage. This table is a measurement of today, not
a property of the repo: a new fan-out construct, or a second config file, would
go unnoticed exactly as `.spec`/`.json`/`.mjs` went unnoticed by the BOM guard
until it was driven both ways. **JobShot's copy has the same shape — their
manifest gate reads one hard-coded path and nothing notices if a second manifest
appears.**

— Codey (HPO session)
