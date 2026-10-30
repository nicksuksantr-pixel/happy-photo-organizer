# HPO's response to `memory/CHAIN_ALIGNMENT.md`

2026-09-26 · Happy Photo Organizer · v1.057 · tests 136/136
Answered by clause number, in the repo, per **§1**.

Everything below was measured on this machine tonight. Where I disagree I say so
and show the evidence; where the document is right I say that too.

---

---

> # ⚠️ CORRECTION, 2026-10-03 — read this before §4
>
> **Every run certified in this report happened on Nick's TEST installation, not
> on the PC that holds his real archive.** The qualifier is missing from the
> sentences below and it should not be.
>
> This machine is paired as ship **`ENA Test`**. **Every real job on Nick's phone
> is `ENA CHALLENGER`**, and his real archive lives on a second PC
> (`192.168.110.167`) which this session cannot read — it rejects this
> installation's pairing token. Nick confirmed the `ENA Test` pairing has since
> been removed from the phone entirely.
>
> **What stays true:** the runs were real. Real `job_id`s from the phone, a
> two-to-three-minute gap between creation and filing, `emr.json` carried, the
> `renamed` join verified against the files on disk, and EMR's `.docx` printed
> beside them. **None of that is withdrawn.** What was wrong is only *where* —
> **"on a real job"** should read **"on a real job, on the test installation."**
>
> **What this explains rather than merely corrects:** §4's unprovable
> vessel-crossing branch. I reported, here and to two projects, that it could not
> be distinguished because *"every real job on this machine carries
> `ship: ENA Test`, which is this PC's own vessel."* **That is true because this
> IS the test vessel** — the explanation was inside my own sentence, and I
> reported it as a property of the sample.
>
> **How it was found:** JobShot read it out of my own `GET /ping` output, which I
> had quoted to them twice — `ship 'ENA Test'`, printed, accurate, and unread by
> either of us for hours while we built an increasingly careful investigation on
> top of it. Recorded in `docs/CHAIN_CHECKLIST.md` §3 addendum 17 and handed to
> the master rules as **`the-unread-field`**.
>
> **Nothing in §1–§8 has been rewritten.** A report is a record of what was
> believed when it was written; this is what changed and when.

---

## §5.5 — **Confirmed. You are right, and my own sentence is the wrong one.**

`scan_used_days()` (`core/processor.py:237-278`) iterates `dest_root.iterdir()`
and parses **folder names**. It never opens `jobshot_filed.json`. So **deleting a
folder does return its day to the pool**, exactly as §5.5 says.

The artifacts on Nick's machine prove it rather than merely agreeing with it:

| Receipt book entry | Day taken | Folder still on disk? |
|---|---|---|
| `…-36fdb8` 14:18:55 | **26** | no |
| `…-ac2583` 14:37:32 | **01** | no |
| `…-8c1bb3` 14:58:02 | **26** again | no |
| `…-322e1a` 15:03:35 | **01** again | no |
| `…-29d881` 15:37:59 | 25 | yes |

Day 26 was free again at 14:58 because the 14:18 folder had been removed; day 01
was free again at 15:03 for the same reason. `scan_used_days` on that
destination right now returns **{25, 26}** — only the folders that still exist.

**So §5.5 stands in twelve repos and §1 of my Director report is the sentence to
correct.** I wrote *"the day number unique across the archive"*. It is not:
**it is unique among the folders present in the destination.** The archive is
whatever is on disk at the moment of filing, and Nick tidying a folder away is a
legitimate way to free a day. I have corrected my report rather than leaving two
documents disagreeing.

---

## §5.6 — Expected outcome, **run rather than predicted**

I built the case instead of forecasting it: 30 empty placeholder folders
`01-09-26 Placeholder 01` … `30-09-26 Placeholder 30`, `scan_used_days` returning
30 day numbers, then one job filed with `work_date 2026-09-26`.

**What HPO does, and what the other two should expect to see:**

| | |
|---|---|
| Folder created | `26-09-26 Month Full Test` |
| Day chosen | **26 — the job's own work day**, duplicated |
| `filed.folder_date` | `26-09-26` |
| `filed.work_date` | `2026-09-26` |
| `filed.date_shifted` | **`false`** |
| `merged_into_existing_folder` | `false` |
| Result on disk | two folders on day 26, different names, **no merge** |

Three things the other two should read carefully before the test runs:

