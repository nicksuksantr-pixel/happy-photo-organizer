# Log — v1.048 (2026-09-23) — built for testing; shipped later inside v1.050

## Entry 1 — the LAN receiver, built inside out

Item 6 from the R&D Director, with Nick's own words as the specification:

> Turn the PC on, open HPO, scan a code to confirm the pairing from the app,
> over Wi-Fi — send, and carry straight on in HPO.

The reply is the feature, not the transport. Today the phone has to say *"the
PC has not confirmed this — keep the job"*, because it genuinely cannot know. A
LAN link lets the PC answer, and only then does "safe to delete from the phone"
become a state that exists.

Built in the order of where the damage would be, not where the work looked
biggest:

### 1. `core/jobshot_receive.py` — the dangerous half, first
Given the bytes of a zip, prove they are a job and nothing else.

- **Zip-slip is the headline risk and is treated as one.** Entry names inside an
  archive that arrived over a network are attacker-controlled strings, not
  paths. Whitelist validation (no `..`, no drive letter, no absolute path, no
  NUL, no reserved device name, no NTFS alternate stream, depth capped) **and**
  every destination re-resolved against the quarantine root after joining.
  `ZipFile.extract` does sanitise; "the library probably handles it" is not a
  security argument.
- Caps on the archive, the unpacked total, the entry count and the compression
  ratio — all before a byte is written.
- Only the two kinds of file a job is made of: photos and the JSON manifest.
- Quarantine first; nothing reaches `dest_root` until `split_arrivals` +
  `import_batch` — the path in production since v1.047 — have accepted it.
- The vessel guard, re-checked on arrival.

### 2. `core/jobshot_server.py` — the thin half
Two routes, token on both, bound to one LAN address, oversize refused on the
`Content-Length` before the body is read, every handler wrapped.

**A real bug the tests found and reading would not have:** answering a POST
without draining its body makes Windows reset the connection mid-send, so the
phone would see *"the Wi-Fi dropped"* where the truth was *"wrong token"* — the
one distinction pairing depends on. Refusals now drain a bounded 8 MB and close.

### 3. The path contract
The Director read both halves side by side and caught that they could not talk:
JobShot called `/jobshot/ping` and `/jobshot/upload`, this server served
`/jobshot/v1/*`. Kept the version prefix (an old phone gets a clean 404 instead
of a confusing 400, and two versions can be served during a fleet update), and
spent the casting vote on **`ping` as canonical because it is the word JobShot
had already published** — `hello` stays an alias so a phone built against
either word still pairs. The 404 now names the routes it does serve, because
the only client that will ever hit it is a phone on an older path.

### 4. `core/jobshot_index.py` — the receipt that outlives the request
The Director's last gap, and the one the design leans on: an upload can succeed
and the reply can still be lost, leaving the phone unable to tell *never
arrived* from *arrived and I missed the answer*.

`GET /jobshot/v1/job/<job_id>` answers afterwards, which also makes it the
double-tap guard — ask first, upload only on 404.

- **The index is a cache; the archive is the truth.** An entry is believed only
  while its folder still exists. Renamed by hand → the manifests are re-scanned
  and the new name returned. Deleted → 404, so the phone keeps its copy: better
  a re-upload than a job deleted from the only device that still has it.
- A merged job answers `filed: true` with the folder it merged into.
- Written by **every** route — the drop zone and the script too. The phone
  cannot tell how a job reached the PC and should not have to.

### 5. The ignition — and it was nearly missed again
`no-entry-point-is-not-finished`, the lesson written two days ago and promoted
into the master rules yesterday, **recurred on the very feature that produced
it**. The receiver was complete, secure, tested — and nothing in the UI called
it. The Director caught it with a ten-second grep. That is the point of the
lesson: building the engine *feels* like finishing, so the check has to be
mechanical rather than a matter of judgement.

- `ui/dialogs/pairing.py` — the QR, the address, the vessel this PC files for,
  and whether it is listening. The Windows firewall prompt is mentioned **on
  screen**, because "the phone says it sent and nothing arrived" is
  indistinguishable from a bug when the cause is a Defender dialog nobody
  clicked.
- A **Phone** button in the header, next to Settings.
- The receiver starts with the app **once paired** — after the first scan, the
  scan is not part of the flow any more. Before pairing there is no token, so
  it could accept nothing anyway and an open port would be pure exposure.
  Closing HPO stops it; the phone queues, which it already does.
- **The QR carries the port actually bound.** If 8765 is taken the server falls
  back to one the OS picks; a QR with the wrong number would pair a phone to
  nothing and look like a network fault.

## Verification

- `tests/test_core.py` **88/88** (64 → 88): hostile zips, the socket over real
  loopback requests, the receipt book, the port fallback.
