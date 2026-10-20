---
name: tester
description: Nick's "Tester" trigger (command_pattern #5) — full-system audit by exactly 3 review-only agents via tools/tester.js, then Coddy verifies and fixes everything by hand with 0 agents. Runs ONLY when Nick types /tester or "Tester" himself; never self-start.
disable-model-invocation: true
---

# Tester — command_pattern #5

Mirror of the rule, shipped to every repo by `sync-rules-to-projects.ps1` so a cloud instance can run
it too (#22). **The rule wins** (`memory/nick-workflow.md`); edit the master copy in
`Documents\Claude\Projects\Nick\skills\`, never this mirror.

1. **Launch once** — the `Workflow` tool, `scriptPath` = this repo's `tools/tester.js`
   (on Nick's PC the master `…\Claude\Projects\Nick\tester.js` is the same file),
   args `{ "workdir": "<this project's folder>" }`.
   The script runs **exactly 3 review-only agents in parallel**: ① functional gaps · ② code
   correctness · ③ holistic (perf / UX / structure). They do not fix, edit, build or spawn.
2. ❌ Never hand-spawn those agents with the Agent tool, never fan out per finding/file (#16).
   **FAIL = STOP**: an error, empty or unexpected result → report in plain words and wait for Nick;
   never re-launch or tweak-and-refire (1 trigger = 1 launch).
3. **Then Coddy, 0 agents:** read the findings → verify each against the real code → fix by hand →
   analyze + test → build → Play internal for mobile apps (Tester carries that permission; no Drive
   upload) → update memory → report findings / fixes / token summary.
4. Unlimited TOKENS, not agents — the 3 is fixed inside the script.
