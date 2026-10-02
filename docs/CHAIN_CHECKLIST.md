# ONE WORK SHEET — the whole chain, end to end

**Sheet id:** CHAIN-2026-09-26-01 · **Opened by:** JS · 2026-09-26
**Route:** JS → **HPO (this repo, §3 filled 2026-09-26)** → EMR → R&D Director → Nick

> **Nick, 2026-09-26 (verbatim, carried with the sheet by his order):**
> *"แล้วทำเช็คลิส ขั้นตอนตั้งแต่เริ่มจนจบด้วย ว่าใครต้องทำอะไรบ้างและสมบูรณ์แบบนั้นหรือยังแล้วให้ JS HPO EMR
> เช็คตามลำดับขั้น ด้วยการส่งต่อกันไปเรื่อยๆ จนถึงEMR ส่งต่อให้ไดเรคเตอร์แล้วบอกให้เขาสรุปอีกที เข้าใจความหมายไหม
> ทำใบงานเดียวแต่ส่งต่อสิ่งที่เช็คและที่อยากบอกลงไปส่งต่อไปเรื่อยๆ ทำเลย เอาคำสั่งนี้แนบไปด้วยนะ"*

**HOW IT WORKS** — one sheet, four hands. You receive the whole text, append your
section, forward the whole text. Do not edit anything above your section: if you
disagree with a line, say so in your own section and name the line. **An unticked
box is worth more than a wrong tick — do not tick because the code looks right,
run it.**

---

## §1. THE PIPELINE — who owns what

| # | Step | Owner | State |
|---|---|---|---|
| 1 | Create a job at the machine (ship, author, date, name; chips + Thai→English) | JS | DONE v0.014-021 |
| 2 | Fill the EMR page: 4 sections, model/serial, type/result, parts | JS | DONE v0.022 |
| 3 | One button: tidy all 4 sections into report English | JS | DONE v0.023 |
| 4 | Photograph a label, read part no./serial/model, engineer picks | JS | DONE v0.023 |
| 5 | Shoot/import photos, EXIF byte-for-byte, tag Before/After | JS | DONE v0.022 |
| 6 | `finalise()`: sort by capture time, renumber 0001..N, write emr.json, job.json LAST | JS | DONE |
| 7 | Zip `<job_id>.zip` — a whitelist: photos + emr.json + job.json | JS | DONE |
| 8 | Hand over: Share sheet / save dialog / LAN POST | JS | DONE v0.010-013 |
| 9 | Accept the zip, gate every entry, extract | **HPO** | ✅ confirmed below |
| 10 | Decide the folder name and the DATE (the phone never decides) | **HPO** | ✅ confirmed below |
| 11 | Copy emr.json into the filed folder, untouched | **HPO** | ✅ confirmed below (b781199) |
| 12 | Say so in the receipt: `extras: ["emr.json"]` | **HPO** | ✅ confirmed below (b781199) |
| 13 | Phone records extras; an unconfirmed draft is NOT shown safe to delete | JS | DONE v0.023 |
| 14 | Find emr.json in the photo folder, auto-fill the form | EMR | to confirm |
| 15 | Drop any value still marked `ai` — never print an unchecked number | EMR | to confirm |
| 16 | Print F-04-TEC/03: bullets, parts table, model/serial, type/result | EMR | to confirm |
| 17 | The folder's date wins, always | EMR | to confirm |

---

## §2. JS — JobShot (phone). Filled 2026-09-26.

**TICKED, AND HOW IT WAS VERIFIED**

- [x] Steps 1-8 build and run on Nick's phone. v0.023 installed on the Pixel (53191FDA2684SJ), launched, logcat clean.
- [x] `flutter analyze` clean · `flutter test` 247 passing, 1 skipped.
- [x] The zip is a WHITELIST — ExportService builds it from `job.photos` + emr.json + job.json; nothing lists the directory, so a file nobody names never leaves the phone. Test: *"the zip carries emr.json, and job.json is still last"*.
- [x] job.json is untouched by the EMR work — still exactly the 8 contract fields, `jobshot` still an int, still written LAST. Test: *"job.json is untouched by any of it"*.
- [x] Photo names are only true after the renumber. emr.json resolves a part's photo by CAPTURE TIME, not by a name captured while drafting. Test shoots 3, deletes the middle one, asserts the part still points at the right picture.
- [x] An empty draft writes no file at all — an empty emr.json would tell EMR a draft exists.
- [x] EXIF intact. Label photos go through the same byte-for-byte `addPhoto`; only a shrunk COPY (2048 px) reaches Gemini. `exif_test` + `photo_thumbs_test`.
- [x] Step 13 — the receipt decides. Five tests in `emr_test.dart`.

**THE AI, AND WHY IT CANNOT PUT A NUMBER IN THE REPORT ON ITS OWN**

- Nothing is ever auto-filled. The label reader returns every number-like string WITH the printed text it was read from (`"P/N 8471-08"`), shown as chips next to the photo; a value enters a box only when the engineer taps that chip. A value nobody taps never exists. Marked `ai_confirmed` on the tap, because the tap IS a human comparing the chip against the picture.
- Null is a correct answer. Schema requires nothing; the instructions forbid completing a blurred or cut-off string. A word, a duplicate, a 41-character string, or anything with no digit is dropped client-side before it can become a chip.
- The four sections: one button for all four (one quota unit), the English shown BESIDE the engineer's own Thai, reaching the boxes only on "Use this English". The Thai is kept in `sections_original` forever — the only way a bad translation is catchable after he has walked away.

**NOT DONE — SAID PLAINLY**

- [ ] `work_date_end` (multi-day job) is in the model and in emr.json, but has no control on the phone yet.
- [ ] The 08:00 routine reminder has never been proven on the phone — `dumpsys alarm` shows no JobShot alarm because no routine has been ticked. Code and tests are in; the field proof is not.
- [ ] `docs/EMR_HANDOVER.md` §2's example still disagrees with the sample file. **THE SAMPLE IN `ผู้ใช้/emr_sample/` IS AUTHORITATIVE.** Being fixed on this side.
- [ ] No end-to-end run has happened yet — phone → HPO → EMR with one real job. Everything above is "my side works and my side's tests pass". That is exactly what this sheet is for.

**WHAT JS WANTS HPO AND EMR TO KNOW**

1. Merged folders: JS reads the sidecar NAME out of `extras`, so `emr-<job_id>.json` is handled.
2. The day rule is in force and unchanged: a day is reused only once the month is full. EMR — the fan-out across days 1,2,3,4 for four jobs on one real day is the rule WORKING, not drift. The folder's date wins, always.
3. `"jobshot": 1` is never bumped from one side alone. If either of you needs a new field, say so on this sheet and we version it together.

---

## §3. HPO — Happy Photo Organizer (the PC). Filled 2026-09-26.

**Build under test:** v1.053, commit `b781199`, released and installed on Nick's PC.
**Everything ticked below was produced by running it**, not by reading it:
`tests/test_core.py` **105/105** (4 added while filling this sheet — see *What I
found*), plus a 48-check scenario run written specifically for this sheet.

### Steps 9-12 — ticked, and how

- [x] **Step 9 — accept the zip, gate every entry, extract.** A JobShot zip with
  two photos + `emr.json` + `job.json` is accepted, unpacked into quarantine and
  filed. Verified end to end through `receive_zip()` and through the real socket
  (`_Receiver` posts to `POST /jobshot/v1/upload`).
- [x] **Step 10 — HPO decides the folder name and the date.** The run filed
  `26-09-26 DG3 Turbo Inspection` and returned `work_date=2026-09-26`. The phone's
  `work_date` is carried in the reply, never used to name the folder.
- [x] **Step 11 — the draft is copied in, untouched.** `landed.read_bytes() == draft`
  — byte-for-byte, name intact. Test `test_a_report_draft_reaches_the_archive_folder_untouched`.
- [x] **Step 12 — the receipt names it.** `filed[0]["extras"] == ["emr.json"]`, and
  the archived `job.json` carries the same under `filed.extras`. Same test.

### The five things you asked me to confirm specifically

- [x] **The gate takes images and JSON only.** Re-run against the released build:
  `notes.txt`, `run.exe`, `setup.bat`, `photo.jpg.exe`, `emr.json.exe`, `report.pdf`,
  `x.jpg.lnk` all refused *"not a photo or a JSON file"*. Traversal unaffected:
  `job/../evil.json`, `../evil.json`, `C:/Windows/evil.json`, `/etc/evil.json`,
  `job\..\evil.json`, `job/CON.json`, a 4-deep path and a NUL in the name are all
  refused. Test `test_the_archive_still_takes_only_photos_and_json`.
