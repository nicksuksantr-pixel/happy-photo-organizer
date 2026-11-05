#!/usr/bin/env node
// records-quota-check.mjs - enforcement of house rule #7: 20 entries per file, 2 files per category.
//
// WHY THIS FILE EXISTS
// Ena's chat log went over its quota three times: 53 entries (Bug 13), 21 (Bug 20), 24 (Bug 26, 2026-11-05).
// After Bug 13 every chat file opened with "Count before you write", and it did not stop Bugs 20 or 26: a
// reading rule only helps when someone remembers to read it. Nick, the same day: build the automatic check.
// Ena wrote it (v0.107, 56cefdf); the Director ran it against all 15 repos and found it blind in nine of them
// (the house has six entry-heading formats, and a count of zero read as "within quota"), and five repos over
// quota on day one, the Director's own chat log among them (63 entries). Nick, 2026-11-05: ship it house-wide
// through the master, #7 stands as written (two rolling files of 20, one-file-per-version logs consolidate).
//
// WHAT IT DOES
// As a PreToolUse hook on Bash/PowerShell it reads the command about to run. If the command runs
// `git ... commit`, it counts the records of the repo that commit lands in (`git -C <dir>`, `cd <dir> &&`, else
// the project folder) and refuses (exit 2) while any of these holds a file over 20 entries, or more than 2 files:
//   chat_log/chat_*.md   log/log_*.md   bug/bug_*.md   changelog/changelog_*.md
// A file is part of the rotating series only when its name is the stem + `_` and carries a digit (tidy.mjs's
// definition): `log/rnd_director_log.md`, `bug/README.md`, `log/reviver_2026-08-27.md` are one-offs, left alone.
// An entry is a heading in one of the formats the house actually uses (see ENTRY below); the standard going
// forward is `## Entry N - date - title` / `## Bug N - ...`. A series file in which NOTHING is countable is a
// WARNING, never a pass: the quota cannot be checked there, and silence would read as "within quota".
// V-Log.md is one timeline file (#11), not a rotating record, so it is not counted.
// As a CLI:   node tools/records-quota-check.mjs --check [--root <dir>]   prints the counts; exit 1 if over.
//
// There is no flag past it: the way through is the rotation itself (split at the 20-entry boundary, oldest file
// to _trash/old_records/), after which the same commit passes. If the check cannot run, it says so on stderr
// and lets the command through (exit 1 = non-blocking), like the other hooks here.

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const MAX_ENTRIES = 20
export const MAX_FILES = 2
// name = stem + `_` + anything with a digit + `.md` (tidy.mjs SERIES, #7: "file names carry version or sequence")
export const CATEGORIES = [
  { dir: 'chat_log', file: /^chat_(?=.*\d).*\.md$/i },
  { dir: 'log', file: /^log_(?=.*\d).*\.md$/i },
  { dir: 'bug', file: /^bug_(?=.*\d).*\.md$/i },
  { dir: 'changelog', file: /^changelog_(?=.*\d).*\.md$/i },
]
// The entry headings in use across the house on 2026-11-05 (one line each, at the start of a line):
//   ## Entry 12 - ...   ## Bug 3 - ...        the standard (Director, Ena, LTB, MyDocs, PLC, HPO chat)
//   ## 81 - 2026-10-30  ## 1 · 2026-06-11     number first (JS, NTWL, ASI)
//   ## 2026-10-31 ...                         date first (EMR, HAT, SM, TTVC)
//   ## v1.058 - ...                           version first (HPO log)
//   ## B1 - ...  ## BUG-016 ...  ## BUG 1 ...  bug ids (TTVC, MyDocs, JS, HAT, HPO bug)
//   ### Session 2 - ...                       NTWL log
//   - **2026-11-02 (Coddy, NP): ...**         NP chat (bullet entries, no heading; a time may follow the date -
//                                             `- **2026-11-04 15:07-17:1x (` - NP found 10 of 13 uncounted on 2026-11-05)
export const ENTRY = /^(?:## (?:Entry|Bug) \d+|## \d+\s*[\u2014\u2013\u00b7-]|## \d{4}-\d{2}-\d{2}|## v\d|## (?:B|BUG)[- ]?\d+|### Session \d+|- \*\*\d{4}-\d{2}-\d{2}\b)/gm

/** Counts per series file, every breach of the quota as a sentence, every file where nothing could be counted, and the
 *  .md files that sit in a record folder OUTSIDE the series (never counted - reported by --check so a dodge is visible). */
export function audit(root) {
  const counts = []; const problems = []; const warnings = []; const outside = []
  for (const c of CATEGORIES) {
    const dir = path.join(root, c.dir)
    if (!fs.existsSync(dir)) continue
    const all = fs.readdirSync(dir).filter((n) => /\.md$/i.test(n) && !n.startsWith('.'))
    const files = all.filter((n) => c.file.test(n)).sort()
    for (const n of all) if (!c.file.test(n)) outside.push(`${c.dir}/${n}`)
    for (const n of files) {
      const text = fs.readFileSync(path.join(dir, n), 'utf8')
      const entries = (text.match(ENTRY) || []).length
      counts.push({ file: `${c.dir}/${n}`, entries })
      if (entries > MAX_ENTRIES) problems.push(`${c.dir}/${n} holds ${entries} entries (max ${MAX_ENTRIES})`)
      if (entries === 0 && text.trim()) warnings.push(`${c.dir}/${n}: no countable entry heading, so its quota is NOT checked - write entries as \`## Entry N - date - title\` (or \`## Bug N - ...\`), one heading per entry`)
    }
    if (files.length > MAX_FILES) problems.push(`${c.dir}/ holds ${files.length} files (keep ${MAX_FILES}): ${files.join(', ')}`)
  }
  return { counts, problems, warnings, outside }
}

const HOW = [
  'Fix (#7), then commit again:',
  '  - a file over 20: keep the newest 20 entries in it; the older ones go, unchanged, into a file under',
  '    _trash/old_records/ (move, never delete; the two parts must rejoin byte for byte);',
  '  - more than 2 files: the oldest files move to _trash/old_records/ until 2 remain; one-file-per-version logs',
  '    are consolidated into rolling files of 20 entries named by the version they start at (Nick, 2026-11-05).',
  'Precedents: Ena Bugs 13, 20 and 26.',
].join('\n')

/** Where each `git ... commit` in this command lands: the segment's own `git -C <dir>`, else the last `cd <dir>` before
 *  it, else the project. Only segments that commit are read - a `git -C <other> status` on the same line is not a commit
 *  there (the Director's first batch was refused on exactly that, 2026-11-05). */
export function commitRoots(cmd, fallback, cwd) {
  const fix = (p) => {
    p = p.replace(/^["']|["']$/g, '')
    if (/^\/[a-zA-Z]\//.test(p)) p = p[1].toUpperCase() + ':' + p.slice(2)     // Git Bash /c/Users -> C:/Users
    return path.resolve(cwd || fallback, p)
  }
  const roots = new Set(); let cur = null
  for (const seg of cmd.split(/&&|\|\||;|\||\n/)) {
    const cd = /^\s*cd\s+("[^"]+"|'[^']+'|\S+)/.exec(seg)
    if (cd) { cur = fix(cd[1]); continue }
    if (!/\bgit\b[\s\S]*\bcommit\b/.test(seg)) continue
    const m = /\bgit\s+(?:-c\s+\S+\s+)*-C\s+("[^"]+"|'[^']+'|\S+)/.exec(seg)
    roots.add(m ? fix(m[1]) : (cur || path.resolve(fallback)))
  }
  if (!roots.size) roots.add(path.resolve(fallback))
  return [...roots]
}

const isMain = !!process.argv[1] && path.resolve(process.argv[1]).toLowerCase() === fileURLToPath(import.meta.url).toLowerCase()
if (isMain) {
  const args = process.argv.slice(2)
  if (args[0] === '--check') {
    const i = args.indexOf('--root')
    const root = i >= 0 && args[i + 1] ? args[i + 1] : (process.env.CLAUDE_PROJECT_DIR || process.cwd())
    const { counts, problems, warnings, outside } = audit(root)
    for (const c of counts) console.log(`${String(c.entries).padStart(3)}  ${c.file}`)
    if (outside.length) console.log(`note ${outside.length} file(s) in a record folder sit outside the rotating series (stem_ + a digit) and are not counted: ${outside.join(', ')}`)
    for (const w of warnings) console.error(`WARN ${w}`)
    if (problems.length) { console.error(`records over quota:\n${problems.map((p) => ' - ' + p).join('\n')}\n${HOW}`); process.exit(1) }
    console.log(`records-quota-check: every record file is within quota${warnings.length ? ` (${warnings.length} file(s) could not be counted - see WARN)` : ''}`); process.exit(0)
  }
  // hook mode
  let hook = {}
  try { hook = JSON.parse(fs.readFileSync(0, 'utf8') || '{}') } catch { process.exit(0) }
  if (!['Bash', 'PowerShell'].includes(hook.tool_name)) process.exit(0)
  const cmd = String(hook.tool_input?.command || '')
  if (!/\bgit\b[^|;&\n]*\bcommit\b/.test(cmd)) process.exit(0)              // only a command that commits
  const fallback = process.env.CLAUDE_PROJECT_DIR || hook.cwd || process.cwd()
  const problems = []; const warnings = []
  try {
    for (const root of commitRoots(cmd, fallback, hook.cwd)) {
      if (!fs.existsSync(root)) continue
      const r = audit(root)
      const tag = (s) => (root === path.resolve(fallback) ? s : `${root}: ${s}`)
      problems.push(...r.problems.map(tag)); warnings.push(...r.warnings.map(tag))
    }
  } catch (e) {
    process.stderr.write(`records-quota-check could not run (${e.message}); the commit is let through. Run \`node tools/records-quota-check.mjs --check\` by hand.\n`)
    process.exit(1)
  }
  if (problems.length) {
    process.stderr.write(`records-quota-check: commit refused, records over quota (#7):\n${problems.map((p) => ' - ' + p).join('\n')}\n${HOW}\n`)
    process.exit(2)
  }
  if (warnings.length) { process.stderr.write(`records-quota-check: ${warnings.map((w) => 'WARN ' + w).join('\n')}\n`); process.exit(1) }   // visible, not blocking
  process.exit(0)
}
