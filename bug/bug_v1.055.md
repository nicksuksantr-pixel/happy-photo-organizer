# Bug Log — v1.055

> **Status: OPEN — deferred by Nick ("จดไว้ค่อยแก้พร้อมครั้งหน้าไม่รีบ", 2026-09-26).**
> Nothing here is fixed. This file is the brief for the session that does fix it.
> Diagnosed read-only by three independent investigations; **nobody ran the app** —
> every claim below is from source, cited to `file:line`. Confirm against a running
> window before trusting the reproduction steps.

## BUG-1: after a batch is committed, nothing can clear the job list but a restart

- **Reported by:** Nick, 2026-09-26 — *"แอพเราเองเวลาสร้างงานเสร็จแล้วเคลียงานจากลิสเพื่อทำใหม่ไม่ได้นะ
  ต้องปิดโปรแกรมเปิดใหม่เท่านั้น"*
- **Severity:** daily friction, no data loss on this path. But see BUG-2 and BUG-3,
  which are the same root cause with teeth.
- **Root cause — the control does not exist.** All three investigations agree. The
  only code in the app that empties Step 3 is inside `_start_phase12`
  (`main.py:1473-1481`): `_rename_done = False`, `self.plan = None`, destroy every
  child of `self.table_scroll`. It is reachable **only** by pressing *Start AI
  Tagging* (`main.py:429`) or Ctrl+Enter. Clearing is a side effect of launching the
  next run, never an action Nick can take on its own. `grep -n "    def "` over
  `MainWindow` shows no `_clear_plan`, `_new_batch`, `_reset_all` or equivalent — so
  this is **not** the project's recurring "finished feature with no entry point"; the
  feature was never written.
- **Why the obvious button does not work.** The one control labelled **Clear**
  (`main.py:372`) calls `_clear_sources` (`main.py:1396-1401`), which clears
  `self.source_paths` and refreshes two labels. It never touches `self.plan`, the
  rows, `review_summary`, `_rename_done` or `phase4_btn`. Pressing it after a commit
  changes nothing visible in Step 3 — **that is the moment the app reads as broken.**
- **Why a restart is the only thing that works:** a restart re-runs `__init__`.
  State that survives a commit and is otherwise reset nowhere:

  | State | Set | Cleared only at |
  |---|---|---|
  | `self.plan` | `main.py:1514` | `main.py:1478` (inside `_start_phase12`) |
  | JobRow widgets in `table_scroll` | `main.py:1622-1628` | `main.py:1479`, `1598` |
  | `self._rename_done` | `main.py:1836` | `main.py:1473` — pins Step 3's badge to "done" |
  | `self.source_paths` | `main.py:1098`, `1390` | `main.py:1399` (the Clear button) |
  | `review_summary` text | `main.py:1620`, `1758` | never restored |
  | progress bar / text | `main.py:1849` (100 %, "Done") | `_set_progress` or restart |
  | `a.temp_folder` on each assignment | `core/processor.py:829` | never — points at a `__pending_NN` path that no longer exists |

- **The only way to empty the list today** is per-row **Delete**
  (`ui/job_row.py:239-240` → `_delete_assignment`, `main.py:1640`), which fires a
  separate `askyesno` per row (`main.py:1651-1658`) worded as deleting photos from
  disk. Twenty rows = twenty destructive-sounding modals. Restarting is faster and
  feels safer, which is exactly the workaround Nick found.

## BUG-2: "Commit Rename" stays armed on a plan that has already been committed

- **Not reported — found while diagnosing BUG-1.**
- `_reset_buttons` (`main.py:1868-1876`) re-enables `phase4_btn` whenever
  `self.plan` is truthy (`1871-1872`), and the commit never nulls the plan. So the
  button is live again on a batch whose folders have already been renamed away.
- Pressing it runs `_start_phase4` over stale assignments whose `temp_folder` no
  longer exists: `rename_photos_for_folder` fails its `iterdir`
  (`core/processor.py:112-115`), the merge branch then iterates a missing folder
  (`core/processor.py:793`) and raises `FileNotFoundError`, caught at
  `core/processor.py:854-855`. Outcome: **renamed 0, one error per row, and a second
  "All Done" box.** Nothing is destroyed, but the app reports a finished run that did
  nothing.

## BUG-3: a second batch re-ingests the first one unless Nick presses Clear

- **Not reported — found while diagnosing BUG-1. This is the one with a real cost.**
- The commit does not clear `self.source_paths`, and `_on_drop` (`main.py:1096-1099`)
  and the browse button (`main.py:1389-1390`) both **append**. Phase 1 copies rather
  than moves (`core/processor.py:431`, `519`), so the previous batch's originals are
  still on disk and still listed.
- Drop a new folder without first pressing Clear and the next run re-collects the
  previous batch's photos too: resized again, sent to Gemini again (quota), and filed
  again as new folders on new day numbers.
- Nick currently avoids this by accident — the restart he uses to clear the list also
  clears `source_paths`. **Fixing BUG-1 without fixing this would remove the accident
  and expose the defect.** They must ship together.

## The fix, when it is time

Both investigations that proposed one proposed the same thing:

1. Factor `main.py:1473-1481` out into `MainWindow._reset_batch()` and have
   `_start_phase12` call it, so the two paths cannot drift. It should restore what
   `__init__` would: `plan = None`, `source_paths.clear()`, `_rename_done = False`,
   destroy the rows, `review_summary` back to "Not yet analyzed",
   `_sync_flagged_button(0)`, `_set_progress(0, "Ready")`, `phase4_btn` disabled,
   `_phase_start = None`, then `_refresh_sources()` + `_refresh_step_states()`.
2. **Deliberately do not reset** `dest_root`, `catalog`, `receiver` or `usage_log` —
   Nick keeps the same destination between jobs.
3. Call it from `_on_rename_done` (`main.py:1835`) **only on a clean finish** —
   `result.errors` empty and `result.skipped == 0`. Rows that errored or were skipped
   still own live `__pending_` folders and must stay on screen.
4. Add the visible control next to *Commit Rename* ("Start a new batch"), because
   after a partial failure the automatic reset will not fire and Nick still needs a
   way out.
5. Guard it while a worker is alive (`self.worker.is_alive()`), or a running
   `_phase12_worker` will write `self.plan` back a moment later
   (`main.py:1514`).

**Blast radius:** `self.plan` is read at `main.py:563, 574, 1647, 1661, 1674,
1697-1723, 1731-1755, 1776-1792, 1817, 1871`. Every reader already handles `None`
(`if not self.plan: return`), so `None` itself is safe. The one human consequence:
nulling the plan flips Step 2 and Step 3 back to "pending" and erases the green
"done" badge Nick may read as his receipt — so the status line
(`main.py:1846-1849`, *"Renamed N folder(s)"*) must survive the reset.

**And it is a window change**, so per the v1.051 lesson it is not done until Nick has
sent a screenshot of it.

## What was not checked

- Nobody ran the app. No claim here is confirmed against live behaviour.
- `ui/dialogs/settings.py`, `pairing.py`, `ai_health.py` were only grepped for
  reset-like controls (none found), not read.
- `ui/job_row.py` was read for the delete path only; `_open_folder`
  (`ui/job_row.py:366`) was not verified.
- The JobShot/LAN import path files its jobs headlessly and does not use Step 3, so
  it was not examined for this defect.
