#!/usr/bin/env node
// disk-space-hook.mjs - command_pattern #29.1 (Nick, 2026-11-28): a SessionStart hook that warns EVERY session,
// in every repo, when the project's disk runs low - and names what is eating it.
//
// Why: C: filled five times (2026-08-17, 09-26, 11-12, 11-20, 11-28). Each time somebody noticed only below 60 GB,
// and each time the eater was a different project hoarding its own output (build dirs, an updater's downloads,
// test temp dirs, video critic frames, superseded renders). Nobody was watching, so it was always found late.
//
// Cost: statfs is instant. Above the threshold it prints NOTHING (no context spent). Below it, it prints a warning
// plus the last measured top eaters from a cache (~/.claude/disk-eaters.json). Sizing ~150 GB of folders takes
// minutes, so the hook never does it inline: when the cache is older than CACHE_MAX_H it starts ONE detached
// background `--scan` (a lock stops two sessions scanning at once) and the NEXT session shows the fresh list.
// It never blocks and always exits 0 - a session must start even on a full disk; the warning is the signal.
// Never deletes anything: what to delete is the owning project's call (#1).
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

export const WARN_GB = 80
export const CRIT_GB = 40
export const CACHE_MAX_H = 6
export const LOCK_MAX_MIN = 30
const GB = 1024 ** 3
const HOME = os.homedir()
export const CACHE = path.join(HOME, '.claude', 'disk-eaters.json')
const LOCK = CACHE + '.lock'

export function freeBytes(dir) {
  const s = fs.statfsSync(dir)
  return Number(s.bavail) * Number(s.bsize)
}

// Pure: what the hook prints. '' = nothing to say.
export function render({ free, warnGb = WARN_GB, cache = null, now = Date.now() }) {
  const gb = free / GB
  if (gb >= warnGb) return ''
  const level = gb < CRIT_GB ? 'CRITICAL' : 'LOW'
  const lines = [`[#29.1 DISK ${level}] ${gb.toFixed(1)} GB free on this project's drive (warns below ${warnGb} GB). ` +
    'Tell Nick in your first reply. If YOUR project is in the list below, free your own hoard before new heavy work ' +
    '(superseded renders, build dirs, your own session scratch). Never delete another project\'s files (#1) - name ' +
    'them to Nick or the Director instead.']
  if (cache && Array.isArray(cache.items) && cache.items.length) {
    const ageH = (now - cache.at) / 3600000
    lines.push(`Top eaters (measured ${ageH < 1 ? Math.round(ageH * 60) + ' min' : ageH.toFixed(1) + ' h'} ago):`)
    for (const it of cache.items.slice(0, 5)) lines.push(`  ${(it.bytes / GB).toFixed(1).padStart(6)} GB  ${it.label}`)
  } else {
    lines.push('Top eaters: not measured yet - a background scan has started; the next session shows the list.')
  }
  return lines.join('\n')
}

// Recursive size; never follows links or junctions (a *-lucifer worktree or a junction would double-count).
export function dirBytes(dir) {
  let total = 0
  const stack = [dir]
  while (stack.length) {
    const d = stack.pop()
    let ents
    try { ents = fs.readdirSync(d, { withFileTypes: true }) } catch { continue }
    for (const e of ents) {
      const p = path.join(d, e.name)
      if (e.isSymbolicLink()) continue
      if (e.isDirectory()) { stack.push(p); continue }
      if (e.isFile()) { try { total += fs.lstatSync(p).size } catch {} }
    }
  }
  return total
}

// sessionId -> project folder name, from ~/.claude/projects/<proj>/<sessionId>.jsonl
export function sessionMap(projectsDir) {
  const map = new Map()
  let projs = []
  try { projs = fs.readdirSync(projectsDir, { withFileTypes: true }) } catch { return map }
  for (const p of projs) {
    if (!p.isDirectory()) continue
    let files = []
    try { files = fs.readdirSync(path.join(projectsDir, p.name)) } catch { continue }
    for (const f of files) if (f.endsWith('.jsonl')) map.set(f.slice(0, -6), p.name.replace(/^C--Users-[^-]+-Documents-Projects-/, ''))
  }
  return map
}

