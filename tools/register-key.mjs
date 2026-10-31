#!/usr/bin/env node
// register-key.mjs — command_pattern #2.1 (Nick, 2026-10-31): the registry of keys the house may build into an app.
//
// A FREE Gemini key (a Google Cloud project with NO billing account) may be built into an app so the user sees no
// key screen. A PAID key never. The registry at ~/.embed-keys/registry.json holds FINGERPRINTS (sha256), never a key;
// the key a build reads sits beside it as ~/.embed-keys/<RepoFolder>.json {"GEMINI_KEY": "..."} — outside every repo.
// tools/release-gate.mjs reads the registry: an artifact carrying a key that is not registered free for THAT repo,
// or a commit/push carrying any registered key's text, is refused. This tool is the only writer of the registry.
//
//   node register-key.mjs free --repo <RepoFolder> --project <Google project name> --no-billing [--file <path>] [--by Nick]
//        registers the key in ~/.embed-keys/<RepoFolder>.json as that repo's free key (one active key per repo);
//        --no-billing is the attestation, on Nick's word, that the project has no billing account
//   node register-key.mjs paid --from <.env|json|text file> [--var NAME] [--note "…"]
//        records a paid key's fingerprint so a build or commit carrying it is refused
//   node register-key.mjs retire --repo <RepoFolder> [--reason "…"]
//        after Nick deleted the key in the Google console: the next build needs a newly registered key
//   node register-key.mjs whose --from <file>        what the registry knows about the key in that file
//   node register-key.mjs list                       the registry, fingerprints only
//   node register-key.mjs move --repo <RepoFolder> --from <in-repo file>
//        writes ~/.embed-keys/<RepoFolder>.json from a key file inside the repo (secrets/gemini_key.txt, keys/gemini.json)
//        — the one sanctioned way a session writes under ~/.embed-keys (rule #1); it then deletes the in-repo file itself
// Exit 0 = done, 1 = refused (the reason is printed), 2 = usage.

import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const HOME = process.env.USERPROFILE || process.env.HOME || ''
export const KEY_DIR = path.join(HOME, '.embed-keys')
export const REGISTRY = path.join(KEY_DIR, 'registry.json')
// the two shapes AI Studio has issued (AIza + 35: Standard, being retired; AQ. + ~47: the Auth key it issues now)
export const KEY_SHAPES = [/^AIza[0-9A-Za-z_-]{35}$/, /^AQ\.[0-9A-Za-z_-]{30,}$/]
const fpOf = (k) => crypto.createHash('sha256').update(String(k)).digest('hex')
const today = () => new Date().toISOString().slice(0, 10)

