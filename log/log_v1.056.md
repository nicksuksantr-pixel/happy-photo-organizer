# Log — v1.056 (2026-09-26)

## Entry 1 — the list you could not clear

Nick: *"แอพเราเองเวลาสร้างงานเสร็จแล้วเคลียงานจากลิสเพื่อทำใหม่ไม่ได้นะ ต้องปิดโปรแกรมเปิดใหม่เท่านั้น"* —
after a batch is committed there was no way to empty the review list; closing and
reopening the app was the only thing that worked. He asked for it to be written
down and fixed next time; the written-down version (`bug/bug_v1.055.md`) turned
up two more defects behind it, and he then said fix all three together.

**1. There was no control.** Not a broken button — no button. The only code in
the app that emptied Step 3 lived inside `_start_phase12`, so clearing was a
side effect of launching the next AI run. The one control labelled *Clear*
emptied Step 1's source list and touched nothing in Step 3, which is exactly why
pressing it read as the app being broken. A restart worked because it re-runs
`__init__`.

**2. Commit stayed armed over a finished batch.** `_reset_buttons` re-enabled it
on any truthy plan, and nothing nulled the plan after a commit — so the button
sat live over folders that had already been renamed away. Pressing it walked
paths that no longer existed and reported an error for every row of a run that
had in fact succeeded.

**3. The commit left its sources loaded, and the drop zone appends.** Drop the
next job without pressing Clear and the batch that had just been filed was
collected again: resized again, sent to Gemini again, filed again on another day
number. Nick had never hit it **only because the restart he used to clear the
list also emptied the source list** — so fixing (1) without fixing (3) would
have removed the accident that was protecting him and exposed the defect.

### What shipped

- `JobAssignment.committed`, set only after a row's folder is actually in the
  archive. `phase4_rename_folders` skips a committed row and counts it in
  `CommitResult.already_done` — so a second commit is genuinely idempotent, and
  the real retry (name the row that was skipped, commit again) still works.
- `MainWindow._reset_batch(keep_sources=…)` — everything a restart used to be
  needed for, and deliberately nothing else: the destination, the catalog, the
  receiver and the usage log survive, because Nick files job after job into the
  same folder. `_start_phase12` now calls it, so the two paths cannot drift.
- **"Start a new batch"** in Step 3, always on screen, disabled when there is
  nothing to clear — a control that only appears in the state where it is needed
  is a control nobody learns about. It asks first when rows are uncommitted, and
  says plainly that their working folders stay and the originals are untouched.
- One `_sync_commit_button()`, consulted by every path that changes the plan.
- Phase 1 no longer walks into an abandoned `__pending_` folder (see Entry 3).

## Entry 2 — three reviewers, three "do not ship", and two defects I had added

The diff went to three independent read-only reviews before it went anywhere
near a build. All three said **do not ship**, and they were right. The two worst
findings were mine, introduced by the fix itself:

- **A cancelled commit was treated as a clean finish.** Cancel breaks the loop
  in `phase4_rename_folders`, so `renamed` is non-zero while rows 4-10 are
  untouched. Reading `renamed` alone, my code cleared his sources, flipped Step 3
  to *done*, set the bar to 100% and told him to start a new batch — with seven
  folders still un-filed. If he had believed the four "finished" signals he would
  have lost seven folders' AI names and their source paths in one click.
  Now everything is driven off what is **left**: `pending = self._pending_rows()`.
- **The clear threw away folders queued while the commit ran.** The drop zone has
  no busy guard, so anything Nick added during a commit was in `source_paths` —
  and a blanket `.clear()` removed it while logging that it had been filed.
  `_start_phase12` now snapshots the sources the batch actually consumed and only
  those are removed.

Plus: `_render_plan` armed Commit unconditionally (bypassing the new guard), the
receipt line *"Renamed N folder(s)"* was painted over by `_set_progress`'s "Done"
in the same callback so it never appeared, committed rows stayed editable while
their edits were silently ignored (`JobRow.mark_filed()` now disables them), and
"Start a new batch" was not greyed while a commit ran.

**Three of the six tests I wrote first asserted on `ast.unparse` spelling** — they
passed on the presence of an identifier, not on behaviour, and two of them went
red when the logic moved into a helper while the behaviour was unchanged. That is
the tell. They were replaced with behavioural tests driving the real `MainWindow`
methods against a stub window, which is what caught nothing and would have caught
everything.

