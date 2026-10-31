#!/usr/bin/env node
// release-gate.mjs — enforcement of command_pattern #28: NO UPDATE DRILL, NO RELEASE.
//
// WHY THIS FILE EXISTS
// 2026-10-30: EMR v0.5.3 ("the app updates itself") was published with its own report saying
// "NOT done: a drill of the packaged exe". On Nick's PC the update renamed the old build to
// `_previous`, the new one appeared as a second folder on the Desktop, and the old folder kept the
// icon's place, so Nick opened the old build from it. Nick: "how can something this basic be missed".
// It was not the first time: SHARED_LESSONS has a whole "Build / Release / Auto-update" section of
// the same class (hoarded installers, a poisoned "applied" flag, comparators that strand the fleet).
// Every one of them was a step NOBODY RAN: the OLD PACKAGED build updating ITSELF to the new one.
// A sentence in a rule did not make anybody run it, so this gate does.
//
// WHAT IT DOES
// As a PreToolUse hook on Bash/PowerShell it reads the command about to run. If that command would put
// a build in front of users, it refuses (exit 2) unless the repo holds a passing drill receipt
// (drills/*.json, schema "update-drill/1") for EXACTLY the bytes being published — matched by SHA-256.
// It recognises:
//   gh release create <tag> [assets…]   (unless --draft)       gh release upload <tag> <assets…>
//   gh release edit <tag> --draft=false | --latest | --prerelease=false
//   gh api …releases… with POST/PATCH                         (refused: use gh release so it can be read)
//   adb [-s SERIAL] install <apk>        (allowed only for an emulator: -e or -s emulator-NNNN)
//     also when adb is reached through a variable ("$ADB" install …), and an APK given as a variable
//   flutter install · flutter run --release|--profile · gradlew install*Release · bundletool install-apks
//     to anything but an emulator: they put a build on a phone whose bytes cannot be matched — use adb
//   running a script named *publish* / *release* that does not itself call `release-gate.mjs --check`
// As a CLI:   node release-gate.mjs --check [--tag vX] <asset>…   exits 0 only if every asset has a passing
//             receipt, or (with --tag) Nick's one-shot note names that tag; the note is consumed
//             node release-gate.mjs --validate <receipt.json>   prints what is missing in one receipt
//
// The way past it is not a flag. It is a drill, or Nick's one-shot note (~/.claude/release-approval.json
// {"tag":"v1.2.3","reason":"…","expiresEpochMs":…}), consumed on use — the same road as the agent cap.
// Like the cap hook, it fails OPEN if it cannot run at all (no node): the rule is still the rule.
//
// SINCE 2026-10-31 IT ALSO ENFORCES command_pattern #2.1: A FREE KEY MAY BE BUILT IN, A PAID KEY NEVER.
// Nick's word that night: a free Gemini key may be built into an app so no key screen is shown; a key on a
// billed project never; "make the rule strict and the guard good; a bad key we delete in the Google console".
// Three apps started building keys in the same evening, so the guard had to exist the same evening:
//   git commit / git push   refused while the index/HEAD holds a key-shaped string (AIza…, AQ.…), the text of a
//                           registered key, or a file that is a secret by its name (.env, *.jks, service-account*.json…)
//   a release / an install  refused while HEAD holds one of those, or the artifact carries a key that is not
//                           registered FREE for THIS repo (~/.embed-keys/registry.json, fingerprints only), or a
//                           registered key the drill receipt does not declare (embedded_key + check embedded_key_works)
// The note waives the drill, never a key: a leak is not a release decision. Standard: memory/KEY_EMBED.md.

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import zlib from 'node:zlib'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const HOME = process.env.USERPROFILE || process.env.HOME || ''
const APPROVAL = path.join(HOME, '.claude', 'release-approval.json')
const INSTALLABLE = /\.(exe|zip|msi|msix|msixbundle|appinstaller|apk|aab|7z)$/i
const KEY_DIR = path.join(HOME, '.embed-keys')            // <Repo>.json = the key a build reads; registry.json = fingerprints
const REGISTRY = path.join(KEY_DIR, 'registry.json')

// ── the standard (UPDATE_DRILL.md) — keep these lists and that document in step ──────────────────
export const PROFILES = {
  'desktop-self-update': {
    required: ['start_from_released_build', 'real_update_path', 'new_version_running', 'one_process',
      'one_install', 'tree_matches_fresh_install', 'shortcuts_open_new', 'relaunched_itself', 'user_data_intact',
      'no_update_loop', 'sees_next_release', 'bad_download_refused', 'unknown_is_not_no'],
    never_na: ['start_from_released_build', 'real_update_path', 'new_version_running', 'one_install',
      'shortcuts_open_new', 'user_data_intact', 'sees_next_release'],
  },
  'desktop-manual-install': {
    required: ['start_from_released_build', 'real_update_path', 'new_version_running', 'one_process',
      'one_install', 'tree_matches_fresh_install', 'shortcuts_open_new', 'user_data_intact'],
    never_na: ['start_from_released_build', 'real_update_path', 'new_version_running', 'one_install',
      'shortcuts_open_new', 'user_data_intact'],
  },
  'android': {                       // sideloaded with adb or delivered by Play: the same checks either way
    required: ['start_from_released_build', 'real_update_path', 'new_version_running', 'one_install',
      'user_data_intact', 'same_signing_key', 'version_code_increased'],
    never_na: ['start_from_released_build', 'real_update_path', 'new_version_running', 'one_install',
      'user_data_intact', 'same_signing_key', 'version_code_increased'],
  },
}

const read = (f) => { try { return fs.readFileSync(f, 'utf8').replace(/^\uFEFF/, '') } catch { return '' } }
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex')
const normTag = (t) => String(t || '').trim().replace(/^v/i, '')

// ── receipts ─────────────────────────────────────────────────────────────────────────────────────
/** Every problem with one receipt, as sentences. Empty = it passes. */
export function receiptProblems(r) {
  const out = []
  if (!r || typeof r !== 'object') return ['not a JSON object']
  if (r.schema !== 'update-drill/1') out.push('schema is not "update-drill/1"')
  if (r.rehearsal) out.push('rehearsal receipt: a test build never ships; drill the release bytes and write a receipt without the marker')
  const prof = PROFILES[r.profile]
  if (!prof) out.push(`profile must be one of: ${Object.keys(PROFILES).join(', ')}`)
  if (!r.from_version) out.push('from_version missing: which released build did the drill start from?')
  if (!r.to_version) out.push('to_version missing')
  if (r.from_version && r.to_version && normTag(r.from_version) === normTag(r.to_version))
    out.push('from_version equals to_version: an update drill starts from the PREVIOUS release')
  if (!/^[0-9a-f]{64}$/i.test(r.from_artifact_sha256 || ''))
    out.push('from_artifact_sha256 missing: the drill must start from the real released file, by hash')
  if (!Array.isArray(r.assets) || !r.assets.length || !r.assets.every((a) => a && typeof a === 'object' && /^[0-9a-f]{64}$/i.test(a.sha256 || '')))
    out.push('assets[] must list every published file with its sha256')
  if (!r.drilled_at) out.push('drilled_at missing')
  if (!r.layout || String(r.layout).length < 15)
    out.push('layout missing: say where and how the old build was installed, and which shortcuts existed')
  const checks = r.checks && typeof r.checks === 'object' ? r.checks : {}
  for (const id of prof ? prof.required : []) {
    const c = checks[id]
    if (!c) { out.push(`check "${id}" missing`); continue }
    const ev = String(c.evidence || '').trim()
    if (c.result === 'pass') { if (ev.length < 10) out.push(`check "${id}" passed with no evidence`) }
    else if (c.result === 'n/a') {
      if (prof.never_na.includes(id)) out.push(`check "${id}" cannot be n/a`)
      else if (ev.length < 15) out.push(`check "${id}" is n/a without a reason`)
    } else out.push(`check "${id}" is ${c.result || 'empty'}, not pass`)
  }
  // #2.1: a build that carries a key says so, and the drill proved that key works from the UPDATED build
  if (r.embedded_key !== undefined) {
    const k = r.embedded_key
    if (!k || typeof k !== 'object' || !/^[0-9a-f]{64}$/i.test(k.fp || ''))
      out.push('embedded_key must be {fp: <sha256 of the key>, repo: <repo folder>} — the fingerprint, never the key')
    else if (KEY_SHAPES.some((re) => new RegExp(re.source).test(JSON.stringify(k))))
      out.push('embedded_key holds the key itself; a receipt carries the fingerprint only')
    const c = checks.embedded_key_works
    if (!c) out.push('check "embedded_key_works" missing: one real call from the updated build with the built-in key (evidence: status 200 + model)')
    else if (c.result !== 'pass') out.push(`check "embedded_key_works" is ${c.result || 'empty'}, not pass`)
    else if (String(c.evidence || '').trim().length < 10) out.push('check "embedded_key_works" passed with no evidence')
  }
  return out
}

