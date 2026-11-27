#!/usr/bin/env node
// repeat-mistakes-hook.mjs - command_pattern #29 (Nick, 2026-11-28): the ledger of mistakes that RECUR is put in
// front of every session, instead of relying on the session to go and read it.
//
// Why a hook and not a line in CLAUDE.md: SM measured it on 2026-09-22 - eleven of its 157 memory files recorded a
// repeat that happened AFTER the lesson was written down. "Read X at session start" is a reminder, and a reminder
// works only while somebody remembers it. #7 rotates bug/ files to _trash/ and #8 forbids reading _trash/, so a bug
// that came back three months later had already left the only place it was written.
//
// Registered as a SessionStart hook in every repo's .claude/settings.json (merged by sync-rules-to-projects.ps1),
// so a cloud session gets it too. Claude Code adds a SessionStart hook's stdout to the session's context.
//
// What it prints: memory/REPEAT_MISTAKES.md up to its `## Closed` heading (closed rows stay in the file, never
// deleted, and cost no context), capped at MAX_BYTES. Warnings for a missing file, a ledger over MAX_ROWS active
// rows, or a ledger over the size cap. It NEVER blocks and always exits 0: a session must start even when the
// ledger is broken - the warning is the signal, and a failing start hook would be a worse outage than the gap.
// No stdin read: SessionStart sends JSON we do not need, and an unread pipe does not hang a process that exits.
import fs from 'node:fs'
import path from 'node:path'

export const MAX_ROWS = 20
export const MAX_BYTES = 12000
const CLOSED = /^##\s+Closed\b/m
const ROW = /^\|\s*\d+\s*\|/gm

export function render(root) {
  const file = path.join(root, 'memory', 'REPEAT_MISTAKES.md')
  let text
  try { text = fs.readFileSync(file, 'utf8').replace(/^﻿/, '') }
  catch {
    return '[#29 REPEAT_MISTAKES] This repo has no memory/REPEAT_MISTAKES.md. The FIRST time a mistake or bug ' +
      'happens a second time, create it from the house template (sync-rules-to-projects.ps1 seeds it) and add the row.'
  }
  const m = CLOSED.exec(text)
  let active = (m ? text.slice(0, m.index) : text).trimEnd()
  const rows = (active.match(ROW) || []).length
  const notes = []
  if (rows > MAX_ROWS) notes.push(`${rows} active rows - over the #29 cap of ${MAX_ROWS}. Move rows whose mechanism has held to "## Closed" (never delete) or merge rows of one class.`)
  if (Buffer.byteLength(active, 'utf8') > MAX_BYTES) {
    active = Buffer.from(active, 'utf8').subarray(0, MAX_BYTES).toString('utf8').replace(/�$/, '')
    notes.push(`TRUNCATED at ${MAX_BYTES} bytes - the active part of the ledger is over the #29 size cap. Shorten rows; details belong in memory topic files.`)
  }
  const head = '[#29 REPEAT_MISTAKES - injected at session start by tools/repeat-mistakes-hook.mjs. These mistakes ' +
    'have happened MORE THAN ONCE in this repo. Before a task, name in your plan every row whose "when it strikes" ' +
    'it touches. After a repeat: bump the count and date in this file in the same session.]'
  return [head, '', active, ...(notes.length ? ['', ...notes.map(n => '[#29 WARN] ' + n)] : [])].join('\n')
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'))
if (isMain) {
  try { process.stdout.write(render(process.env.CLAUDE_PROJECT_DIR || process.cwd()) + '\n') }
  catch (e) { process.stdout.write('[#29 REPEAT_MISTAKES] hook error, ledger not shown: ' + (e && e.message) + '\n') }
  process.exit(0)
}
