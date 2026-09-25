#!/usr/bin/env node
// PreToolUse guard for the Workflow tool — enforcement of command_pattern #16.
//
// WHY THIS FILE EXISTS
// 2026-09-25: one Workflow launch spawned 54 agents (Engine_Maintenance_Report).
// It was the 7th run over the cap out of 96; the worst was 74 on 2026-09-10.
// The cap is written in bold at the top of CLAUDE.md and it still happened, because
// THE AGENT COUNT WAS NOT IN THE SCRIPT — IT WAS IN THE DATA:
//
//     pipeline(LENSES, lens => agent(...),            // 5 agents, visible
//              res => parallel(res.findings.map(f =>  // 1 agent PER FINDING,
//                        () => agent(...))))          // count unknown until runtime
//
// The permission dialog showed "five independent lenses". Nobody could read "54"
// off that script, so nobody declared it and nobody stopped it.
// A cap you cannot count before you launch is not a cap. This hook makes the
// count mandatory and refuses the uncapped-fan-out shape outright.
//
// Blocks by writing the reason to stderr and exiting 2 (works in bypass-permissions
// mode, where a permission prompt would never appear).

import fs from 'node:fs'
import path from 'node:path'

const CAP = 5                    // #16: default <=3, absolute max 5, >5 = ask Nick
const HOME = process.env.USERPROFILE || process.env.HOME || ''
const APPROVAL = path.join(HOME, '.claude', 'workflow-approval.json')

// Nick's own trigger scripts: agent count is fixed at exactly 3 inside the script
// and each one was reviewed when it was written. Nothing else is exempt.
const HOUSE = new Set([
  'tester.js', 'supertester.js', 'supertester-security.js',
  'reviver.js', 'clean.js', 'lucifer.js',
])

const read = (fd) => { try { return fs.readFileSync(fd, 'utf8') } catch { return '' } }
const deny = (msg) => { process.stderr.write(msg + '\n'); process.exit(2) }
const allow = () => process.exit(0)

let hook = {}
try { hook = JSON.parse(read(0) || '{}') } catch { allow() }       // unparsable = don't break the session
if (hook.tool_name !== 'Workflow') allow()

const input = hook.tool_input || {}

// ── resolve the script text ──────────────────────────────────────────────────
let script = typeof input.script === 'string' ? input.script : ''
let origin = 'inline script'
if (!script && input.scriptPath) {
  if (HOUSE.has(path.basename(input.scriptPath))) allow()          // house trigger, fixed at 3
  script = read(input.scriptPath)
  origin = input.scriptPath
}
if (!script && input.name) {
  if (HOUSE.has(input.name) || HOUSE.has(input.name + '.js')) allow()
  deny(`RULE #16 — Workflow BLOCKED: saved workflow "${input.name}" cannot be counted from here.
Read its script, state the worst-case agent count to Nick, and relaunch with an inline
script carrying a "// MAX_AGENTS: <n>" line.`)
}
if (!script) allow()                                               // resume-only / nothing to inspect

// ── GATE A — the count must be declared, in the script, before launching ─────
const decl = script.match(/\/\/\s*MAX_AGENTS:\s*(\d+)/)
if (!decl) {
  deny(`RULE #16 — Workflow BLOCKED: no agent count declared (${origin}).

Add ONE line to the script naming the WORST CASE, counted by hand:

    // MAX_AGENTS: 3      <- finders + verifiers + synthesizer, worst case, not typical

Default <=3 per round, absolute max ${CAP}. More than ${CAP} => STOP and ask Nick first,
saying how many and why. Count it before you launch; do not launch to find out.`)
}
const declared = Number(decl[1])

