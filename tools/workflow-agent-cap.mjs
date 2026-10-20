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

// ── Read CODE, not prose ────────────────────────────────────────────────────
// Every gate below matches keywords and brackets against the script text, and
// a workflow script is mostly PROMPTS — English sentences full of the words
// `for`, `do` and `while` and full of brackets. Driven on 2026-10-02, before
// this existed:
//
//     log("searching for things (quickly)")
//     const r = await agent("one agent")        // <- BLOCKED as "a for loop"
//
// One honest single-agent script, refused, because `for` sat inside a string
// and the next `(` belonged to a sentence. **A guard that fires on legitimate
// code is a guard somebody turns off**, and then there is none — which is why
// this is a correctness requirement and not tidiness. (Same morning, same
// lesson: manifest_test.dart was satisfied by a commented-out permission
// because it matched raw text too.)
//
// The contents of strings and comments are replaced with spaces, LENGTH AND
// NEWLINES PRESERVED, so every index, regex and bracket-match below reads the
// same positions in a text that contains only code. A template literal keeps
// its `${...}` holes — those really are code, and an agent() call can live in
// one.
const scrub = (src, keepComments) => {
  const out = src.split('')
  const n = src.length
  const wipe = (a, b) => {
    for (let i = a; i < b && i < n; i++) if (out[i] !== '\n') out[i] = ' '
  }

  // Returns the index just past the construct it consumed.
  function template(start) {              // src[start] === '`'
    let i = start + 1
    let from = i
    while (i < n) {
      if (src[i] === '\\') { i += 2; continue }
      if (src[i] === '`') { wipe(from, i); return i + 1 }
      if (src[i] === '$' && src[i + 1] === '{') {
        wipe(from, i)
        i = code(i + 2, false)            // the hole is real code; keep it
        from = i
        continue
      }
      i++
    }
    wipe(from, n)                         // unterminated: treat the rest as text
    return n
  }

  function code(start, top) {
    let i = start
    let depth = 0
    while (i < n) {
      const c = src[i]
      const d = src[i + 1]
      if (c === '/' && d === '/') {
        let j = src.indexOf('\n', i)
        if (j < 0) j = n
        if (!keepComments) wipe(i, j)
        i = j
        continue
      }
      if (c === '/' && d === '*') {
        let j = src.indexOf('*/', i)
        j = j < 0 ? n : j + 2
        if (!keepComments) wipe(i, j)
        i = j
        continue
      }
      if (c === "'" || c === '"') {
        let j = i + 1
        while (j < n && src[j] !== c) { if (src[j] === '\\') j++; j++ }
        wipe(i + 1, j)
        i = j + 1
        continue
      }
      if (c === '`') { i = template(i); continue }
      if (!top && c === '{') { depth++; i++; continue }
      if (!top && c === '}') {
        if (depth === 0) return i + 1     // closes the ${ } hole
        depth--
        i++
        continue
      }
      i++
    }
    return n
  }

  code(0, true)
  return out.join('')
}

// Gate A looks for `// MAX_AGENTS: n`, so it needs the comments and must not
// accept the line quoted inside a string. Everything after it reads code only.
const declText = scrub(script, true)
script = scrub(script, false)

// ── GATE A — the count must be declared, in the script, before launching ─────
const decl = declText.match(/\/\/\s*MAX_AGENTS:\s*(\d+)/)
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
//
// ⚠ An entry is counted when something STARTS it, not once per comma. The first
// version returned `commas + 1`, so the trailing comma every multi-line array
// here ends with (`},\n]`) was one more agent than the script runs. Harmless
// while the only comparison was against the cap; once gate E compared it to
// the script's own MAX_AGENTS it refused 7 of the 10 honest scripts in the
// persisted history — each one three lenses, declared 3, counted 4. Replayed
// 2026-10-20 before this was promoted to the master. (`[]` used to count 1.)
const countLiteral = (src, openIdx) => {
  let depth = 0, entries = 0, open = false              // open: an entry has started since the last comma
  for (let i = openIdx; i < src.length; i++) {
    const c = src[i]
    if (c === '[' || c === '{' || c === '(') { depth++; if (depth === 2) open = true }
    else if (c === ']' || c === '}' || c === ')') { depth--; if (depth === 0) break }
    else if (c === ',' && depth === 1) { if (open) entries++; open = false }
    else if (depth === 1 && !/\s/.test(c)) open = true
  }
  return entries + (open ? 1 : 0)
}

