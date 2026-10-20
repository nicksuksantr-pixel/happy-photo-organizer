---
name: supertester-security
description: Nick's "supertester security" trigger (command_pattern #24) — attacker-mindset defensive audit, 3 sequential rounds × 3 read-only agents via tools/supertester-security.js. SAFE MODE — approve-before-fix: Coddy proposes fixes with blast radius and WAITS for Nick. Runs ONLY when Nick types it himself; never self-start.
disable-model-invocation: true
argument-hint: "[scope — optional]"
---

# supertester security — command_pattern #24 · 🔐 SAFE MODE

Mirror of the rule, shipped to every repo by `sync-rules-to-projects.ps1` (#22). **The rule wins**
(`memory/nick-workflow.md`); edit the master in `Documents\Claude\Projects\Nick\skills\`.
Defensive audit of Nick's own systems = authorized. ❌ No exploit / PoC / malware, no live run or scan.

1. **Scope:** `$ARGUMENTS` if given, else auto-scope; state it in one line.
2. **Each round** = one `Workflow` call, `scriptPath` = this repo's `tools/supertester-security.js`,
   args `{ "workdir": "<this project>", "round": 1|2|3, "scope": "<scope>" }` → 3 read-only agents,
   fixed attacker angles: 🌐 remote/network · 🔧 tampering/supply-chain · 🔑 auth/privilege/secrets.
   Rounds deepen: recon → exploit-chain + verify (challenge "trusted LAN") → remediation-verify +
   residual / blast radius. One round at a time.
3. **⛔ Approve-before-fix — the difference from Tester/supertester:** after each round present the fix
   plan with **per-fix blast radius**, then **STOP and wait for Nick's approval**. Fix only what he
   approved, on a **security branch, backup first**, then the next round.
4. ❌ **Never auto-build or deploy** — Nick decides deployment.
5. **FAIL = STOP** · 1 trigger = 1 run · cap #16 (3 per round, sequential).