export function scan({ projectsRoot, tempDir, claudeProjects, downloads }) {
  const items = []
  const add = (label, dir) => { const b = dirBytes(dir); if (b > 0) items.push({ label, bytes: b }) }
  const ls = d => { try { return fs.readdirSync(d, { withFileTypes: true }) } catch { return [] } }
  for (const e of ls(projectsRoot)) if (e.isDirectory() && !e.isSymbolicLink()) add(`project ${e.name}`, path.join(projectsRoot, e.name))
  const sessions = sessionMap(claudeProjects)
  const claudeTemp = path.join(tempDir, 'claude')
  for (const h of ls(claudeTemp)) {
    if (!h.isDirectory()) continue
    for (const s of ls(path.join(claudeTemp, h.name))) {
      if (!s.isDirectory()) continue
      const proj = sessions.get(s.name) || h.name
      add(`session scratch ${proj} ${s.name.slice(0, 8)} (Temp\\claude)`, path.join(claudeTemp, h.name, s.name))
    }
  }
  let other = 0
  for (const e of ls(tempDir)) {
    if (e.name === 'claude' || e.isSymbolicLink()) continue
    const p = path.join(tempDir, e.name)
    if (e.isDirectory()) other += dirBytes(p); else if (e.isFile()) { try { other += fs.lstatSync(p).size } catch {} }
  }
  if (other > 0) items.push({ label: 'Temp (everything except Temp\\claude)', bytes: other })
  add('session transcripts (~/.claude/projects)', claudeProjects)
  add('Downloads', downloads)
  items.sort((a, b) => b.bytes - a.bytes)
  return items.slice(0, 10)
}

function readCache() { try { return JSON.parse(fs.readFileSync(CACHE, 'utf8')) } catch { return null } }

function startBackgroundScan(now) {
  try {
    const st = fs.statSync(LOCK)
    if (now - st.mtimeMs < LOCK_MAX_MIN * 60000) return
  } catch {}
  try {
    fs.mkdirSync(path.dirname(CACHE), { recursive: true })
    fs.writeFileSync(LOCK, String(now))
    const child = spawn(process.execPath, [fileURLToPath(import.meta.url), '--scan'], { detached: true, stdio: 'ignore', windowsHide: true })
    child.unref()
  } catch {}
}

const norm = p => (process.platform === 'win32' ? p.toLowerCase() : p)
const isMain = process.argv[1] && norm(path.resolve(process.argv[1])) === norm(fileURLToPath(import.meta.url))
if (isMain && process.argv.includes('--scan')) {
  try {
    const items = scan({
      projectsRoot: path.join(HOME, 'Documents', 'Projects'),
      tempDir: os.tmpdir(),
      claudeProjects: path.join(HOME, '.claude', 'projects'),
      downloads: path.join(HOME, 'Downloads'),
    })
    fs.writeFileSync(CACHE, JSON.stringify({ at: Date.now(), items }, null, 1))
  } catch {}
  try { fs.unlinkSync(LOCK) } catch {}
  process.exit(0)
} else if (isMain) {
  try {
    const now = Date.now()
    const warnGb = Number(process.env.DISK_WARN_GB) || WARN_GB
    const free = freeBytes(process.env.CLAUDE_PROJECT_DIR || process.cwd())
    if (free / GB < warnGb) {
      const cache = readCache()
      if (!cache || now - cache.at > CACHE_MAX_H * 3600000) startBackgroundScan(now)
      process.stdout.write(render({ free, warnGb, cache, now }) + '\n')
    }
  } catch (e) { process.stdout.write('[#29.1 DISK] hook error, disk not checked: ' + (e && e.message) + '\n') }
  process.exit(0)
}
