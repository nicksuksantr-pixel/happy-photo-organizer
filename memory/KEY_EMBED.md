# KEY_EMBED — a free key may be built in, a paid key never (command_pattern #2.1)

> Nick, 2026-10-31: *"If it is a free key, build it in, the safest way there is. A paid key stays forbidden as before.
> Find what prevents a mistake and what checks it before it ships. Make the rule strict and the guard good; a key
> that goes wrong we delete from Google's key system."* Three apps (JobShot, HPO, EMR) built a key in that same evening.
> This is the standard; `tools/release-gate.mjs` enforces it; `tools/register-key.mjs` keeps the registry.
> Master: `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\KEY_EMBED.md` · every repo: `memory/KEY_EMBED.md`.

## 0 · The rule in four lines

1. **Nick names the apps that build a key in** (2026-11-01: "I say which project embeds; it is not a rule that an app must" — three today: JobShot, HPO, EMR). Such an app ships with a Gemini key built in, so the user never sees a key screen — **only a key from a Google Cloud
   project that has no billing account.** A key on a billed project is never built in, never in a repo, never in a build.
2. **One key per app**, from its own Google project with no billing account (Nick, 2026-10-31: *"no billing, and three
   different keys"*). Name a new one `embed-free-<app>` so the name itself reminds that it never gets billing; an existing
   project keeps its real name in the registry. If billing is ever attached, the key is retired first (§7).
3. **The key never enters git.** It lives outside every repo (`%USERPROFILE%\.embed-keys\<RepoFolder>.json`), the build
   reads it from there, and the registry records its **fingerprint** (sha256), never the key.
4. **The guard is in code, not in a sentence.** `release-gate.mjs` refuses a commit, a push, a release or a phone install
   that breaks any of this (§5). Nick's one-shot release note waives a *drill*, never a key.

## 1 · What "safest" means here, honestly

A key inside a client app can be read out by anyone who has the app: `strings` on the installer, `libapp.so` out of the
APK, a debugger. Masking (XOR, base64, splitting) only defeats casual scanners — and ours is one of them: a sealed key
is invisible to the gate's byte scan too, so a paid key sealed in by mistake would pass on the receipt's word alone.
**The key ships in plain text** (EMR asked, 2026-10-31); the protection is the model below, never the hiding. What protects Nick is the **model**, not the hiding:

| Protection | What it buys |
|---|---|
| No billing account on the key's project | A leaked key can cost nothing. The worst case is quota, never money. |
| One project per app, API-restricted to the Generative Language API | A leak or a revocation hits one app; the key cannot reach another Google API. |
| The key is disposable | Leaked or abused → delete it in the Google console → `retire` → new key → release under #28. The app keeps working meanwhile (§4). |
| Never in git, never in a record, never in a log | The only copies are `~/.embed-keys` on Nick's PC and the shipped build. |
| The gate | A mistake is refused before it reaches GitHub or a phone — in any Claude Code session (Nick's own terminal, VS Code and GitHub Desktop are not seen; a tracked `.githooks/pre-commit` running `release-gate.mjs --scan --staged` is the second net a repo may add). |

What it does **not** change — say it, do not hide it:
- **Quota is shared by every install of that app:** free tier is RPM 15 / RPD 500 / TPM 250k *per model, per key*. One
  user's batch can use the day's quota for all. The app says so when it happens (§4).
- **Free tier = Google may use the content, and human reviewers may read it** (Gemini API terms, 2026-03-23: content
  sent through unpaid services is used to improve Google's products; "do not submit sensitive, confidential, or personal
  information"). For HPO that is the user's photos, for EMR the ship's maintenance text. The app says so in one line in
  About/Settings.
- A key inside a **public** artifact (HPO's installer on a public repo) is readable by the world. Allowed only because the
  key is free, restricted and disposable; prefer a private distribution when the app has one (JobShot: phone over adb).
- Google retires the old `AIza…` Standard keys through 2026; AI Studio now issues `AQ.…` Auth keys. Any scan or validation
  that matches `AIza` alone is wrong (JS, 2026-10-31).

## 2 · Where the key lives

```
%USERPROFILE%\.embed-keys\
  registry.json          fingerprints only — written by tools/register-key.mjs, read by tools/release-gate.mjs
  <RepoFolder>.json      {"GEMINI_KEY": "<the key>"}   — the file the build reads; one per app; never copied into a repo
```
- `<RepoFolder>` is the project folder's name (`JobShot`, `Happy-Photo-Organizer`, `Engine-Maintenance-Report`): the gate
  matches the registry entry to the repo it runs in by that name.
- Not `keys/` or `secrets/` inside the repo, however well ignored: an ignore rule is one `git mv`, one `add -f`, one
  Backups zip away from public (both lessons are in SHARED_LESSONS). A repo-side guard test (JS's
  `no_key_in_source_test`, HPO's pre-commit) is welcome as a second net, never the only one.
- Nick's **paid** key stays where it is (the project's `.env` for development). Its fingerprint is recorded too
  (`register-key.mjs paid`) so a build or a commit that carries it is refused by name.
- Never in `C:\Users\Public` (the drill account's share), never in a chat, never in a record, never printed by a tool.
  The built product staged for a drill carries the key by design — that is the product, not a key file; no clash.

## 3 · Registering a key (Nick, once per app)

1. In the Google Cloud console: a new project `embed-free-<app>`, **no billing account**, an AI Studio key for it,
   restricted to the Generative Language API.
2. Write `%USERPROFILE%\.embed-keys\<RepoFolder>.json` with `{"GEMINI_KEY": "<the key>"}`.
   A key that already sits inside a repo (`secrets/gemini_key.txt`, `keys/gemini.json`) is moved by the tool —
   `node tools/register-key.mjs move --repo <RepoFolder> --from secrets/gemini_key.txt` — the one sanctioned write under
   `~/.embed-keys` for a session (rule #1 stands otherwise); the session then deletes the in-repo file.
3. `node tools/register-key.mjs free --repo <RepoFolder> --project "<the Google project's name>" --no-billing`
   — `--no-billing` is the attestation, on Nick's word, that the project has no billing account; refused without it, and
   refused for a key already registered paid or already registered for another app.
4. Once, for the paid key: `node tools/register-key.mjs paid --from <the .env that holds it> --note "Nick's paid key"`.
5. `node tools/register-key.mjs list` shows fingerprints and projects, never a key.

## 4 · In the app

- **No key screen at first run.** The app starts working with the built-in key.
- **An app that builds a key in has no own-key field or stored-key path — the built-in key is its only key** (Nick,
  2026-10-31, first to EMR: *"no place for others to enter a key at all — we built it in and hid it; remove that field
  and everything about entering a key"*, then to the Director: that is the house answer). Every path that reads a pasted
  or stored key goes — the field, Paste/Show/Test, the per-user key file, every message that points to Settings, hidden
  shortcuts included. The escape when the shared key is withdrawn or out of quota is the next release (§7), which is why
  the next bullet is not optional. An app shipped before this answer (HPO v1.067 with a hidden Ctrl+Shift+K path)
  removes it in its next version; a candidate not yet staged removes it before the drill.
- **An app that builds no key in keeps its own-key field** (Nick, 2026-11-01, in NotiWallet's chat: NotiWallet keeps the
  field — the user's own key is its only AI path and its payload is users' bank notifications). Such an app is outside
  this standard's embed clauses (registry, embed-free project, `embeds_key`) and inside #2 and the commit/push gate.
  Whether an app whose payload is personal or financial may ever build a free key in is Nick's line to draw (§8a).
- **A dead key never breaks the app.** On 400/401/403/429 or no network the AI step reports one readable line
  ("AI unavailable: key withdrawn / today's shared quota used up / offline — the app works without it; update when a
  new version is out") and everything else keeps working. Never a crash, never a silent "done" with every row failed
  (HPO found exactly that gap), never the key in a log or an error text.
- The app logs "ai: key built in" at most; it never logs the key, not even masked.
- One line in About/Settings, one sentence: *"AI runs on a free Google key shared by all installs; Google may use what is
  sent to improve its products."* (nothing about an own key — there is no field).
- The build **refuses to produce a keyless app with a hidden field** (HPO's spec exits 1 without the key file). An
  explicit override exists only for a test build, and a test build never ships (#28: rehearsal receipts are refused).

## 5 · The gate (`tools/release-gate.mjs`, the same PreToolUse hook as #28)

What it refuses, with the reason printed and no way past it in the command line:

| Command | Refused when |
|---|---|
| `git commit` | what will land holds a key-shaped string (`AIza`+35, `AQ.`+30…), the text of any registered key (whatever its shape), a `PRIVATE KEY` block, or a file that is a secret by its name (`.env`, `*.jks`, `*.keystore`, `*.p12`, `*.pfx`, `service-account*.json`, `release-approval.json`, `*gemini*key*.txt/json/key/env/bin`, `keys/gemini.json`, `secrets/*.txt/json/key/env`). "What will land" = the staged blobs read as bytes (binary, UTF-16, a zip inside); with `-a`/`-am`/a pathspec/`--pathspec-from-file` the worktree too; after a `git add` on the same line the files it adds; the commit message (`-m`, `-F`). A `cd`, a `-C`, an `if (…) { }`, a `cmd /c` / `powershell -Command` / `bash -c` body are followed; a folder held in a variable is refused, never guessed |
| `git push` | the tree of every ref the push names (`--all`/`--mirror` = every branch; nothing = HEAD) holds any of the above — including UTF-16 and NUL-bearing files; after a `git commit` on the same line, the worktree too. History below those trees is not read (§8's `git log -G` is the by-hand check) |
| `gh release …`, `adb install` to a phone, a publish script, Play deploy | HEAD holds any of the above, **or** the artifact's bytes (inside an APK/AAB/zip too) carry a key that is not registered **free** for **this** repo, is registered **paid**, belongs to **another** app, is **retired**, or is not declared in the drill receipt (§6), **or** `drills/drill.json` says `embeds_key: true` and the receipt declares nothing |

- A fixture line that must look like a key says `not-a-key` on the line and is skipped — a *registered* key is never skipped, marker or not. Nothing else is.
- By hand: `node tools/release-gate.mjs --scan` (HEAD), `--scan --staged` (index + worktree + untracked), `--scan <artifact>…`
  (what the bytes carry and whether the registry allows it; before the drill exists "the receipt says nothing yet" is printed
  as a note and exits 0 — an unregistered, paid, retired or other app's key still exits 1).
- A build that carries a key is released from Nick's PC, where `~/.embed-keys` is; a machine without the registry refuses it
  and says so (a cloud instance never releases a keyed build).
- Not seen: `gh pr create` (pushes a branch), `gh repo create --push`, `Start-Process git`, history under a pushed tree — the §8 check covers history by hand.
- A refusal because the gate could not READ what it must scan (a folder in a variable, a folder that does not exist yet, a message on stdin from a pipe) prints "RULE #2.1 — CANNOT CHECK" with the way to write the command so it can, never "KEY BLOCKED" (three sessions, 11-01). `git commit -F -` with a heredoc on the same line is read as the message.
- The note (`~/.claude/release-approval.json`) is read only after the key checks pass and is never consumed by one.
- A desktop installer compresses its payload, so the byte scan sees nothing inside an Inno/MSI package: for those the
  guard is the receipt (§6) plus `embeds_key: true` in `drills/drill.json`. Set it the day the app builds a key in.
- The gate fails OPEN without `node`, like every hook here; the rule is still the rule.

## 6 · The drill (#28) proves the built-in key works from the updated build

The receipt (`drills/<version>.json`) of an app that builds a key in carries:
```json
"embedded_key": { "fp": "<sha256 of the key>", "repo": "<RepoFolder>" },
"checks": { "embedded_key_works": { "result": "pass", "evidence": "models.get 200 gemini-3.5-flash-lite, called from the updated build at 20:41" } }
```
- The fingerprint, never the key; the gate refuses a receipt whose `embedded_key` holds a key-shaped string. `fp` is what the
  gate matches; `repo`, when given, must be this repo's folder name. The fingerprint is what the UPDATED build reports
  (JobShot searches TO's `libapp.so` for the key file's value; HPO's exe writes `logs\embedded-key-check.json`), never a value
  copied from the registry — a copied fingerprint would make a wrong key "pass".
- These receipt problems are never waived by Nick's release note: the note waives a drill, not the key proof.
- `embedded_key_works` = one real call made by the **updated** build with its **built-in** key. That is the only proof the key reached the shipped bytes and the shipped code reads it. A build that
  was made with the "no key" override, a masked key that does not unmask, a wrong `_MEIPASS` path, a stale
  `dart-define` — every one of these fails this check and nothing ships.
- `drills/drill.json` gets `"embeds_key": true` so a receipt that forgets the field is refused.

## 7 · Rotation — the safety valve Nick chose

A key that leaks, is abused, or is found in the wrong place:
1. Nick deletes it in the Google console (AI Studio → the project's keys). Every shipped build loses AI at once and keeps
   working without it (§4) — that is why §4 is not optional.
2. `node tools/register-key.mjs retire --repo <RepoFolder> --reason "…"` — the next release or install is refused until a
   new key is registered (`free` refuses to reinstate a retired key quietly; `--reinstate` only on Nick's word).
3. A new key in the same `embed-free-<app>` project (or a new project if the old one is compromised) → §3 → build →
   drill with `embedded_key_works` → release under #28.
4. A key found **in git** is rotated even if the repo is private: the history already holds it. Rewrite history only on
   Nick's word (force-push rule).

## 8 · Before a release — the checklist a session walks

- [ ] `~/.embed-keys/<RepoFolder>.json` exists; `register-key.mjs list` shows it **active · free** for this repo (registered with `--no-billing`)
- [ ] `node tools/release-gate.mjs --scan` clean; `--scan <installer|apk>` names the key as this repo's free key (APK; before
      the drill it adds a note to drill it) or finds nothing (compressed installer) — never UNREGISTERED, never PAID, never
      another app's
- [ ] `drills/drill.json` has `"embeds_key": true`
- [ ] the receipt has `embedded_key.fp` = the registry entry, and `embedded_key_works` passed from the updated build
- [ ] no key screen, no own-key field or path anywhere (hidden shortcuts included); the About/Settings line present
- [ ] the key's project has no billing (Nick's word in the registry, `--no-billing`); an API restriction to the Generative Language API is recommended, not required (Nick 11-01: HPO's key is a normal key like the others, no card)
- [ ] a dead key: the app says one line and goes on (tested with a well-formed fake key, not by reading the code)
- [ ] `git log --all -G'AIza[0-9A-Za-z_-]{35}|AQ\.[0-9A-Za-z_-]{30,}'` finds nothing in history (a public repo: this is the one that matters)

## 8a · Decisions recorded

- 2026-10-31 Nick: the three keys (JobShot, HPO, EMR) are **three different keys, each from a project with no billing**
  ("ไม่ผูกบัตร และคนละตัวกันเลย 3 อันนั้น"); JobShot registered first (project "JobShot", fp cfbcb564…).
- 2026-10-31 Nick, told first that EMR-releases and HPO's repo are public and anyone can take the key out: build it in anyway —
  the key is free, restricted, disposable (§7). A public artifact with a free key inside is therefore allowed.
- 2026-10-31 Nick, asked whether the `embed-free-*` projects should live in a separate Google account from the paid one:
  the account they are in **has no billing and no card at all** (checked) — so an abuse report cannot reach a paid
  project through it. Closed.
- 2026-10-31 Nick: **no own-key field in an app that builds a key in** (§4) — the house answer, not an EMR exception.
  *Corrected 2026-11-01:* "in any app" overreached — NotiWallet (no built-in key, bank data) keeps its field on Nick's word
  in its chat ("ยกเว้นได้"), and a server (LTB, key in Secret Manager) builds nothing in.
- 2026-11-01 Nick: **which app embeds a key is his call, app by app — never a rule that an app must** ("ส่วนที่ว่าโปรเจกต์ไหนจะให้ฝังคีย์ นิกจะเป็นคนบอกเอง"); three embed today. So no house line on payload classes is needed: an app asks Nick, and his answer settles it.
- Staging the drilled installer in `C:\Users\Public` carries the built-in key by design: that is the product, the same
  bytes the release carries, not a key file — no clash with "never stage a key or token in Public" (HPO asked, 2026-10-31).

## 9 · What this standard is not

- Not a licence to put a **paid** key anywhere but Nick's own `.env`. #2 stands.
- Not a promise of secrecy: the key is public the moment the build is. Everything above is what makes that acceptable.
- Not a server standard. A server that reads its key at runtime from a secret store (LTB: Secret Manager) builds nothing
  in: no registry entry, no embed-free project, no About line; #2 (the key never enters git) and the commit/push gate
  apply. A proxy that holds a key for a client app would be a different design, not yet in the house.

---
*2026-10-31 · written the evening the first three apps built a key in · enforced by `tools/release-gate.mjs` (tests in
`release-gate.test.mjs` §8) and `tools/register-key.mjs` (`register-key.test.mjs`).*