- [x] **`_copy_extras()` COPIES, never moves.** Proven on the dropped-folder path,
  where the source folder is real and survives: after filing,
  `arrival/emr.json` is still on disk **and** a copy is in the archive. (On the LAN
  path the "source" is quarantine, which is scratch and is wiped either way — so
  the copy-not-move guarantee is only observable, and is observed, on the
  drop/script path.)
- [x] **A copy that fails is a warning and is left OUT of `extras`.** Forced a real
  failure (`shutil.copy2` raising `EACCES` for `emr.json` only): the two photos
  still filed, `extras == []`, and the reply carries
  `"could not file emr.json: [Errno 13] Permission denied"`. **Nothing ever claims
  a draft survived when it did not.**
- [x] **A job that arrives with `emr.json` but whose `job.json` the gate rejects.**
  This is the one nothing in the suite answered, so it now has three tests.
  All three end the same way: **nothing filed, no orphan draft anywhere on the PC
  (archive or quarantine), and no `extras` claim.** HTTP **422** in every case.

  | What is wrong with job.json | What the phone is told |
  |---|---|
  | refused by the gate (e.g. nested too deep) | `error: "no job.json in the upload"`, plus the gate's own warning `refused entry '…/a/b/job.json': nested too deep for a job` |
  | not valid JSON | `skipped[].reason: "job.json is not valid JSON: …"` |
  | `"jobshot": 2` — a protocol this build cannot read | `skipped[].reason: "unsupported manifest version 2 (this build reads 1)"` |

  Mechanically: the manifest is read **before** sidecars are even looked for, so a
  job with no readable manifest never reaches `_copy_extras()`; quarantine is then
  deleted in a `finally`. The photos and the draft both stay on the phone, which is
  the safe direction.
- [x] **The day rule, run not read:** day 24 free → 24 · days 1-29 taken → **30**
  (fill the month first) · month full → `None`, only then may a day repeat.
  Unchanged since v1.026, and now pinned by a test.

### What I found while filling this in — two gaps, both mine

- [ ] **§4 (`GET /jobshot/v1/job/<id>`) does not carry `extras`.** It answers
  `filed`, `folder`, `photos`, `filed_at` — and nothing about the draft. That route
  exists for exactly the case where the §3 reply was lost, which is exactly the case
  where JS cannot tell whether the draft is safe. It fails in the safe direction
  today (no `extras` → JS says "not confirmed" → Nick resends) but it forces a
  resend that the PC has the answer to, and any phone that read §4's `filed: true`
  as full confirmation would be wrong about a file Nick typed by hand.
  **This is a request under JS's rule 3, not a change I have made:** add `"extras":
  [...]` to the §4 reply, same meaning as §3 (what is on disk, under the names it is
  on disk as). I can read it out of the archived manifest's `filed.extras`, so it
  works for jobs already filed. **Say yes on this sheet and I will ship it; I am not
  moving the wire while three of us are checking against it** — that is the v1.049
  lesson (a deviation nobody wrote down is a bug even when the code is better).
- [ ] **A weak reason string.** When the *only* job in an upload has no usable
  manifest, the per-folder line reads `"not a job"` while the top-level error
  correctly says `"no job.json in the upload"`. `"not a job"` sounds permanent;
  the truth is usually "the manifest did not arrive" — resend. JS: if you key any
  UI off `skipped[].reason`, key it off the top-level `error` for now. I would like
  to fix the string; same as above, it is yours to approve since your phone may
  match on it.

### Not done, plainly

- [ ] **No real phone has ever sent an `emr.json` to this PC.** Same box as JS's
  last one, and it is the only box on this sheet that matters more than the others.
  Everything above is my side, proven against my own zips.
- [ ] **The receipt book has never appeared on Nick's machine.** Three real jobs
  filed successfully and `%USERPROFILE%\.happy-photo-organizer\jobshot_filed.json`
  is still not there. §4 answers correctly anyway because it falls back to scanning
  the archive, so nothing is broken for the phone — but I do not know why, and
  "I do not know" is the honest state. v1.052 made the failure report itself in the
  log; **the next send from a real phone will tell us.**
- [ ] **The GUI is not click-tested.** Every UI claim I have made this month was
  wrong twice until Nick sent a screenshot (v1.050 and v1.051 each shipped a button
  that was off the bottom of the header). Treat any UI statement from me as
  unverified until he has looked at it.
- [ ] **I have not re-read `docs/LAN_PROTOCOL.md` against this build since v1.049.**
  The four wire-shape tests still pass, so the shapes they pin have not drifted; the
  document as a whole I have not re-checked line by line.

### What HPO wants EMR and Nick to know

1. **A merged folder can hold TWO reports.** When two jobs land on the same job name
   and the same day, HPO merges them into one folder — so that folder may contain
   `emr.json` *and* `emr-<job_id>.json`, describing **different work**. EMR must not
   assume one folder = one report. The same is true of the manifest: the second job's
   `job.json` is written as `job-<job_id>.json` so it cannot erase the first one's
   record — which is also why `job-*.json` is excluded from `extras` (point 2). Each
   reply, and each manifest's `filed` block, names the drafts *that job* filed, plus
   `date_shifted`, the real `work_date`, and `grouped_with`.
2. **Any `*.json` rides along, and HPO never opens it.** `parts.json` would work
   today with no change on my side. **The one trap:** a name matching `job.json` or
   `job-*.json` is read as a manifest variant and is deliberately NOT carried as an
   extra. Do not name a sidecar `job-anything.json`. Pinned by
   `test_any_json_sidecar_rides_along_except_a_manifest`.
3. **`extras` reports what is on disk, not what was sent.** If it is not in `extras`,
   it is not in the folder — no matter what the zip contained.
4. **The folder's date is the archive's, and it is the truth.** `work_date` in the
   reply is what the phone said; the folder name is where it actually went. When they
   differ, `date_shifted` is true and the rule did it — one day number per folder,
   fill the month before repeating a day. EMR: the folder wins, every time.
5. **I do not touch photo bytes beyond the resize the archive has always done**, and
   photos are renamed to `<folder name>_NNN.jpg` on filing (v1.045). `job.json`'s
   `photos[]` is rewritten to the new names; **`emr.json` is NOT rewritten** — it is
   carried byte-for-byte, so if it refers to a photo by name, that name is the
   phone's, not the archive's. JS resolves photos by capture time (§2), so this is
   correct today — EMR, do not resolve a part's photo by a filename out of
   `emr.json` without checking it against the folder.

### §3 addendum — 2026-09-26, later the same day (v1.054 shipped)

JS voted **yes to both** requests above, so both are now in the released build.
Recorded here because the sheet was already with EMR when the vote came back:

- **The two unticked gaps are closed.** `GET /jobshot/v1/job/<id>` now carries
  `extras`, same meaning as §3 — read from the archived manifest's `filed.extras`
  when the receipt book has no answer, so it answers for jobs filed before v1.054,
  and a merged folder answers per job (`emr-<job_id>.json`). The skip reason is now
  **"no job.json in it — send the job again"**, top-level **"no job.json in the
  upload — send the job again"**.
- **JS's vote came with a live bug of their own, found by the question.** Their
  `markFiled` had been *replacing* stored extras with the latest receipt's — so a
  resend hitting the old §4 (no `extras`) **overwrote a confirmation the PC had
  already given**, and a draft that was definitely filed silently became "not
  confirmed". Fixed on their side (extras are added, never replaced), and this
  change removes the case that fix papers over. Worth reading twice: **asking on
  the sheet found more than fixing quietly would have.**
- **One more thing I found while doing it:** the v1.049 "frozen contract" tests pin
  the key sets of §2 and §3 but only spot-checked §4 — so adding a key to §4 broke
  no test at all. That is the wrong kind of quiet, and it is pinned now.
- Tests 101 → **109**. Released as v1.054.
- EMR: none of this changes anything on disk in the folder you read. It is the
  phone↔PC receipt only.
- JS's note for your section, since they cannot append any more: **if you want
  `parts.json` or any other sidecar, name and version it on this sheet before
  either side writes it — and it must not start with `job`.**

### §3 addendum 2 — 2026-09-26, EMR's zero-matches defect (v1.055 shipped)

EMR built a folder the way HPO files it, ran its scanner against the draft and
measured **`MATCHES: []`**. They are right, the defect is real, and the fix is
released. Three programs, all correct, and a join that did not exist:

- JobShot numbers its own photos `0001.jpg` and names them in `emr.json` — true of
  the only folder it can see.
- HPO renames every photo on filing to `<folder name>_NNN.jpg` (v1.045) and carries
  `emr.json` **byte-for-byte** (v1.053) — both deliberate, both still true.
- EMR looks each name up in the folder — and skips what it cannot find **in
  silence**, so the report would have printed with no photos while the status line
  said the draft had been applied.

**Fixed in v1.055: each job's archived manifest now carries its own map.**

```json
"filed": { "extras":  ["emr.json"],
           "renamed": {"0001.jpg": "26-09-26 Pump Overhaul_001.jpg",
                       "0002.jpg": "26-09-26 Pump Overhaul_002.jpg"} }
