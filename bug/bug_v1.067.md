# Bug Log — v1.067 (built 2026-10-31, not released: waits for its drill, #28)

## Fixed in v1.067

| # | Defect | Fix | Test |
|---|---|---|---|
| K1 | **A run where the AI never answered said "done".** With a refused key, a used-up quota or no network, every folder failed in its own row ("API key not valid…"), but Phase 2 logged "done — awaiting review" and showed no alert. `plan.ai_error` was set only when the client could not be created, and a dead key creates a client fine. Measured live with a well-formed fake key. Old since the alert was added (F7, 2026-06-04); it became serious in v1.067, because the key field is now hidden and the user has nowhere to look. | **KEY_EMBED point 4.** `analyzer.ai_down_fields` reads the FULL exception: 401/403/key-invalid = withdrawn; day quota (`PerDay` quota id, or the local daily cap) = used up for today; other 429 = busy right now. The row's 200-character cut loses the quota id, so this is read before the cut. Phase 2 names a key-level failure in one line even when other folders got through, with "N of M folders were not analyzed". A permanent failure stops the remaining calls; those rows read "skipped: AI unavailable". A non-key failure is flagged only when nothing got through. The alert is one line, and the folders can still be named by hand. | `test_ai_down_is_read_from_the_full_error`, `test_phase2_says_when_ai_is_unavailable_and_stops_calling_a_dead_key` (counts the calls). Each turned red when the classification was removed. |
| K2 | **Ctrl+Shift+K did not reveal the key field when tested with a key event.** A synthetic Tk key event on Windows arrives with keysym `??` and proves nothing. Rebinding on the K key's code fixed it, proven with a real key press. | **Superseded by KEY_EMBED:** the built-in key now wins, so a revealed field would save a key that is never used. The shortcut was removed. `_reveal_key` stays unbound until Nick decides on a "use my own key" option. | — |
| K3 | The installer showed "Saving API key..." on every install. The uninstaller asked "Also remove your config (API key)?". Both were leftovers of the key page. | The step shows only when a key is passed. The uninstaller now asks "Also remove your settings?". | Found by grep over every visible string; checked by picture. |
| K4 | **The v1.066 → v1.067 drill would have stopped at its busy step.** The kit runs `Set-AppBusy` on the CANDIDATE (`Invoke-Drill.ps1` ~l.281). HPO's adapter made the app busy by blanking the saved key, so the app opened Settings at start. From v1.067 the built-in key wins and Settings never opens by itself, so the kit would throw "could not make the app busy". Found by reading the kit before any drill ran. | `updater.take_drill_busy_marker`: in drill mode only, a `drill-open-settings` marker in the user data dir makes the next start open Settings once, and it is deleted. `hpo.ps1` `Set-AppBusy` drops it, and `Restore-AfterBusy` removes a leftover. | `test_drill_busy_marker_opens_settings_once_and_only_in_a_drill`. On the BUILT exe, with a temp profile and drill mode: the marker made Settings open and was consumed, and the next start without it did not open Settings. |
| K5 | The free-tier notice in Settings was cut off at the right edge. A `wraplength` is scaled with DPI × UI Scale while the dialog is not: 640 overflowed at 125 %, and 460 still overflowed at UI Scale 1.3. | Broken by hand into three short lines. | Pictures at UI Scale 0.7, 1.0 and 1.3. |

## Found by the independent review (3 read-only reviewers, 2026-10-31), all fixed before commit