// ── keys (command_pattern #2.1, memory/KEY_EMBED.md) ─────────────────────────────────────────────
// The two shapes Google AI Studio has issued: AIza + 35 (the Standard key, being retired through 2026) and
// AQ. + ~50 (the Auth key it issues now; JS found that a scan matching AIza alone lets it into git unseen).
// Shapes catch an unknown key; the registered keys are also searched by their text, whatever their shape.
// Round 2 (2026-10-31, three review firms): the index is read by BLOB (binary, UTF-16, a zip inside), what an earlier
// `git add` in the same line stages is read from disk, a push scans the refs it pushes, `cd`/wrappers/`-am` are read.
export const KEY_SHAPES = [/AIza[0-9A-Za-z_-]{35}/g, /(?<![0-9A-Za-z_-])AQ\.[0-9A-Za-z_-]{30,}/g]
const PRIVATE_BLOCK = /-----BEGIN [A-Z ]*PRIVATE KEY-----/
const NOT_A_KEY = /not-a-key/i                            // a fixture line says so and is skipped — never for a registered key
// files that are secrets by their name: never tracked, whatever they hold. .env.example and friends are templates; a .md or
// .py that merely talks about a key is not a key file (EMR's ADR 0002-built-in-shared-gemini-key.md would have been refused)
const SECRET_PATH = /(^|\/)(\.env(?![^/]*\.(example|sample|template|dist)(\.|$))(\.[^/]*)?|[^/]*\.(jks|keystore|p12|pfx)|service-account[^/]*\.json|release-approval\.json|[^/]*gemini[^/]*key[^/]*\.(txt|json|key|env|bin)|keys?\/gemini\.json|secrets?\/[^/]*\.(txt|json|key|env))$/i
const MEDIA = /\.(png|jpe?g|webp|gif|bmp|ico|mp3|mp4|m4a|ogg|wav|ttf|otf|woff2?)$/i
const ZIPPY = /\.(apk|aab|aar|jar|zip|msix|msixbundle|appx|xapk|apks|ipa|whl|nupkg)$/i
const BIG = 64 << 20                                      // a blob or zip member above this is not read; a problem says so
const fpOf = (k) => crypto.createHash('sha256').update(String(k)).digest('hex')
const readJson = (f) => { try { return JSON.parse(read(f)) } catch { return null } }

/** What the gate knows about keys, read once per process: the registry (fingerprints) and the texts a build reads. */
let KNOWN = null
export function known() {
  if (KNOWN) return KNOWN
  const reg = readJson(REGISTRY); const keys = Array.isArray(reg?.keys) ? reg.keys : []
  const texts = []
  let names = []; try { names = fs.readdirSync(KEY_DIR) } catch {}
  for (const n of names) {
    if (!/\.json$/i.test(n) || /^registry\.json$/i.test(n)) continue
    const o = readJson(path.join(KEY_DIR, n))
    if (!o || typeof o !== 'object') { process.stderr.write(`release-gate: ${path.join(KEY_DIR, n)} is not readable JSON; its key cannot be searched by text\n`); continue }
    // only the values that ARE keys: a note or a project name in the same file must not become a search pattern
    for (const [name, v] of Object.entries(o)) if (/key|token|secret/i.test(name) && typeof v === 'string' && v.trim().length >= 20) texts.push(v.trim())
  }
  return (KNOWN = { keys, texts, dirExists: fs.existsSync(KEY_DIR), registryExists: !!reg })
}
/** What the registry says about a key, or null when it is unregistered. */
const whose = (key) => { const fp = fpOf(key); return known().keys.find((e) => String(e.fp || '').toLowerCase() === fp) || null }
const isRegistered = (key) => !!whose(key) || known().texts.includes(key)
function describeKey(key) {
  const e = whose(key)
  if (!e) return `an UNREGISTERED key (sha256 ${fpOf(key).slice(0, 12)}…)`
  if (e.tier === 'paid') return `Nick's PAID key (${e.note || 'registered paid'})`
  return `the free key registered for ${e.repo}${e.status && e.status !== 'active' ? ` (status: ${e.status})` : ''}`
}
/** A shape match that runs past a registered key (the bytes after it were letters) is that key, not a second one. */
function normalize(found) {
  const texts = known().texts; const out = new Set()
  for (const k of found) { const t = texts.find((x) => k !== x && k.startsWith(x)); out.add(t || k) }
  return [...out]
}
export function keysInText(text) {
  const s = String(text); const found = new Set()
  for (const re of KEY_SHAPES) for (const m of s.matchAll(re)) found.add(m[0])
  for (const k of known().texts) if (s.includes(k)) found.add(k)
  return normalize(found)
}
/** Keys in raw bytes: the latin1 and the UTF-16LE view, 8 MB chunks with overlap, plus every registered text by indexOf. */
function keysInBytes(buf) {
  const found = new Set(); const CH = 8 << 20; const OV = 512
  for (let o = 0; o < buf.length; o += CH) {
    const part = buf.subarray(Math.max(0, o - OV), Math.min(buf.length, o + CH))
    for (const s of [part.toString('latin1'), part.toString('utf16le')]) for (const re of KEY_SHAPES) for (const m of s.matchAll(re)) found.add(m[0])
  }
  for (const k of known().texts) if (buf.indexOf(k, 0, 'latin1') >= 0 || buf.indexOf(Buffer.from(k, 'utf16le')) >= 0) found.add(k)
  return found
}
/** The members of a zip (APK, AAB, MSIX, .zip): stored or deflated, under 64 MB, not zip64/encrypted. [] when not a zip. */
export function zipEntries(buf) {
  const out = []
  let eocd = -1
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 66000); i--) if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break }
  if (eocd < 0) return out
  const n = buf.readUInt16LE(eocd + 10); let p = buf.readUInt32LE(eocd + 16)
  for (let i = 0; i < n && p + 46 <= buf.length; i++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) break
    const flags = buf.readUInt16LE(p + 8); const method = buf.readUInt16LE(p + 10); const csize = buf.readUInt32LE(p + 20); const usize = buf.readUInt32LE(p + 24)
    const nl = buf.readUInt16LE(p + 28); const el = buf.readUInt16LE(p + 30); const cl = buf.readUInt16LE(p + 32); const lho = buf.readUInt32LE(p + 42)
    const name = buf.toString('utf8', p + 46, p + 46 + nl)
    p += 46 + nl + el + cl
    if (name.endsWith('/')) continue
    const skip = (why) => out.push({ name, data: null, skipped: why })
    if (csize === 0xffffffff || usize === 0xffffffff || lho === 0xffffffff) { skip('zip64'); continue }
    if (usize > BIG) { skip('over 64 MB'); continue }
    if (flags & 1) { skip('encrypted'); continue }
    if (lho + 30 > buf.length || buf.readUInt32LE(lho) !== 0x04034b50) { skip('bad local header'); continue }
    const start = lho + 30 + buf.readUInt16LE(lho + 26) + buf.readUInt16LE(lho + 28)
    const raw = buf.subarray(start, start + csize)
    if (method === 0) out.push({ name, data: raw })
    else if (method === 8) { try { out.push({ name, data: zlib.inflateRawSync(raw) }) } catch { skip('deflate error') } }
    else skip(`compression method ${method}`)
  }
  return out
}
/** Every key a buffer carries, looking inside zip-shaped data two levels deep (an APK's libapp.so, a bundle inside it). */
export function keysInBuffer(buf, name = '', depth = 0, notes = []) {
  const found = new Set(keysInBytes(buf))
  const zipShaped = ZIPPY.test(name) || (buf.length > 4 && buf.readUInt32LE(0) === 0x04034b50)
  if (zipShaped && depth < 2) for (const e of zipEntries(buf)) {
    if (MEDIA.test(e.name)) continue
    if (!e.data) { notes.push(`${path.basename(name) || 'zip'}: member ${e.name} not read (${e.skipped})`); continue }
    for (const k of keysInBuffer(e.data, e.name, depth + 1, notes)) found.add(k)
  }
  return normalize(found)
}
export function keysInArtifact(file, notes = []) { return keysInBuffer(fs.readFileSync(file), file, 0, notes) }

