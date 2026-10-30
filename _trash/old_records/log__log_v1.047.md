# Log — v1.047 (2026-09-22)

## Entry 1 — the import gets a way in, because Nick uses it tomorrow

The R&D Director's message: Nick is using this for real on **2026-09-23**, and
`import_job()` appears in `core/`, in the tests, in the CHANGELOG and in the
logs — **and in no UI file**. The code was finished and unreachable. That was
fine as a release-note problem yesterday; today it is the whole problem.

Three ways in were offered (drop target / button / script). **All three were
built**, because they cost little once the splitting rule exists and they fail
in different ways: the drop zone is the gesture Nick already uses, the button
covers the case where dragging is awkward, and the script still works when the
app will not start or the PC has no installed build.

### The rule that decides what a drop is
`jobshot.split_arrivals(paths)` → `(jobs, still-arriving, everything else)`.

- A folder with a `job.json` in it is a job.
- A folder is a **JobShot parent** only when one of its immediate children has
  a `job.json` — the case where Nick copies the whole JobShot directory off the
  phone. Its manifest-less siblings are transfers that were still running when
  the copy was made: reported as *not ready yet*, never processed, never
  deleted (the Director asked for exactly this, and it is also what the app
  already promised through `is_complete()`).
- Everything else is photos and goes to the card-reader path **exactly as
  before**. That guard is the whole reason the parent rule needs a `job.json`
  below it: without it, an ordinary folder of photos would be pulled away from
  the workflow it belongs to.

The rule lives in `core/jobshot.py`, not in `main.py`, so it can be tested
without opening a window — the test suite never imports the GUI.

### In the app
- The drop zone routes job folders to the importer and photos to Step 1, from
  the same drop. Hint text now reads "Drop photos, folders, or a job from the
  phone".
- A **From phone** button next to Clear opens a folder picker for the same
  path.
- Destination: `self.dest_root` if set, else the folder remembered for that
  vessel (step 3's `get_dest_root`), else ask once and remember it. An arriving
  job should file itself.
- The import runs on a worker thread with the progress bar and log wired up,
  and the log says what was filed, what merged, what shifted date, and what was
  skipped as still arriving. A summary dialog lists the folders at the end.
- Any exception in the worker is caught, logged with its traceback, and leaves
  the app alive — a bad manifest must never take down the window.

### On the command line
`python scripts/import_job.py <folder> [...] [--dest <folder>] [--remember]`.
Accepts a parent folder, same rule as the drop zone. Prints what was filed,
what merged, what shifted, and what was skipped; exits non-zero only when
something actually failed — a still-arriving folder is a skip, not a failure.

## Entry 2 — the version gate accepted `true` (and `1.0`)

EMR hit this in its own gate and the Director passed it on: `"jobshot": true`
sailed through `version != SUPPORTED_MANIFEST_VERSION`, because `True == 1` in
Python. **Probed rather than read, and it was worse than reported — `1.0` also
passed**, since `1.0 == 1`. A float or a boolean where the version belongs is
exactly the sender bug the gate exists to catch, and it would have let a
manifest nobody validated file a job.

Fixed by demanding a real `int`:
`not isinstance(version, int) or isinstance(version, bool) or version != 1`.

EMR's framing is worth keeping: they caught it because the case was written as
**a sweep of wrong shapes** rather than one happy value. The new test sweeps
`true`, `false`, `[1]`, `"1"`, `null`, `1.0`, `2`, `0` and then confirms `1`
still works. A gate tested only with `1` and `2` proves nothing.

## Verification

- `tests/test_core.py` **64/64 PASS** (61 + 3: the version-gate sweep, the
  split rule over a realistic mixed drop, and an unfinished transfer left
  untouched).
- **Run, not just read**: a synthetic arrival was built on disk and put through
  `scripts/import_job.py` end to end — two jobs filed into `22-09-26 DG3 Turbo
  Inspection` and `01-09-26 Bow Thruster Overhaul` (day 22 was taken, so the
  archive rule moved the second and said so), photos renamed after their
  folders at 23.6–23.8 KB, manifests rewritten to the filed names, and the
  half-copied folder refused and left exactly as it was.
- `main.py` imports cleanly and the new methods are present. The GUI itself was
  not click-tested — no display automation here — so the drop zone and button
  are the parts Nick should try first.

## Shipped

Built and released as **v1.047**. Unlike v1.046 this has something Nick can
see and use, which is what makes it worth an installer.

## Not done

Steps 4 (LAN receiver, receive log, undo for a merge) and 5 (QR pairing,
catalog service) — still not started, and explicitly not tonight's job.
