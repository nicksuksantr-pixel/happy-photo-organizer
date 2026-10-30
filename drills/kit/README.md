# Drill kit (UPDATE_DRILL §5a)

A generic update-drill harness for a Windows desktop app that updates itself.
**Nothing in this folder names an app.** Everything app-specific lives in the
project's `drills/drill.json` (the manifest) and the adapter script it names.
Windows PowerShell 5.1, ASCII only, no modules to install: it runs as a
standard `drill` account that cannot read the developer's profile.

| File | What it does |
|---|---|
| `Invoke-Drill.ps1` | The runner: installs FROM, loads fixtures, lets FROM update itself, measures every §4 check, injects failures, writes `<OutDir>\<ver>.json` (schema `update-drill/1`) and `<OutDir>\logs\<ver>.log`. Exit 0 only if every check passed. `-Reset` removes what a drill installed (the adapter refuses outside a drill account). |
| `FakeFeed.ps1` | A loopback (127.0.0.1) fake `releases/latest` + asset server. Range/206 resume, fault switches (`truncate`, `flip`, `500`, `drop` per asset; `500`, `403`, `drop` for `/latest`), and a JSONL access log as the oracle for "no update loop" and "sees N+1". It re-reads its state file on every request, so the runner switches scenarios by rewriting one file. |
| `DrillKit.psm1` | Shared helpers: drill log, hashing and tree diffs, shortcuts, the app's processes, the app's update log (`<ISO> UPDATE <STAGE> <version> <detail>` / `<ISO> STARTED <version> <exe>`), Win32 window lookup/close, feed state, receipt writer. |
| `Stage-Drill.ps1` | Copies the kit, manifest, adapter and the FROM/TO release files into the manifest's `stage_dir` (under `C:\Users\Public`) and writes `run.ps1` / `reset.ps1` there. Refuses to stage anything that looks like a key or token. |
| `Collect-Drill.ps1` | Copies the receipt and logs back into the repo's `drills/`, runs `tools/release-gate.mjs --validate` when present, removes the stage. |

## What the app must provide (UPDATE_DRILL §3)

- `<drill_env>=1` plus `<feed_env>=http://127.0.0.1:<port>/latest`: check that feed, at start.
- The update log at the manifest's `update_log`, one line per stage
  (`CHECK FOUND DOWNLOADED VERIFIED REFUSED HANDOVER SWAPPED FAILED CLEANED`) and a `STARTED` line per start.
- A way to lay out a fresh install of the candidate into an empty folder (the adapter's `Invoke-FreshInstall`).

## The adapter contract

The manifest's `adapter` is dot-sourced by the runner and must define:
`Install-FromBuild`, `Set-DrillFixtures`, `Get-FixtureReport`, `Start-TheApp`, `Invoke-FreshInstall`,
`Get-FromRouteEvidence`, `Set-AppBusy`, `Clear-AppBusy`, `Restore-AfterBusy`, `Reset-DrillAccount`,
`Get-LayoutDescription`. The header of `Invoke-Drill.ps1` lists their parameters.

## Rules it keeps

- Runs **outside the Claude app** (its MSIX container virtualises `%LOCALAPPDATA%`); the runner writes a marker
  file to confirm from a second, unpackaged shell.
- Refuses any account whose name does not match the manifest's `drill_user_like`: a drill installs, closes and
  deletes the app, so it must never run in a real user's account.
- Refuses to run as an administrator: a UAC prompt is a fail, not a step.
- One drill at a time on the PC: takes `C:\Users\Public\drill-busy.txt` (atomically) before installing anything,
  waits while another app's drill holds it, and removes only a lock it took, pass or fail.
- Refuses a FROM file whose SHA-256 is not the manifest's released one.
- Refuses an account that already has the app or its data (run `-Reset` first).
- Never writes a receipt by hand: only the runner writes one, and every check it could not measure is a `fail`.
