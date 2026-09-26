# Director report — Happy Photo Organizer, 2026-09-26

Written to the eight headings supplied, in that order, unaltered. Delivered as a
file in the repo because that is the channel that works: three replies from this
session reached the rules session today and none arrived.

Everything below was measured on this machine today unless it says otherwise.

---

## 1. What the app does today

Happy Photo Organizer takes a marine electrician's work photos and files them
into a dated archive. Photos arrive three ways — dropped on the window, imported
from a folder, or **sent from the phone over Wi-Fi** — and the app resizes and
groups them by shooting day, asks Gemini for a job name per group, lets Nick
review and correct the names, then commits: each group becomes one folder named
`DD-MM-YY <job name>`, every photo inside renamed after its folder, and the
day number unique across the archive. A job that arrives from the phone skips
the AI and the review entirely: it is already named and grouped, so it is filed
straight through, carrying its report draft (`emr.json`) into the folder
untouched and recording which phone photo became which archive photo.

---

## 2. Version truth

| | Version | Evidence |
|---|---|---|
| Repo | **1.057** | `VERSION` at `HEAD` |
| Released | **1.057** | tag `v1.057`; `/releases/latest` returns it with the 91,607,708-byte installer |
| **Installed on Nick's PC** | **1.057** | uninstall registry: `DisplayVersion=1.057`, `InstallLocation=C:\Users\NickSuksanTr\AppData\Local\HappyPhotoOrganizer` |
| **Running right now** | **1.057** | the app's own `GET /jobshot/v1/ping` answers `version: 1.057, ready: true, ship: "ENA Test"` |

**The Director's reading is confirmed, from the registry, and independently by
the running process** — which is the better of the two, because the registry
records what an installer claimed and the ping records what is actually
executing. `dist/` was not consulted for any of it.

`ready: true` in that ping is itself the v1.057 fix working in the field: before
today the destination was forgotten on every start and the phone was told there
was nowhere to send.

---

## 3. The contract I read and write

**Authoritative document: `docs/LAN_PROTOCOL.md` in the JobShot repo.** It is
theirs, not mine, and it is the contract — when my code and that document
disagreed in v1.049, the document won on process even where my shape was better.

### What I accept from the phone
- **`job.json`** — the manifest. I require `"jobshot": 1` (a real int; `true` and
  `1.0` are refused), a non-empty `job_name`, and a non-empty `photos[]` list.
  I read `ship`, `work_date`, `job_id` and `created_at` but **do not require
  them** — see §7, which is where that matters.
- **`emr.json`** — the report draft. I never parse it. It is copied into the
  filed folder byte-for-byte, name intact.
- Any other `*.json` sidecar rides along the same way. The one trap: a name
  matching `job.json` or `job-*.json` is read as a manifest variant and is
  deliberately **not** carried as a sidecar.
- Over the wire, the zip gate accepts **images and JSON only** — traversal,
  absolute paths, device names, ratio and size caps unchanged.

### What I hand to EMR
The filed folder, and inside it the archived `job.json` with a **`filed` block
that is HPO's own record**, not the phone's:

```json
"filed": { "folder": "26-09-26 Inspected and Serviced FloodLight",
           "folder_date": "26-09-26", "work_date": "2026-09-26",
           "date_shifted": false, "merged_into_existing_folder": false,
           "grouped_with": [], "extras": ["emr.json"],
           "renamed": {"0001.jpg": "26-09-26 …_001.jpg", …},
           "hpo_version": "1.057", "filed_at": "…" }
```

### What the code does that the document does not describe
Named rather than left to be discovered:

- **`filed.renamed`** (v1.055) and **`filed.extras`** (v1.053) are mine. They are
  in the archived manifest, which is not the LAN document's territory, but EMR
  depends on both and nothing outside this repo specifies them.
- **`extras` in the §4 receipt** (v1.054) was agreed on the chain sheet with
  JobShot and shipped; whether `LAN_PROTOCOL.md` has caught up is theirs to say.