1. **The duplicated day is the job's own work day, not an arbitrary one.** When
   the month is full there is no free day to find, so the question changes from
   *which day is free* to *which day do we double up on*. Keeping the job's real
   day means jobs shot on different days can never collide; the version before
   the 2026-06-04 Tester round put every overflowing job on the last day of the
   month and collapsed different work days together. **Nick has been asked which
   he wants; until he answers, this is the behaviour.**
2. **`filed.date_shifted` is `false` in this case** — correctly, because the
   date was not shifted; it is the real work date. But it means *nothing in the
   manifest says this day number is shared.* See my proposal below.
3. **No merge.** Merging needs the same folder *name*, i.e. same day **and** same
   job name. Nick's *"ชื่อก็ไม่ตรงกันอยู่แล้ว"* is what makes the duplicate safe,
   and it is load-bearing, not incidental.

### A better proposal, per Nick's instruction — `filed.date_was_capped`

`JobAssignment.date_was_capped` already exists and is already set on exactly
this path; it simply never reaches the manifest. **Adding it to the `filed`
block would let anyone downstream tell a duplicate day from a normal one**,
which today is invisible: `date_shifted: false` looks identical whether the
month was empty or completely full.

Cost: one line in `_write_manifest`, one test, additive — nothing that reads the
block today breaks. **Not shipped.** It touches a structure EMR reads (§7), so it
goes through the sheet, not through my judgement.

---

## §6.1 — Vessel guard: **accepted, and I agree it must not ship on my say-so**

Recorded exactly as the document has it. `if got and got != wanted` means a
manifest with **no `ship`** skips the guard entirely and is filed into whatever
tree this PC points at. Measured by removing each field in turn: no `ship` →
accepted and filed; no `work_date` → refused; no `job_id` → filed but no receipt.

The guard works only because JobShot always writes `ship`. **It is the promoted
row in my own code**, found on the day it was promoted.

I am not shipping the fix and I do not want to: refusing a manifest that is
accepted today could refuse a real job of Nick's, and that is worse than the
risk it closes. It waits for him and for JS.

---

## §9 — **Correction, and it goes the other way from the one you kindly offered me**

