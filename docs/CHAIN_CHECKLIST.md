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

— Codey (HPO session)

---

## §4. EMR — to fill.

## §5. R&D Director — summary back to Nick.