## Entry 3 — the orphan that Phase 1 would have walked back into

A batch abandoned before its commit leaves its `__pending_NN` folder in the
destination, and the name is only the date plus a per-run counter. Phase 1 did
`mkdir(parents=True, exist_ok=True)` — so the next run on the same day walked
straight back into the abandoned folder and would have filed its leftover photos
under the new job's name. The only visible sign would have been a photo count
slightly larger than expected.

It predates this release. What made it worth fixing now is that the new button
turns "abandon a batch" from *restart the app* into a one-click action. Phase 1
now steps past any existing non-empty pending folder.

## Verification

- `tests/test_core.py` **119 → 130**, including the behavioural stub-window
  tests, one that plants an abandoned pending folder under the exact name Phase 1
  would have chosen, and one that asserts the new button actually comes alive.
- The second-commit guard was proven **red** against the old behaviour first
  (four errors) before being trusted.
- Build verified: payload VERSION 1.056, catalog 174.
- **Not verified, and it is a window change:** Nick has not seen it yet. Per the
  v1.051 lesson this is not finished until he sends a screenshot.

## Entry 3b — the verify round, and the test that only passed in company

The fixes from Entry 2 went back out to three read-only verifiers. All three
said **do not ship** again, and the most valuable thing they found was in my
tests rather than my code.

**Three tests drove `_on_rename_done`, which ends in `messagebox.showinfo` —
with the real Tk messagebox.** Run on its own, that test opens a modal and waits
for a click: proven, `timeout 25` returns exit 124. Inside the full run it
passed. **A gate whose result depends on what ran before it is not a gate**, and
it means the "127/127 green" I had already reported was not a result I was
entitled to. Every dialog is stubbed now, through one shared helper.

**And one new test was vacuous.** The abandoned-pending-folder test planted an
orphan dated 2026-09-21 while its fixture JPEGs carry no EXIF, so the group fell
back to today's date and the two names could never have collided — it passed on
the unfixed code too. Rewritten to ask Phase 1 what it *would* have called the
folder, plant the orphan under exactly that name, and then run: red on the old
code, green on the new one.

**Nothing asserted the button Nick asked for ever comes alive.** Hard-coding it
to `disabled` would have restored his original defect with every test green.
Covered now, across four states.

Code findings from the same round, all of them mine:

- `_render_plan`'s empty-plan early return jumped over `_sync_commit_button()`,
  so emptying the list with "Delete not-work" left Commit armed over no rows.
- `_render_plan` rebuilt rows without consulting `committed`, so any re-render
  after a partial commit handed back editable rows whose edits are ignored.
- A filed row's thumbnail still opened `temp_folder` — renamed away by the
  commit — so the one control left alive on a filed row answered *"the source
  folder has moved or been deleted"* about a row that had filed perfectly.
- **"Start a new batch" discarded a folder queued during the commit** — by way
  of the very click the "All Done" box recommends, undoing the protection Entry
  2 had just added. That button now clears the job list only; Step 1 keeps its
  own Clear.
- `_start_phase4` had no busy guard.
- `_delete_assignment` would "delete" a filed row's working folder that is not
  there any more and log a deletion that never happened.

Last one, and it is the same shape as the modal: the call to `mark_filed` was
wrapped in `except Exception: pass`. When the signature grew a parameter, the
`TypeError` went into that `pass` and **no row was ever marked** — green tests,
dead feature. The behavioural test caught it; the AST tests it replaced could
not have. The handler logs now.

## Entry 4 — the first real job, filed while this release was being built

Unrelated to the fix and worth recording where it happened: at **14:18:55** the
first real JobShot job carrying a report draft arrived over Wi-Fi and filed
cleanly under v1.055 — `26-09-26 Inspected and Serviced FloodLight`, six photos,
`emr.json` carried through, `extras: ["emr.json"]` in both the reply and the
manifest, `date_shifted: false`.

Two things it settled:

1. **The rename map earned itself on its first outing.** The draft references
   `0001.jpg`–`0006.jpg`; the folder holds `…_001.jpg`–`…_006.jpg`. All six
   resolve through `filed.renamed`. Shipped this morning; without it EMR would
   have matched zero and printed a complete-looking report with no photographs.
2. **`jobshot_filed.json` exists.** The two-day "silent failure" was never one —
   nothing had been filed on this machine since v1.052 made that failure report
   itself. The record was corrected this morning from an inference; the first
   real job confirmed it by measurement.
