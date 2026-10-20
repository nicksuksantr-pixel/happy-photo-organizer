---
name: clean
description: Nick's "clean" trigger (command_pattern #27) — refactor / clean-code / format+speed review of ONE layer by 3 independent firms via tools/clean.js, plus the tidy.mjs housekeeping report. Report-only; Coddy never flows on into fixing. Runs ONLY when Nick types /clean or "clean" himself; never self-start.
disable-model-invocation: true
argument-hint: "<layer — one layer, never the whole repo>"
---

# clean — command_pattern #27 · clean = change the SHAPE, never the BEHAVIOUR

Mirror of the rule, shipped to every repo by `sync-rules-to-projects.ps1` (#22). **The rule wins**
(`memory/nick-workflow.md`); edit the master in `Documents\Claude\Projects\Nick\skills\`.

1. **Prepare the four gates first — `clean.js` opens no agent without all four:**
   `layer` = `$ARGUMENTS` (ONE layer whose outside edge you can write down) · `backup` (zip under
   `Documents\Projects\Backups\`) · `branch` (`clean/…`, never `main`) · `baseline` (run the test suite
   BEFORE touching anything — already red = no baseline = STOP).
2. **Housekeeping (not a gate, never silent):** `node tidy.mjs --project <proj>` (0 agents, ~1 s) and
   pass its output as `housekeeping`. Not run = say so; empty means "not looked", not "clean".
3. **Launch once** — `Workflow`, `scriptPath` = this repo's `tools/clean.js`,
   args `{ "workdir", "layer", "backup", "branch", "baseline", "housekeeping" }`.
   3 firms, each walking all three aspects (structure · clarity · format+speed); a proposal without a
   `behaviourProof` is dropped by the script.
4. **Report-only:** tiers `DO` (3 firms) · `ADJUDICATE` (2 — open the code, decide) · `LOG ONLY`
   (1 — maybe taste, never a to-do). ❌ Do not start fixing. A bug found on the way is filed
   separately, never bundled into a refactor.
5. Housekeeping: never delete — over-quota files are moved (`--rotate`); emptying a bin is Nick's `--yes`.
6. **FAIL = STOP** · 1 trigger = 1 launch · cap #16 (3, one parallel, no fan-out).
