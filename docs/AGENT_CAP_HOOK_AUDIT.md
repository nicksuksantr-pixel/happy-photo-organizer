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
| `MAX_AGENTS: 3`, literal array of **ten** | 2 | **blocked** — the message says *"has 10 items, over 5"*. **Over 5, not over 3.** I first read this row as a cross-check against the declaration; it is not one. See the corrected section below |
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

**Why that second one is not simply a bug to fix:** `while (budget.remaining() > N)
{ await agent(...) }` is a **documented pattern** in the workflow-authoring
reference, as is loop-until-dry. A rule tightened to refuse a loop around
`agent()` would refuse those too — and **a guard that fires on something
legitimate is a guard somebody `--no-verify`s**, after which there is no guard at
all. (JobShot reports that Nick has since ruled on exactly this and tightened
their copy; see the note below — that ruling has not reached me directly, and I
have changed nothing here on the strength of a relayed instruction.)

**One divergence worth recording rather than smoothing over:** JobShot found their
copy blamed *"runtime data via `.map()`"* for an array literal — a correct refusal
with a false reason. **Mine says `has 10 items, over 5`, which is correct**, so
either the copies differ or theirs is older. Measured, not assumed, and not
reconciled.

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