// ── git: what a commit or a push is about to publish ──────────────────────────────────────────────
let GIT = 'git'                                            // the executable the command named by path, when it did
const gitAt = (dir, args, input) => spawnSync(GIT, args, { cwd: dir, encoding: 'utf8', maxBuffer: 256 << 20, input })
const gitBuf = (dir, args, input) => spawnSync(GIT, args, { cwd: dir, maxBuffer: 1 << 30, input })
const EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
const headOr = (dir) => gitAt(dir, ['rev-parse', '--verify', '-q', 'HEAD']).status === 0 ? 'HEAD' : EMPTY_TREE
const zlist = (r) => String(r.stdout || '').split('\0').filter(Boolean)
const allHeads = (dir) => String(gitAt(dir, ['for-each-ref', '--format=%(refname:short)', 'refs/heads']).stdout || '').split('\n').filter(Boolean)
/** The blobs behind object names such as ":path" (the index) or "REF:path", read in one git process. */
function blobs(dir, names) {
  if (!names.length) return []
  const r = gitBuf(dir, ['cat-file', '--batch'], names.join('\n') + '\n'); const b = r.stdout || Buffer.alloc(0); const out = []
  let p = 0
  for (const name of names) {
    const nl = b.indexOf(0x0a, p); if (nl < 0) break
    const m = /^(\S+) (\S+) (\d+)$/.exec(b.toString('utf8', p, nl)); p = nl + 1
    if (!m) { out.push({ name, data: null, missing: true }); continue }
    const size = Number(m[3]); const data = b.subarray(p, p + size); p += size + 1
    out.push({ name, data: size > BIG ? null : Buffer.from(data), big: size > BIG })
  }
  return out
}
const looksText = (buf) => !buf.subarray(0, 8000).includes(0)
/** The keys a file holds, as sentences into `out`: by line for text (where a fixture may say not-a-key), by bytes otherwise. */
function hitsIn(buf, where, out) {
  if (looksText(buf)) {
    const lines = buf.toString('utf8').split('\n')
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      if (PRIVATE_BLOCK.test(line) && !NOT_A_KEY.test(line)) out.push(`${where}:${i + 1} holds a private key block: never committed`)
      for (const k of keysInText(line)) {
        if (NOT_A_KEY.test(line) && !isRegistered(k)) continue     // a fixture may say so; a real key may not
        out.push(`${where}:${i + 1} holds ${describeKey(k)}: a key is never committed — take the line out (git reset the file, edit, add again; a fixture may say not-a-key)`)
      }
    }
  } else {
    for (const k of keysInBuffer(buf, where)) out.push(`${where} (binary) holds ${describeKey(k)}: a key is never committed`)
    if (PRIVATE_BLOCK.test(buf.toString('latin1'))) out.push(`${where} (binary) holds a private key block: never committed`)
  }
}
const u16 = (s) => [...s].map((c) => c.replace(/[.*+?^${}()|[\]\\\/-]/g, '\\$&') + '\\x00').join('')
/** Keys and secret-named files in what git is about to publish. Sentences; empty = clean.
 *  staged: the index (+ the worktree with `all`, + untracked files with `untracked` = true or a path list), scoped to
 *  `paths` as git resolves them from `cwd`. Otherwise: the trees of `refs` (a push, a release), default HEAD. */
export function secretProblems(root, { staged = false, all = false, untracked = false, paths = [], cwd = root, refs = ['HEAD'], message = '', exclude = [] } = {}) {
  const out = []; const dir = cwd || root
  const probe = gitAt(dir, ['rev-parse', '--show-toplevel'])
  if (probe.error) return [fs.existsSync(dir) ? `could not run git (${probe.error.message}), so nothing here can be judged: a commit or a publish waits until git runs` : `the folder ${dir} does not exist, so nothing there can be judged`]
  if (probe.status !== 0) return []                       // not a repository: git refuses the command by itself
  const top = String(probe.stdout).trim(); const sp = paths.length ? ['--', ...paths] : []
  if (message) for (const k of keysInText(message)) out.push(`the commit message holds ${describeKey(k)}: a key is never committed, not even in a message`)
  if (staged) {
    const at = paths.length ? dir : top                   // a pathspec is read from where the command runs; the whole index from the top
    const names = zlist(gitAt(at, ['diff', '--cached', '--name-only', '-z', '--diff-filter=AMRC', ...sp]))
    const work = all ? zlist(gitAt(at, ['diff', '--name-only', '-z', '--diff-filter=AMRC', headOr(at), ...sp])) : []
    const usp = Array.isArray(untracked) ? (untracked.length ? ['--', ...untracked] : []) : sp
    const others = untracked ? zlist(gitAt(Array.isArray(untracked) && untracked.length ? dir : top, ['ls-files', '--others', '--exclude-standard', '--full-name', '-z', ...usp])) : []
    for (const q of new Set([...names, ...work, ...others])) if (SECRET_PATH.test(q)) out.push(`${q} is a secret by its name and would be committed: keep it out (git rm --cached, .gitignore)`)
    for (const b of blobs(at, names.slice(0, 5000).map((q) => `:${q}`))) {
      const q = b.name.slice(1)
      if (b.big) { out.push(`${q} is over 64 MB and cannot be scanned: a file that size is not committed`); continue }
      if (b.data) hitsIn(b.data, q, out)
    }
    for (const q of [...new Set([...work, ...others])].slice(0, 5000)) {   // git names them from the top (--full-name / diff default)
      const f = path.resolve(top, q)
      let st; try { st = fs.statSync(f) } catch { continue }
      if (!st.isFile()) continue
      if (st.size > BIG) { out.push(`${q} is over 64 MB and cannot be scanned: a file that size is not committed`); continue }
      hitsIn(fs.readFileSync(f), q, out)
    }
    return [...new Set(out)]
  }
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'rgate-')); const f1 = path.join(d, 'f'); const f2 = path.join(d, 'p')
  try {
    const texts = known().texts
    if (texts.length) fs.writeFileSync(f1, texts.join('\n') + '\n', { mode: 0o600 })   // registered keys by text: a private file, never argv
    fs.writeFileSync(f2, [...texts.map(u16), 'A\\x00I\\x00z\\x00a\\x00(?:[0-9A-Za-z_-]\\x00){35}', 'A\\x00Q\\x00\\.\\x00(?:[0-9A-Za-z_-]\\x00){30,}'].join('\n') + '\n', { mode: 0o600 })
    const E = [...KEY_SHAPES.map((r) => r.source.replace(/^\(\?<!\[[^\]]*\]\)/, '')), PRIVATE_BLOCK.source].join('|')
    for (const ref of [...new Set(refs)]) {
      const tree = gitAt(top, ['ls-tree', '-r', '--name-only', '-z', ref])
      if (tree.status !== 0) continue                     // an unborn HEAD, a ref that does not exist yet
      const label = ref === 'HEAD' ? '' : `${ref}:`
      const skip = new Set(exclude)                        // paths a commit on the same line replaces: judged from the worktree instead
      for (const q of zlist(tree)) if (SECRET_PATH.test(q) && !skip.has(q)) out.push(`${label}${q} is a secret by its name and is tracked: git rm --cached it and list it in .gitignore`)
      const lines = [
        ...String(gitAt(top, ['grep', '--text', '-n', '-E', E, ref, '--', '.']).stdout || '').split('\n'),
        ...(texts.length ? String(gitAt(top, ['grep', '--text', '-n', '-F', '-f', f1, ref, '--', '.']).stdout || '').split('\n') : []),
        ...String(gitAt(top, ['grep', '--text', '-n', '-P', '-f', f2, ref, '--', '.']).stdout || '').split('\n'),   // UTF-16 files
      ]
      for (const raw of lines) {
        if (!raw.startsWith(ref + ':')) continue
        const m = /^([^\n]+?):(\d+):([\s\S]*)$/.exec(raw.slice(ref.length + 1)); if (!m || skip.has(m[1])) continue
        const text = m[3].replace(/\0/g, '')
        if (PRIVATE_BLOCK.test(text) && !NOT_A_KEY.test(text)) out.push(`${label}${m[1]}:${m[2]} holds a private key block: never committed`)
        for (const k of keysInText(text)) {
          if (NOT_A_KEY.test(text) && !isRegistered(k)) continue
          out.push(`${label}${m[1]}:${m[2]} holds ${describeKey(k)}: a key is never committed — take it out of the history that is pushed`)
        }
      }
    }
  } finally { try { fs.rmSync(d, { recursive: true, force: true }) } catch {} }
  return [...new Set(out)]
}
function drillManifest(root) { return readJson(path.join(root, 'drills', 'drill.json')) }
/** What is wrong with the key(s) built into `file`, judged against the registry and the receipt `r` that covers it.
 *  `strict` false (--scan by hand before a drill): "the receipt says nothing" is a note, not a problem. */
