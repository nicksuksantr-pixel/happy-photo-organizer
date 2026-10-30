# What is actually open — Happy Photo Organizer

**Written 2026-10-20 for the Director handover.** One screen, so nobody has to
reconstruct it from seventeen addenda in `CHAIN_CHECKLIST.md`. **Current state
only — the reasoning lives in the addenda this points at.**

Everything below is in git. **Nothing of this project exists only in a session.**

---

## 🔴 Waiting on Nick — nothing

**The two agent-cap hook items listed here until 2026-10-30 were already fixed.**
They arrived through the master sync `e46ffd5` (2026-10-20, command_pattern
**v3.19**, "agent cap gates D+E"). This page was written the same day and never
caught up. Re-measured 2026-10-30 by driving `tools/workflow-agent-cap.mjs` with
synthetic payloads, 0 agents. **The Director measured the same thing independently
that day** and found this copy byte-identical to the live `~/.claude/hooks` one:

| Script | Now |
|---|---|
| `MAX_AGENTS: 3`, `for (let i=0;i<40;i++) await agent(…)` | **refused**: *"a for loop calls agent() 40 times, over 5"* (gate D) |
| `MAX_AGENTS: 3`, `while (budget.remaining()>5) await agent(…)` | **refused** (gate D) |
| `MAX_AGENTS: 3`, named literal of 10, `parallel(L.map(…))` | **refused, true reason**: *"fans out 10 ways, over 5"* |
| `MAX_AGENTS: 1`, literal of 5 | **refused**: *"declares MAX_AGENTS: 1"* (gate E) |
| `MAX_AGENTS: 3`, literal of 3 | allowed |
| `MAX_AGENTS: 1`, `log("searching for things (quickly)")` + one `agent()` | allowed (strings are blanked before matching) |

⚠ When driving it from Git Bash, pass the script inside the JSON, not as a bare
`node -e` argument. The argument path drops the inner `"`, so a string turns into
code and a false refusal appears that the hook does not actually give.

---

## 🟡 Needs all three projects + a version on the sheet

| Item | State |
|---|---|
| **LAN_PROTOCOL v1.2** — `revision`, `removed`, `photo_id` for correcting a job's **photographs** | Designed and agreed in principle by all three (§3 addenda 8–10). **Not started by anyone.** Deliberately sequenced after the sidecar route. |
| **A machine identity in the §2 ping reply** | **The gap that cost a week.** HPO's ping prints `ship` and no host; JobShot's `Receipt` carries no PC identity at all, while every string in their app says *"the PC"*. **One printed an identity nobody read, one never printed one** — which is why two installations on one LAN stayed invisible for days. My half is cheap and additive; theirs has to persist it. **Neither of us has built it, and neither has been asked to.** |

---

## ✅ Closed — recorded here because the handover note still lists one of them as open

| Item | Ruling |
|---|---|
| **§6.1 — the vessel guard** (refusing a manifest with no `ship`) | **CLOSED by Nick, 2026-10-02. Not shipping, and should not.** *"มันจะข้ามเรือได้ไง ก็สเกนจับคู่อยู่แล้ว และทำงานในวงแลนเท่านั้น"* — the token is per-PC and the socket binds to the LAN interface, both measured, so a job cannot arrive from another vessel over Wi-Fi at all. Shipping it would refuse input accepted today for no gain. §3 addendum 14, and `CHAIN_CHECKLIST.md:1251`. **The 2026-10-20 Director handover lists this as still waiting on Nick; it is not.** |
| §5.6 — the full-month day rule | Already correct before I asked. `monthrange()`, real calendar per month. |
| `filed.date_was_capped` | Shipped v1.059 on Nick's approval. |
| The vessel-**crossing** test gap | Explained, not outstanding: **this machine is the test installation** (ship `ENA Test`), so of course every job it holds names its own vessel. Addendum 17. |

---

## 📦 The sidecar route — **unused, not unverified**

**Nobody owes anything here.** Nick has never had a job that needed correcting
(*"ยังไม่เคยยิงซ้ำจริงๆสักที"*), so the archive side was never a verification debt —
**it is an unused feature**, and a debt justifies pressing where an unused feature
does not. All three of us had been pressing. §3.6.

| | |
|---|---|
| HPO | implemented v1.060, hardened v1.062 |
| JobShot | built and installed, v0.038+ |
| EMR | v0.4.7 live; v0.4.2 refuses two drafts under one manifest |
| **The real PC** | `DESKTOP-NPAM51V` · `192.168.110.167` · ship **`ENA CHALLENGER`** · **v1.062** |
| **This machine** | ship **`ENA Test`** — the **test** install. Its archive is not Nick's real one. |
| Exercised in anger | **zero.** One cable test, 2026-10-03 06:49:14, on **v1.060** — 44 min before v1.062 existed. |

**Green light given 2026-10-13.** The next correction Nick actually needs will be
the first real use, and the folder gets read afterwards as a by-product.

---

## 📤 Handed to the rules session — consumed 2026-10-20

`memory/TO_PROMOTE.md` — **nothing waiting.** All four items reached the master
and came back in the mirror at `e46ffd5` (command_pattern v3.19), each row read
at that commit: `an-absence-is-not-a-fact` · `a-true-fact-is-not-evidence-for-the-next-thing` ·
`the-unread-field` · `wanting-the-confirmation-is-not-the-user-needing-to-act`.
⚠ The first was handed over as an *amendment*, but the row it amended had
**never reached the master** — it landed as a whole row (original + widening).

---

