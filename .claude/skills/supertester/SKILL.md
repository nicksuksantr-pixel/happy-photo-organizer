---
name: supertester
description: Nick's "supertester" trigger (command_pattern #23) — deep review in EXACTLY 3 sequential rounds of 3 review-only agents via tools/supertester.js, Coddy fixing by hand between rounds. Runs ONLY when Nick types /supertester or "supertester" himself; never self-start.
disable-model-invocation: true
argument-hint: "[scope — optional; auto-scoped from recent work if empty]"
---

# supertester — command_pattern #23

Mirror of the rule, shipped to every repo by `sync-rules-to-projects.ps1` (#22). **The rule wins**
(`memory/nick-workflow.md`); edit the master in `Documents\Claude\Projects\Nick\skills\`.

1. **Scope:** use `$ARGUMENTS` if given; otherwise auto-scope from recent work + the latest 20
   `log/` entries. Say the scope in one line before launching.
2. **Three rounds, one at a time** — each round is one `Workflow` call, `scriptPath` = this repo's
   `tools/supertester.js`, args `{ "workdir": "<this project>", "round": 1|2|3, "scope": "<scope>" }`.
   Each round = **3 review-only agents** (R1 broad · R2 verify-fix + deeper / data / security ·
   R3 acceptance + regression + release). ❌ Never launch two rounds at once (9 total, ≤3 concurrent).
3. **After each round, Coddy fixes by hand with 0 agents**, then the next round:
   review → fix → review → fix → review → fix.
4. **FAIL = STOP** (error / empty / unexpected → report, wait for Nick; never re-launch). 1 trigger = 1 run of 3 rounds.
5. After round 3: analyze + test → build → Play internal for mobile (no Drive) → memory + bug +
   SHARED_LESSONS hand-over (`memory/TO_PROMOTE.md`, #10.1) → report.