export function embeddedKeyProblems(root, file, r, { strict = true, notes = [] } = {}) {
  const out = []; const repo = path.basename(root).toLowerCase(); const base = path.basename(file)
  let keys = []
  try { keys = keysInArtifact(file, notes) } catch (e) { return [`could not scan ${base} for keys (${e.message})`] }
  const declared = r && r.embedded_key && typeof r.embedded_key === 'object' ? r.embedded_key : null
  if (keys.length && !known().dirExists) return [`${base} carries a key, and this machine has no key registry (${KEY_DIR}): a build that carries a key is released from Nick's PC, where the registry is`]
  for (const k of keys) {
    const e = whose(k)
    if (!e) out.push(`${base} carries ${describeKey(k)}: a key ships only after Nick registers it free for this repo (node tools/register-key.mjs free --repo ${path.basename(root)} --project "<Google project>" --no-billing)`)
    else if (e.tier !== 'free') out.push(`${base} carries ${describeKey(k)}: a paid key is NEVER built in`)
    else if (String(e.repo || '').toLowerCase() !== repo) out.push(`${base} carries ${describeKey(k)}, not this repo's: one key per app`)
    else if (e.status && e.status !== 'active') out.push(`${base} carries ${describeKey(k)}: register the replacement and rebuild`)
    else if (!declared) {
      const s = `${base} carries ${describeKey(k)} but the receipt has no embedded_key {fp, repo}: the drill must prove the built-in key works from the updated build (check embedded_key_works)`
      if (strict) out.push(s); else notes.push(s + ' — drill it, then --scan again')
    }
    else if (String(declared.fp || '').toLowerCase() !== fpOf(k)) out.push(`receipt embedded_key.fp is not the key built into ${base}`)
  }
  if (declared && /^[0-9a-f]{64}$/i.test(declared.fp || '')) {
    const e = known().keys.find((x) => String(x.fp || '').toLowerCase() === String(declared.fp).toLowerCase())
    if (!e) out.push('receipt embedded_key.fp is not in ~/.embed-keys/registry.json: register the key, then drill')
    else if (e.tier !== 'free' || String(e.repo || '').toLowerCase() !== repo) out.push(`receipt embedded_key.fp is ${e.tier === 'free' ? `${e.repo}'s key, not this repo's` : 'a PAID key'}`)
    if (declared.repo && String(declared.repo).toLowerCase() !== repo) out.push(`receipt embedded_key.repo is "${declared.repo}", this repo is "${path.basename(root)}"`)
  }
  if (!declared && drillManifest(root)?.embeds_key) out.push('drills/drill.json says this app builds a key in, but the receipt has no embedded_key: the drill must prove it (check embedded_key_works)')
  return out
}