- **`CommitResult.already_done`** (v1.056) is internal and reaches nobody.
- **I have not re-read `LAN_PROTOCOL.md` line by line since v1.049.** Four tests
  pin the shapes I knew about then; anything added to that document since would
  not be caught by them.

---

## 4. Proven vs unproven

### ① Proven by a real run on this machine

- **The whole phone → archive path, 2026-09-26 14:18:55.** A real job from Nick's
  phone filed itself as `26-09-26 Inspected and Serviced FloodLight`: six photos
  renamed, `emr.json` carried through, `extras: ["emr.json"]` and the full
  `renamed` map in both the reply and the manifest, `date_shifted: false`.
  **I verified the join EMR depends on against that artifact** — the draft names
  `0001.jpg`–`0006.jpg`, the folder holds `…_001.jpg`–`…_006.jpg`, all six
  resolve. Without v1.055, shipped four hours earlier, that would have matched
  zero and the report would have printed complete with no photographs.
- **`GET /jobshot/v1/job/<id>` answering for that job**, live: `filed: true`,
  `folder`, `photos: 6`, `extras: ["emr.json"]`, `filed_at`.
- **The receipt book exists.** `jobshot_filed.json` was written at 14:18:55 with
  `extras` in it. It had never appeared before, which I had been carrying as a
  silent failure; it was never one — nothing had been filed on this machine
  since the version that made the failure report itself.
- **v1.057 remembering the destination.** Nick confirmed it in words
  (*"จำค่าแล้วครับ"*), the app's ping says `ready: true` on a fresh start, and his
  screenshot shows the log line order that matters: destination restored
  **before** the receiver starts listening.
- **The update cache reclaiming itself.** The Director measured 87.4 MB in
  `~/.happy-photo-organizer/updates`; after Nick installed 1.057 and restarted I
  measured **0 entries, 0.0 MB**.

### ② Proven by tests only — read this as *not yet proven*

- **v1.057's vessel fix.** `_jobshot_dest` returns early when a destination is
  already set; that was harmless while it was `None` on every fresh start, and
  **the restore I added in v1.057 is what made it dangerous** — a hand-dropped
  job from another vessel would have been filed into this PC's tree, and unlike
  the Wi-Fi path this one has no vessel guard. There is a test, and it was proven
  red against the old ordering. **The bug existed only in a state a real restart
  produces, and a fixture chooses its own state.** 136 green tests are not that
  proof. **Nick sends one real job after a genuine restart and this moves to ①,
  or it does not move.**
- v1.056's three fixes — clearing a finished batch, Commit not re-arming, the
  commit dropping its consumed sources. Nick has seen the button in a screenshot
  and the version banner; he has not run a batch through it in front of me.
- Phase 1 stepping past an abandoned `__pending_` folder.
- Every hostile-zip refusal. Real hostile input has never arrived.

### ③ Not proven at all

- **A second vessel.** Everything about per-vessel destinations has only ever run
  with one ship configured on one PC.
- **A month that is actually full** (30–31 day numbers used). The capped path is
  tested and has never happened in the archive.
- **A merged folder in production** — two jobs, same name, same day, two drafts.
  Tested; never seen.
- **The GUI itself.** No automated test opens a window. Every UI claim I made
  this month was wrong twice until Nick sent a screenshot.
- **A failed or resumed download.** The retry/resume path has never been
  exercised outside tests.

---

## 5. Every step that still needs a human

For the phone → archive half, which is mine:

| Step | Human? |
|---|---|
| Pair the phone (scan the QR) | **Once, ever.** Not per job, not per restart. |
| Allow HPO through the Windows firewall | **Once**, the first time it binds — and if it is refused, the symptom is "the phone says it sent and nothing arrived", indistinguishable from a bug. |
| Choose the destination folder | **Once.** Until v1.057 it was once *per app start*, which is what made sending fail at random. |
| Keep HPO open while sending | Yes — the receiver only runs while the app is open. |
| Everything else — accept, gate, name the folder, pick the date, resize, rename, carry the draft, write the map, answer the receipt | **None.** Measured on the 14:18:55 job: nobody touched the PC. |

