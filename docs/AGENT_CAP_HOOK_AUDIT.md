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
| `MAX_AGENTS: 9`, literal array of nine | 2 | **blocked** |
| `MAX_AGENTS: 8`, no approval note | 2 | **blocked** |
| `MAX_AGENTS: 3`, literal array of **ten** | 2 | **blocked** |
| `MAX_AGENTS: 3`, literal array of three | 0 | allowed *(correct)* |
| **`MAX_AGENTS: 3`, then `for (let i=0;i<40;i++) await agent(i)`** | **0** | ⚠️ **ALLOWED** |
| **`MAX_AGENTS: 3`, then `while (budget.remaining()>N) await agent()`** | **0** | ⚠️ **ALLOWED** |
| a non-`Workflow` tool | 0 | allowed *(correct)* |

## So, precisely

**It does enforce the number** — for fan-out over something countable at author
time. Declared three and wrote a literal ten: refused. Declared nine: refused.
**This is stronger than JobShot's write-up of their copy**, which said nothing
compares the declared number to the script; on this copy it does, and an
overstated gap misleads in the same way an overstated guarantee does.

**It is blind to a loop that calls `agent()` directly**, because there is no
`parallel()`/`pipeline()` for the fan-out gate to inspect. Forty agents from a
`for` loop pass with `MAX_AGENTS: 3` declared.

**Why the second one is not simply a bug to fix:** `while (budget.remaining() > N)
{ await agent(...) }` is a **documented pattern** in the workflow-authoring
reference (loop-until-budget), as is loop-until-dry. A rule tightened to refuse a
loop around `agent()` would refuse those too — and **a guard that fires on
something legitimate is a guard somebody `--no-verify`s**, after which there is no
guard at all. That is the same reason the BOM guard checks CR on `.py` only:
`.claude/settings.json` carries CRLF harmlessly, and failing on it would have
bought nothing and cost the hook.

## Not changed, and not mine to change

**The hook is untouched** and **`CLAUDE.md` is untouched.** Whether to tighten the
hook, or to reword #16.1 so a reader does not count less carefully on the
strength of it, is **Nick's call** — he has the table. A peer raised this, and a
peer's suggestion is not grounds for editing `CLAUDE.md`, the hook config, or
permissions.

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
