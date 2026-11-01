# Log — v1.068 (2026-11-01) — When the free AI is back

**Both field-version drills PASSED 15/15** (#28, UPDATE_DRILL step 1, v3.26): from v1.067 (`drills/1.068.json`) and from v1.065 (`drills/1.068.from-1.065.json`), on the same bytes, sha256 `4345dc38d0072c5128d257991ebeed23bfc30f2bc3280cb7d7130eaf3944ed28`. `release-gate --check --tag v1.068` passed.

**RELEASED 2026-11-01 08:46** (tag `v1.068` at `f482697`) through `tools/publish_release.py --previous 1.067`. Every gate passed: the lock, the draft upload with its size verified, then, read from outside after publishing, `latest` is v1.068, a v1.067 user is offered it, and the re-downloaded asset hashes to the drilled file.

**Asked:** Nick, in this chat, answering *"Build v1.068 so the quota message names the 15:00 reset time?"*: **"Build
v1.068"** (2026-11-01, about 01:15).

## What changed in the app

- **The used-up-quota line says when AI is back, on the PC's own clock.** v1.067 said "try again tomorrow". The free
  tier's daily quota resets at midnight US Pacific: 14:00 in Thailand under US daylight time, 15:00 otherwise. So a
  quota that runs out in a Thai morning is back the same afternoon. It now reads, for example, "AI is back after 14:00
  today".
- `processor.quota_back_at()` works out the next Pacific midnight by hand (the US daylight-time rule), so the app needs
  no tz database.

## Step 0 — the rubric walk before the first drill (0 agents)

The candidate's app diff against v1.067 is `core/processor.py` only.
- **Correctness:**
  - the reset instant matched the tz database (`zoneinfo` + `tzdata`) at 105,168 instants, every hour and every
    hour + 59:59 from 2025 to 2030, with 0 mismatches;
  - at the exact reset instant, the next one is named;
  - the US daylight-time start and end days are tested.
- **Callers:** the skipped-row reasoning and `plan.ai_error` both call `ai_down_line(cause)`, and both get the same
  text. Every cause other than "day" is unchanged.
- **Tests:** the new test was red first (no `quota_back_at`) and is green now. It does not depend on the PC's zone:
  it passes Thai time explicitly, and the live-clock case only checks the shape. Suite 245/245.
- **Known fixes at this moment:**
  - K15 (the publish gates writing into Nick's logs) is fixed in `tools/`, not in the app bytes;
  - U8 (`job_catalog.json` inside the install tree) stays open by plan, as "its own drilled release"
    (log_v1.066).
  - No other known app fix is pending.

## Field versions (drill.json `field_versions`)

| Version | Where | Read | Drill |
|---|---|---|---|
| 1.067 | Nick's PC | 2026-11-01, his update.log: STARTED 1.067 at 00:30:15 | `drills/drill.json`, the loopback feed, receipt `drills/1.068.json` |
| 1.065 | the ship PC | 2026-10-30, V-Log v1.065 (21:09) | `drills/drill.from-1.065.json`, repo-env via the test repo, receipt `drills/1.068.from-1.065.json` |

## The drills

| FROM | Route | Run | Result |
|---|---|---|---|
| 1.067 (`bf807b97...`) | loopback feed | 2026-11-01 01:39:42-01:49:19 | **15/15 PASS**, receipt `drills/1.068.json` |
| 1.065 (`46902c79...`), attempt 1 | repo-env, the test repo | 01:25:49-01:38:51 | 15/15, but filed under the FROM-1.067 log name, so not a receipt (the Director's ruling); kept as `drills/logs/1.068.from-1.065.run1.*` |
| 1.065, attempt 2 | repo-env | 02:00:10 | FAIL in 6 s at the pre-run probe: DNS could not resolve the Gemini host, nothing installed (`run2-no-network.runner.log`); the Director measured the network fine at 02:04, so a resolver blip |
| 1.065, attempt 3 | repo-env, kit fafc0e7, `-ReceiptName 1.068.from-1.065` | 08:31:30-08:43:13 (11.7 min) | **15/15 PASS**, receipt `drills/1.068.from-1.065.json` |

Attempt 3 was run on Nick's go ("Re-run it", 2026-11-01 about 08:30), after the lock, the stage, the runner and the test repo were checked:
- the test repo's latest was v1.068, `4345dc38`, 91,707,491 bytes;
- the drill lock was free and `HPO.cmd` was absent.

What it showed:
- v1.065's own updater fetched `api.github.com/repos/nicksuksantr-pixel/hpo-update-drill/releases/latest` at 08:32:01 and handed over;
- v1.068 started itself at 08:34:26, as one process in one install folder;
- the 1900 files are identical to a fresh install (allowlist: `uninstall.bat`, `job_catalog.json`);
- the shortcuts open the new exe;
- `auth.json` and the job data are unchanged;
- the built-in key answered 200, fp `e656add8f927`.

Every log is named by the receipt name, and the receipt's `drill_log` is `drills/logs/1.068.from-1.065.log`. No key shape appears in any receipt or log.

**Stale wording, not a defect of the run:** two `not_covered` lines in `drill.json` have named v1.066 since the bridge (ad00773), where they mean the version being drilled to: "v1.066's own updater against real GitHub: every check on v1.066 runs through the loopback feed" and "the 'Install now' button: in v1.066 ...". `drill.from-1.065.json` copied them. The receipts for v1.067 and v1.068 carry them as written and were not edited (#28). After the release, both manifests were reworded to "the updated version's own updater" and "since v1.066", so the next drills say it right. The Director then found the same old meaning in `drills/README.md` ("Not drilled here"), checked that no other repo or the master kit carried it, and the README was brought up to date: one drill per field version, the v1.065 route through the test repo, `embedded_key_works`, the `drill-open-settings` busy step, and commands that read the versions from `VERSION` and `drill.json`.

## In the field

**Nick's PC, v1.067 → v1.068, read-only from his `logs\update.log`:**
- 08:50:48 SWAPPED, 1898 files;
- 08:50:50 STARTED 1.068;
- 08:50:55 "nothing newer";
- 08:51:02 CLEANED (the rollback copy was removed).

It took four minutes after publishing and needed no click. This is the route drilled in `drills/1.068.json`. The ship
PC (v1.065) is not read yet; its route is the one drilled in `drills/1.068.from-1.065.json`.

## After the release: README + CODEMAP + a docs gate (rule #15; no version, no build, no drill)

**Asked:** Nick, in the Director chat (about 09:2x), after he asked "why is there no CODEMAP": "Both of them".
- **Item 1, here:** README, CODEMAP and a docs gate in HPO.
- **Item 2, the Director's:** the same check in the house release gate.

**Why it was missing:** GitHub history starts at v1.027 with no README. PROJECT_SUMMARY.md took the README's place,
and it froze at "v1.057" because nothing made it move. Rule #15 (2026-06-09) never reached this repo's records.

### What was added

- **`README.md`** with the five #15.2 blocks:
  - the name and purpose;
  - the stack and `**Version: v1.068**`;
  - run, build, and the release order;
  - one line per feature;
  - the doc map.
- **`docs/CODEMAP.md`:**
  - layer A is hand-written: 61 rows of task → file → entry point;
  - layer B is generated: 41 modules with their public names and first docstring lines.
- **`tools/gen_codemap.py`**, a repo-local generator:
  - same markers and bullet shape as the house one, plus each module's first docstring line;
  - `--check` writes nothing and exits 1 with the command to run;
  - console output is ASCII;
  - why repo-local: the house generator maps only `features/` folders and would empty layer B here, and a gate must
    not read outside the repo (#22). The Director agreed.
- **57 one-line docstrings** where layer B found none (#15.4):
  - 52 were added by 3 agents, each on its own files, docstrings only;
  - 5 were mine, in `tools/publish_release.py`;
  - checked mechanically: every changed `.py` has an AST identical to HEAD once docstrings are removed, and the diff
    is added lines only;
  - one agent's edit had dropped a space in 5 code lines (AST-equal, so only the diff showed it); I restored them.
- **Gate 5 in `publish_release.local_gates()`**, after `gate_version_agrees`:
  - `gate_readme_names_this_version` refuses unless README.md has exactly one `**Version: vX.XXX**` line equal to
    `VERSION`, and names the line to fix;
  - `gate_codemap_is_fresh` loads the generator in-process, refuses a stale layer B or missing markers, names
    `python tools/gen_codemap.py`, and writes nothing.
- **`PROJECT_SUMMARY.md` stays as history,** with a "frozen 2026-11-01" banner pointing to README and CODEMAP.
  `RELEASE.md` got a banner too: its per-release steps are old notes.

### How it was checked

- **Tests:**
  - `test_the_readme_gate_refuses_a_readme_still_on_the_previous_version` covers a previous version, no line, two
    lines, a missing file, and a BOM pass;
  - `test_the_codemap_gate_refuses_a_stale_map_and_names_the_command` covers stale → refused, fresh → passes, code
    moved → refused with the check writing nothing, and no markers → refused;
  - each test is red with its gate swapped for a no-op;
  - suite 247/247.
- **The house gate's view** (`release-gate --check --tag v1.068`, v3.27 docs check): exit 0.
- **An independent accuracy check:** 2 read-only agents tried to refute every README sentence (66 claims) and every
  CODEMAP layer A row (50). They found 29 problems, and all were fixed. Among them:
  - the build prerequisites (pyinstaller 6.20.0, pywin32, node, gh);
  - the release order;
  - stale doc pointers (RELEASE.md, GEMINI_LIMITS.md, log/ and bug/ coverage);
  - the update.log path;
  - "aims for" 10–25 KB;
  - rows pointing at a mechanism instead of the decision: digest verify in `update_worker`, install timing, where the
    10/25 numbers and the 90-min gap are really set, the prompt constant, `discard_assignment`, two Pacific-day
    computations, the installer's own colours and paste;
  - five missing rows: button states, the update button, the EN translate prompt, the pre-flight estimate, window
    state.
- **Two findings are app bugs:** L1 (a midnight burst pulls the next day in) and L2 (a custom RPD above 500 is not
  clamped with the built-in key). Both were reproduced and are filed OPEN in `bug/bug_v1.068.md`, not fixed here. The
  README names both.
- **Not done:** no build. `dist/` is now older than the docstring edits by mtime, so the next release rebuilds anyway.