| # | Defect | Fix | Test |
|---|---|---|---|
| K6 | **The HTTP-code regex in `ai_down_fields` held two BACKSPACE bytes** where `\b` belonged, written by a Python patch run through a Bash-tool heredoc, which turned a doubled backslash into a single one (the same heredoc turned this very sentence's example into nonsense the first time it was written). It never matched a code. The tests passed because "permission_denied", "unauthenticated" and "resource_exhausted" appeared in the same test messages. | Anchored to where google-genai puts the code: `^\s*(401\|403\|429)\s+<status>`. An `OSError` is never classified. The source guard now refuses control bytes in `.py/.spec/.json/.mjs/.js`. | Code-only cases ("403 Forbidden", "429 Too Many Requests"). Names holding 403/40317/429 are not key failures. |
| K7 | **The key guard read the working tree, not the index.** If a key was staged and then deleted (or edited out) on disk, the guard passed and the commit held the key. The hook also ran the guard inside the suite import, which skips on any import error (fail OPEN). Masked keys and commit messages were not looked at. | `tools/key_guard.py`: staged blobs via `git cat-file --batch`; both shapes, plus the registered key plain and masked; fails CLOSED. Run first and on its own by `pre-commit`, and by a new `commit-msg` hook. The build stages the masked copy outside the repo and removes it. `*.key` is ignored. Stale "secrets/" guidance removed. | `test_key_guard_reads_what_is_staged_and_fails_closed`; the real hooks were driven on the real index: a staged key that had been deleted gave exit 1, a key in the message gave exit 1, and clean input gave exit 0. |
| K8 | **A tier or model saved for an old paid key misfired on the free one.** A saved "paid" tier (no throttle) ran the shared free key unthrottled into per-minute 429s. A model with no free quota got 429 `limit: 0`, which was reported as "used up for today" every day. | While the built-in key is in use, any tier is held to the free limits, and AI Health says so. `limit: 0` reads "choose another model in Settings" (permanent). | `test_the_built_in_key_is_throttled_as_free_whatever_tier_was_saved`, plus the `limit: 0` case. |
| K9 | **The v1.066 → v1.067 drill would have failed `real_update_path`.** `Get-FromRouteEvidence` knew only v1.065's test-repo breadcrumbs. In drill mode v1.066 reads the loopback feed, so its breadcrumbs name 127.0.0.1. `drill.json` still named FROM v1.065 and route `repo-env`, and README step 2 still published to the test repo. | Feed patterns for route `feed`; `from` = v1.066 (sha256 `93c4d69c…`, the released asset); README updated. | Read against v1.066's `updater.py` and the kit. Proven only by the drill itself. |
| K10 | **A transient reason hid the permanent one.** Results arrive in completion order: a "busy right now" seen first was what the one-line message said, while "used up for today" was what stopped the run. | The permanent reason wins. | The phase-2 test's `[minute, day]` case. |
| K11 | VERSION was still 1.066, so the candidate would have called itself 1.066, and the kit would wait for 1.067 while the feed offered it again (a loop). | VERSION 1.067, and the bundle was rebuilt (its VERSION was checked). | — |
| K12 | The kept own-key path could not work: a key saved from the field would never be used, because the built-in key wins. | A key saved from the field sets `use_own_key`, which lets it win. An old key merely sitting in auth.json does not. | Cases in `test_api_key_is_the_built_in_one_then_the_saved_one`. |

## Realigned to the written house standard (memory/KEY_EMBED.md, synced d790295)

The Director's first note said "the built-in key wins" and asked for no visible own-key path. The written
standard says the opposite on both counts, and it also asks for the key in plain text. v1.067 now follows the
written standard:

- **The user's own saved key wins; the built-in key is the fallback (§4).** The `use_own_key` flag from K12 is
  gone: with saved-first it has no job.
- **Ctrl+Shift+K is back (§4 names it).** It uses the binding proven with a real key press under K2.
- **The key ships in PLAIN text (§1).** A masked key hides from the gate's byte scan, so a paid key masked in by
  mistake would pass. The mask and the guard's masked-key needle were removed.
- **The `AQ.` shape is matched from 30 characters, with the gate's lookbehind**, as `tools/release-gate.mjs`
  matches it.
- **The AI-down line says whose key failed** (`processor.ai_down_line`):
  - the built-in key: "update when a new version is out";
  - your own key: "press Ctrl+Shift+K in Settings";
  - no internet: said as such.
- **`drills/drill.json` sets `"embeds_key": true`**, so the gate refuses a receipt that does not prove the key.
- **The key is registered** (`tools/register-key.mjs free`, project `Happy-Photo-Organizer`, `--no-billing`).

## The house answer: the built-in key is the ONLY key (KEY_EMBED §4, Nick 2026-10-31)

Nick told the Director: no own-key field in any app. The built-in key is the only key, and every path that reads a
pasted or stored key goes. Asked in HPO's chat, he said not to use the key saved in the system at all, and to follow
the rule fully (it is the same account anyway). Removed:
- `auth.get_api_key()` returns the built-in key only. `get_saved_api_key`, the own-key fallback and the unused
  `save_config(api_key, …)` are gone.
- Settings has no key field, Paste/Show, Test button, Ctrl+Shift+K or "Enter a key first".
- `main` no longer opens Settings when no key is set (only for the drill's marker), and no longer blocks a run with
  "Open Settings to enter your key". A keyless test build sorts the photos, and Phase 2 says in one line that AI is
  unavailable.
- The phase-2 lines name only the shared built-in key. The own-key lines that pointed to Ctrl+Shift+K are gone.
- The installer's dead key-save block and its `api_key` attribute are gone.
- A guard, `test_no_key_entry_path_is_left_in_the_app`, was driven red on the previous settings.py.

Why it mattered for v1.067 itself: Nick's PC and the ship PC have an old `api_key` in auth.json from the old key page.
With own-key-first they would have kept spending that key, not the built-in one.