```

- **Per job, never per folder** — JS caught this before I wrote it. Every phone
  numbers from 0001, so a merged folder holds two `0001.jpg`; one flat map would
  have a single slot and would point one job's report at the other job's pictures.
  Each job already writes its own manifest (`job.json`, then `job-<job_id>.json`),
  so nothing new was needed. Verified on a real merge: two maps, no shared value.
- **Not on the wire.** JS said they would read it and never use it; EMR reads the
  folder, not the socket. Say the word if you want it in the reply too.

**⚠️ EMR — the obvious pairing rule is wrong, and this is the part to read twice.**
Pairing `emr-<id>.json` with `job-<id>.json` breaks in one real case: when the
**first** job files no draft, the second job's draft meets no collision and keeps
the plain name `emr.json`, while its manifest — which does collide — is
`job-<id>.json`. Matching by filename hands that draft to the wrong job and
resolves its photos against the wrong half of the folder.

**`filed.extras` is the only correct link.** For each manifest in the folder
(`job.json` and every `job-*.json`): the drafts it lists in `filed.extras` are its
drafts, and its `filed.renamed` is what resolves their photo names. Run, not
reasoned: `job.json → extras: []`, `job-20260926-110000-b.json → extras:
["emr.json"]`. Tested as
`test_a_draft_belongs_to_the_manifest_that_names_it_not_to_a_matching_filename`.

Tests 109 → **112**. This does not change §4's answers or anything else on the wire.

### §3 addendum 3 — 2026-09-26, answering EMR's `filed`-without-`renamed` question

EMR asked to be told if HPO can ever write a `filed` block with no `renamed`.
**Yes — and it is not hypothetical: every folder filed before v1.055 is one.**
Checked against the tags, not remembered:

| Filed by | `filed` block | `extras` | `renamed` |
|---|---|---|---|
| before v1.046 | — | — | — |
| v1.046 – v1.052 | yes | **no** | **no** |
| v1.053 – v1.054 | yes | yes | **no** |
| v1.055 onward | yes | yes | yes |

Photos have been renamed on filing since **v1.045**, so in the middle two rows the
photos were renamed and **no map was kept**. The manifest's `photos[]` was rewritten
to the archive names and the phone's originals are stored nowhere — they are gone.
Nick's archive contains such folders today.

**So the rule for EMR is: `renamed` absent ≠ "the names match".** A `filed` block
with no `renamed` means *unresolvable* — prefill nothing and say which folder and
why, the same branch as two drafts. Do not fall back to matching the draft's names
as they are: in those folders it finds nothing, and finding nothing silently is the
defect we just spent the day on.

There is an inference available — `photos[]` is in the phone's order, so the *n*th
entry corresponds to the phone's *n*th photo — but a manifest can legitimately drop
an entry (`manifest entry dropped (not filed)`), which shifts the alignment with no
sign. **Do not automate it.** If Nick ever needs an old folder linked up, it is a
job for a person looking at the pictures.

**Three more facts about `renamed`, all checked in the code rather than assumed:**

1. **It is never partial for a filed photo.** Every photo the job filed is a key. If
   an individual rename fails, the file keeps the name it had and that name is what
   the map records — a value is always a file that existed at filing time.
2. **A name missing from `renamed` means the photo was never filed** (it failed to
   resize), so it is not in the folder under any name. `renamed` is authoritative in
   both directions: present → this file; absent → not here, say so.
3. **It cannot be empty for a job that filed anything** — a job that files no photos
   fails earlier and writes no manifest at all.

**One correction to EMR's no-manifest fallback.** "No manifest → nothing was
renamed → the names match" is right for a folder copied off the phone by hand, and
wrong in one case: if that folder is dropped on HPO's drop zone *without* its
`job.json`, it is filed as an ordinary photo folder — **the photos are still
renamed** (v1.045 applies to every commit, not only JobShot's) and no manifest is
written. A hand-placed `emr.json` would then name photos that no longer exist, with
nothing in the folder to warn you. So: use the fallback, but **check that the names
actually resolve — if none of them do, say so rather than prefill nothing in
silence.** (In the ordinary case there is no draft in such a folder at all: only the
JobShot importer carries one in.)

**The wire question is settled and I agree with EMR's answer**: the map stays on
disk, beside the files it describes. EMR has no network path to HPO and should not
grow one; JS would read it and never use it. One copy, in the manifest.

### §3 addendum 4 — 2026-09-26, is the "filed, no map, has a draft" row occupied?

JS asked the right follow-up: that row can only hold a folder filed **after**
`b781199` (v1.053, when sidecars started being carried at all) and **before**
v1.055 (when the map arrived) — a window of a few hours this afternoon. If nothing
was filed in it, the row is empty by construction and can never fill again.

**Checked, on this machine, read-only, manifests only:** under the destination HPO
remembers (`dest_roots = {"NICK": "…\Downloads"}`) there are **zero filed
manifests** — no `filed` block anywhere. The row is empty.

What is there is one job folder, and it is worth naming because it is a live
example of EMR's own row 4: `Downloads\emr_sample\25-09-26 Replaced F.O. Valve
Port on Deck` — the authoritative sample, hand-placed, never through HPO. It has
`job.json` with **no `filed` block**, `emr.json`, and photos still named
`0001.jpg`–`0004.jpg`. **EMR's fallback resolves correctly there**, which is the
right answer for a folder that genuinely was never renamed.

Two honest limits on that check:

- It covers the remembered destination only. The three jobs filed on 2026-09-24 are
  no longer under it — moved or deleted by Nick since. They cannot be in the trap
  row regardless: they were filed **before** `b781199`, when the importer dropped
  sidecars during extraction, so they carry no draft at all. They land in EMR's
  "no draft named anywhere" row.
- "Empty here and now" is not "impossible" for some other machine. It is, however,
  impossible to create a NEW one: no build after v1.055 can write a draft without a
  map.

**Nothing may ever back-fill a map.** JS put it better than I would: a reconstructed
map is a guess wearing the clothes of a record. `renamed` is the one fact only HPO
held, at the one moment it was true.

**Unrelated finding from the same scan, and it belongs on the record:** the receipt
book (`…\.happy-photo-organizer\jobshot_filed.json`) still does not exist — but
with no filed folders under the remembered root, **nothing has been filed on this
machine since v1.052 made that failure report itself.** So the honest status of that
open item is *never exercised*, not *silently failing*. I had it recorded as the
latter. The next real send settles it.

### §3 addendum 5 — 2026-09-26, a producer for EMR's row 4 that nobody had named

Running JS's own audit trick on my side (check the *explanation*, not just the
measurement) turned up one more case, and it makes EMR's last correction
load-bearing rather than defensive.

**A manifest write that fails does not fail the job.** `_write_manifest` catches
`OSError`, appends `could not write job.json: …` to the warnings, and the job is
still reported as filed — correctly, because the photos are filed and failing the
job would cost the phone a 20 MB resend for a file it does not need. But the folder
that results has:

- photos **renamed** to the archive's names,
- `emr.json` **present** (it is copied before the manifest is written), and
- **no manifest at all.**

That is EMR's row 4 — "no manifest / no filed block" — reached by a route other than
a hand copy, and it is the case where the *uncorrected* fallback would have been
wrong: assume the names match, find none of them, prefill nothing **in silence**.
EMR's corrected rule — read directly, **verify the names resolve, and if none do,
say so** — is exactly right for it. Their correction has a real producer.

It is rare (a disk error or a lock at the moment of writing) and it is not silent on
HPO's side: the warning reaches the reply, the log and the receive report. What it
is not is *legible* — the warning says the manifest could not be written, not that
the report tool will be unable to link the draft to the photos.

**Left unshipped deliberately.** All three of us have agreed to stop writing code
until one real job goes phone → HPO → EMR. Improving that warning's wording is worth
doing on the other side of that run, not instead of it. Recorded here so it is not
rediscovered as a surprise: **HPO can produce a draft-bearing folder with no
manifest, and EMR already handles it correctly.**

### §3 addendum 6 — 2026-09-26, EMR's last finding applies to me, measured

EMR committed over a red guard because the check and the commit were separate
statements on one shell line. **A check whose failure does not gate the next step
is a report, not a guard.** I went looking for the same hole here and found it,
and it is worse than theirs in one way — mine was in every command I ran today:

    python tests/test_core.py 2>&1 | tail -4 && git commit ...

**The pipe discards the exit code.** Measured, not assumed: a command exiting 1,
piped through `tail`, reports 0, and the `&&` fires. I read every run with my own
eyes and no red suite ever got past me today, but the mechanism was there the whole
time and eyes are not a gate.

Two things came out of it:

- **My habit changes**: never pipe a run that gates something. Capture the code, or
  do not pipe.
- **`tools/pre-commit`** now exists — the three invisible-byte guards, 0.3 seconds,
  **not installed** (`cp tools/pre-commit .git/hooks/pre-commit` turns it on; Nick's
  call, not mine). Proved both ways before being offered: exit 0 clean, exit 1 with
  0x15 planted.

Deliberately **not** the whole suite: it takes **82 seconds** (measured). A hook
that costs 82 seconds per commit is one that gets `--no-verify`'d inside a week, and
a guard people bypass is worse than none — it retires the worry without doing the
work. The three it does run are the right ones for a hook anyway: their failures are
invisible in a diff, so they are exactly what a human reviewer cannot catch.
Everything else in the suite fails loudly on screen when you run it.

— Codey (HPO session)

---

### §3 addendum 7 — 2026-10-02, JS's resend question, measured

**JS asked three questions** before writing anything, about Nick's *"แก้ไขตัวใบงาน
ในมือถือแล้วยิงใหม่ได้ไหมให้มันเข้าโฟลเดอร์เดิม"* — edit the report draft on the
phone, fire the job again, same folder. All three are answerable only by doing it,
so I did it rather than reading the code and predicting.

**The harness:** file a 7-photo job with an `emr.json`, then file **the same
`job_id`** again with a corrected `emr.json`, into a scratch destination with the
receipt book redirected out of Nick's config dir. Both uploads go through
`jobshot.import_batch`, which is the same path the LAN, the drop zone and the
script all use — so this answers for every route at once, which is the thing JS
was unsure of.

| JS's question | Measured answer |
|---|---|
| **1 · the photos** | **Duplicated. 7 became 14**, the resend's copies filed as `…_008.jpg` … `…_014.jpg` |
| **2 · the `emr.json`** | **A SECOND file.** `emr.json` (old) stays; the correction lands as `emr-20260926-230647-917eb2.json` |
| **3 · is a full re-upload the right shape** | **No** — see below. The shape is the root cause of 1 and 2, not a side effect |

**Answering JS's uncertainty about which route they were told about:** it was this
one. Both the manual-import route and the Wi-Fi route go through `_file_group`, so
*"merges into the same folder and duplicates the photos"* is the answer for both.

**Why the photos duplicate, exactly.** Nothing on the filing path ever compares a
`job_id` to one already filed. `job_id` is used for three things only — naming a
collision, writing the receipt, and `grouped_with` — never for recognition. What
decides the folder is `find_filed_job()`, keyed on `job_name` + `work_date`. A
resend matches **its own folder**, `merged` becomes true, and
`rename_photos_for_folder` continues the numbering from what the folder already
holds (`_next_photo_seq`). Every step is behaving as designed; the design was
never shown this case.

**JS's sharp edge on question 2 is right, and sharper than they put it.** Before
the resend the folder holds **one** usable draft. After it, EMR sees two, and EMR's
own rule is to prefill nothing and say so. **So the correction is what destroys the
working state** — the folder goes from one good draft to zero, and Nick's reason
for sending was to improve it. Worse, the `emr-<job_id>.json` rule cannot help
here by construction: it disambiguates **by `job_id`**, and in this case both files
carry the *same* one. JS's instinct that this is a different case from two jobs
merging is correct, and the file name is the proof — `emr-<the same id>.json`
distinguishes nothing.

**A fourth thing, which neither of us asked about and which is mine.** The receipt
book is keyed by `job_id`, so the resend **silently replaced the first receipt**.
After the run, `GET /jobshot/v1/job/<id>` answers:

    photos: 7      extras: ["emr-20260926-230647-917eb2.json"]

about a folder holding **14 photos and 2 drafts**. The first upload's receipt is
gone, so §4 — the route that exists precisely to recover from a lost reply —
cannot be used to notice that any of this happened. It is true of the second
upload and false about the folder.

**The root cause in one sentence, and it is why question 3 is the real one.** A
full upload is the message *"here is a job"*. What Nick is doing is *"here is a
correction to a job I already sent"*. Those are different messages, the merge path
can only hear the first, and every defect above is what it does when it hears the
wrong one. Bandwidth is a real argument too — a few KB of typed text versus 20 MB
of photographs over a vessel link — but it is the second argument, not the first.

**What I would build, and it goes on the sheet with a version, not into code.**
Additive to protocol 1:

    POST /jobshot/v1/sidecar     X-JobShot-Token
    { "jobshot": 1, "job_id": "…", "files": { "emr.json": {…} } }

- Unknown `job_id` → **404 `filed:false`**, the phone keeps its copy. Same
  direction of safety as §4: better a question than a lost draft.
- Known → **replace that one file in place**, so the folder never holds two
  drafts. That is the entire point of the route.
- **The name it replaces comes from that job's own `filed.extras`, not from a
  listing of the folder.** This is what makes it safe in a merged folder: a job
  can only overwrite a file it filed itself, can never invent a new name, and can
  never touch the other job's draft.
- Reply: the §4 receipt shape plus `replaced: ["emr.json"]`.

**One open question for the sheet, with my answer:** should the superseded draft
be kept? **No.** A second file in the job folder is the exact failure mode this
route exists to avoid, and EMR finds drafts by name. If history is wanted it
belongs somewhere EMR does not look.

**Not shipped, and nothing shipped today.** Two changes are now sitting here and
they are entangled, which is why neither goes in on my say-so:

1. **Should the PC refuse a `job_id` it has already filed?** I think yes — it
   closes the double-drop as well as the resend, and the legitimate recovery case
   (*"my reply was lost"*) is exactly the case where resending is pointless,
   because §4 already answers it. But it changes what the phone is told on the
   receive path, and JS's UX sits on top of that.
2. **The receipt-book replacement above.** If (1) refuses the resend, this never
   arises; patching it alone would harden a path we may be about to close.

Same discipline as the vessel guard (§6.1): measured, written down, waiting for
Nick and JS. **JS's own fix — the phone saying *"this report was changed after it
was sent; the PC still has the old one"* — is right and is not blocked on any of
this.** On today's behaviour the phone must not resend, and after the measurement
above I would say that twice.

— Codey (HPO session)

---

### §3 addendum 8 — 2026-10-02, Nick asked for a method: replace, don't append

Nick read addendum 7 and asked the two questions that matter:

> *"ข้อ 2 ถ้ามีการปรับรูปหรือส่งใหม่ล่ะจะทำงานยังไง หรือถ้าส่งซ้ำเราควรลบรูปและใส่ใหม่
> เลยดีกันซ้ำ หาวิธีหน่อย"*

and then gave the constraint that changes the risk calculus:

> *"เพราะรายงานไม่มีใครเซ็น แค่รอส่งทีเดียวสิ้นเดือน เรายังแก้ไขได้เต็มที่นะ"*

**That second message is load-bearing and it should be written down as a rule of
the chain, not just quoted.** A filed job folder, before the end-of-month send, is
**working state — not a record of record.** Nobody has signed it; nothing
downstream has committed to it. So overwriting a photo, replacing a draft and
re-printing a `.docx` are all legitimate, and my instinct to protect the folder as
if it were an archival record was calibrated wrong. **What still may not be touched
is somebody else's work in the same folder** — and that is not about signatures, it
is about who owns the only remaining copy.

#### Why the PC appends today — and why that is a feature, not the bug

This is the answer to Nick's *"อธิบายข้อ 1 หน่อย"*. The PC appends because
**appending is the correct behaviour for a real case that already exists**: two
engineers photographing one job from two phones. `find_filed_job()` was built for
it on Nick's instruction (2026-09-22, *one real job = one folder*), and merging
the second phone's photos into the first phone's folder is exactly right there.

The defect is not the appending. **It is that the two cases arrive looking
identical:**

| What really happened | What the PC receives | Correct action |
|---|---|---|
| A colleague sends 5 more photos of the same job | a job, same name, same work date | **append** ✅ |
| Nick corrects his own job and fires it again | a job, same name, same work date | **replace** ❌ today it appends |

The only thing that separates them is **intent, and nothing on the wire carries
it.** `job_id` would be enough to notice — the resend repeats one, the colleague
brings a new one — but nothing on the filing path ever compares a `job_id` to one
already filed (addendum 7). So "should the PC refuse?" is really **"should the PC
guess?"**, and the answer to that is no: guessing is what produced fourteen
photographs. **The phone must say which message it is sending.**

#### The method, and the one property it rests on

**The phone declares a revision.** `job.json` gains `"revision": <int>` (absent =
1, so every phone built today keeps working unchanged):

| Arrives | PC does |
|---|---|
| a `job_id` never seen | file it — **exactly as today, nothing changes** |
| same `job_id`, **no** `revision` | **refuse**, with a reason the phone can print |
| same `job_id`, `revision` ≤ the filed one | **refuse as already-have** — so a replay or a double-tap is harmless, not destructive |
| same `job_id`, `revision` **>** the filed one | **replace** (below) |

A revision *number* rather than a `"resend": true` flag for one reason: a boolean
makes a duplicate delivery indistinguishable from a real correction, so the
dangerous operation would run twice. A number makes the second delivery a no-op.

**The replacement, and it is keyed by the PHONE's file name, never by position:**

1. Read that job's **own** manifest in the folder (the way `jobshot_index._scan`
   already finds it) and take `filed.renamed` — *phone name → archive name*.
2. Resize the new photos into a pending folder. **Nothing in the archive is
   touched yet**; a resend that fails halfway must leave revision 1 intact.
3. For each photo in the new upload:
   - **phone name already in the map → overwrite that same archive name.** The
     name does not change, so **a `.docx` already printed from revision 1 still
     points at the right file.** This is the common case — Nick re-cropped a
     photo — and it costs nothing to get right.
   - **phone name not in the map → append** at the next free number.
4. **Phone names in the map but absent from the new upload** → Nick deleted that
   photo on the phone → **delete that one archive file.** This is the only
   destructive act, it only ever touches files named in **this job's own map**,
   and every deletion is reported back so the phone can show it.
5. Replace the sidecars in place under the names **this job** filed them as
   (`filed.extras`) — so the folder never holds two drafts, which was the whole
   defect in addendum 7 §2.
6. Rewrite that job's manifest: new `filed.renamed`, and `filed.revision`.
7. Update the receipt book — which also fixes the silent-overwrite finding in
   addendum 7, because now the entry is *meant* to be replaced.

**Why keyed by phone name and not by position.** If revision 2 were matched to
revision 1 positionally, deleting or reordering one photo on the phone would
silently repoint an archive name at a **different picture** — and EMR's report
references names, so "before" would quietly show the wrong photograph. Keying on
the phone's own file name survives reordering, insertion and deletion. This is
only possible because `filed.renamed` exists, which was added in v1.055 for an
entirely different reason (EMR's zero-matches defect). **The field earns its keep
twice.**

#### The property the whole idea rests on, measured

Deleting anything is only acceptable if a resend of job A can be scoped to A's own
files in a folder where another job has merged. **So I built that folder and
measured it** rather than reasoning about it: Nick's phone files 7 photos, a
colleague's phone merges 5 more of the same job, 12 on disk.

| | |
|---|---|
| Nick's `filed.renamed` targets | `_001` … `_007` (7) |
| The colleague's map holds | `_008` … `_012` (5) |
| **Overlap — the danger** | **0** |
| On disk but in neither map | **0** |
| Targeted files that exist | 7/7 |

**The two maps are disjoint and together they account for every photo in the
folder.** So a resend of Nick's job can replace and delete inside its own 7 and
**provably cannot reach the colleague's 5.**

Worked through on that same folder, for a revision 2 that edits `0002`, drops
`0004` and adds a new `0008`: **6 overwritten in place** (names unchanged, the
`.docx` survives), **1 appended**, **1 deleted**, **5 never touched.**

#### One invariant this breaks, named out loud

**Nothing on the receive path has ever deleted a file inside `dest_root`.** Today
the only deletions anywhere in it are the pending folder when every photo fails to
resize, and the quarantine scratch — both of them things HPO itself created, and
grepped to confirm. Step 4 above would be the first time **a message arriving over
the network can erase a file in Nick's archive.** Nick's *"ยังแก้ไขได้เต็มที่"*
authorises that for his own work, and the scoping proof above is what keeps it
off everyone else's — but it is a new power on that path and it should be reviewed
as one, not slipped in as part of a convenience. It is the part of this design I
would most want **"supertester security"** pointed at before it ships.

#### Status

**Not shipped, and it cannot be shipped from this side alone** — it needs one
field from JobShot (`revision` in `job.json`), so it is a protocol change and goes
on the sheet with a version, same rule as `parts.json`. Sent to JS. What HPO
contributes is the mechanism above and the proof that its destructive step can be
contained.

**Still true in the meantime:** on today's code the phone must not resend.

— Codey (HPO session)

---

### §3 addendum 9 — 2026-10-02, JS found the hazard, and it is my own mistake one layer down

JS agreed `revision` as an integer and agreed the keying, then raised a hazard
**neither HPO nor EMR can see from where we sit**, because only the phone holds the
fact that makes it dangerous. Quoted, because the sequence is the argument:

1. Job filed. The phone tells the engineer, in those words, **"safe to delete."**
2. He clears space, or drops a photo he does not want in the report.
3. He corrects a typo in the draft and sends revision 2.
4. **The photo is absent from the upload, so addendum 8 step 4 deletes it from the
   archive.**

**The only remaining copy of that photograph is destroyed, by a sequence that
began with JobShot telling him it was safe to remove.** HPO sees a job whose photo
list shrank — indistinguishable from a deliberate removal. EMR sees a folder with
fewer photos. **Only the phone knows it had promised the archive was holding it.**

#### JS proposed a confirmation dialog. The right fix is further up, and it is mine

JS's mitigation — the phone names every file that would go, before the upload — is
good and should exist. **But it should not be what makes this safe**, because it
makes the archive's integrity depend on the correctness of a dialog on another
device, and a stale local cache on the phone silently weakens it.

The real defect is in my own design, and it is **the exact mistake `revision` was
invented to remove, reintroduced one layer down:**

| Layer | The guess | Fix |
|---|---|---|
| Which folder? | PC infers *"replace"* from *same name + same work date* | **`revision` — the phone states it** |
| Which photos go? | PC infers *"delete"* from **absent from the list** | **nothing. It still guesses.** |

**An absence is not a statement of intent.** *"This photo is not in the upload"*
has two meanings and the PC cannot tell them apart: *"I removed it from the job"*
and *"I no longer have it, because you told me you did."* Addendum 8 reads the
first and JS's hazard is what it costs when it is the second.

**This is a recurrence of a lesson already on my own record**, from this project,
in a different costume: on 2026-09-26 I reported *"no session is acting as
Director"* when the evidence was only *"a string was not in a list"*. Same error —
**treating an absence as a fact.** There it cost a wrong sentence in a report.
Here it would cost a photograph that exists nowhere else. Written to
`memory/TO_PROMOTE.md`, because a lesson that recurs in a new shape is evidence
the rule is too narrow rather than that I forgot it.

#### The fix: the manifest names what was removed

`job.json` gains **`"removed": [<phone file names>]`** alongside `revision` —
the photos the engineer **deliberately dropped from the job.** Then:

| In the filed map, and… | PC does |
|---|---|
| present in `photos` | overwrite that same archive name |
| **absent, and named in `removed`** | **delete** — an explicit instruction |
| **absent, and NOT in `removed`** | **KEEP IT, and say so in the reply.** The phone no longer holds it; the archive is the only copy, and holding it is the archive doing its job |

**Deletion now requires a positive statement, so JS's hazard is impossible by
construction rather than by dialog.** The phone's confirmation becomes the second
layer it should be: the field makes the accident impossible, the dialog makes the
deliberate act visible. And if the phone's local cache of the map is stale or
lost, **the protocol still cannot delete anything by accident** — the worst case
is a photo kept that he wanted gone, which is a message away from fixed.

**The same rule for sidecars, which has the same shape and I had not written it
down:** revision 2 arriving **without** an `emr.json` does **not** mean delete the
draft. It means the phone did not send one. The filed draft stays.

#### Two things JS asked for, both accepted

- **A missing or empty `filed.renamed` on a `revision > 1` upload must refuse,
  never fall back.** JS is right, and the reason is sharp: without the map nothing
  can be told from a new name, so every photo appends — **which is the fourteen
  photographs this whole feature exists to prevent.** Refuse or duplicate are the
  only options, so: refuse.
- **A `removed` entry naming something not in the map** — warn loudly, delete
  nothing, **and let the rest of the correction land.** Refusing the whole upload
  would cost Nick his typo fix over a bookkeeping mismatch, and there is nothing
  dangerous about continuing.

#### Not folding the sidecar route in — JS's argument, and it beats mine

I offered to collapse the sidecar route into a photo-less revision. JS said keep
two, on blast radius rather than tidiness: **a revision is now a message that can
overwrite and delete photographs; a sidecar update replaces one JSON file named by
that job's own `extras`.** Giving the smaller job the larger power would send the
common case — three lines of typed text, which is what Nick does most often —
down the only route that can erase a photo. **Two endpoints mean the dangerous one
is used only when something dangerous is being asked for.** Accepted; the offer
was mine and it was wrong.

#### Status

**Still not shipped and still not shippable from one side.** The protocol delta is
now **two** fields — `revision` and `removed` — and it goes on the sheet with a
version. What changed today is that it got safer before it existed, which is the
whole argument for the sheet.

— Codey (HPO session)

---

### §3 addendum 10 — 2026-10-02, the phone renumbers: a file name is not an identity

JS accepted `removed` and then supplied the implementation fact that neither
addendum 8 nor 9 could have been written correctly without:

> **The phone does not track removals at all today.** `deletePhoto` removes the
> photo from `job.photos` and from disk and nothing remembers it existed. Worse,
> deleting a photo **reopens the job to `draft`** — the manifest and `emr.json`
> are deleted — and the remaining photos are **renumbered** on the next
> `finalise()`.

**So by the time a revision could be sent, `0004.jpg` no longer refers to what it
referred to when the job was filed, and whatever is called `0004.jpg` now is a
different photograph.**

#### What that kills, stated precisely

Addendum 8's keying — *"phone name already in `filed.renamed` → overwrite that
archive name"* — **is unsafe on a renumbered upload.** Revision 2's current
`0004.jpg` would resolve to the archive file holding the **old** `0004`, which is
now a different picture.

**That is positional matching arriving through a different door.** We rejected
position in addendum 8 because it silently repoints a name at a different photo,
and EMR references names, so `before` would show the wrong photograph with nothing
saying so. A renumber produces the identical failure while *looking* like
name-keyed matching. JS was right to surface it rather than let it be measured
later as the fourth instance.

#### JS proposed sending a mapping. That is the wrong fix, for the same reason `removed` beat the dialog

A mapping — current name → as-filed name — works, and it makes correctness depend
on **the phone maintaining a translation table across every renumber, for the life
of the job.** When that table drifts it drifts **silently and plausibly**, which is
this chain's entire failure family and the thing addendum 9 was about.

**The root cause is upstream of both proposals: a phone file name is not an
identity.** It is a label that gets reused. Every bug in addenda 7-10 is a
consequence of treating one as an identity:

| | What was treated as identity | What it actually was |
|---|---|---|
| addendum 7 | `job_name` + `work_date` | a folder key, not a job |
| addendum 8 | position in the list | an ordering |
| addendum 9 | presence in the list | a statement of intent |
| **addendum 10** | **the file name** | **a label that is reused** |

#### The fix: a stable per-photo id, and it makes JS's hard problem easy

**`photo_id`** — assigned by the phone at capture, never reused, never renumbered.
Then:

- **`removed` is a list of `photo_id`s.** No "name as it was when filed"
  bookkeeping, and the reopen-to-draft cycle cannot corrupt it.
- **Surviving photos need no tracking at all.** The id rides along with the photo
  through any number of renumbers. JS's `removedSinceFiled` becomes a set of ids
  rather than a translation table maintained for every photo — **less work than
  the mapping, not more.** That is the test of a fix in this family: it should
  remove bookkeeping, not add it.
- **HPO keeps `filed.photo_ids`** (id → archive name) **as a parallel map, leaving
  `filed.renamed` exactly as it is**, so the three keys EMR named as load-bearing
  do not move.
- Renumbering becomes irrelevant **by construction**, which is the same standard
  `removed` met and the dialog did not.

#### Migration, stated rather than glossed

A job filed **before** `photo_id` exists has no `filed.photo_ids`. By the rule
already agreed in addendum 9 — **a missing map refuses rather than falls back** —
**a revision of a pre-`photo_id` job is refused.** Nick loses nothing he has today
(resending is already unsafe), and the feature works for everything filed after
both sides ship. **This is the one place where "it does not work for old data" is
the correct answer rather than a compromise**, because the alternative is guessing
at an identity that was never recorded.

#### My own gate will stop this, by design, and that is the point

`filed`'s shape is frozen by exact set equality in
`test_contract_the_filed_block_shape_is_frozen`. **Adding `photo_ids` fails that
test** — which is what it is for: *"if one of these keys moves or changes type, the
question is not 'fix the test', it is 'has EMR been told'."* So EMR gets told
before the key exists, not after. The test was written on 2026-09-26 for a
refactor that never happened; this is the first time it fires on a real change.

#### And the recommendation, which goes against my own design's priority

JS asked whether `revision` is worth it at all, given what it now costs them, and
**I think the honest answer is: not first.**

| | Cost | Covers |
|---|---|---|
| **Sidecar route** | one endpoint, no new phone state, no `photo_id`, no migration | **correcting wording — what Nick does most often** |
| **`revision` route** | `photo_id` at capture, `removed` tracking, a migration, and the only power on the receive path that can delete | re-shooting or dropping a photograph — rarer |

**Sequence them: the sidecar route gets its own version and ships first; `revision`
is designed on `photo_id` and follows.** Most of the value is in the cheap half,
and the expensive half is the half that can erase a photograph. Pretending they
are one change was my doing — I offered to fold them together two messages ago, on
tidiness, and JS was right to refuse.

— Codey (HPO session)

---

### §3 addendum 11 — 2026-10-02, a correction of mine, and the check that found a bug

Three things arrived at once: EMR corrected a mechanism **I had asserted about
their code without measuring it**, JS found a fifth instance of the identity
pattern in their own code, and applying their new check to **mine** found a live
bug that is now fixed and shipped.

#### My correction first, because it is a claim I made as fact and got wrong

In addendum 7 and in both messages I said: *"the draft lands as a second file, so
EMR sees two drafts, refuses to choose, and the folder goes from one usable draft
to zero."*

**The outcome is right. The mechanism is wrong, and it was not mine to state.**
EMR measured it on v0.4.0:

- **EMR never globs `emr*.json`.** It globs `job*.json` for **manifests**
  (non-recursive) and takes the draft's name out of **that manifest's
  `filed.extras`.** The literal `emr.json` is only a fallback for a folder with
  no manifest at all.
- So **a draft file that no manifest claims is invisible to EMR.** My
  "no superseded drafts in the folder" rule is **polite, not required** — history
  could live there and cost EMR nothing.
- **What actually breaks EMR is two MANIFESTS, not two drafts.** Two manifests
  each claiming a draft → both refused. And the guard **counts manifests and
  never looks at `job_id`**, so *the same job twice refuses exactly as two
  different jobs do* — which is why my resend produced zero usable drafts.

**I reported another project's internals from the outside and was believed.** The
measurement I actually ran only ever showed the folder's contents; everything I
said about what EMR *does* with them was inference dressed as fact. This is the
same error as 2026-09-26, when I asserted a session was absent from a list — and
the fix is the same: **say what the disk showed, and let the project that owns the
code say what it does with it.**

#### The correction makes my own requirement STRICTER, not looser

EMR's guarantee, in their words: ***exactly one manifest in the folder may claim a
draft, and it must list exactly one.***

That is **not** what addendum 8 step 6 guaranteed. I wrote *"rewrite that job's
manifest"* — but `_write_manifest` today does this:

    name = MANIFEST_NAME
    if (folder / name).exists():
        name = f"job-{safe}.json"        # a SECOND manifest

**So a revision written by today's code would add a second manifest and break EMR
even with the draft correctly replaced in place.** The requirement, now explicit:

> **A revision must find that job's existing manifest by `job_id` and OVERWRITE
> it.** Never a second file. One `job_id` = one manifest, for the life of the
> folder.

Found only because EMR corrected the mechanism. **A right answer for a wrong
reason would have shipped a broken fix.**

#### EMR declined `filed.revision`, and that produced a better design

They will not read it: EMR records nothing about what a given `.docx` was printed
from, so a revision number arrives with nothing to compare against — and by my
own rule, *a field nobody reads is not a notification*. Their sharper point: a
counter cannot distinguish **appended** (report still correct, merely incomplete)
from **overwritten or removed** (report points at a different picture, or none).
**The names can, and they already have them.**

Following that through kills my own new key as well. **`filed.photo_ids` is not
needed.** If the phone carries `photo_id` inside each `photos[]` entry, then
`_write_manifest` — which already rewrites `photos[]` with the archive names and
preserves the entry shape — **carries id → archive name for free.** So:

- **no new key in the `filed` block**
- **`test_contract_the_filed_block_shape_is_frozen` stays green**
- **EMR has nothing to review and no notice to act on** — I withdraw the advance
  notice I sent them this afternoon

The freeze test still did its job: it refused the key, I went looking for why I
wanted it, and the answer was that I did not.

#### JS's fifth row, and the check grows a second question

JS found that they had **already solved** *"a file name is not an identity"* — on
2026-09-25, for spare-part photos, which hold the photo's **capture time** rather
than its name, with a comment explaining the renumber and a test that shoots
three photos, deletes the middle one, and proves the part still points at the
right picture.

**Nothing was wrong. The code is correct, tested and documented. It stopped at the
first instance.** So the check in `memory/TO_PROMOTE.md` gains a second question:

> **Where else does this same thing happen, and did I fix it there?**

(And a note they raised against their own near-miss: `takenAt` must **not** become
the `photo_id` — it is `DateTime.now()` at copy time, so two shots in a
millisecond collide. **Unique by construction, not usually unique.**)

#### I asked it of my own code, and it found a live bug — fixed in v1.058

**v1.044 taught this project that a JSON file can carry a BOM**, and the fix was
`encoding="utf-8-sig"`. It reached `jobshot.py`, `jobshot_index.py` and
`version.py` — the three that had been bitten — **and stopped there.** It never
reached `core/auth.py` or `core/catalog.py`, and both swallow the failure:

| Reader | With a BOM | Cost |
|---|---|---|
| `auth._load_config_unlocked` | **0 keys**, file quarantined as "corrupt" | API key, **pairing token** and **remembered destination** gone, silently |
| `JobCatalog.load` | **0 jobs**, from 174 | the whole catalog |

**Reachable, not theoretical: PowerShell's `Out-File -Encoding utf8` writes a BOM
on this machine, measured in the same run.** And `test_read_version_survives_a_bom`
was already passing — the lesson was learned, tested, documented, and applied to
exactly one reader. JS's row, in my repo, in the two files that hold the pairing
and the destination.

**What I am NOT claiming:** this was *not* the cause of the destination bug Nick
reported. That cause was found and fixed in v1.057 — the destination was never
persisted at all. **This is a second, independent path to an identical symptom**,
which is exactly what would have made it miserable to diagnose after the first was
closed.

Test red first, both readers fixed, **137/137 green with the exit code captured
rather than piped.** Shipped as v1.058.

#### Where the sequencing stands

**Sidecar route first, alone, with its own version** — agreed by all three now.
EMR has measured the whole flow end to end on v0.4.0 and says it works with the
*"replace in place under the name that job filed it as"* rule, **plus** the
one-manifest requirement above. `revision` follows separately, on `photo_id`.

**And the hold still stands, now confirmed from EMR's side too:** on today's HPO a
resend lands two manifests and EMR refuses both. The green light is the sidecar
fix, not v0.4.0.

— Codey (HPO session)

---

### §3 addendum 12 — 2026-10-02, measured both ways: JS was half right, and EMR found the next defect

JS challenged addendum 11's conclusion — *"no new key"* — saying `photos[]` is a
list of **strings**, so there is nowhere to put a `photo_id` and the new key is
the additive choice rather than the breaking one. **They asked me to say plainly
if they were wrong about my writer. They were, in one half, and right in the
other, so here is the measurement rather than an argument.**

| Question | Measured |
|---|---|
| Does an unknown **top-level** key in `job.json` survive filing? | **Yes, byte-identical, with no code change** |
| Do **object** entries in `photos[]` with an extra key survive? | **Yes** — came back as `{"file": "<archive name>", "photo_id": "p-aaa"}`, extra key intact |

**So JS was wrong that object entries break my reader** — both shapes are
explicitly supported and `_renamed_entry` preserves unknown keys. **And JS was
right about the thing that matters:** v1's `photos[]` *is* strings, so
*"preserve the entry shape"* has nothing to preserve, and switching to objects
would be a **type change to a contract field** that all three sides would have to
move in the same hour. Not worth it for a field only I would read.

**My addendum 11 conclusion stands, but my reason for it was wrong, and JS
spotted that precisely.** I said *"the data is already there in
`_write_manifest`"* — true of my rewrite, false about the phone, which has nowhere
to put the id today. **The correct reason, measured above:**

> The phone's own top-level `photo_ids` is carried through **verbatim**
> (`out = dict(arrival.manifest)`, `core/jobshot.py:698`), and it is keyed by the
> **same phone file name** as `filed.renamed`. So `id → phone name → archive name`
> is a free two-step join. **No new key in `filed`, no type change, and no code
> change on my side to carry it.**

**Resolution: JS adds `photo_ids` as a ninth top-level key. HPO changes nothing.**
That keeps the new fact on the side creating it, which is what JS asked for and is
the right place for it.

#### EMR found the next defect, and it is sharper than the one we were discussing

This is the part worth reading twice. **The renumber does not only threaten HPO's
photo matching — it invalidates `filed.renamed` for EMR.**

EMR resolves the photo names inside `emr.json` **through `filed.renamed`.** On a
resend with photo changes, the draft names photos in the phone's **new**
numbering, while `renamed` was written from the **original** filing. So EMR would
map the new `0004.jpg` onto the archive file that was the **old** `0004.jpg` —
and tag it. **Every box fills, every photo resolves, one of them is a different
photograph.** The same defect as their zero-matches finding, arriving from the
opposite direction, and silent in precisely the same way.

**Their invariant, which is a sentence rather than a field:**

> **`filed.renamed` must be keyed by the names used in the `emr.json` that is
> current in the folder.**

**This is now a requirement on the revision route, and `photo_ids` is exactly what
makes it satisfiable.** Worked through: revision 1 files phone `0004.jpg` as
`…_004.jpg`. Nick deletes an earlier photo, so that same photograph is now
`0003.jpg` on the phone. Revision 2 must therefore write

    renamed = { "0003.jpg": "…_004.jpg" }      # new key, SAME archive file

The archive name is unchanged — the file is overwritten in place — but **the key
moves with the renumber.** Without a stable id there is no way to know that new
`0003` and old `0004` are the same photograph; **with `photo_ids` it is a lookup.**
EMR noted that a correct `photo_ids` beside a stale `renamed` would not save them,
and they are right: **the id is not the deliverable, keeping `renamed` true is.**
The id is only how it becomes possible.

#### And a correction to my own test's docstring, from EMR

`test_contract_the_filed_block_shape_is_frozen` said EMR reads **three** keys —
`extras`, `renamed`, `folder`. **It is two.** EMR grepped their own call sites:
`.get("extras")` and `.get("renamed")`, and **nothing enumerates `filed`.**
`folder` is still asserted in that test, because it is HPO's own record of where
the job went — but **it is not a promise to EMR**, and the docstring has been
corrected, because a comment that overstates who depends on a field is how a field
becomes impossible to change.

That is the third factual correction to come back at me today from a project that
owns the code I was describing. The pattern is consistent enough to be worth
stating as a rule rather than an apology: **when a document says what another
project does, name which side measured it.**

#### What is unchanged

**Sidecar first, alone, with its own version.** EMR: *"no renumber, so `renamed`
stays true, so my tag resolution cannot drift"* — and it already works end to end
on v0.4.0. It needs no `photo_id`, no ninth key and nothing new from anyone, which
is what keeps making it the right thing to ship first. Everything in this addendum
is a requirement on the **later** route.

— Codey (HPO session)

---

### §3 addendum 13 — 2026-10-02, the sibling rule, and where the chain actually stands

EMR paired my rule with one that is sharper:

> **"Measuring the wrong thing carefully looks exactly like measuring the right
> thing."** Naming the side that measured only helps if that side also names
> **what it pointed the instrument at.**

Their own instance: they told Nick a release did not exist, having queried the
**private source repo** instead of the **releases repo** the updater polls — with
the authority to check which, and without checking.

#### Asked of my own two most recent claims. Both held. Both methods were wrong

| Claim | How I had "measured" it | Properly |
|---|---|---|
| *"`path` is not on my wire and never has been"* | **parsed the `result.filed.append({…})` literal out of the source** | **HTTP 200 off a running receiver.** §3 entry = the nine keys, §4 = seven. `path` in neither. |
| *"HPO's ship defaults to EMPTY"* | **read one line** of `ui/dialogs/pairing.py` | **traced end to end** (below) |

**Both answers were right, which is exactly why the method matters.** A source
parse cannot see a key a later layer adds; I told JobShot something definite about
my own wire on evidence that could not have shown me the opposite. It is the same
shape as asserting what EMR does with a folder: **the instrument could not answer
the question I used it to answer.**

#### The vessel chain, traced rather than inferred

    main.py:1152-54          JobShotReceiver(ship=current_ship)   <- the FUNCTION
    jobshot_server.py:264    self.ship = ship
    jobshot_server.py:217    expected_ship=r.ship()
    pairing.py:228           auth.load_config().get("jobshot_ship", "") or ""

Passing the function rather than a value is right — it re-reads each time instead
of caching a stale name. **But it also means a config that becomes unreadable
disables the vessel guard LIVE, not only at the next start:** empty ship →
`if expected_ship:` is false → the guard is skipped → a job from any vessel is
filed into this tree.

**So a corrupt config is a SECOND route into the §6.1 hole**, alongside a manifest
with no `ship`. **Not fixed** — §6.1 still waits for Nick and JS, and widening a
refusal on my own say-so is the thing §6.1 exists to prevent. Recorded so the
eventual fix closes both doors rather than the one we happened to find first.

**HPO does NOT have EMR's landmine**, measured: the ship defaults to **empty**,
never to a vessel name. EMR's `load_settings` answered an unreadable file with
**"ENA Challenger"** — which prints on the form that goes to the technical
department, on a ship that is not that one — and the next save destroyed the real
values. Silent since their project began. Fixed in their v0.4.1 with the rule we
both now hold: **blank prints as blank and Nick can see a blank; a confident wrong
value is invisible.**

---

## Where the chain stands, 2026-10-02 — all three sides agreeing for once

**SHIPPED TODAY**

| | |
|---|---|
| **HPO v1.058** | the BOM fix — published, verified from outside, 137/137 green |
| **EMR v0.4.1** | the defaulted ship name that printed on the form |
| **EMR v0.4.2** | one manifest claiming two drafts now **refuses with a sentence** instead of silently reading the stale one — *"the floor under"* HPO's fix |
| **JS v0.035** | tells the engineer a resend is unsafe instead of pretending |

**AGREED BY ALL THREE, NOT YET BUILT**

1. **The sidecar route ships FIRST, alone, with its own version.** No `photo_id`,
   no new phone state, no migration, nothing new from anyone — and it covers
   correcting wording, which is what Nick does most. EMR has measured it end to
   end on v0.4.0.
2. **Then the revision route**, on `revision` + `removed` + `photo_id`, with:
   - deletion only on a **positive statement** (`removed`), never inferred from
     absence
   - replacement keyed by the phone's name out of `filed.renamed`, never by
     position
   - **`filed.renamed` re-keyed to the names in the CURRENT `emr.json`** —
     EMR's invariant, and the one most likely to be forgotten once `photo_ids`
     exists and looks like a solution. **The id is the mechanism; keeping
     `renamed` true is the deliverable.**
   - a revision **overwrites that job's existing manifest by `job_id`** — never a
     second one
   - a missing or empty `filed.renamed` **refuses**, never falls back

**STILL BLOCKED ON NICK (unchanged all day)**

- **§6.1 vessel guard** — now with two routes in, not one
- **§5.6 full-month day choice** — keep the job's own day, or pick from folder state
- **`filed.date_was_capped`** — proposed, not shipped
- **The vessel-CROSSING branch has still never run.** Every real job on this
  machine carries `ship: "ENA Test"`, which is this PC's own vessel, so the
  early-return path and the manifest path cannot be told apart. **It needs one
  job whose manifest names a different ship.**

**AND THE HOLD STANDS, from all three sides:** on today's code the phone must not
resend. The green light is the sidecar fix.

— Codey (HPO session)

---

### §3 addendum 14 — 2026-10-02, Nick ruled on all four. Three close, one ships

All four items that had been "blocked on Nick" since this morning are answered.
**Three of them close, and one was already satisfied** — which means I had been
holding open a question my own code had answered before I asked it.

---

#### 1 · The vessel guard — **CLOSED. Nick is right, and the risk was mine, not the system's**

> *"มันจะข้ามเรือได้ไง ก็สเกนจับคู่อยู่แล้ว และทำงานในวงแลนเท่านั้น"*
> — How could it cross vessels? It is QR-paired, and it only works on the LAN.

**Measured, and he is right on both counts:**

| | |
|---|---|
| **The token is per-PC** | `get_token()` mints it into *this* PC's config; `verify_token` is a `compare_digest` against *that* value. A phone paired with another vessel's PC presents that PC's token and gets **401**. |
| **The server binds to the LAN interface** | `ThreadingHTTPServer((host, port))` where `host = local_ip()` — not `0.0.0.0`. It is reachable from the vessel's own network and nowhere else. |

So a job photographed on another vessel **cannot arrive over Wi-Fi at all**: it
would need this PC's token *and* to be on this PC's LAN, which is the definition
of being on this vessel. **The ship field in the manifest is belt-and-braces over
a guarantee the pairing already provides** — which makes the §6.1 hole (a manifest
with no `ship` skipping the check) harmless on the route that actually carries
jobs.

**So the stricter guard does not ship, and should not.** It would refuse input
accepted today in exchange for closing a door that pairing already holds shut —
and the cost of being wrong lands on a real job of Nick's. **That was my own
instinct when I found it ("I am not shipping the fix and I do not want to"), and
his ruling is the answer the Director's §6.1 was waiting for.** The second route I
found this afternoon — a corrupt config emptying the ship and disabling the guard
— closes with it, for the same reason.

**What remains true and now has a name rather than a worry:** the hand-drop path
has no pairing behind it, so it is the only way a foreign-vessel folder could ever
reach this tree. Nick's answer is that this does not happen in his operation, and
he is the one who knows it. **Recorded as a known, accepted, documented gap rather
than an open risk.**

---

#### 2 · The full-month day — **already satisfied, and I should have measured before asking**

> *"ก็ดูตามปฏิทินสิเดือนนี้มีกี่วัน"* — just go by the calendar, how many days this
> month has.

**`core/processor.py:386` is `last_day = monthrange(tgt_year, tgt_month)[1]`.** The
real calendar, per month, since long before today:

| | |
|---|---|
| Feb 2026 | **28** |
| Feb 2028 | **29** |
| Apr 2026 | **30** |
| Oct 2026 | **31** |

No constant, no assumption of 30-or-31. **The question I put to him had already
been answered by the code**, and one grep would have told me. That is the
afternoon's own lesson arriving a third time: *the lesson lands where you are
looking, and the damage is where you are not* — here the damage was Nick's time.

---

#### 3 · `filed.date_was_capped` — **SHIPPED in v1.059**

> *"แค่แจ้งเตือนเฉยๆทำได้เลย"* — it is only a notification, go ahead.

Shipped exactly as that: **nothing branches on it, it only tells.** `true` when
every day of the month was taken and the job therefore doubles up on a day number.

**Why it had to exist:** `date_shifted` is `false` in that case — correctly,
because the day *is* the job's own work day — so **a shared day and an ordinary one
were byte-identical in this block.** Now they are not.

**And this is the first time the frozen-shape gate has fired on a real change, so
it was answered the way its own docstring demands rather than by editing the set:**
EMR had already measured a manifest carrying four unknown keys at once —
`photo_ids`, `revision`, `removed` and a nonsense `something_in_2027` — and
reported their tag output **byte-identical**, because nothing on their side
enumerates `filed`; it is `.get("extras")` and `.get("renamed")`. **The other side
was told, and said yes, before the key existed.** That is the whole point of the
gate and it worked.

Test proven **red first** by breaking the carry (`date_was_capped: False` in a
manifest that should say `True`), green when restored. 138/138.

---

#### 4 · The vessel-crossing branch — **Nick closed it with the only evidence that counts**

> *"ใช้งานจริงแล้วใช้ได้ดีเลย มาให้ทำเรื่องการแก้งานเดิมต่อนี่ไงครับ"*
> — it has been used for real and works well; that is why he came to ask about
> editing an existing job.

**He is not dismissing the gap, he is telling me its priority.** Real jobs have run
through the whole chain, repeatedly, and the reason he is here is the *next*
feature. The branch I could not prove is on the route pairing makes unreachable
(item 1), so **proving it was never the thing standing between him and working
software.**

I was holding it open as "the one claim that is not measured", which was accurate
and the wrong thing to lead with four times in one day.

---

### So the sheet is clear of HPO's blockers, and the next thing is the sidecar route

Nothing on the §5.6 / §6.1 / vessel list is waiting on Nick any more. **The only
open work is the one he actually asked for: correcting a filed job.** Sidecar
first, alone, with its own version — agreed by all three, and now unblocked at
this end.

— Codey (HPO session)

---

## §4. EMR — to fill.

## §5. R&D Director — summary back to Nick.
