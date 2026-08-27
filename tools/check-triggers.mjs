#!/usr/bin/env node
/**
 * check-triggers.mjs — the guard that pins the trigger-script decisions.
 *
 * v2, 2026-08-27 — rebuilt after reviver #26 round 3 took v1 apart. Three firms, 33 findings,
 * and the honest summary was firm B's: *"the tool built to prevent sibling misses has no ability
 * to check sibling sets at all — fix the SHAPE of the guard, not one point at a time."*
 *
 * WHAT V1 GOT WRONG (all proven by running it, not argued):
 *   1. It stripped only whole-line `//` comments, so deleting a guard and leaving it as a
 *      TRAILING comment or inside a `/* *\/` block kept the check GREEN — the most natural way a
 *      person removes code was the one way past it.
 *   2. `bashGranted` was `/Bash/.test(src)`. tester.js mentions "Bash" in prose too, so the check
 *      could never go red for the very file it was written for.
 *   3. Its "proven red" self-test fired predicates at hand-written snippets. A snippet can be
 *      written to fail. That proves the snippet is broken, not that the check protects the REAL file.
 *   4. It wrote temp files into the source directory while advertising itself as read-only.
 *
 * WHAT V2 DOES INSTEAD:
 *   • `stripComments()` is a real scanner: it removes `//` to end-of-line and `/* … *\/` blocks
 *     while KEEPING string and template-literal contents (prompt text must survive — that is where
 *     the grants live). Known limit: a regex literal containing `//` would confuse it; none exists
 *     in these files and `syntax` would catch the fallout.
 *   • MUTATION-BASED RED PROOF. Every check is fired at the REAL file with its guard surgically
 *     removed. If the mutation cannot find what to remove, the check is reported STALE — its anchor
 *     drifted and it is now green for a reason nobody chose.
 *   • SIBLING RULES. A rule states a property and DERIVES the set of files it must hold across
 *     (e.g. "every script that grants Bash must carry the import warning"). It names the missing
 *     member. This is the class of defect that produced 9 findings in one day; a per-file check
 *     cannot see it, because each file is individually fine.
 *   • Temp files go to the OS temp dir.
 *
 * STILL NOT A BEHAVIOURAL TEST. These are text properties. Green means "the decision is still
 * written down and still reachable", never "the behaviour is correct". Two pieces of real logic
 * (samePath, dimLetterOf) are unit-tested at the bottom against COPIES of their source — copies,
 * because importing the module would execute it (PROCEDURE 8.4).
 *
 * USAGE:  node check-triggers.mjs           node check-triggers.mjs --quiet
 * Run after ANY edit to the scripts, and before syncing them to the repos (#19/#22).
 */

import fs from 'fs'
import os from 'os'
import path from 'path'
import { fileURLToPath } from 'url'
import { execFileSync } from 'child_process'

const DIR = path.dirname(fileURLToPath(import.meta.url))
const QUIET = process.argv.includes('--quiet')
const say = s => { if (!QUIET) console.log(s) }
let failed = 0, passed = 0
const fail = m => { console.log('  ✗ ' + m); failed++ }
const ok = m => { passed++; say('  ✓ ' + m) }

const REVIEW = ['tester.js', 'supertester.js', 'supertester-security.js', 'reviver.js']
const ALL = [...REVIEW, 'lucifer.js']
const ROUNDS = ['supertester.js', 'supertester-security.js']
const read = f => fs.readFileSync(path.join(DIR, f), 'utf8')

/** remove real comments, keep string/template contents (that is where the prompts live) */
export function stripComments(src) {
  let out = '', i = 0, mode = null
  while (i < src.length) {
    const c = src[i], d = src[i + 1]
    if (mode === null) {
      if (c === '/' && d === '/') { mode = 'line'; i += 2; continue }
      if (c === '/' && d === '*') { mode = 'block'; i += 2; continue }
      if (c === "'" || c === '"' || c === '`') { mode = c; out += c; i++; continue }
      out += c; i++; continue
    }
    if (mode === 'line') { if (c === '\n') { mode = null; out += c } i++; continue }
    if (mode === 'block') { if (c === '*' && d === '/') { mode = null; i += 2 } else i++; continue }
    if (c === '\\') { out += c + (d ?? ''); i += 2; continue }        // escape inside a string
    if (c === mode) { mode = null; out += c; i++; continue }
    out += c; i++
  }
  return out
}