## ✅ Found while shipping v1.063 — fixed 2026-10-23 on Nick's word

| Item | State |
|---|---|
| **`publish_release.py` reads `latest` the instant it publishes** | **Fixed** (Nick: *"Fix the publish_release.py gate so it waits and re-checks `latest`"*). What happened: 2026-10-23 16:24Z, published, `gate_published` read `latest` at once, got **v1.062**, and advised *"revert it to a draft now"* — seconds later every gate passed. **Following it would have un-published a good release.** Fix: `settle()` re-asks while a gate raises `NotYetKnown` (an OLDER `latest`, GitHub not answering, or the updater not offering it yet) for **120 s / 7 asks** — longer than the `Cache-Control: max-age=60, s-maxage=60` the endpoint sends (measured), gentle on the 60/h unauthenticated limit. A real refusal (no asset, wrong bytes) still comes on the **first** ask. **"Revert it to a draft" is now said only when `latest` names THIS release** — a `latest` naming another tag means users are not on it, so reverting changes nothing. Same fix caught a second wrong case: `--check 1.062` today also said "revert it to a draft now". 5 new tests; the 23-10 sequence replayed through the old `publish()` refuses on read 1, through the new one publishes on read 3; live `--check 1.063 --previous 1.062` passes. |

---

## 📦 Shipped in v1.064 (2026-10-30, Nick: *"แก้ไขที่เห็นสมควรเลย … แล้วก็ออกเวอร์ชันใหม่ไปเลย"*)

Held on `main` from 2026-10-29 (*"no release yet"*) until this release.

| Item | State |
|---|---|
| **The latest arrival is the job's record** | Found while preparing this release, as a direct effect of the no-overwrite fix below. With 4+ arrivals of one `job_id`, `find_manifest_path` returned the first match in sort order (`-2` before `-3`, `-10` before `-2`). A phone correction to the latest draft was therefore refused with 409 *"this job did not file …"*, and with the index lost the receipt named a different draft. Now arrival order is read from the names, and `jobshot_index._scan` uses the same chooser, so the two routes cannot disagree. 2 tests, red first. |
| **Sidecar route writes report drafts only**, and **the upload never files `report_history.json`** | Done, with JobShot's proposal and Nick's go. EMR v0.4.9 writes its own `report_history.json` into the job folder (CHAIN_ALIGNMENT §4). Before this, a phone file under that name would have been filed and listed in `filed.extras`, and a later correction could then have overwritten EMR's history. Now the upload skips the name case-insensitively, with a warning and no `extras` entry, and the correction route answers **409** for anything other than `emr.json` / `emr-*.json`. 2 new tests, both red on the old code; the multi-file tests now use `emr-notes.json` etc. instead of `notes.json`. CHANGELOG 1.064. |
| **A resend never erases an earlier arrival**, and **the §4 probe's 404 says when it cannot be trusted** (Nick, 2026-10-30: *"1+2"*) | Both were found answering EMR's second-`emr.json` question (`CHAIN_ALIGNMENT_RESPONSE.md`, paths 2b and 2a). (1) `_copy_extras` / `_write_manifest` only checked the first name, so a third arrival of one `job_id` overwrote the second's `emr-<id>.json` and `job-<id>.json`. Now `_job_own_name` goes on to `-2`, `-3` and so on, and the warning says the job had arrived before. (2) `GET /jobshot/v1/job/<id>` now adds `unreadable_records` to its 404 when a `job*.json` cannot be parsed. This is the same field the sidecar route has had since 2026-10-02. It is additive, and the status is still 404. **JobShot reads it from JS v0.045 on** (`9b559fb`, per the Director 2026-10-30, mirror `a2c02a6`): when the field is present, the phone refuses to upload, keeps the job Ready, and tells the engineer to check HPO's log. **So the guard is live once v1.064 is on the ship's PC.** 2 new tests, both red on the old code. Photos still multiply on a resend, which is the `revision` work. CHANGELOG 1.064. |

## 🔧 On `main`, not released — stopping one job being filed twice (Nick, 2026-10-30, via the Director)

Nick took all four fixes for duplicate filings on 2026-10-30. HPO's part is
items 1 and 2. JobShot builds the phone-side lock and the "wait" message, and
EMR takes the newest draft using v1.064's ranking rule.

| Item | State |
|---|---|
| **1. The §4 probe waits for a job being filed** | **Built, on `main`.** It covers every route. Measured on one 15-photo job: held 15.7 s and 16.3 s, then 200. After 120 s it answers 503 `filing: true`, never 404. Four tests, red first. **The 503 waits for JobShot's confirmation of what the phone does with it before release.** |
| **2. Read `X-JobShot-Job-Ids` on the upload**, so the hold starts at the first byte | **Proposed to JS, not built.** One header, a comma-separated list of every `job_id` in the zip, used only to hold probes, never to decide what is filed. Without it, today's phone still gets 404 for 1–2 s over loopback, and for the whole transfer time over Wi-Fi. Needs JS's yes, a protocol version from the Director, and a CHAIN_CHECKLIST line. |

Release plan: one version with both items, so the ship PC takes one update.
It still has to take v1.064 first.

## State of the tree, at the time of writing

    VERSION 1.064 (2026-10-30 — RELEASED 02:45Z, verified from outside; a phone job sent twice no longer erases anything), see CHANGELOG
    182/182 tests green
    working tree clean, 0 ahead / 0 behind origin
    releases go through tools/publish_release.py — 8 gates, each proven to refuse,
    and a `latest` that has not caught up is waited for, not reverted

— Codey (HPO session)