// ── reading the git command ───────────────────────────────────────────────────────────────────────
const CD = /^(cd|chdir|pushd|set-location|sl|push-location)$/i
// Git Bash writes C:\Users as /c/Users; path.resolve on Windows would read that as C:\c\Users (the Director's own
// commit was refused with "could not run git" the minute the gate shipped, 2026-10-31)
const msysPath = (d) => process.platform === 'win32' && /^\/[a-zA-Z](\/|$)/.test(d) ? `${d[1].toUpperCase()}:${d.slice(2) || '/'}` : d
const STAGES = /^(add|rm|mv|stash|apply|am|cherry-pick|merge|rebase|revert|restore|checkout|switch)$/
/** The command inside a shell construct: `if (...) { git push }`, `do git commit …`, `{ … }`, `sudo env git …`. */
function unwrap(seg) {
  let s = seg.trim()
  for (;;) {
    const before = s
    s = s.replace(/^(if|elseif|foreach|while|switch|for)\s*\([^)]*\)\s*\{\s*/i, '').replace(/^(else|try|catch|finally|do)\s*\{\s*/i, '')
    s = s.replace(/^[{(]\s*/, '').replace(/\s*[})]+\s*$/, '')
    s = s.replace(/^(do|then|else|elif|time|env|nice|nohup|sudo|exec|command|builtin)\s+/, '')
    if (s === before) return s
  }
}
/** `cmd /c "…"`, `powershell -Command "…"`, `bash -c "…"`: the body those wrappers run. */
function bodyOf(w) {
  const exe = path.basename(w[0] || '').toLowerCase().replace(/\.exe$/, '')
  if (exe === 'cmd') { const i = w.findIndex((x) => /^\/[ck]$/i.test(x)); return i >= 0 ? w.slice(i + 1).join(' ') : null }
  if (/^(powershell|pwsh)$/.test(exe)) { const i = w.findIndex((x) => /^-(c|command)$/i.test(x)); return i >= 0 ? w.slice(i + 1).join(' ') : null }
  if (/^(bash|sh|zsh|dash|ksh)$/.test(exe)) { const i = w.findIndex((x) => x === '-c'); return i >= 0 ? w.slice(i + 1).join(' ') : null }
  return null
}
/** `git commit` / `git push` in a command, with the folder each runs in, what the same line staged before it, the
 *  message, the pathspecs. A `cd` carries forward; a folder held in a variable is reported, never guessed. */
export function gitWriteIntents(cmd, cwd = '.') {
  const found = []; let cur = null; let unknown = false
  const walk = (text) => {
    for (const seg of splitSegments(stripDataBodies(String(text || '')))) {
      let w = words(unwrap(seg))
      while (w.length && (w[0] === '&' || /^[A-Z_][A-Z0-9_]*=/.test(w[0]))) w = w.slice(1)
      if (!w.length) continue
      const exe = path.basename(w[0]).toLowerCase().replace(/\.exe$/, '')
      if (CD.test(exe)) {
        const d = w.slice(1).find((x) => !x.startsWith('-'))
        if (!d || isVar(d) || d === '-' || d.startsWith('~')) { unknown = true; cur = null } else { cur = path.resolve(cwd, cur || '.', msysPath(d)); unknown = false }
        continue
      }
      if (/^(popd|pop-location)$/i.test(exe)) { cur = null; unknown = false; continue }
      const body = bodyOf(w); if (body) { walk(body); continue }
      if (exe !== 'git') continue
      const gitExe = /[\\/]/.test(w[0]) ? w[0] : null
      let i = 1; let dir = null; let dirVar = false
      for (; i < w.length && w[i].startsWith('-'); i++) {
        if (w[i] === '-C') { const d = w[++i]; if (!d || isVar(d)) dirVar = true; else dir = d }
        else if (/^-C./.test(w[i])) dir = w[i].slice(2)
        else if (w[i] === '-c' || w[i] === '--git-dir' || w[i] === '--work-tree') i++
      }
      const verb = w[i]; const rest = w.slice(i + 1)
      const base = { seg, gitExe, dir: dirVar ? null : (dir ? path.resolve(cwd, cur || '.', msysPath(dir)) : cur), unknownDir: dirVar || (unknown && !dir) }
      if (STAGES.test(verb)) {
        const all = verb !== 'add' || rest.some((x) => /^(-A|--all|--no-ignore-removal|\.|\*)$/.test(x) || /^-[a-zA-Z]*A[a-zA-Z]*$/.test(x))
        found.push({ kind: 'stage', ...base, all, paths: verb === 'add' ? rest.filter((x) => !x.startsWith('-')) : [] })
        continue
      }
      if (verb === 'push') {
        let all = false; const pos = []
        for (let k = 0; k < rest.length; k++) {
          const x = rest[k]
          if (x === '--all' || x === '--branches' || x === '--mirror') all = true
          else if (x.startsWith('-')) { if (/^(-o|--push-option|--receive-pack|--exec|--repo)$/.test(x)) k++ }
          else pos.push(x)
        }
        const refs = pos.slice(1).map((r) => r.replace(/^\+/, '').split(':')[0]).filter(Boolean)
        found.push({ kind: 'push', ...base, all, refs: refs.length ? refs : ['HEAD'] })
        continue
      }
      if (verb !== 'commit') continue
      let all = false; const paths = []; const msgs = []; let messageFile = null; let pathsFile = null
      const TAKES = /^(--author|--date|-c|-C|--reuse-message|--reedit-message|--fixup|--squash|-t|--template|--trailer|--cleanup)$/
      for (let k = 0; k < rest.length; k++) {
        const x = rest[k]
        if (x === '--') { paths.push(...rest.slice(k + 1)); break }
        if (x === '-m' || x === '--message') { msgs.push(rest[++k] || ''); continue }
        if (x.startsWith('--message=')) { msgs.push(x.slice(10)); continue }
        if (x === '-F' || x === '--file') { messageFile = rest[++k] || '-'; continue }
        if (x.startsWith('--file=')) { messageFile = x.slice(7); continue }
        if (x === '--pathspec-from-file') { pathsFile = rest[++k] || '-'; continue }
        if (x.startsWith('--pathspec-from-file=')) { pathsFile = x.slice(21); continue }
        if (x === '-a' || x === '--all' || x === '--include' || x === '-i') { all = true; continue }
        if (/^-[a-zA-Z]+$/.test(x)) {                                           // a cluster: -am "msg", -qam, -sm
          if (x.includes('a') || x.includes('i')) all = true
          if (/m$/.test(x)) { msgs.push(rest[++k] || ''); continue }
          if (/F$/.test(x)) { messageFile = rest[++k] || '-'; continue }
          if (/[cCt]$/.test(x)) k++
          continue
        }
        if (x.startsWith('-')) { if (TAKES.test(x)) k++; continue }
        paths.push(x)
      }
      found.push({ kind: 'commit', ...base, all: all || paths.length > 0, paths, message: msgs.join('\n'), messageFile, pathsFile })
    }
  }
  walk(cmd)
  // what an earlier segment stages lands in the commit; the commit lands in the push: read what WILL be there
  let stagedAll = false; const stagedPaths = []; let committed = false
  for (const it of found) {
    if (it.kind === 'stage') { if (it.all) stagedAll = true; stagedPaths.push(...it.paths); continue }
    if (it.kind === 'commit') { if (stagedAll || stagedPaths.length) { it.all = true; it.untracked = stagedAll ? true : [...stagedPaths] }; committed = true; continue }
    if (it.kind === 'push' && (committed || stagedAll || stagedPaths.length)) { it.worktree = true; it.untracked = stagedAll ? true : stagedPaths.length ? [...stagedPaths] : false }
  }
  return found.filter((it) => it.kind !== 'stage')
}

function receiptsIn(dir) {
  const d = path.join(dir, 'drills')
  let names = []
  try { names = fs.readdirSync(d).filter((n) => n.toLowerCase().endsWith('.json')) } catch { return [] }
  return names.map((n) => {
    let r = null
    try { r = JSON.parse(read(path.join(d, n))) } catch {}
    return { file: path.join('drills', n), r }
  }).filter((x) => x.r && x.r.schema === 'update-drill/1')
}

/** Walk up from `start` to the folder holding .git (the repo the command runs in). */
function repoRoot(start) {
  let d = path.resolve(start || '.')
  for (;;) {
    if (fs.existsSync(path.join(d, '.git'))) return d
    const up = path.dirname(d)
    if (up === d) return path.resolve(start || '.')
    d = up
  }
}

function passingReceiptFor(root, { sha, tag }) {
  for (const { file, r } of receiptsIn(root)) {
    const hit = sha ? (Array.isArray(r.assets) ? r.assets : []).some((a) => a && String(a.sha256 || '').toLowerCase() === sha)
      : normTag(r.to_version) === normTag(tag)
    if (!hit) continue
    const p = receiptProblems(r)
    // the receipt is a summary; the drill's own log is the evidence, and it has to exist beside it
    if (!r.drill_log || typeof r.drill_log !== 'string') p.push('drill_log missing: commit the drill\'s own log and name it here')
    else if (!fs.existsSync(path.resolve(root, r.drill_log))) p.push(`drill_log ${r.drill_log} not found in the repo`)
    else {
      // 2026-10-31: six of fourteen repos hid drills/logs/*.log behind a template `*.log` ignore, so a receipt reached
      // GitHub without its evidence while this file check passed on the one PC that had the log. The evidence has to
      // travel with the tag: tracked in git (index or HEAD). Only this release-command path asks git; a shell that
      // cannot run git here cannot publish anyway, so that answer is a problem, not a pass.
      const ls = spawnSync('git', ['-C', root, 'ls-files', '--error-unmatch', '--', r.drill_log], { encoding: 'utf8' })
      if (ls.error) p.push(`could not ask git whether ${r.drill_log} is tracked (${ls.error.message}); commit the log and run this where git works`)
      else if (ls.status !== 0) p.push(`drill_log ${r.drill_log} is not tracked in git: \`git add\` it (check .gitignore for *.log; add !drills/logs/*.log) and commit it with the receipt`)
    }
    return { file, problems: p, r }
  }
  return null
}

// ── shell parsing (good enough for one command line; refuses what it cannot read) ───────────────────
function splitSegments(cmd) {
  const segs = []; let cur = ''; let q = null
  for (let i = 0; i < cmd.length; i++) {
    const c = cmd[i]
    if (q) { cur += c; if (c === q) q = null; continue }
    if (c === '"' || c === "'") { q = c; cur += c; continue }
    if (c === '\n' || c === ';' || c === '|' || (c === '&' && cmd[i + 1] === '&')) {
      segs.push(cur); cur = ''; if (cmd[i + 1] === c) i++; continue
    }
    cur += c
  }
  segs.push(cur)
  return segs.map((s) => s.trim()).filter(Boolean)
}
function words(seg) {
  const out = []; const re = /"([^"]*)"|'([^']*)'|(\S+)/g; let m
  while ((m = re.exec(seg))) out.push(m[1] ?? m[2] ?? m[3])
  return out
}
const isVar = (w) => /\$|%[A-Za-z_]+%|`/.test(w)

const SCRIPT_NAME = /(^|[\\/])[^\\/]*(publish|release|deploy|upload|promote)[^\\/]*\.(py|ps1|sh|bat|cmd|js|mjs)$/i
const INTERPRETERS = new Set(['python', 'python3', 'py', 'node', 'powershell', 'pwsh', 'bash', 'sh', 'cmd', 'call', 'start', 'uv', 'pipenv', 'poetry'])
// flags that take a value, so the value is not mistaken for the script
const VALUE_FLAGS = new Set(['-executionpolicy', '-ep', '-w', '-x', '-X', '--env-file', '--import', '--require', '-r'])
/** The script a command RUNS, if its name looks like a publisher; null when a script is only named. */
function scriptRun(w) {
  const first = path.basename(w[0] || '').toLowerCase().replace(/\.exe$/, '')
  if (SCRIPT_NAME.test(w[0] || '')) return w[0]                              // .\publish_release.ps1
  if (!INTERPRETERS.has(first)) return null                                   // grep / cat / git … name it, never run it
  for (let i = 1; i < w.length; i++) {
    const x = w[i]
    if (/^(-c|-e|-Command|--eval|-m)$/i.test(x)) return null                  // inline code or a module, not a file
    if (x === 'run' && /^(uv|pipenv|poetry)$/.test(first)) continue
    if (x.startsWith('-') || x.startsWith('/')) { if (VALUE_FLAGS.has(x.toLowerCase())) i++; continue }
    return SCRIPT_NAME.test(x) ? x : null                                     // the first positional is the script
  }
  return null
}

// A heredoc body or a PowerShell here-string is DATA: a chat_log entry naming `adb … install` in a table is not an
// install (JS hit that false positive, 2026-10-30, and routed around the lock with the Edit tool — the habit a guard
// must not teach). A body handed to a shell or to iex IS commands, so that one is still read.
const RUNS_BODY = /^(bash|sh|zsh|dash|ksh|powershell|pwsh|cmd|iex|invoke-expression|invoke-command|ssh)$/i
const PIPES_TO_SHELL = /\|\s*(bash|sh|zsh|dash|ksh|powershell|pwsh|cmd|iex|invoke-expression)\b/i
// `<<` inside quotes, or a `<<<` here-string, opens no body: reading one there would hide the lines after it
function insideQuotes(line, at) {
  let q = null
  for (let k = 0; k < at; k++) { const c = line[k]; if (q) { if (c === q) q = null } else if (c === '"' || c === "'") q = c }
  return !!q
}
function stripDataBodies(cmd) {
  const lines = String(cmd).split('\n'); const out = []
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const hd = /(?<!<)<<(?!<)(-?)\s*(['"]?)([A-Za-z_][\w.-]*)\2/.exec(line)
    if (hd && !insideQuotes(line, hd.index)) {
      out.push(line)
      const seg = line.slice(0, hd.index).split(/;|&&|\|\||\|/).pop().trim().split(/\s+/)
      while (seg.length && /^[A-Z_][A-Z0-9_]*=/.test(seg[0])) seg.shift()
      const consumer = path.basename(seg[0] || '').replace(/\.exe$/i, '')
      if (RUNS_BODY.test(consumer) || PIPES_TO_SHELL.test(line.slice(hd.index))) continue
      let j = i + 1
      while (j < lines.length && (hd[1] ? lines[j].replace(/^\t+/, '') : lines[j]).trimEnd() !== hd[3]) j++
      i = j                                                        // body and terminator dropped; no terminator = to the end
      continue
    }
    const hs = /@(['"])\s*$/.exec(line)
    if (hs) {
      let j = i + 1
      while (j < lines.length && !lines[j].startsWith(hs[1] + '@')) j++
      const closing = j < lines.length ? lines[j] : ''
      out.push(line.slice(0, hs.index))
      // run through iex & co, the body IS commands: keep them, minus the quote marks (an open ' would swallow them)
      if (/\b(iex|invoke-expression|invoke-command|powershell|pwsh|bash|scriptblock)\b/i.test(line + '\n' + closing)) out.push(...lines.slice(i + 1, j))
      if (closing) out.push(closing.slice(2))                      // the rest of the command after '@ (| Set-Content …)
      i = j
      continue
    }
    out.push(line)
  }
  return out.join('\n')
}

/** What a command would publish: a list of {kind, …} the gate must clear. */
export function publishIntents(cmd) {
  const found = []
  for (const seg of splitSegments(stripDataBodies(String(cmd || '')))) {
    let w = words(seg); const env = {}
    while (w.length && (w[0] === '&' || w[0] === '.' || /^[A-Z_][A-Z0-9_]*=/.test(w[0]))) {
      const m = /^([A-Z_][A-Z0-9_]*)=(.*)$/.exec(w[0]); if (m) env[m[1]] = m[2]
      w = w.slice(1)
    }
    if (!w.length) continue
    const exe = path.basename(w[0]).toLowerCase().replace(/\.(exe|bat|cmd)$/, '')
    const emuSerial = (s) => /^emulator-\d+$/.test(String(s || ''))
    if (exe === 'gh' && w[1] === 'release' && ['create', 'upload', 'edit'].includes(w[2])) {
      const verb = w[2]; const rest = w.slice(3)
      const flags = rest.filter((x) => x.startsWith('-'))
      const pos = []
      for (let i = 0; i < rest.length; i++) {
        const x = rest[i]
        if (x.startsWith('-')) {
          if (!x.includes('=') && /^(-t|--title|-n|--notes|-F|--notes-file|--target|--repo|-R|--discussion-category|--notes-start-tag)$/.test(x)) i++
          continue
        }
        pos.push(x)
      }
      const tag = pos[0]; const files = pos.slice(1).map((f) => f.split('#')[0])
      if (verb === 'create' && flags.some((f) => f === '--draft' || f === '-d' || f === '--draft=true')) continue
      // which repo it targets: the drill's own public test repo is judged differently (judge → isDrillRepo)
      const ri = rest.findIndex((x) => x === '--repo' || x === '-R')
      const repo = ri >= 0 ? rest[ri + 1] : ((rest.find((x) => x.startsWith('--repo=')) || '').slice(7) || null)
      if (verb === 'edit') {
        const publishes = flags.some((f) => /^--draft=false$|^--latest(=true)?$|^--prerelease=false$/.test(f))
        if (publishes) found.push({ kind: 'publish-tag', tag, seg, repo })
        continue
      }
      // a variable could be anything, including an installer: it has to be written literally to be hashed
      const installables = files.filter((f) => INSTALLABLE.test(f) || isVar(f))
      if (verb === 'create' && !installables.length) found.push({ kind: 'publish-tag', tag, seg, repo })
      for (const f of installables) found.push({ kind: 'asset', file: f, tag, seg, repo })
      continue
    }
    if (exe === 'gh' && w[1] === 'api' && w.some((x) => /releases/i.test(x)) &&
        w.some((x, i) => (/^(-X|--method)$/.test(x) && /^(POST|PATCH|PUT)$/i.test(w[i + 1] || '')) || /^--method=(POST|PATCH|PUT)$/i.test(x)))
      { found.push({ kind: 'raw-api', seg }); continue }
    // adb, also when its path sits in a variable (JS found "$ADB" -s <phone> install … walked straight past, 2026-10-30)
    const INSTALL_VERB = /^install(-multiple|-multi-package)?$/
    const isAdb = exe === 'adb' || (isVar(w[0]) && (/adb/i.test(w[0]) ||
      (w.some((x) => INSTALL_VERB.test(x)) && w.some((x) => /\.apk$/i.test(x)))))
    if (isAdb) {
      const i = w.findIndex((x) => INSTALL_VERB.test(x))
      if (i < 0) continue
      const emu = w.includes('-e') || w.some((x, k) => x === '-s' && emuSerial(w[k + 1])) || emuSerial(env.ANDROID_SERIAL)
      if (emu) continue
      // an APK held in a variable could be any build: it has to be written literally to be hashed
      for (const f of w.slice(i + 1).filter((x) => !x.startsWith('-') && (/\.apk$/i.test(x) || isVar(x)))) found.push({ kind: 'asset', file: f, seg })
      continue
    }
    // Tools that build-and-install in one step put bytes on a phone that no receipt can be matched to. On an
    // emulator they are the drill's own business; anywhere else, install the drilled file with adb instead.
    const deviceOf = (names) => {
      for (let k = 0; k < w.length; k++) {
        const x = w[k]
        for (const n of names) {
          if (x === n) return w[k + 1] || ''
          if (x.startsWith(n + '=')) return x.slice(n.length + 1)
        }
      }
      return null
    }
    const phoneInstall = (what) => found.push({ kind: 'device-install', seg,
      why: `"${seg}" ${what} on a device that is not an emulator, so its bytes cannot be matched to a drill receipt. ` +
        'Drill it on the emulator, then install that exact file with: adb -s <serial> install -r <file.apk>' })
    if (exe === 'flutter' && (w[1] === 'install' || (w[1] === 'run' && w.some((x) => /^--(release|profile)$/.test(x))))) {
      if (!emuSerial(deviceOf(['-d', '--device-id']))) phoneInstall(`puts a ${w[1] === 'install' ? 'release' : 'release/profile'} build`)
      continue
    }
    if ((exe === 'gradlew' || exe === 'gradle') && w.some((x) => /(^|:)install\w*(release|profile)$/i.test(x))) {
      if (!emuSerial(env.ANDROID_SERIAL)) phoneInstall('installs a release build on every connected device')
      continue
    }
    if (w.includes('install-apks') && (exe === 'bundletool' || w.some((x) => /bundletool[^\\/]*\.jar$/i.test(x)))) {
      if (!emuSerial(deviceOf(['--device-id']))) phoneInstall('installs a build')
      continue
    }
    // A wrapper script that publishes must carry the gate itself, or the gate never sees the gh line.
    // Only a script being RUN counts: the command itself, or the first positional argument of an interpreter.
    // A script merely NAMED (grep, cat, git add, an editor) is not run — NTWL hit that false positive, 2026-10-30.
    const script = scriptRun(w)
    if (script) found.push({ kind: 'script', file: script, seg })
  }
  return found
}

// ── the decision ─────────────────────────────────────────────────────────────────────────────────
/**
 * The drill's own public test repo, declared in drills/drill.json as `drill_repo` (UPDATE_DRILL §5): a shipped build
 * can only be pointed at a real GitHub repo, so the candidate has to be published THERE before any receipt can exist.
 * Allowed only when it is declared, its name says "drill", and it is not the app's real `release_repo`.
 */
function isDrillRepo(root, repo) {
  let m = null
  try { m = JSON.parse(read(path.join(root, 'drills', 'drill.json'))) } catch { return false }
  const norm = (r) => String(r || '').toLowerCase().replace(/^https?:\/\/github\.com\//, '').replace(/\.git$/, '')
  const want = norm(m?.drill_repo)
  return !!want && norm(repo) === want && /drill/.test(want) && want !== norm(m?.release_repo)
}

export function judge(cmd, cwd) {
  const root = repoRoot(cwd)
  const problems = []
  // #2.1 — `hard` problems are keys and secrets: Nick's release note never waives them
  const hard = []
  for (const it of gitWriteIntents(cmd, cwd || '.')) {
    if (it.unknownDir) { hard.push(`${it.kind}: cannot read the folder "${it.seg}" runs in (a variable, or a cd the gate cannot follow); write it literally so the right repo is scanned`); continue }
    if (it.gitExe) GIT = it.gitExe
    const dir = it.dir || cwd || root; const r = repoRoot(dir)
    if (!fs.existsSync(dir)) { hard.push(`${it.kind}: the folder "${it.seg}" runs in does not exist (${dir}); write the path the shell will really use`); continue }
    if (it.kind === 'commit') {
      let message = it.message || ''; const paths = [...it.paths]
      if (it.messageFile) { const m = it.messageFile === '-' ? '' : read(path.resolve(dir, it.messageFile)); if (!m) hard.push(`commit: cannot read the message in ${it.messageFile}; give it with -m`); else message += '\n' + m }
      if (it.pathsFile) { const m = it.pathsFile === '-' ? '' : read(path.resolve(dir, it.pathsFile)); if (!m) hard.push(`commit: cannot read --pathspec-from-file ${it.pathsFile}; name the paths on the line`); else paths.push(...m.split(/\r?\n/).filter(Boolean)) }
      hard.push(...secretProblems(r, { staged: true, all: it.all || paths.length > 0, untracked: it.untracked || false, paths, cwd: dir, message }).map((p) => `commit: ${p}`))
    } else {
      // a commit earlier on the line replaces files in HEAD: those are judged as they will land, not as HEAD has them now
      const changed = it.worktree ? [...zlist(gitAt(r, ['diff', '--cached', '--name-only', '-z'])), ...zlist(gitAt(r, ['diff', '--name-only', '-z']))] : []
      hard.push(...secretProblems(r, { refs: it.all ? allHeads(r) : it.refs, cwd: r, exclude: changed }).map((p) => `push: ${p}`))
      if (it.worktree) hard.push(...secretProblems(r, { staged: true, all: true, untracked: it.untracked || false, cwd: r }).map((p) => `push (what the commit before it lands): ${p}`))
    }
  }
  const intents = publishIntents(cmd)
  if (intents.some((it) => it.kind === 'asset' || it.kind === 'publish-tag')) hard.push(...secretProblems(root))
  for (const it of intents) {
    if (it.repo && isDrillRepo(root, it.repo)) continue               // publishing to the drill's test repo is the drill
    if (it.kind === 'device-install') { problems.push(it.why); continue }
    if (it.kind === 'raw-api') { problems.push(`"${it.seg}" publishes through the raw API, which this gate cannot read. Use gh release create/upload/edit.`); continue }
    if (it.kind === 'script') {
      const p = path.resolve(cwd || root, it.file)
      const body = read(p)
      if (!body) continue                                            // not a file we can see: not ours to judge
      // only a script that itself publishes: a build or release-notes script named *release* is not one
      // what makes a script a publisher, read off its body: gh release, the releases API written by hand
      // (SM's publish_release.py uses urllib, not gh), adb install, or the Play Developer API (play_deploy.py)
      const publishes = /\bgh\s+release\s+(create|upload|edit)\b|\badb\b[^\n]*\binstall\b|create_release|upload_release_asset|androidpublisher|bundles\(\)\.upload|internalappsharing/i.test(body) ||
        (/\/releases\b/.test(body) && /\b(POST|PATCH)\b|uploads\.github\.com|make_latest/.test(body))
      if (!publishes) continue
      if (!/release-gate\.mjs[^\n]*--check/.test(body))
        problems.push(`${it.file} looks like a publish script but never calls "node tools/release-gate.mjs --check <assets>" before publishing. Add that line (it must stop the script on a non-zero exit).`)
      continue
    }
    if (it.kind === 'publish-tag') {
      if (!it.tag || isVar(it.tag)) { problems.push(`cannot read the tag in "${it.seg}"; write it literally.`); continue }
      const hit = passingReceiptFor(root, { tag: it.tag })
      if (!hit) problems.push(`no drill receipt in drills/ for ${it.tag}.`)
      else splitReceipt(hit, `${hit.file} for ${it.tag}`, problems, hard)
      continue
    }
    if (isVar(it.file)) { problems.push(`cannot read the asset in "${it.seg}"; write the path literally so it can be hashed.`); continue }
    const p = path.resolve(cwd || root, it.file)
    if (/[*?[]/.test(it.file)) { problems.push(`cannot read the asset "${it.file}": a glob could match any build; write each path literally.`); continue }
    if (!fs.existsSync(p)) { problems.push(`asset ${it.file} not found from ${cwd || root}; cannot hash it.`); continue }
    let sha; try { sha = sha256(p) } catch (e) { problems.push(`asset ${it.file} cannot be read (${e.message}).`); continue }
    const hit = passingReceiptFor(root, { sha })
    if (!hit) problems.push(`no drill receipt in drills/ lists ${path.basename(p)} (sha256 ${sha.slice(0, 12)}…). A receipt for a different build does not count.`)
    else splitReceipt(hit, `${hit.file} lists ${path.basename(p)} but`, problems, hard)
    hard.push(...embeddedKeyProblems(root, p, hit ? hit.r : null))
  }
  return { root, problems, hard: [...new Set(hard)] }
}
/** A receipt's problems: the drill ones (the note may waive) and the key ones (it may not). */
const KEY_RECEIPT = /^embedded_key|^check "embedded_key_works"/
function splitReceipt(hit, label, problems, hard) {
  const drill = hit.problems.filter((p) => !KEY_RECEIPT.test(p)); const key = hit.problems.filter((p) => KEY_RECEIPT.test(p))
  if (drill.length) problems.push(`${label} does not pass: ${drill.join('; ')}.`)
  for (const k of key) hard.push(`${hit.file}: ${k}`)
}

/** Nick's one-shot note, if `matches(tag)` accepts its tag; consumed on use. */
function takeApproval(matches) {
  let ok = null
  try { ok = JSON.parse(read(APPROVAL)) } catch { return false }
  if (!ok || (ok.expiresEpochMs && Date.now() >= Number(ok.expiresEpochMs))) return false
  if (!ok.tag || !matches(String(ok.tag))) return false
  try { fs.unlinkSync(APPROVAL) } catch {}
  process.stderr.write(`RULE #28: released ${ok.tag} WITHOUT a drill, on Nick's one-shot note (${ok.reason || 'no reason given'}); note consumed.\n`)
  return true
}
// hook mode: the tag has to appear in the command itself
const approvalFor = (cmd) => takeApproval((tag) => String(cmd).includes(tag))
// CLI mode: a publish script names the tag it is about to publish (SM found the note could never reach
// a gated script otherwise: the hook passes the script because it carries --check, and --check refused)
const approvalForTag = (want) => takeApproval((tag) => normTag(tag) === normTag(want))