// ── per-file checks. `has` runs on stripped code · `mutate` removes the guard from the REAL file ──
const CHECKS = [
  { id: 'args guard', files: ALL,
    why: 'args JSON-string guard (60-agent burn 2026-06-13)',
    has: c => /typeof _A === 'string'/.test(c),
    mutate: s => s.replace(/typeof _A === 'string'/, "typeof _A === 'STRINGY'") },

  { id: 'no clock/random', files: ALL,
    why: 'Date.now()/Math.random() throw inside a workflow script',
    has: c => !/Date\.now\(\)|Math\.random\(\)|new Date\(\)/.test(c),
    mutate: s => s.replace(/const _A = args|let _A = args/, 'let _A = args; const _t = Date.now()') },

  { id: 'agentsUsed is real', files: REVIEW,
    why: 'must report the count that ANSWERED, not the count launched',
    has: c => /agentsUsed:\s*reports\.length/.test(c),
    mutate: s => s.replace(/agentsUsed:\s*reports\.length/g, 'agentsUsed: FIRMS.length') },

  { id: 'notCovered required', files: REVIEW,
    why: 'undeclared scope-cutting reads as a complete review',
    has: c => /required:\s*\[[^\]]*'notCovered'/.test(c),
    mutate: s => s.replace(/,\s*'notCovered'/, '') },

  { id: 'no silent round fallback', files: ROUNDS,
    why: 'ROUNDS[round] || ROUNDS[1] runs round 1 while telling the agent it is round 4',
    has: c => !/\|\|\s*ROUND(S|_FOCUS)\[1\]/.test(c),
    mutate: s => s.replace(/const (R|RF) = ROUND(S|_FOCUS)\[round\]/, 'const $1 = ROUND$2[round] || ROUND$2[1]') },

  { id: 'no Number()||1 coercion', files: ROUNDS,
    why: 'swallows 0 / "" / NaN into round 1',
    has: c => !/Number\(\s*_A\.round\s*\)\s*\|\|/.test(c),
    mutate: s => s.replace(/const round = \(_rawRound[^\n]*/, 'const round = Number(_A.round) || 1') },

  { id: 'scope required r2-3', files: ROUNDS,
    why: 'the verify lens would guess what the previous round fixed',
    has: c => /round\s*>=\s*2\s*&&\s*!scope/.test(c),
    mutate: s => s.replace(/round\s*>=\s*2\s*&&\s*!scope/, 'false') },

  { id: 'round-3 title states no assumption', files: ['supertester-security.js'],
    why: 'the title told the agent to ASSUME while the body forbade it',
    has: c => !/สมมติ Coddy แก้/.test(c),
    mutate: s => s.replace(/3: \{ name:'[^']*'/, "3: { name:'ปิดจ็อบ (สมมติ Coddy แก้ R1–R2 ไปแล้ว)'") },

  { id: 'target .toString()', files: ['reviver.js'],
    why: 'a non-string target throws TypeError before any agent starts',
    has: c => /_A\.target\s*\|\|\s*''\)\.toString\(\)/.test(c),
    mutate: s => s.replace(/\(_A\.target \|\| ''\)\.toString\(\)/, "(_A.target || '')") },

  { id: 'agreement counts firms', files: ['reviver.js'],
    why: 'printed "all 3 firms agreed" from a sample of one (seen live)',
    has: c => /nums\.length\s*===\s*1/.test(c),
    mutate: s => s.replace(/nums\.length === 1/, 'false') },

  { id: 'intent counts firms', files: ['reviver.js'],
    why: 'three silences read as unanimity once intent became optional',
    has: c => /statedIntents/.test(c),
    // ⚠️ ต้องเป็น /g และเปลี่ยน "ทุกที่": ลบแค่บรรทัดประกาศ ชื่อยังโผล่ที่อื่น การ์ดเลยยังเขียว
    // (mutation red-proof จับข้อนี้ได้เอง 2026-08-27 — ซึ่งคือเหตุผลที่ v2 ใช้ mutation แทน snippet)
    mutate: s => s.replace(/statedIntents/g, '_gone') },

  { id: 'dimension flag counts firms', files: ['reviver.js'],
    why: 'one firm scoring a dimension printed ✅ agreement',
    has: c => /ns\.length\s*===\s*1\s*\?/.test(c),
    mutate: s => s.replace(/ns\.length === 1 \?/, 'false ?') },

  { id: 'next STOPs when degraded', files: ['reviver.js'],
    why: 'the instruction channel must flip, not just a warning field',
    has: c => /next:\s*\(reports\.length\s*<\s*2/.test(c),
    mutate: s => s.replace(/next: \(reports\.length < 2/, 'next: (false') },

  { id: 'path tail matching', files: ['reviver.js'],
    why: 'absolute vs relative citations stopped pairing, sinking corroborated',
    has: c => /const samePath/.test(c),
    mutate: s => s.replace(/const samePath = /, 'const _unusedSamePath = ') },

  { id: 'dimension by letter', files: ['reviver.js'],
    why: 'charAt(0) put Correctness (A) and Consistency (H) in bucket C',
    has: c => /dimLetterOf\(d\.dimension\)/.test(c),
    mutate: s => s.replace(/dimLetterOf\(d\.dimension\)/, 'String(d.dimension).charAt(0)') },

  { id: 'schema required <= 10', files: ['reviver.js'],
    why: '21 required fields made 2 of 3 firms fail StructuredOutput 5x',
    has: c => { const m = c.match(/required:\s*\[([^\]]*)\]/); return m ? (m[1].match(/'/g) || []).length / 2 <= 10 : false },
    mutate: s => s.replace(/required:\['verdictSummary'/, "required:['a','b','c','d','e','f','g','h','i','j','k','verdictSummary'") },

  { id: 'partial panel stops', files: ['lucifer.js'],
    why: 'one surviving reviewer could certify a Play upload (BLOCKER)',
    has: c => /scored\.length\s*<\s*LENS\.length/.test(c),
    mutate: s => s.replace(/scored\.length < LENS\.length/, '!scored.length') },

  { id: 'dedupe keeps whole problem', files: ['lucifer.js'],
    why: 'an 80-char key collapsed distinct issues that open the same way',
    has: c => !/problem\)\.slice\(\s*0\s*,\s*\d+\s*\)/.test(c),
    mutate: s => s.replace(/String\(x\.problem\)\.toLowerCase\(\)\.replace\(\/\\s\+\/g, ' '\)\.trim\(\)/, 'String(x.problem).slice(0, 80)') },

  { id: 'all reviewers feed back', files: ['lucifer.js'],
    why: 'round 2 saw only the lowest scorer, so the other two re-filed and failed the last gate',
    has: c => /allIssues/.test(c),
    mutate: s => s.replace(/allIssues/g, '_gone') },
]

// ── SIBLING RULES: the property states its own file set. This is the check v1 could not express. ──
const SIBLING_RULES = [
  { id: 'every review script grants read-only Bash',
    set: () => REVIEW,
    holds: c => /Bash แบบอ่านอย่างเดียว|Bash อ่านอย่างเดียว/.test(c),
    why: 'PROCEDURE 8.4 ("run the thing") is unreachable without it' },

  { id: 'every script that grants Bash carries the import warning',
    // the set is DERIVED, so adding a Bash grant to a new script automatically extends the rule
    set: files => files.filter(f => /Bash แบบอ่านอย่างเดียว|Bash อ่านอย่างเดียว/.test(stripComments(read(f)))),
    holds: c => /top-level/.test(c),
    why: 'import executes a module; without the warning a "read-only" agent can change state' },

  { id: 'every review script reports the real agent count',
    set: () => REVIEW,
    holds: c => /agentsUsed:\s*reports\.length/.test(c),
    why: 'a degraded run must not read as a complete one' },

  { id: 'every review script has a degraded STOP path',
    set: () => REVIEW,
    holds: c => /STOP \(#16\)/.test(c),
    why: 'recording the degradation without acting on it changes nothing' },
]

// ───────────────────────── run ─────────────────────────
say('── per-file guards (with mutation red-proof) ──')
for (const chk of CHECKS) {
  for (const f of chk.files) {
    const p = path.join(DIR, f)
    if (!fs.existsSync(p)) { fail(`${chk.id} · ${f} — FILE MISSING`); continue }
    const raw = fs.readFileSync(p, 'utf8')
    if (!chk.has(stripComments(raw))) { fail(`${chk.id} · ${f} — ${chk.why}`); continue }
    const mutated = chk.mutate(raw)
    if (mutated === raw) { fail(`${chk.id} · ${f} — STALE: the mutation found nothing to remove, so this check is green for an unknown reason`); continue }
    if (chk.has(stripComments(mutated))) { fail(`${chk.id} · ${f} — GREEN ON THE BROKEN FILE (worse than no check)`); continue }
    ok(`${chk.id} · ${f}  [red-proven on the real file]`)
  }
}

say('\n── sibling rules (a property + the set it must hold across) ──')
for (const r of SIBLING_RULES) {
  const set = r.set(ALL)
  if (!set.length) { fail(`${r.id} — the set came out empty; the rule cannot hold over nothing`); continue }
  const missing = set.filter(f => !r.holds(stripComments(read(f))))
  if (missing.length) fail(`${r.id} — missing in ${missing.join(', ')}  (set: ${set.join(', ')}) — ${r.why}`)
  else ok(`${r.id} — holds across all ${set.length}: ${set.join(', ')}`)
}

say('\n── syntax (wrapped; these run inside an async wrapper) ──')
for (const f of ALL) {
  const tmp = path.join(os.tmpdir(), `chk_${process.pid}_${f}`)   // OS temp, never the source dir
  try {
    const body = read(f).replace(/^export const meta/m, 'const meta')
    fs.writeFileSync(tmp, `async function __w(args, agent, parallel, log, phase){\n${body}\n}\n`, 'utf8')
    execFileSync(process.execPath, ['--check', tmp], { stdio: 'pipe' })
    ok(`${f}`)
  } catch (e) { fail(`${f} — ${String(e.stderr || e.message).split('\n').slice(0, 2).join(' ')}`) }
  finally { try { fs.unlinkSync(tmp) } catch {} }
}

say('\n── docs ──')
for (const [file, re, want, why] of [
  ['command_pattern.md', /Unlimited tokens\/agents for this triggered flow only/, false, '#12 promises unlimited AGENTS (contradicts #16)'],
  ['command_pattern.md', /3 consecutive `waiting` ticks/, true, '#25 has no escape from a permanent waiting state'],
  ['nick-master-workflow.md', /≤10 total/, true, "the brief omits Lucifer's ≤10-total cap"],
  ['nick-master-workflow.md', /3 consecutive `waiting` ticks/, true, 'the brief lacks the waiting escape'],
  ['CODE_REVIEW_PROCEDURE.md', /`import` is not read-only/, true, '8.4 shows the unsafe import example'],
]) {
  const p = path.join(DIR, file)
  const present = fs.existsSync(p) && re.test(fs.readFileSync(p, 'utf8'))
  present === want ? ok(`${file} · ${why}`) : fail(`${file} — ${why}`)
}

// ── unit tests against the LIVE source, not a copy ──────────────────────────────────────
// reviver #26 round 3 (firm A): v2 pasted copies of samePath/dimLetterOf in here, so editing the
// REAL ones in reviver.js left these tests green — a guard passing for a reason nobody chose, which
// is the defect this whole file exists to stop. Now the function text is lifted out of reviver.js at
// run time and executed. Not `import`: importing reviver.js would EXECUTE it (PROCEDURE 8.4).
// If extraction fails the check goes RED — an untestable function must not read as a tested one.
function liveFn(file, name, deps = '') {
  const src = read(file)
  const start = src.indexOf(`const ${name} = `)
  if (start < 0) throw new Error(`no "const ${name} = " in ${file}`)
  const arrow = src.indexOf('=>', start)
  if (arrow < 0) throw new Error(`${name} is not an arrow function`)
  let j = arrow + 2
  while (/\s/.test(src[j])) j++
  if (src[j] === '{') {                       // block body: walk to the matching brace
    let depth = 0
    for (; j < src.length; j++) {
      if (src[j] === '{') depth++
      else if (src[j] === '}') { depth--; if (depth === 0) { j++; break } }
    }
  } else {                                    // single-expression body: to end of line
    j = src.indexOf('\n', j)
  }
  return new Function(`${deps}\n${src.slice(start, j)}\nreturn ${name}`)()
}

say('\n── unit: samePath / dimLetterOf (LIVE source lifted from reviver.js) ──')
let samePath, dimLetterOf
try {
  samePath = liveFn('reviver.js', 'samePath')
  dimLetterOf = liveFn('reviver.js', 'dimLetterOf', "const DIM_LETTERS = 'ABCDEFGHIJ'")
  ok('lifted samePath + dimLetterOf out of reviver.js (editing them there now breaks these tests)')
} catch (e) {
  fail(`could not lift the live functions out of reviver.js — ${e.message}. These tests are NOT running.`)
  samePath = () => 'EXTRACTION-FAILED'
  dimLetterOf = () => 'EXTRACTION-FAILED'
}
for (const [n, got, want] of [
  ['samePath abs/rel', samePath('c:/u/nick/reviver.js', 'reviver.js'), true],
  ['samePath not a substring', samePath('myreviver.js', 'reviver.js'), false],
  ['samePath different dirs stay apart', samePath('src/core/store.py', 'lib/other/store.py'), false],
  ['samePath empty', samePath('', 'x'), false],
  ['dim (A) suffix', dimLetterOf('Correctness (A)'), 'A'],
  ['dim (H) not C', dimLetterOf('Consistency (H)'), 'H'],
  ['dim leading letter', dimLetterOf('A — ความถูกต้อง'), 'A'],
  ['dim unparseable', dimLetterOf('ความถูกต้อง'), null],
]) got === want ? ok(n) : fail(`${n} — got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`)

say('\n── self-check: does stripComments actually strip? ──')
for (const [n, src, shouldSurvive] of [
  ['trailing // comment', 'const x = 1  // scored.length < LENS.length', false],
  ['block comment', '/* scored.length < LENS.length */\nconst x = 1', false],
  ['whole-line comment', '// scored.length < LENS.length\nconst x = 1', false],
  ['inside a string (prompt text must survive)', 'const p = `ใช้ Bash แบบอ่านอย่างเดียว`', true],
  ['url in a string is not a comment', 'const u = "https://x.dev/a"', true],
]) {
  const stripped = stripComments(src)
  const survived = /scored\.length < LENS\.length|Bash แบบอ่านอย่างเดียว|https:/.test(stripped)
  survived === shouldSurvive ? ok(n) : fail(`stripComments · ${n} — survived=${survived}, expected ${shouldSurvive}`)
}

console.log(`\n${failed ? '❌' : '✅'}  ${passed} passed, ${failed} failed`)
console.log('   Text properties only: green = the decision is still written and reachable, not that the behaviour is right.')
process.exit(failed ? 1 : 0)