export function readRegistry() {
  try { const r = JSON.parse(fs.readFileSync(REGISTRY, 'utf8')); return Array.isArray(r?.keys) ? r : { schema: 'embed-keys/1', keys: [] } }
  catch { return { schema: 'embed-keys/1', keys: [] } }
}
function writeRegistry(r) {
  fs.mkdirSync(KEY_DIR, { recursive: true })
  const tmp = REGISTRY + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify({ schema: 'embed-keys/1', keys: r.keys }, null, 2) + '\n', { mode: 0o600 })
  fs.renameSync(tmp, REGISTRY)
}
/** The key in a file: {"GEMINI_KEY": …} / any JSON string value / NAME=value lines / the whole text. Never printed. */
export function keyFrom(file, varName) {
  const text = fs.readFileSync(file, 'utf8').replace(/^﻿/, '')
  try {
    const o = JSON.parse(text)
    if (o && typeof o === 'object') {
      if (varName && typeof o[varName] === 'string') return o[varName].trim()
      if (typeof o.GEMINI_KEY === 'string') return o.GEMINI_KEY.trim()
      const v = Object.values(o).find((x) => typeof x === 'string' && x.trim().length >= 20)
      if (v) return v.trim()
    }
  } catch {}
  if (varName) {
    const m = new RegExp(`^\\s*(?:export\\s+)?${varName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*=\\s*(.+)$`, 'm').exec(text)
    if (m) { keyFrom.took = varName; return m[1].trim().replace(/^["']|["']$/g, '') }
  } else {
    // a .env lists many secrets: take the Gemini-named one; with none, one generic KEY/TOKEN/SECRET line, else ask for --var
    const all = [...text.matchAll(/^\s*(?:export\s+)?([A-Z0-9_]*(KEY|TOKEN|SECRET)[A-Z0-9_]*)\s*=\s*(.+)$/gm)].map((m) => [m[1], m[3].trim().replace(/^["']|["']$/g, '')])
    const gem = all.filter(([n]) => /GEMINI|GOOGLE_API/.test(n))
    const pick = gem.length ? gem : all
    if (pick.length > 1) throw new Error(`${file} holds ${pick.length} candidate lines (${pick.map(([n]) => n).join(', ')}); say which with --var NAME`)
    if (pick.length === 1) { keyFrom.took = pick[0][0]; return pick[0][1] }
  }
  const one = text.trim()
  if (one && !/\s/.test(one)) { keyFrom.took = '(the whole file)'; return one }
  throw new Error(`no key found in ${file} (expected {"GEMINI_KEY": …}, NAME=value, or the key alone)`)
}
const shaped = (k) => KEY_SHAPES.some((re) => re.test(k))
const describe = (e) => e.tier === 'paid' ? `PAID (${e.note || 'no note'}, since ${e.on})`
  : `free for ${e.repo} (project ${e.project}, ${e.status}, since ${e.on})`

function arg(args, name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined }
function usage() {
  const lines = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n')
  const a = lines.findIndex((l) => /^\/\/\s+node register-key\.mjs/.test(l)); const b = lines.findIndex((l, i) => i > a && /^\/\/ Exit 0/.test(l))
  console.error(lines.slice(a, b + 1).map((l) => l.replace(/^\/\/ ?/, '')).join('\n')); return 2
}

export function main(args) {
  const cmd = args[0]
  const reg = readRegistry()
  const by = arg(args, '--by') || process.env.USERNAME || process.env.USER || 'unknown'
  if (cmd === 'list') {
    if (!reg.keys.length) { console.log(`registry empty (${REGISTRY})`); return 0 }
    for (const e of reg.keys) console.log(`${(e.repo || '-').padEnd(26)} ${e.tier.padEnd(5)} ${String(e.fp).slice(0, 12)}…  ${describe(e)}`)
    return 0
  }
  if (cmd === 'whose') {
    const from = arg(args, '--from'); if (!from) return usage()
    let k; try { k = keyFrom(from, arg(args, '--var')) } catch (e) { console.error(e.message); return 1 }
    const e = reg.keys.find((x) => x.fp === fpOf(k))
    console.log(e ? `registered ${describe(e)}` : `UNREGISTERED (sha256 ${fpOf(k).slice(0, 12)}…, shape ${shaped(k) ? 'known' : 'unknown'})`)
    return 0
  }
  if (cmd === 'free') {
    const repo = arg(args, '--repo'); const project = arg(args, '--project')
    if (!repo || !project) return usage()
    // the Google project's REAL name goes in the registry; the attestation that it has no billing account is the flag,
    // given on Nick's word (2026-10-31: "no billing, and three different keys"). Naming it embed-free-<app> is advice.
    if (!args.includes('--no-billing')) { console.error(`refused: pass --no-billing to attest that project "${project}" has NO billing account (Nick's word, checked in the Google console); a key from a billed project is never built in`); return 1 }
    const file = arg(args, '--file') || path.join(KEY_DIR, `${repo}.json`)
    if (!fs.existsSync(file)) { console.error(`refused: ${file} not found — write {"GEMINI_KEY": "<the key>"} there first (outside every repo)`); return 1 }
    let k; try { k = keyFrom(file, arg(args, '--var')) } catch (e) { console.error(`refused: ${e.message}`); return 1 }
    if (!shaped(k) && !args.includes('--any-shape')) { console.error('refused: the key has neither known shape (AIza + 35, AQ. + 30 or more). Is this a Gemini API key? Pass --any-shape if it is'); return 1 }
    const fp = fpOf(k)
    const same = reg.keys.find((e) => e.fp === fp)
    if (same && same.tier === 'paid') { console.error(`refused: this is a PAID key (${same.note || 'registered paid'}, ${same.on}); a paid key is never built in`); return 1 }
    if (same && same.repo.toLowerCase() !== repo.toLowerCase()) { console.error(`refused: this key is ${same.repo}'s free key; one key per app — create a new project embed-free-${repo.toLowerCase()} and a new key`); return 1 }
    if (same && same.status === 'active') { console.log(`already registered: free for ${repo} (project ${same.project}, since ${same.on})`); return 0 }
    if (same && same.status === 'retired' && !args.includes('--reinstate')) { console.error(`refused: this key was RETIRED on ${same.retiredOn}${same.reason ? ` (${same.reason})` : ''}; write the NEW key to ${file} first, or pass --reinstate if Nick says this one is fine after all`); return 1 }
    for (const e of reg.keys) if (e.tier === 'free' && e.repo.toLowerCase() === repo.toLowerCase() && e.status === 'active') { e.status = 'replaced'; e.replacedOn = today() }
    if (same) { same.status = 'active'; same.project = project; same.on = today(); same.registeredBy = by }
    else reg.keys.push({ repo, tier: 'free', fp, shape: k.startsWith('AQ.') ? 'AQ' : k.startsWith('AIza') ? 'AIza' : 'other', project, billing: 'none', registeredBy: by, on: today(), status: 'active' })
    writeRegistry(reg)
    console.log(`registered: ${repo} free key ${fp.slice(0, 12)}… from project ${project}\n` +
      `  the build reads ${file}; the registry holds the fingerprint only\n` +
      `  never attach a billing account to ${project}; if the key leaks or is abused: delete it in the Google console,\n` +
      `  then: node tools/register-key.mjs retire --repo ${repo}, register the new one, release under #28`)
    return 0
  }
  if (cmd === 'paid') {
    const from = arg(args, '--from'); if (!from) return usage()
    let k; try { k = keyFrom(from, arg(args, '--var')) } catch (e) { console.error(`refused: ${e.message}`); return 1 }
    const fp = fpOf(k)
    const same = reg.keys.find((e) => e.fp === fp)
    if (same && same.tier === 'free' && same.status === 'active') { console.error(`refused: this key is registered FREE for ${same.repo}; a key is one or the other — if billing was attached to ${same.project}, retire it first (retire --repo ${same.repo}) and register the paid record after`); return 1 }
    if (same && same.tier === 'paid') { console.log(`already recorded as paid (${same.note || 'no note'}, ${same.on})`); return 0 }
    reg.keys.push({ tier: 'paid', fp, note: arg(args, '--note') || path.basename(from), registeredBy: by, on: today() })
    writeRegistry(reg)
    console.log(`recorded: paid key ${fp.slice(0, 12)}… taken from ${keyFrom.took || 'the file'} — a build or commit carrying it is now refused`)
    return 0
  }
  if (cmd === 'move') {
    const repo = arg(args, '--repo'); const from = arg(args, '--from')
    if (!repo || !from) return usage()
    let k; try { k = keyFrom(from, arg(args, '--var')) } catch (e) { console.error(`refused: ${e.message}`); return 1 }
    if (!shaped(k) && !args.includes('--any-shape')) { console.error('refused: the key has neither known shape (AIza + 35, AQ. + 30 or more); pass --any-shape if it is a Gemini key anyway'); return 1 }
    const dst = path.join(KEY_DIR, `${repo}.json`)
    if (fs.existsSync(dst)) {
      let cur = null; try { cur = keyFrom(dst) } catch {}
      if (cur === k) { console.log(`already there: ${dst} holds this key`); return 0 }
      console.error(`refused: ${dst} exists and holds a different key; retire or rename it first`); return 1
    }
    fs.mkdirSync(KEY_DIR, { recursive: true })
    fs.writeFileSync(dst, JSON.stringify({ GEMINI_KEY: k }, null, 2) + '\n', { mode: 0o600 })
    console.log(`moved: the key now lives at ${dst} (the file inside the repo is yours to delete: ${from})\n` +
      `  next: node tools/register-key.mjs free --repo ${repo} --project "<its Google project name>" --no-billing`)
    return 0
  }
  if (cmd === 'retire') {
    const repo = arg(args, '--repo'); if (!repo) return usage()
    let n = 0
    for (const e of reg.keys) if (e.tier === 'free' && e.repo.toLowerCase() === repo.toLowerCase() && e.status === 'active') { e.status = 'retired'; e.retiredOn = today(); e.reason = arg(args, '--reason') || ''; n++ }
    if (!n) { console.error(`nothing to retire: ${repo} has no active free key`); return 1 }
    writeRegistry(reg)
    console.log(`retired: ${repo}'s free key. Delete it in the Google console too if not yet done; the next build is refused until a new key is registered`)
    return 0
  }
  return usage()
}

const isMain = !!process.argv[1] && path.resolve(process.argv[1]).toLowerCase() === fileURLToPath(import.meta.url).toLowerCase()
if (isMain) process.exit(main(process.argv.slice(2)))