- **Run, not read:** a smoke calling `MainWindow`'s own methods against a stub
  `self` — so the code exercised is the code that runs when Nick opens the app.
  Unpaired PC does not listen · paired one does · a real zip over the socket
  filed as `23-09-26 Bow Thruster Test` with both photos renamed · the app's
  log line appeared · the receipt answered · closing stopped the socket.
- That smoke left an empty `incoming/` folder in the real config directory,
  which was removed. The suite itself stays GUI-free and redirects the receipt
  book to a temp file before any test runs — the job-catalog trap from v1.047,
  one version older.

## Status: shipped inside v1.050 (2026-09-24)

Held back for a day exactly as written below, then **released on Nick's word**
("รีลิสเลย") as part of v1.050 without waiting for the phone-to-PC test. His
call to make: the receiver only listens after a pairing, so an unpaired machine
behaves precisely as it did before.

### The original reasoning, kept because it was right at the time

Nick's call, and mine to recommend: **the installer is built for testing on
this machine only — no GitHub Release.** The phone half (JobShot v0.011) now
calls the right paths, but nobody has confirmed a real phone can send yet, and
releasing an ignition with no engine on the other side is the v1.046 mistake in
a new costume. Release when a phone-to-PC test has actually passed.

⚠️ If anything changes before that release, bump to v1.049 — a published
v1.048 that differs from this locally-installed one would never be offered by
the updater.

## Not built
mDNS discovery. The QR is the path that has to work: the Director's own Tuya
evidence (a UDP announce found 1 of 3 devices where a TCP sweep found 3 of 3)
is reason enough not to depend on broadcast on a vessel's managed switches.

## Entry 2 — the reply shape was mine to agree, not to announce (v1.049)

The Director ran my receiver against a JobShot-shaped zip and found that my
upload reply does not match `docs/LAN_PROTOCOL.md` §3 — the document both halves
are built from, in the JobShot repo:

    document:  {"filed": true, "jobs": [ … ]}        filed = boolean, list = jobs
    mine:      {"ok": true, "filed": [ … ], …}       filed = LIST, no `jobs`

JobShot implemented the document, so its reader evaluated `body['filed'] != true`
against a List, threw, and reported **a completely successful upload as a
refusal** — the folder correctly on disk, the receipt sitting unread in the
reply, and the phone telling Nick the PC had refused the job. He would re-send,
it would merge harmlessly, and "safe to delete from the phone" would never
unlock.

The ruling went my way on substance — `ok` with parallel `filed`/`skipped`/
`warnings` says *partially* more cleanly than a boolean plus a `failed` array,
so the document was amended to describe what HPO sends — and against me on
process, correctly:

**I took the paths from that document and then announced a reply shape of my
own from the same page.** The document is the contract, not a description of
one. A deviation nobody writes down is a defect even when the code is better,
and this one was invisible to reading because both sides use the word `filed`
and only the *type* differs.

### What I did about it, beyond agreeing
Read the whole document instead of the part I had been quoted, and found two
more divergences the Director had not reached:

- **`app` was a display name.** §2 specifies `"app": "happy-photo-organizer"`;
  I was sending `"Happy Photo Organizer"`. If the phone compares that string,
  pairing fails for a reason no one would look for. Now matches.
- **`ready: false` carried no reason.** §2 says the phone shows the reason and
  does not send. Now it says "no destination folder chosen on the PC yet", so
  Nick learns what to fix before waiting on an upload rather than after.

And one thing the document offered that I was ignoring: the sender declares
`X-JobShot-Jobs`. §3's rule is that *a job in neither list is unconfirmed* —
which is only detectable if the declared count is checked, so a mismatch is now
a warning on the reply rather than a job quietly vanishing between two lists.

### The freeze, made mechanical
Four tests now pin the **shape** of what goes on the wire: the exact key set and
types of the upload reply, of `ping`, and of the receipt — including the detail
that `filed` is a **list** in §3 and a **bool** in §4. That is not a rule anyone
will remember; it is the precise trap that already cost one false failure.

If one of those tests fails, the question is never "fix the test". It is "has
the other half moved yet".

### Version
**v1.049** — v1.048 was built and handed to Nick for testing, so anything that
changes after it has to be a new number, or a published v1.048 would never be
offered to the machine already running one.

### Verification
`tests/test_core.py` **92/92** (88 + 4). The Director's independent run of the
live receiver passed twelve checks — wrong token, no token, unknown route, a
zip-slip attempt that escaped nowhere, a double upload creating no second
folder, §4 answering correctly, and the bind being narrow enough that
`127.0.0.1` was refused. The three that failed were his test reading `jobs`,
which is how this was found at all.