const MESSAGE = (problems, root) => `RULE #28 — RELEASE BLOCKED: no update drill, no release.
${problems.map((p) => ' • ' + p).join('\n')}

An update reaches users only after the PREVIOUS PACKAGED release, installed the way users have it,
updated ITSELF to exactly these bytes, and every check in the repo's memory/UPDATE_DRILL.md passed:
one install and no second folder, every shortcut opens the new version, it relaunched by itself,
user data intact, no update loop, the next release still visible, a bad download refused.
The drill writes drills/<version>.json (schema "update-drill/1") with the SHA-256 of each asset.
Check one:   node tools/release-gate.mjs --validate drills/<version>.json
Repo: ${root}
Only Nick can waive it, once, by having ~/.claude/release-approval.json written with this tag.
A publish script reaches that note by naming its tag: node tools/release-gate.mjs --check --tag <tag> <assets>`

const KEY_MESSAGE = (hard, root) => `RULE #2.1 — KEY BLOCKED: a free key may be built in, never committed; a paid key is never built in.
${hard.map((p) => ' • ' + p).join('\n')}

A key reaches a build only from %USERPROFILE%\\.embed-keys\\<RepoFolder>.json, registered free by Nick for that one repo
(node tools/register-key.mjs free --repo <RepoFolder> --project "<Google project>" --no-billing; fingerprints only, one key
per app, a Google project with no billing account). Check by hand: node tools/release-gate.mjs --scan [--staged] [<artifact>…]
Standard: memory/KEY_EMBED.md        Repo: ${root}
Nick's release note does not waive this; a leak is not a release decision.`

