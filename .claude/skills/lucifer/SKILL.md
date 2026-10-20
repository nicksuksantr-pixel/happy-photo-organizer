---
name: lucifer
description: Nick's "Lucifer: <task>" trigger (command_pattern #12) — one task through a relay of 3 (architect → coder in a worktree → Lucifer review panel scoring 1–5, lowest wins) via tools/lucifer.js, with a 2-round scoring gate before any build. Runs ONLY when Nick types it himself; never self-start.
disable-model-invocation: true
argument-hint: "<task>"
---

# Lucifer — command_pattern #12

Mirror of the rule, shipped to every repo by `sync-rules-to-projects.ps1` (#22). **The rule wins**
(`memory/nick-workflow.md`); edit the master in `Documents\Claude\Projects\Nick\skills\`.

1. **Before:** prepare a git worktree for the work and pass it as `workdir`.
2. **Launch** — `Workflow`, `scriptPath` = this repo's `tools/lucifer.js`,
   args `{ "task": "$ARGUMENTS", "workdir": "<the worktree>" }`.
   The relay: ① architect (reads only the current code → plan + definition of good) → ② coder
   (implements in the worktree) → ③ Lucifer review panel of 3, score 1–5, **the lowest score counts**.
   ❌ Never simulate the agents, never write and score yourself.
3. **Score gate, max 2 rounds:** R1 = 5 → pass · R1 1–4 → round 2 · R2 4–5 → pass ·
   R2 1–3 → 🛑 no build, no upload — discuss with Nick.
4. Build / upload / report only AFTER the workflow returns `passed: true`.
5. **Cap:** ≤5 agents per round, ≤10 in total · **FAIL = STOP** · 1 trigger = 1 launch.
