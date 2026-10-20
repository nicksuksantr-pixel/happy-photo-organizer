---
name: reviver
description: Nick's "reviver" / "reviewer" trigger (command_pattern #26) — the house code-review standard, run by exactly 3 independent review firms via tools/reviver.js that each do the WHOLE job, then cross-checked. Report findings + fix plan and ask; no auto-fix. Runs ONLY when Nick types it himself; never self-start.
disable-model-invocation: true
argument-hint: "[target path or commit — optional; default = the current changes]"
---

# reviver — command_pattern #26 (+ 26.1 cost discipline)

Mirror of the rule, shipped to every repo by `sync-rules-to-projects.ps1` (#22). **The rule wins**
(`memory/nick-workflow.md`); edit the master in `Documents\Claude\Projects\Nick\skills\`.
The standard itself: `memory/CODE_REVIEW_RUBRIC.md` (what to look at) +
`memory/CODE_REVIEW_PROCEDURE.md` (how to run it).

1. **Cheap check first (26.1):** if a test run or a direct read answers it, do that before agents.
2. **Launch once** — `Workflow`, `scriptPath` = this repo's `tools/reviver.js`,
   args `{ "workdir": "<this project>", "target": "$ARGUMENTS" }` (omit `target` for the current changes).
   **Exactly 3 firms, identical job** — each walks all 7 parts and scores all 10 dimensions A–J itself
   (they never split the work: three complete opinions is the cross-check).
3. **Read the comparison, not just the findings:** `scoreAgreement`, `dimensionComparison`,
   `thoroughness`, `conflicts`, `corroborated` / `solo`, `intentAgreement`. Where firms disagree, open
   the code and decide yourself.
4. **Rules that do not bend:** score = the LOWEST dimension, not the average · no concrete failure
   scenario = not a finding · report what was cleared AND what was not covered.
5. **❌ No auto-fix:** present findings + fix plan + blast radius and ask — unless Nick said to fix.
   0 BLOCKER + 0 corroborated MAJOR = pass. Two rounds per target, then it is Nick's call.
6. **FAIL = STOP** · 1 trigger = 1 launch · cap #16.