// ── entry points ─────────────────────────────────────────────────────────────────────────────────
const isMain = !!process.argv[1] && path.resolve(process.argv[1]).toLowerCase() === fileURLToPath(import.meta.url).toLowerCase()
if (isMain) {
  const args = process.argv.slice(2)
  if (args[0] === '--validate') {
    let r = null
    try { r = JSON.parse(read(args[1])) } catch {}
    const p = receiptProblems(r)
    if (p.length) { console.error(`FAIL ${args[1]}\n${p.map((x) => ' • ' + x).join('\n')}`); process.exit(1) }
    console.log(`PASS ${args[1]}`); process.exit(0)
  }
  if (args[0] === '--scan') {           // #2.1 by hand: what git holds, and what the named artifacts carry
    const root = repoRoot(process.cwd())
    const staged = args.includes('--staged'); const files = args.slice(1).filter((a) => !a.startsWith('--'))
    const hard = secretProblems(root, staged ? { staged: true, all: true, untracked: true, cwd: process.cwd() } : { cwd: root }); const notes = []
    for (const f of files) {
      if (!fs.existsSync(f)) { hard.push(`artifact ${f} not found`); continue }
      const r = passingReceiptFor(root, { sha: sha256(f) })
      hard.push(...embeddedKeyProblems(root, f, r ? r.r : null, { strict: false, notes }))
      const keys = keysInArtifact(f)
      console.log(`${path.basename(f)}: ${keys.length ? keys.map(describeKey).join('; ') : 'no key found in its bytes'}`)
    }
    for (const n of notes) console.log(`note: ${n}`)
    if (hard.length) { console.error(KEY_MESSAGE([...new Set(hard)], root)); process.exit(1) }
    console.log(`release-gate: no key or secret in ${staged ? 'the index, the worktree or the untracked files' : 'HEAD'}${files.length ? ', and the artifacts carry nothing that is not allowed' : ''}`); process.exit(0)
  }
  if (args[0] === '--check') {
    const root = repoRoot(process.cwd())
    const problems = []; const hard = secretProblems(root)
    let tag = null; const files = []
    for (let i = 1; i < args.length; i++) {
      if (args[i] === '--tag') tag = args[++i] || ''
      else if (args[i].startsWith('--tag=')) tag = args[i].slice(6)
      else files.push(args[i])
    }
    if (!files.length) problems.push('--check needs the asset paths it is about to publish')
    for (const f of files) {
      if (!fs.existsSync(f)) { problems.push(`asset ${f} not found`); continue }
      let sha; try { sha = sha256(f) } catch (e) { problems.push(`asset ${f} cannot be read (${e.message})`); continue }
      const hit = passingReceiptFor(root, { sha })
      if (!hit) problems.push(`no drill receipt in drills/ lists ${path.basename(f)} (sha256 ${sha.slice(0, 12)}…)`)
      else splitReceipt(hit, hit.file, problems, hard)
      hard.push(...embeddedKeyProblems(root, f, hit ? hit.r : null))
    }
    if (hard.length) { console.error(KEY_MESSAGE([...new Set(hard)], root)); process.exit(1) }   // before the note: never consumed for a leak
    if (problems.length && files.length && tag && approvalForTag(tag)) process.exit(0)
    if (problems.length) { console.error(MESSAGE(problems, root)); process.exit(1) }
    console.log('release-gate: every asset has a passing drill receipt and no stray key'); process.exit(0)
  }
  // hook mode
  let hook = {}
  try { hook = JSON.parse(fs.readFileSync(0, 'utf8') || '{}') } catch { process.exit(0) }
  if (!['Bash', 'PowerShell'].includes(hook.tool_name)) process.exit(0)
  const cmd = hook.tool_input?.command || ''
  if (!/\bgh\b|adb|install|publish|release|deploy|upload|promote|\bgit\b/i.test(cmd)) process.exit(0)   // fast path
  const cwd = hook.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd()
  let verdict
  try { verdict = judge(cmd, cwd) } catch (e) {
    // a bug in the gate must not brick the shell — but a command that commits or publishes is refused until the gate
    // is fixed (review 2026-10-31: a malformed receipt made judge() throw and the fail-open path let a paid key through)
    let writes = false
    try { writes = gitWriteIntents(cmd, cwd).length > 0 || publishIntents(cmd).length > 0 } catch {}
    if (!writes) process.exit(0)
    process.stderr.write(`release-gate: could not judge this command (${e.message}); it commits or publishes, so it is refused until the gate is fixed (node tools/release-gate.test.mjs).\n`)
    process.exit(2)
  }
  if (verdict.hard.length) { process.stderr.write(KEY_MESSAGE(verdict.hard, verdict.root) + '\n'); process.exit(2) }
  if (!verdict.problems.length) process.exit(0)
  if (approvalFor(cmd)) process.exit(0)
  process.stderr.write(MESSAGE(verdict.problems, verdict.root) + '\n')
  process.exit(2)
}
