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

import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const HOME = process.env.USERPROFILE || process.env.HOME || ''
const APPROVAL = path.join(HOME, '.claude', 'release-approval.json')
const INSTALLABLE = /\.(exe|zip|msi|msix|msixbundle|appinstaller|apk|aab|7z)$/i

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

const read = (f) => { try { return fs.readFileSync(f, 'utf8') } catch { return '' } }
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex')
const normTag = (t) => String(t || '').trim().replace(/^v/i, '')

// ── receipts ─────────────────────────────────────────────────────────────────────────────────────
/** Every problem with one receipt, as sentences. Empty = it passes. */
export function receiptProblems(r) {
  const out = []
  if (!r || typeof r !== 'object') return ['not a JSON object']
  if (r.schema !== 'update-drill/1') out.push('schema is not "update-drill/1"')
  const prof = PROFILES[r.profile]
  if (!prof) out.push(`profile must be one of: ${Object.keys(PROFILES).join(', ')}`)
  if (!r.from_version) out.push('from_version missing: which released build did the drill start from?')
  if (!r.to_version) out.push('to_version missing')
  if (r.from_version && r.to_version && normTag(r.from_version) === normTag(r.to_version))
    out.push('from_version equals to_version: an update drill starts from the PREVIOUS release')
  if (!/^[0-9a-f]{64}$/i.test(r.from_artifact_sha256 || ''))
    out.push('from_artifact_sha256 missing: the drill must start from the real released file, by hash')
  if (!Array.isArray(r.assets) || !r.assets.length || !r.assets.every((a) => /^[0-9a-f]{64}$/i.test(a?.sha256 || '')))
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
  return out
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
    const hit = sha ? (r.assets || []).some((a) => String(a.sha256).toLowerCase() === sha)
      : normTag(r.to_version) === normTag(tag)
    if (!hit) continue
    const p = receiptProblems(r)
    // the receipt is a summary; the drill's own log is the evidence, and it has to exist beside it
    if (!r.drill_log) p.push('drill_log missing: commit the drill\'s own log and name it here')
    else if (!fs.existsSync(path.resolve(root, r.drill_log))) p.push(`drill_log ${r.drill_log} not found in the repo`)
    return { file, problems: p }
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

/** What a command would publish: a list of {kind, …} the gate must clear. */
export function publishIntents(cmd) {
  const found = []
  for (const seg of splitSegments(String(cmd || ''))) {
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
  for (const it of publishIntents(cmd)) {
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
      else if (hit.problems.length) problems.push(`${hit.file} for ${it.tag} does not pass: ${hit.problems.join('; ')}.`)
      continue
    }
    if (isVar(it.file)) { problems.push(`cannot read the asset in "${it.seg}"; write the path literally so it can be hashed.`); continue }
    const p = path.resolve(cwd || root, it.file)
    if (!fs.existsSync(p)) { problems.push(`asset ${it.file} not found from ${cwd || root}; cannot hash it.`); continue }
    const sha = sha256(p)
    const hit = passingReceiptFor(root, { sha })
    if (!hit) problems.push(`no drill receipt in drills/ lists ${path.basename(p)} (sha256 ${sha.slice(0, 12)}…). A receipt for a different build does not count.`)
    else if (hit.problems.length) problems.push(`${hit.file} lists ${path.basename(p)} but does not pass: ${hit.problems.join('; ')}.`)
  }
  return { root, problems }
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
  if (args[0] === '--check') {
    const root = repoRoot(process.cwd())
    const problems = []
    let tag = null; const files = []
    for (let i = 1; i < args.length; i++) {
      if (args[i] === '--tag') tag = args[++i] || ''
      else if (args[i].startsWith('--tag=')) tag = args[i].slice(6)
      else files.push(args[i])
    }
    if (!files.length) problems.push('--check needs the asset paths it is about to publish')
    for (const f of files) {
      if (!fs.existsSync(f)) { problems.push(`asset ${f} not found`); continue }
      const sha = sha256(f); const hit = passingReceiptFor(root, { sha })
      if (!hit) problems.push(`no drill receipt in drills/ lists ${path.basename(f)} (sha256 ${sha.slice(0, 12)}…)`)
      else if (hit.problems.length) problems.push(`${hit.file}: ${hit.problems.join('; ')}`)
    }
    if (problems.length && files.length && tag && approvalForTag(tag)) process.exit(0)
    if (problems.length) { console.error(MESSAGE(problems, root)); process.exit(1) }
    console.log('release-gate: every asset has a passing drill receipt'); process.exit(0)
  }
  // hook mode
  let hook = {}
  try { hook = JSON.parse(fs.readFileSync(0, 'utf8') || '{}') } catch { process.exit(0) }
  if (!['Bash', 'PowerShell'].includes(hook.tool_name)) process.exit(0)
  const cmd = hook.tool_input?.command || ''
  if (!/\bgh\b|adb|install|publish|release|deploy|upload|promote/i.test(cmd)) process.exit(0)   // fast path
  const cwd = hook.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd()
  let verdict
  try { verdict = judge(cmd, cwd) } catch (e) { process.exit(0) }        // a bug in the gate must not brick the shell
  if (!verdict.problems.length) process.exit(0)
  if (approvalFor(cmd)) process.exit(0)
  process.stderr.write(MESSAGE(verdict.problems, verdict.root) + '\n')
  process.exit(2)
}