// ── GATE B — the uncapped fan-out shape, the one that actually cost us ───────
// Every parallel()/pipeline() must fan out over something COUNTABLE at author time:
// a literal array, an Array.from({length: N}), or an explicit .slice(0, N).
// Count the top-level entries of the array literal whose '[' sits at openIdx.
// An array literal is countable at author time; that is what makes a fan-out declarable.
const countLiteral = (src, openIdx) => {
  let depth = 0, entries = 0, seen = false
  for (let i = openIdx; i < src.length; i++) {
    const c = src[i]
    if (c === '[' || c === '{' || c === '(') { depth++; if (depth === 1) seen = true }
    else if (c === ']' || c === '}' || c === ')') { depth--; if (depth === 0) break }
    else if (c === ',' && depth === 1) entries++
    else if (depth === 1 && !/\s/.test(c)) seen = true
  }
  return seen ? entries + 1 : 0
}

const litLens = new Map()                                          // const X = [ ... ]  -> entry count
for (const m of script.matchAll(/(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\[/g)) {
  litLens.set(m[1], countLiteral(script, m.index + m[0].length - 1))
}

const offenders = []
for (const m of script.matchAll(/\b(parallel|pipeline)\s*\(/g)) {
  const head = script.slice(m.index, m.index + 260).replace(/\s+/g, ' ')

  // inline literal:  parallel([1, 2, 3].map(...))  /  pipeline([{...}, {...}], ...)
  const openIdx = script.indexOf('(', m.index) + 1
  let j = openIdx
  while (j < script.length && /\s/.test(script[j])) j++
  if (script[j] === '[') {
    const n = countLiteral(script, j)
    if (n > CAP) offenders.push(`${m[1]}([...]) has ${n} items, over ${CAP}`)
    continue
  }

  const arg = head.match(/^\w+\s*\(\s*([A-Za-z_$][\w$.]*)/)        // first argument
  const sliced = head.match(/\.slice\(\s*0\s*,\s*(\d+)/)
  const fromLen = head.match(/Array\.from\(\s*\{\s*length:\s*(\d+)/)

  if (sliced) { if (Number(sliced[1]) > CAP) offenders.push(`${m[1]}(...) .slice(0, ${sliced[1]}) exceeds ${CAP}`); continue }
  if (fromLen) { if (Number(fromLen[1]) > CAP) offenders.push(`${m[1]}(...) Array.from length ${fromLen[1]} exceeds ${CAP}`); continue }
  if (arg) {
    const root = arg[1].split('.')[0]
    if (litLens.has(root) && !/\.map\(/.test(head.slice(0, 80))) {
      if (litLens.get(root) > CAP) offenders.push(`${m[1]}(${root}) has ${litLens.get(root)} items, over ${CAP}`)
      continue
    }
    if (litLens.has(root) && litLens.get(root) <= CAP) continue     // literal array, mapped, still countable
  }
  if (/\.map\(/.test(head)) {
    offenders.push(`${m[1]}(...) fans out over runtime data via .map() with no .slice(0, N) — ` +
                   `this is the 54-agent shape: one agent per finding, count unknown until it runs`)
  }
}
if (offenders.length) {
  deny(`RULE #16 — Workflow BLOCKED: uncapped fan-out (${origin}).

${offenders.map((o) => '  * ' + o).join('\n')}

"1 agent per finding / file / page" is forbidden unless its hard cap is named IN THE CODE.
Fix: rank first, then cap the list —  .slice(0, ${CAP})  — or verify in one batched agent.`)
}

// ── GATE C — over the cap needs Nick himself, not a bigger number in a comment ─
if (declared > CAP) {
  let ok = null
  try { ok = JSON.parse(read(APPROVAL)) } catch { ok = null }
  const valid = ok && Number(ok.maxAgents) >= declared &&
                (!ok.expiresEpochMs || Date.now() < Number(ok.expiresEpochMs))
  if (!valid) {
    deny(`RULE #16 — Workflow BLOCKED: declares ${declared} agents, cap is ${CAP}.

STOP and tell Nick the number and the reason, in his language, and wait for his answer.
He approves by having the guard note written to:
  ${APPROVAL}
No approval note, or one smaller than ${declared}, or expired => the launch does not happen.`)
  }
  try { fs.unlinkSync(APPROVAL) } catch {}                          // one shot, never standing
  process.stderr.write(`RULE #16: ${declared} agents ran on Nick's one-shot approval; note consumed.\n`)
}
allow()