**There is no retyping anywhere in my segment.** The engineer types the report
once, on the phone, which is the point of the chain.

**What I do not certify: EMR's half.** JobShot reports an F-04-TEC/03 printed
from a phone job. I have not watched that run and will not report another
project's state as fact. For the vessel-this-week decision, that half has to
come from EMR.

---

## 6. Open disagreements and questions

**With JobShot — none open.** Everything raised today closed with agreement,
including two of their positions they withdrew and one of mine. The live item is
Nick's, not ours: JobShot is asking him to confirm before removing the
`work_date_end` control they shipped yesterday.

**The multi-day consequence, which the Director asked me to include.** Nick has
ruled: one job = one day, existing rule, duplicates allowed when the month is
full. The consequence is that **a date range has nowhere to appear** — and that
is now settled rather than open, on a measurement rather than an argument:

- The folder **name** must never carry a range. Naming one `26-28.09.26` while
  the allocator reserved a single day claims days nothing reserved, and inside
  one batch `assign_unique_dates` could hand day 27 to another folder in the
  same pass — reader and writer disagreeing in one run.
- I proposed recording the span in `filed.work_date_end` instead. **EMR then
  opened the form: `F-04-TEC-03_template.docx` has exactly one date field.** No
  period, no from/to, no hours — they published the complete field list so
  nobody re-measures. The span cannot reach the printed document by any route
  without changing the form, and EMR's own answer to "would one date for three
  days be wrong as evidence?" is **no**: the `Date` field is the filing date of
  a report, not elapsed work, and a span that matters for a particular job
  already prints as a line of text inside Troubleshooting/Maintenance.
- My argument (an archive fact outlives whatever prints it) survives on its own
  terms, and does not survive both at once.

**CLOSED by Nick, 2026-09-26:** *"เอาออก — ไม่มีใครอ่านมัน"*. JobShot removed the
control in their v0.028 — screen, model and `emr.json` — and their generated
fixture now asserts the key is absent so it cannot drift back.
**`filed.work_date_end` closes unbuilt; HPO writes nothing and changed nothing.**

**With EMR — asked and now answered, and the answer matters.** They read
**`filed.extras`, `filed.renamed` and `filed.folder` out of every `job*.json`**
in the folder. Until today their own contract document said *"job.json is not
read at all"* — false since their v0.3.3 — so a tidy-up of my `filed` block
would have killed every photo tag on the printed report while every text box
still filled in. They have flagged both wrong sentences in place rather than
quietly correcting them.

**Acted on rather than noted:** the `filed` block's key set and the types of
those three fields are now frozen by a test, proven red against exactly the
change that would have done the damage (renaming `renamed` to `photo_map` in a
refactor). It is the same instrument as the §2/§3/§4 wire tests — if it goes
red the question is not "fix the test", it is "has EMR been told".

**One I am carrying alone:** the receiver binds a single interface address
chosen at startup. If that address stops being the reachable one — a PC with
both Ethernet and Wi-Fi, which is a ship — the failure is silent and points the
engineer at the network, the one place the fault is not. Agreed with JobShot to
record rather than change the bind.

---

## 7. What the other two rely on me for — and whether I guarantee it

I read `a-guard-the-other-side-props-up-is-not-a-guard` first, then went looking
in both directions. **It found something in my code on the day it was promoted.**

### What I assume the phone always sends — measured by removing each field

| Field removed | What happens |
|---|---|
| `ship` | **Manifest accepted. Job filed.** |
| `work_date` | Not filed — fails in `_read_arrival` |
| `job_id` | Filed, but no receipt written (warned) — §4 cannot answer for it |
| `created_at` | Filed, no effect |

