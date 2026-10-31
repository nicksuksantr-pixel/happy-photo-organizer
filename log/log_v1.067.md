# Log — v1.067 (2026-11-01) — No key to set up: the built-in free key is the only key

**Drill run 4 PASSED every check** (`drills/1.067.json`). It updated the released v1.066 (`93c4d69c...`) to these
exact bytes, `bf807b97243c71b3e3b72239e6275afdd1aab9b63b07eb7c32b87f545d429364`, and proved the built-in key works
from the updated build. The release goes out through `tools/publish_release.py`, which asks the lock first and
reads the release back from outside afterwards.

**Asked:** build Nick's free Gemini key into the app and hide the key page (*"it is a free key"*). Then: the safest
way is that the key never enters git, test the failure cases hard, and send the tests to the Director. Then the
house answer: no own-key path at all (*"don't use the key saved in the system; it is the same account anyway"*).
Detail per change: `CHANGELOG.md` [1.067] · bugs and fixes: `bug/bug_v1.067.md` · day log: `chat_log/chat_2026-10-31.md`.

## What changed in the app

- **The built-in key is the only key** (house rule KEY_EMBED §4).
  - `auth.get_api_key()` returns the bundled key and nothing else.
  - A key an older version saved in `auth.json` is never read, and the file keeps it untouched.
- **No key field anywhere.** The installer, Settings, shortcuts and messages are all clean. A guard test scans every
  string in the app for a key-entry path; it was driven red on the old Settings.
- **Settings says what the free key means:** it is shared by all installs, Google may use the photos, and people
  at Google may look at them. The installer's licence text says the same.
- **AI-down is said in one line and the run goes on without AI.**
  - The cause is read from the full error, with the HTTP code anchored at the start: withdrawn, today's quota,
    busy, or a model with no free quota.
  - A permanent cause stops further calls.
  - No internet is said as such.
  - A local file error is never blamed on the key.
- **The free limits hold whatever tier was saved** while the built-in key is in use.
- **For the drill:** `--check-embedded-key` (drill mode only) writes status, model and fingerprint, never the key.
  The `drill-open-settings` marker makes the app busy.

## How the key is kept out of git

- **Where it lives:** only in `%USERPROFILE%\.embed-keys\Happy-Photo-Organizer.json`. It is registered (free, no
  billing, project Happy-Photo-Organizer), and the registry holds the fingerprint only: `e656add8f927...`.
- **The build:** the spec reads that file, writes the plain key to a temp folder for PyInstaller and cleans it up.
  It refuses to build without a key unless `HPO_ALLOW_NO_KEY=1`.
- **The hooks:** `tools/key_guard.py` reads the STAGED blobs (`git cat-file --batch`) and commit messages, matches
  both key shapes (`AIza`+35, `AQ.`+30) and the registered plaintext, and fails closed. It runs in pre-commit and
  commit-msg.
- **Checked at each build:**
  - the bundled key equals the registered one;
  - there is no plain key in `dist`'s files;
  - the gate's byte scan finds no key in the compressed installer;
  - git history has 0 key-shaped strings.

## How it was checked

- **Tests:** suite 243/243, with fake keys built at runtime.
- **Error cases:** both key shapes; the AI-down causes; a dead key stops calls; the drill marker fires once and only
  in a drill; `--check-embedded-key` is refused outside a drill.
- **The frozen exe under a temp `USERPROFILE`:** the key check gives status 200 and the model from the reply; the
  marker opens Settings once.
- **Settings captured with PrintWindow:** no key field and no Test button, even with an old key saved in the config.
- **An independent read-only review** found K1–K12, all fixed before the commit.

## The drills (v1.066 → v1.067 through the loopback feed)

| Run | Candidate | Result | Why |
|---|---|---|---|
| 1 | 71435e02 (old, own-key path) | 14/15 | `no_update_loop` counted FROM's own feed fetch (kit bug, fixed in master 746d323) |
| 2 | bf807b97 | 14/15 | `embedded_key_works`: `getaddrinfo failed`; the PC's Wi-Fi had dropped to a printer's SSID (K13) |
| 3 | bf807b97 | void | my re-stage deleted the running drill's logs and feed (K14); it hung and Nick ended it |
| 4 | bf807b97 | **15/15 PASS** | the API probe passed before the run; `embedded_key_works` status 200, fp e656add8f927 |

The kit gained these during the day, all landed in the master first and adopted by copy:
- the AQ. secret scan;
- the `embedded_key_works` call;
- the `no_update_loop` window;
- the pre-run API probe and the `could not check (no network)` wording (status-aware);
- Stage-Drill refusing under a live run of the same app;
- a run-level STOP file every wait polls.

## Not drilled (stated, not papered over)

- The real GitHub endpoint for the v1.066 → v1.067 offer: the drill uses the loopback feed. The publish script reads
  the real endpoint back after publishing.
- A real quota exhaustion or a withdrawn key on the shared key: unit-tested with fakes, never live.