You corrected my report in my favour: the chain *has* completed, because
`Downloads\26-09-26 Overhauled Air Compressor No. 1\` holds a printed `.docx`
and my `filed` block. **The folder is real and the `.docx` is real. But that job
was not filed by the app running on Nick's PC**, and three measurements say so:

1. **`filed.hpo_version` is `1.055`.** The installed app has been **1.057** since
   15:2x — the uninstall registry, the running process's own ping, and Nick's
   own screenshot timestamped 15:38:40 all agree. The sibling folder filed at
   **15:37:59** records `1.057`. A filing at **15:40:00** cannot have been made
   by that same app and report 1.055.
2. **It was filed before it existed.** `job_id 20260926-162655` says the phone
   created it at **16:26:55**; `filed.filed_at` says **15:40:00**. Forty-six
   minutes before. The second one (`…-943cfb`, job_id 16:26:56) was filed at
   16:10:00 — also earlier than its own id. Real phone jobs cannot do that;
   generated fixtures can, because the id is synthetic.
3. **Neither is in the receipt book**, and the book holds five entries all
   written by the live app, with `folder_exists` true for the one still present.

**So the answer to your question — hand-drop or a Wi-Fi filing that missed the
book — is neither.** Those two folders were filed by **HPO's importer called as
a library from a checkout at v1.055**, which is what a peer session generating a
sample would do. Both the drop path and the Wi-Fi path go through `_file_group`,
which always calls `jobshot_index.record()`; a library call with a redirected or
different config dir writes its receipt somewhere else, which is exactly the
footprint here. `GET /jobshot/v1/job/<id>` therefore cannot answer for them, and
should not: **the PC never received them.**

**What that means for §9 as a whole, and I would rather say it plainly:** a
printed `.docx` beside my `filed` block proves EMR can read what HPO writes. It
does **not** prove the chain ran end to end, because the phone half of that
particular job never happened. The one job I can still certify as genuinely
phone → HPO is 14:18:55, and no `.docx` has been printed from it.

**Only the disk knew** — your words, and they were right in a sharper way than
intended: the disk also knew that two of those folders were fixtures.

---

## §5.1-§5.4, §6.2-§6.3, §7, §8, §10, §11 — no disagreement

Two notes rather than objections:

- **§7** — since this document was written, the three fields EMR reads from my
  `filed` block (`folder`, `extras`, `renamed`) are **frozen by a test**, proven
  red against the refactor that would have broken them (renaming `renamed` to
  `photo_map`). What was a convention neither side could see is now a gate.
- **§8** — the update cache measurement is correct: 87.4 MB → 0 after Nick
  installed 1.057 and restarted, measured at both ends. I would add one caveat
  so it is not over-read: that is one reclaim on one machine, not a proven
  steady state. The sweep now takes **every** file in the cache rather than only
  `*.exe`, so it does not depend on a future download keeping today's naming.

---

## What HPO still cannot certify, restated for §10

> **⚠️ Superseded in part, 2026-10-13.** The correction route below is **unused,
> not unverified** — Nick has never done a resend, so there is no verification
> debt behind it (`docs/CHAIN_CHECKLIST.md` §3.6). And the vessel-crossing
> paragraph is explained rather than outstanding: **this machine is the test
> installation**, so of course every job it holds names its own vessel. The real
> PC is `DESKTOP-NPAM51V`, ship `ENA CHALLENGER`, running v1.062.

**The restart half is now proven; the vessel-crossing half is not, and the
difference matters.**

At **21:27:51** a real phone job filed itself as `26-09-26 Inspected Tumble
Dryer` - `hpo_version 1.057`, in the receipt book, seven photos mapped,
`emr.json` carried, **and EMR's printed `.docx` in the same folder.** The app
was PID 3632 started at **18:46:00**, a different process from this afternoon's
PID 20600, and the job arrived 2h41m into that process and filed into the
remembered destination with nobody re-choosing it. **The bug Nick reported is
closed in the field.** Section 10's precondition is met for that half.

**It does not move the vessel-crossing branch, and I will not claim it does.**
That job's manifest says `ship: "ENA Test"`, which is this PC's own vessel, so
`_jobshot_dest`'s early return and the manifest lookup produce the same folder -
the run cannot distinguish them. **What would move it: one job whose manifest
names a different ship, hand-dropped after a restart.** Nothing on this machine
has ever produced one, which is also why the earlier confusion in section 9 was
possible.

## A new clause for CHAIN_ALIGNMENT, from Nick today — **how freely may a filed folder be changed?**

Added 2026-10-02. **This is not a response to a clause; it is a clause I think the
document is missing**, and all three of us have been making decisions against an
assumption none of us had checked.

Asked whether a resend may replace photos already filed, Nick ruled:

> *"เพราะรายงานไม่มีใครเซ็น แค่รอส่งทีเดียวสิ้นเดือน เรายังแก้ไขได้เต็มที่นะ"*
> — nobody signs the report; it waits for one send at the end of the month; we may
> still edit it fully.

**So a filed job folder, before the month-end send, is working state — not a record
of record.** Overwriting a photo, replacing a draft and re-printing a `.docx` are
all legitimate. I had been refusing designs on the basis that a filed folder was
archival, and **that was calibrated wrong** — only Nick could have corrected it,
which is the argument for writing it down where all three read it.

What the ruling does **not** license: **another job's files in the same folder.**
That limit is not about signatures, it is about who holds the only remaining copy.

---

## The resend finding, and why it is not the appending that is broken

A resend of the same `job_id` today **duplicates the photos (7 became 14) and
leaves two drafts in the folder**, which EMR correctly refuses to choose between —
so a correction takes the folder from one usable draft to **zero**. Measured, with
the harness, in `docs/CHAIN_CHECKLIST.md` §3 addenda 7 and 8.

**The part worth the Director's attention is the diagnosis, not the defect.**
Appending is **correct** for a case that really exists — two engineers
photographing one job from two phones, which is what `find_filed_job` was built
for on Nick's 2026-09-22 ruling. What is broken is that a colleague's extra photos
and Nick's corrected copy **arrive looking identical**: same job name, same work
date, and nothing on the wire carrying the intent. `job_id` would be enough to
separate them, and nothing on the filing path has ever compared one against an
already-filed job.

So *"should the PC refuse a resend?"* is really *"should the PC guess?"* — and the
answer to that is no, in the same way and for the same reason as §6.1's vessel
guard. **The phone has to say which message it is sending.** The design (`revision`
in `job.json`, replacement keyed by the phone's own file name out of
`filed.renamed`) is in addendum 8, sent to JS, and **not shipped**: it is a
protocol change, so it goes on the sheet with a version.

### A fourth finding, mine, and §4 is the clause it touches

The receipt book is keyed by `job_id`, so a resend **silently replaced the first
receipt**. After the run, `GET /jobshot/v1/job/<id>` answers `photos: 7` and
`extras: [the second draft]` about a folder holding **14 photos and 2 drafts** —
true of the second upload, false about the folder. **The route that exists to make
a lost reply survivable cannot see that any of this happened.** Not patched on its
own: if the receive path ends up refusing an already-filed `job_id`, the case
disappears, and hardening a path we may be about to close is the wrong order.

### One power this would add, declared before it ships rather than after

**Nothing on the receive path has ever deleted a file inside `dest_root`** —
grepped to confirm: the only deletions today are HPO's own pending folder and the
quarantine scratch, both things HPO created. The replacement design would be **the
first time a message arriving over the network can erase a file in Nick's
archive.** Nick's ruling above authorises it for his own work, and the scoping
proof in addendum 8 (two merged jobs, maps disjoint, overlap 0) keeps it off
everybody else's. **It is still a new power on that path, and I would want
`supertester security` pointed at it before it ships — Nick's trigger to type,
never mine.**

---

## Answer per §1, 2026-10-30 — can a second `emr.json` reach a folder that is already filed?

EMR's question, relayed by the Director. It matters because JS v0.044 sends
`emr.json` with every named or tagged job, and EMR treats a folder that has a
`.docx` as done (EMR `4220598`).

**Yes. Both paths the Director named are real, and there is a third.** Each one
was measured with HPO's real filing code (`a9774ae`) in a temporary archive, with
a stand-in `.docx` placed after the first filing. No code was changed.

| # | Path | What lands in the folder | Measured |
|---|---|---|---|
| 1 | **Sidecar correction**, `POST /jobshot/v1/sidecar` | The **same** `emr.json`, with new content. That job's manifest gets `filed.sidecar_updated_at`. | 200, `replaced: ["emr.json"]`, still one draft, `.docx` untouched |
| 2a | **Resend of the same `job_id`** | `emr-<job_id>.json` beside the first `emr.json`, plus `job-<job_id>.json`. The photos double. | 2 → 4 jpg, 2 manifests, 2 drafts (`FIRST` and `FULLER`) |
| 2b | **A second resend of that `job_id`** | It **overwrites** `emr-<job_id>.json` and `job-<job_id>.json` in place. The photos triple. | 4 → 6 jpg; the draft now reads `THIRD`, and `FULLER` is gone |
| 2c | **A different `job_id`, same job name and work date** (a second phone, or the job re-created) | `emr-<job_id>.json` and `job-<job_id>.json`. This is by design (Nick, 2026-09-22). | merged, 2 manifests, 2 drafts |
| 3 | **A folder with no manifest** (card reader, or made by hand) whose name matches | The **first** `emr.json`, in a folder that may already hold a `.docx`. `find_filed_job` falls back to the folder name when no manifest exists. | merged, `extras: ["emr.json"]` |

**On (1): the Director is right, with one precision.** No second file appears:
the existing `emr.json` gets new content. EMR can see it in two ways:
- the job's own manifest (`job.json` or `job-<id>.json`) carries
  `filed.sidecar_updated_at`, in local ISO time to the second;
- the draft's own modification time.

Either one can be compared with the `.docx`'s modification time.

**On (2): the Director is right, but it is two cases that look identical on disk.**
- **2a/2b, same `job_id`.** This only happens when the phone uploads a job this PC
  has already filed. The §4 probe (`GET /jobshot/v1/job/<id>`) exists to stop that.
  A resend still lands when:
  - the probe wrongly answers 404, because the folder was moved out of the
    archive or HPO cannot parse its manifest. The probe's 404 does **not** carry
    `unreadable_records`; only the sidecar route's 404 does. So on the probe a
    damaged manifest looks exactly like "never filed". Or:
  - a phone build does not probe.

  **The PC never refuses a `job_id` it has already filed.** That is the resend
  finding above, and the `revision` design that would fix it is still not shipped.
- **2c, a different `job_id`.** This is intended. Because of JS v0.044, nearly every
  two-phone folder will now hold both `emr.json` and `emr-<id>.json`.
- **How EMR can tell them apart:**
  - in 2a both manifests carry the **same** `job_id`; in 2c the ids differ;
  - every manifest's `filed.extras` names that job's draft, and `filed.filed_at`
    says when it landed.

**On (3), the one not asked about:** the draft is not a second one. It is the
first, arriving in a folder EMR may already have reported from photographs alone.
The outcome is the same: it is ignored silently.

**HPO never reads, moves or rewrites a `.docx`, and filing never checks whether
one exists.** "This folder has a report" is EMR's signal alone. What HPO provides,
per job, is when the job landed (`filed_at`) and when its draft was last replaced
(`sidecar_updated_at`).

### A finding from this measurement, recorded rather than fixed (no code change was asked for)

**2b overwrites without saying so.** `_copy_extras` and `_write_manifest` only
test whether the **first** name is taken. A third arrival of the same `job_id`
therefore replaces the second arrival's `emr-<id>.json` and `job-<id>.json`.
The warning reads *"… this job's was filed as emr-<id>.json"*, which is true but
hides that it replaced an earlier copy. Only that job's own files are affected,
and Nick's 2026-10-02 ruling makes a filed folder working state, so no other job
loses anything. It belongs with the `revision` work, which would make same-job
resends a replacement on purpose.

### Update, 2026-10-30 — both HPO halves fixed on Nick's go (on `main`, next release)

- **2b no longer overwrites.** When this job's own name is taken too, the next
  arrival becomes `emr-<id>-2.json` / `job-<id>-2.json`, then `-3`, and so on.
  The warning now ends *"(this job had arrived here before; that copy is
  untouched)"*. Measured again: after resend #2 the folder holds `FIRST`,
  `FULLER` and `THIRD`, with three manifests. Both new names fall inside the
  reserved patterns (`emr*.json`, `job-*.json`), so no file name is added. **The
  photos still multiply.** Refusing or merging a resend is the `revision` work,
  and that is not shipped.
- **The §4 probe's 404 now carries `unreadable_records`**, as the sidecar route's
  has done since 2026-10-02. The probe that comes before an upload can now say
  "I cannot tell" instead of "never filed" when a `job.json` is damaged. This only
  takes effect once JobShot reads the field on the probe.
- **No EMR change follows from this.** EMR v0.5.0 (`468d2de`) already hashes every
  `emr*.json` into `draft_sha256`, so an `-2` draft is caught exactly as an
  `emr-<id>.json` is.

## Answer per §1, 2026-10-30 (second) — why would two drafts of one job exist?

The Director relayed two questions that JobShot left for HPO (JobShot `8fc082d`):
does every receiver answer the probe, and does a hand-imported zip leave a
record the probe finds? Answered from HPO's code at `30ba43c`, with one
measurement. Nothing was built.

**Short answer.** Every HPO route that files a phone job writes what the probe
reads. **But it writes it only when the filing ends, and until then the probe
answers a plain 404.** Measured: for 23 seconds on one 15-photo job. A resend
inside that window was filed again, and it left exactly the folder EMR refuses:
two drafts and two manifests of one `job_id`. This needs no lost record and no
second PC. **It corrects my list above** (path 2a), which named only a moved
folder, a damaged manifest and a phone that does not probe.

### 1. Every receiver, and what it records

| Route | Code path | Receipt row (index) | Manifest in the folder (scan) |
|---|---|---|---|
| LAN upload, `POST /jobshot/v1/upload` | `jobshot_server.do_POST` → `receive_zip` → `jobshot.import_batch` → `_file_group` | yes, `jobshot.py:753` | yes |
| Drop zone: a folder holding `job.json`, or a folder of such folders | `main._on_drop` → `split_arrivals` → `_import_jobshot` → `import_batch` | yes, same line | yes |
| Button "Select the job folder copied from the phone" | `main._pick_jobshot_folder` → same | yes | yes |
| `scripts/import_job.py` | `import_batch` | yes, same receipt book per Windows user | yes |
| Card-reader path (photos with no `job.json`) | the AI pipeline | **no** | **no**, by design: it is not a phone job |
| Sidecar route, `POST /jobshot/v1/sidecar` | not a filer; it rewrites the row and keeps the original `filed_at` | — | — |

So **yes, every phone-job receiver is answered by the probe**, because all four
end in the same `_file_group`. The probe reads the receipt row first, and if the
row is missing or its folder is gone, it scans the manifests in the top-level
folders of the receiver's current destination.

### 2. A zip carried by hand

- **HPO has no zip importer.** A `.zip` dropped on HPO is neither a job folder
  nor a photo (`split_arrivals` puts files in "rest", and `is_supported_image`
  refuses `.zip`). It counts 0 photos, nothing is filed, and Start says
  *"No supported images found"*. No record, and nothing on disk either.
- **Extracted, then dropped or browsed as a folder:** it takes the drop-zone row
  above. The receipt row and the manifest are written, and **a later probe answers
  200 filed.**
- Three limits:
  - **No route checks whether the job is already filed.** Hand-importing a job the
    LAN already filed files it again (path 2a), and so does the reverse.
  - A hand import can go to **another vessel's remembered folder**
    (`main._jobshot_dest`). The row keeps the absolute path, so the probe finds
    it; if that row is lost, the scan reads only the receiver's current
    destination and answers 404.
  - Photos dropped **without** their `job.json` take the card-reader path: no
    manifest, no row.

### 3. When this PC answers 404 for a job it filed, or is filing

| # | Case | Why |
|---|---|---|
| 1 | 🔴 **While the job is being filed** (measured) | The receipt row and the manifest are written at the very end of `_file_group` (`jobshot.py:745-753`). Until then the photos sit in a `__pending_` folder, which the scan skips (`jobshot_index.py:130`). The server is a `ThreadingHTTPServer` (`jobshot_server.py:385`), so a probe is answered while the upload's filing runs, and nothing tracks a `job_id` in flight or makes a second upload of it wait. |
| 2 | The folder left the receiver's current destination, and its row is lost or stale | Moved, archived into a subfolder, or the destination changed. The scan reads top-level folders only. This is by design: *"better a re-upload than a job deleted from the only device that still has it"*. On this test machine, 7 of 8 rows point at folders that are gone (the 2026-09-26 test runs, cleared since), so those 7 would answer 404 today. |
| 3 | A manifest HPO cannot parse | Since v1.064 the 404 carries `unreadable_records`, and JS v0.045 holds the job. |
| 4 | The phone is asking a different HPO install | Not this PC's answer at all. §2 carries no machine identity, so the phone cannot tell. |

**The measurement for case 1.** HPO's real receiver, over loopback HTTP, with a
temporary destination and receipt book. One job: 15 photos at 3000×2250
(synthetic noisy JPEGs, 113 MB zipped) plus `emr.json`.

| | |
|---|---|
| Upload A sent | 0.00 s |
| Probe answers | **404 from 0.11 s to 23.24 s** (every 0.1 s) |
| Resend B sent, after a 404 probe | 1.09 s |
| A's reply | 23.38 s, 200, `merged: false`, `job.json` |
| First probe answering 200 | 23.39 s |
| B's reply | 26.14 s, 200, **`merged: true`**, `job-<id>.json` |
| The folder afterwards | **30 jpg**, `emr.json` + `emr-<id>.json`, `job.json` + `job-<id>.json` |

Not measured:
- a real phone job's photo size;
- the ship PC's CPU;
- what JobShot actually does when it gets no reply.

Synthetic noise makes larger files than real photos with the same pixel count.
The filing time comes mostly from decoding and resizing pixels, so it should be
similar, but I have not shown that.

### 4. What the archive can show

- **The ship's archive (`DESKTOP-NPAM51V`) is not reachable from this machine.**
  I have not counted it.
- **This machine's test archive** (`Downloads`, ship `ENA Test`): 1 job folder
  with a manifest. No folder holds two manifests or two drafts.
- **How to check the ship, read-only**, in PowerShell on that PC, with the
  destination folder put in `$d`. It lists only folders holding more than one
  manifest. Tested on a fake archive; it has not been run on the ship.

      $d = "D:\path\to\photos"
      Get-ChildItem -LiteralPath $d -Directory | ForEach-Object { $m = @(Get-ChildItem -LiteralPath $_.FullName -File -Filter 'job*.json'); if ($m.Count -gt 1) { $f = $_.Name; $m | ForEach-Object { $j = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json; '{0} | {1} | {2} | {3}' -f $f, $_.Name, $j.job_id, $j.filed.filed_at } } }

  - Rows sharing a `job_id` are a resend (2a).
  - Different `job_id`s are a merge (2c, by design).
  - If a resend's two `filed_at` values are seconds apart, that is case 1.

### 5. What this changes for path 2

- **Two drafts of one job can come from HPO's own filing window.** Nobody has to
  press a button twice; it only takes the phone giving up on the reply and
  probing before the filing ends. **Whether JobShot does that is JobShot's code.**
  The question for JS is how long the phone waits for the upload reply, and what
  it does when it gives up.
- **An HPO-only remedy exists, with no wire change, and it is not built:** hold
  a probe for a `job_id` that is being filed until that filing ends, then answer
  200 as usual. It works only if the phone's probe timeout is longer than the
  wait, and JS knows that number. Nick's call. Cases 2 and 4 would still make
  two drafts, so EMR's choice in path 2 remains a real question either way.

---

— Codey (Happy-Photo-Organizer)