**The first row is the defect.** The vessel guard reads
`if got and got != wanted` — so a manifest **with no `ship` skips the check
entirely** and is filed into whatever tree this PC is pointed at. The guard that
stops one vessel's job landing in another's archive works only because JobShot
always writes `ship`. It passes every test, on every run, for as long as they
keep the habit. **That is the promoted row, in my code, exactly.**

I am not fixing it unilaterally: it would start refusing manifests that are
accepted today, and refusing a real job of Nick's is worse than the risk it
closes. **Proposed and put to JobShot and Nick:** when this PC has a ship
configured and a manifest carries none, refuse it with *"this job does not say
which vessel it is from"* rather than file it. One line, one test, their
agreement first.

### What EMR relies on me for, and what I actually guarantee

| They rely on | Guaranteed? |
|---|---|
| `emr.json` carried byte-for-byte | **Yes** — asserted on bytes in the suite, and verified on the real job |
| `filed.extras` naming what is on disk | **Yes** — a failed copy is a warning and is left out |
| `filed.renamed` mapping every filed photo | **Yes for v1.055+.** Folders filed earlier have no map and cannot get one; EMR's rule for that row is theirs and correct |
| A missing key in `renamed` meaning the photo was never filed | **Yes** — it is only ever absent when the photo failed to resize |
| Photos existing under the names in `renamed` | **Yes** at filing time |
| `filed.folder`, `filed.extras`, `filed.renamed` keeping their names and types | **Yes, and now enforced** — frozen by `test_contract_the_filed_block_shape_is_frozen`, added after EMR told me they read all three (2026-09-26). Before that it was a convention nobody could see from either side |

**One gap I am naming rather than claiming:** `extras` reports what `shutil.copy2`
returned without error, **not that the bytes on disk are complete.** A copy that
succeeded and then lost the tail — a disk filling at exactly that moment — would
be listed as filed. The phone would then show the draft as safe to delete. It has
never happened, I have no evidence it can, and I have not added the check because
re-reading every sidecar has a cost for a failure nobody has seen. **Recorded so
that it is a decision rather than an assumption.**

---

## 8. Defects I have decided not to fix, and why

**The `.part` gap is closed, not deferred — and not by argument.** The
measurement said it cannot happen: `download_installer` writes straight to its
final `.exe` name, resumes by reading that file's size, deletes the partial when
retries are exhausted, and the module's only `tempfile` use is the debug log. But
"it cannot happen today" is a sentence, and the row promoted this afternoon says
a sentence is not a fix. **`cleanup_old_installers` now sweeps every file in the
cache except the one being kept**, proven red against the old suffix filter. A
`.part`, a `.tmp` or whatever a future refactor invents is reclaimed without
anyone remembering to widen anything. Third raising, closed with a change.

Genuinely not fixed:

- **The vessel guard skipping a manifest with no `ship`** (§7). Proposed, waiting
  on JobShot and Nick, because the fix refuses input that is accepted today.
- **`extras` not re-reading the bytes it claims** (§7). Cost against a failure
  never seen.
- **The receiver binding one interface address** (§6). The bind is deliberate —
  every interface not listened on is one the ship's network cannot reach us on.
  What is wrong is that the failure is silent; the fix is the PC noticing that
  `local_ip()` no longer matches what it bound, and it is on the chain sheet.
- **The updater's debug log is outside the sweep** — `%TEMP%\happy-photo-organizer-updater.log`,
  129.2 KB today, rotating at a 1 MB cap with one generation, so 1.9 MB worst
  case forever. Bounded, so left alone.
- **No automated test opens a window.** Every UI claim stays unverified until
  Nick sends a screenshot. I have not fixed this because a GUI test harness is a
  project, and the screenshot rule has caught both failures it needed to.
- **I have not re-read `LAN_PROTOCOL.md` since v1.049** (§3).

---

*HPO, 2026-09-26. Tests 136/136. Working tree clean, everything pushed.*
