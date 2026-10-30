# Log — v1.058 → v1.065 (2026-10-02 → 2026-10-30)

**Backfilled on 2026-10-30** under rule #20.0. `log/` had stopped at v1.057 while
seven more versions shipped. One short entry per version, written from git log,
the GitHub release notes and `CHANGELOG.md`. The detail lives in those, and in
`docs/CHAIN_CHECKLIST.md` and `docs/PARKED.md`.

## v1.058 — 2026-10-02 — a BOM no longer un-pairs the phone or forgets the folder
- v1.044's BOM fix (`utf-8-sig`) had reached three readers and stopped there.
  `core/auth.py` and `core/catalog.py` still read a BOM file as corrupt and returned
  a default. The cost was silent: the API key, the pairing token and the remembered
  destination all lost, or a catalog of 0 jobs instead of 174.
- Found by asking JobShot's question of my own code: where else does this happen?
- Both readers fixed. Test red first. 137/137.

## v1.059 — 2026-10-02 — a full month now says so
- `filed.date_was_capped` is `true` when every day of the month was taken and the job
  shares a day number. It is a notification only, on Nick's approval (*"แค่แจ้งเตือนเฉยๆทำได้เลย"*).
- The month length comes from `monthrange`. The frozen `filed` shape test fired, and
  EMR confirmed before the key existed. 138/138.

## v1.060 — 2026-10-02 — correct a filed report without re-sending a photograph
- LAN_PROTOCOL v1.1, the sidecar route: `POST /jobshot/v1/sidecar` replaces a report
  draft on a filed job, in place. Re-uploading had turned 7 photos into 14.
- The gate: a name must be in that job's own `filed.extras`.
- Three-reviewer pass before release, 7 fixes, each red first. 157/157.

## v1.061 — never shipped
- Never published, and it has no tag. Commit `0cdcc14` ("v1.061 never shipped")
  records why. Its fixes went out in v1.062.

## v1.062 — 2026-10-03 — interrupted writes and damaged records
- The manifest beside a draft is written temp + fsync + replace, like the draft.
- A damaged job record no longer answers exactly like a job never filed: the §4 404
  carries `unreadable_records`.
- Three temp-file leaks closed.
- First release through `tools/publish_release.py` (eight gates, each proven to refuse). 166/166.

## v1.063 — 2026-10-23 — "offline" no longer reads "Up to date"
- `_fetch_latest_release` swallowed network errors into `None`, the same value as
  "nothing newer", so a PC with no internet said "Up to date (1.062)". Now it raises
  `UpdateCheckFailed`, and the button says "Updates: offline". 172/172.
- Found by applying SM's `not-known-is-not-no` lesson to this repo.

## v1.064 — 2026-10-30 — a job sent twice no longer erases anything
- A resend never overwrites an earlier arrival's `emr-<id>.json` / `job-<id>.json`.
- The latest arrival is the job's record (arrival order read from the names).
- The sidecar route writes report drafts only, and an upload never files `report_history.json`.
- The §4 404 carries `unreadable_records`, which JobShot reads from v0.045.

## v1.065 — 2026-10-30 — the "was this filed?" check waits for a job that is landing
- Root cause of duplicate jobs: the §4 probe answered 404 while a job was still being
  filed, and the phone re-sent it. Now the probe waits up to 20 s, then answers 200,
  or 404 if the filing failed, or 409 `receiving` if the job is still arriving.
- LAN_PROTOCOL v1.1.1: `X-JobShot-Job-Ids` holds the probe from the first byte. The
  header is a hint only and never a reason to refuse. 189/189.
- On the ship PC since 21:09 the same day (read from Nick's phone, JS `fb2d69f`).