const litLens = new Map()                                          // const X = [ ... ]  -> entry count
for (const m of script.matchAll(/(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\[/g)) {
  litLens.set(m[1], countLiteral(script, m.index + m[0].length - 1))
}

const offenders = []

// How wide this fan-out is, or null when a reader cannot tell before it runs.
// Order matters: an explicit .slice(0, N) is the author writing the cap down,
// and it wins over whatever the list behind it happens to be.
const fanWidth = (head, callIdx) => {
  const sliced = head.match(/\.slice\(\s*0\s*,\s*(\d+)/)
  if (sliced) return Number(sliced[1])
  const fromLen = head.match(/Array\.from\(\s*\{\s*length:\s*(\d+)/)
  if (fromLen) return Number(fromLen[1])

  // parallel([a, b, c].map(...)) / pipeline([{...}, {...}], ...) — right there
  const openIdx = script.indexOf('(', callIdx) + 1
  let j = openIdx
  while (j < script.length && /\s/.test(script[j])) j++
  if (script[j] === '[') return countLiteral(script, j)

  // parallel(DIMENSIONS.map(...)) — countable iff DIMENSIONS is a literal
  // array declared in this same script, mapped or not.
  const arg = head.match(/^\w+\s*\(\s*([A-Za-z_$][\w$.]*)/)
  if (arg) {
    const root = arg[1].split('.')[0]
    if (litLens.has(root)) return litLens.get(root)
  }
  return null
}

for (const m of script.matchAll(/\b(parallel|pipeline)\s*\(/g)) {
  const head = script.slice(m.index, m.index + 260).replace(/\s+/g, ' ')
  const n = fanWidth(head, m.index)

  if (n === null) {
    if (/\.map\(/.test(head)) {
      offenders.push(`${m[1]}(...) fans out over runtime data via .map() with no ` +
        `.slice(0, N) — this is the 54-agent shape: one agent per finding, ` +
        `count unknown until it runs`)
    }
    continue
  }
  // ⚠ The message used to say "fans out over runtime data" for a LITERAL array
  // of ten, because the countable branches were skipped whenever `.map(` was
  // present and everything fell through to the catch-all. The refusal was
  // right and its stated reason was false — a reader would go looking for
  // runtime data that was not there. Measured 2026-10-02.
  if (n > CAP) {
    offenders.push(`${m[1]}(...) fans out ${n} ways, over ${CAP}`)
    continue
  }
  // ── GATE E — the declared number must survive contact with the script ─────
  // #16.1: *the count was in the DATA, not the script* — `meta.description`
  // honestly read "five lenses" while 54 ran. A declaration smaller than a
  // fan-out this file can COUNT is that same sentence, caught this time.
  //
  // One-directional on purpose: static reading gives a LOWER bound on agents
  // (it cannot see three phases of three), so `counted > declared` proves the
  // declaration wrong, while `counted <= declared` proves nothing and says
  // nothing. A guard that only speaks when it is certain is a guard that
  // stays switched on.
  if (n > declared) {
    offenders.push(`${m[1]}(...) fans out ${n} ways but the script declares ` +
      `MAX_AGENTS: ${declared} — the declaration is the thing Nick reads`)
  }
}

if (offenders.length) {
  deny(`RULE #16 — Workflow BLOCKED: uncapped fan-out (${origin}).

${offenders.map((o) => '  * ' + o).join('\n')}

"1 agent per finding / file / page" is forbidden unless its hard cap is named IN THE CODE.
Fix: rank first, then cap the list —  .slice(0, ${CAP})  — or verify in one batched agent.`)
}

// ── GATE D — a loop around agent() must have a bound you can read ───────────
// Nick, 2026-10-02: *บล็อกลูปที่เรียก agent แบบไม่มีขอบเขตด้วย ให้ใช้ได้ตามกฎแค่นั้น.*
//
// Gate B catches the fan-out that cost us 54 agents, but it only ever looked at
// parallel() and pipeline(). Driven with synthetic payloads on 2026-10-02, these
// two walked straight through it:
//
//     for (let i = 0; i < 40; i++) await agent(i)          // 40 agents
//     while (budget.remaining() > N) await agent()         // unbounded
//
// Neither contains a fan-out construct, so nothing counted them — and nothing
// anywhere compared the declared number to the script. The hook made a count
// MANDATORY without making it TRUE.
//
// The test is the same one as gate B, applied to iteration instead of fan-out:
// **can a reader count this before it runs?** A literal array, a numeric bound,
// an explicit .slice(0, N) — yes. A variable, a condition, runtime data — no,
// and "no" is what the 54 agents were.
//
// ⚠ This fires ONLY when the body actually calls agent(). A loop that does
// anything else is not this gate's business: a guard that goes off on
// legitimate code is a guard somebody turns off, and then there is no guard.
//
// ⛔ It fires regardless of Nick's approval note, and BEFORE gate C reads one,
// on purpose: **an approval approves a NUMBER, and an uncountable shape has no
// number to approve.** Approving five and running 54 is the whole incident.

// The index of the bracket closing the one that opens at openIdx, or -1.
// Unbalanced (or a bracket inside a string) returns -1, which this gate reads
// as "cannot be determined" and therefore refuses — the safe direction.
const matchBracket = (src, openIdx) => {
  const close = { '(': ')', '[': ']', '{': '}' }[src[openIdx]]
  const open = src[openIdx]
  let depth = 0
  for (let i = openIdx; i < src.length; i++) {
    if (src[i] === open) depth++
    else if (src[i] === close && --depth === 0) return i
  }
  return -1
}

// How many times this header runs, or null when a reader cannot tell.
// Deliberately generous about SHAPE and strict about COUNTABILITY: every form
// the authoring guide recommends is countable, and nothing else is.
const iterations = (header) => {
  const flat = header.replace(/\s+/g, ' ')

  // for (const d of [a, b, c])  — the array is right there
  const inline = flat.indexOf('[')
  if (/\bof\b/.test(flat) && inline !== -1) return countLiteral(flat, inline)

  // .slice(0, N) and Array.from({length: N}) — the author wrote the cap down
  const sliced = flat.match(/\.slice\(\s*0\s*,\s*(\d+)\s*\)/)
  if (sliced) return Number(sliced[1])
  const fromLen = flat.match(/Array\.from\(\s*\{\s*length:\s*(\d+)/)
  if (fromLen) return Number(fromLen[1])

  // for (let i = 0; i < 3; i++)  — a literal bound. `<=` is one more than it
  // looks, and an off-by-one in a cap is a cap that is wrong.
  const lt = flat.match(/<(=?)\s*(\d+)\b/)
  if (lt) return Number(lt[2]) + (lt[1] ? 1 : 0)

  // for (const d of DIMENSIONS) — countable only if DIMENSIONS is a literal
  // array declared in this same script.
  const over = flat.match(/\bof\s+([A-Za-z_$][\w$]*)/)
  if (over && litLens.has(over[1])) return litLens.get(over[1])

  return null                      // a variable, a condition, runtime data
}

const loopOffenders = []
const say = (what, n) =>
  n === null
    ? `${what} calls agent() and nothing says how many times it runs`
    : `${what} calls agent() ${n} times, over ${CAP}`

// ── loops: for, while, do ────────────────────────────────────────────────────
for (const m of script.matchAll(/\b(for|while|do)\b/g)) {
  const kind = m[1]
  let bodyStart

  if (kind === 'do') {
    bodyStart = script.indexOf('{', m.index)
  } else {
    const headOpen = script.indexOf('(', m.index)
    if (headOpen === -1) continue
    const headClose = matchBracket(script, headOpen)
    if (headClose === -1) { loopOffenders.push(say(`a ${kind} loop`, null)); continue }
    bodyStart = headClose + 1
  }
  if (bodyStart === -1 || bodyStart === 0) continue

  // The body: a braced block, or a single statement up to the next ';'.
  let j = bodyStart
  while (j < script.length && /\s/.test(script[j])) j++
  let body
  if (script[j] === '{') {
    const end = matchBracket(script, j)
    body = end === -1 ? script.slice(j) : script.slice(j, end)
  } else {
    const semi = script.indexOf(';', j)
    body = script.slice(j, semi === -1 ? script.length : semi)
  }

  if (!/\bagent\s*\(/.test(body)) continue          // not this gate's business

  // `while` and `do` have no count by construction — a condition is not a
  // number, however small it usually turns out to be.
  const n = kind === 'for'
    ? iterations(script.slice(script.indexOf('(', m.index), bodyStart))
    : null
  if (n === null || n > CAP) loopOffenders.push(say(`a ${kind} loop`, n))
}

// ── the same shape spelled as a callback: xs.map(x => agent(x)) ──────────────
// Gate B only sees these inside parallel()/pipeline(). Promise.all(xs.map(…))
// is the identical thing with a different wrapper, and it was invisible too.
for (const m of script.matchAll(/\.(map|forEach|flatMap)\s*\(/g)) {
  const open = script.indexOf('(', m.index)
  const close = matchBracket(script, open)
  const body = close === -1 ? script.slice(open) : script.slice(open, close)
  if (!/\bagent\s*\(/.test(body)) continue

  // What is being mapped OVER: the text to the left of the dot.
  const before = script.slice(Math.max(0, m.index - 160), m.index)
  let n = null
  const sliced = before.match(/\.slice\(\s*0\s*,\s*(\d+)\s*\)\s*$/)
  const fromLen = before.match(/Array\.from\(\s*\{\s*length:\s*(\d+)[\s\S]*$/)
  const ident = before.match(/([A-Za-z_$][\w$]*)\s*$/)
  if (sliced) n = Number(sliced[1])
  else if (before.trimEnd().endsWith(']')) {
    const openArr = before.lastIndexOf('[')
    if (openArr !== -1) n = countLiteral(before, openArr)
  } else if (fromLen) n = Number(fromLen[1])
  else if (ident && litLens.has(ident[1])) n = litLens.get(ident[1])

  if (n === null || n > CAP) loopOffenders.push(say(`.${m[1]}(...)`, n))
}

if (loopOffenders.length) {
  deny(`RULE #16 — Workflow BLOCKED: agent() in an uncountable loop (${origin}).

${[...new Set(loopOffenders)].map((o) => '  * ' + o).join('\n')}

A cap you cannot count BEFORE you launch is not a cap. Write the bound into the code:

    for (const d of DIMENSIONS)        // a literal array declared above, <= ${CAP} items
    for (let i = 0; i < 3; i++)        // a number, not a variable
    ranked.slice(0, ${CAP}).map(...)          // rank first, then cap the list

A loop that runs until something is "dry" or until a budget is spent can exceed ${CAP},
so it is over the cap by construction: STOP, tell Nick the worst case and why.
His one-shot note does NOT open this shape — a note approves a NUMBER, and this has
none. If he agrees to more, write it as rounds a reader can count (each <= ${CAP}),
declare the total in MAX_AGENTS, and launch THAT on his note.`)
  // ⚠ This text used to end "launch it on his one-shot note — the same road as
  // any other number above 5", while this gate fires before gate C reads a
  // note and refuses even with one (the test asserts it). The refusal promised
  // a road the code had closed. Found while promoting this file, 2026-10-20.
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
