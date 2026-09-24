# Log — v1.050 (2026-09-24)

## Entry 1 — the updater was working perfectly and invisibly

Nick: *"ครั้งต่อไปทำปุ่มกดระบบอัพเดทหน่อยนะ ไม่รู้ไม่เห็นอะไรเลย กดก็ไม่ได้"*

He is right, and worse, **I had told him twice to "press Check for updates in
the app"** — there was no such button. The only manual check was a right-click
on the system-tray icon (`core/tray.py:56`), which is not somewhere anyone
looks, and the only sign that anything was happening at all was a line
scrolling past in the log box before the app silently restarted itself.

The feature had no surface. `no-entry-point-is-not-finished` again, in its
other form: not *missing* an entry point this time, but having one nobody would
find, which for the person using it is the same thing.

### What Nick can now see, in the header next to Settings

One button, and it always says what the updater is actually doing:

| State | Button | Clickable |
|---|---|---|
| never checked | `Check for updates` | yes — checks now |
| checking | `Checking…` | no |
| nothing newer | `Up to date (1.050)` | yes — checks again |
| GitHub unreachable | `Updates: offline` (amber) | yes — retries |
| found, downloading | `Downloading 37%` | no |
| downloaded, ready | `Install v1.051` (highlighted) | yes — asks, then installs |
| found mid-batch | `Update v1.051` (highlighted) | yes |

Pressing it when nothing is happening runs a check **and says what came back** —
`No update available — v1.050 is the latest` — because a button that goes quiet
is exactly the complaint being fixed. Pressing it when an installer is ready
asks first and explains that the app will close and reopen, and that nothing on
disk is touched.

Two things it will not do: install while a batch is running (it says so instead
— restarting mid-run would cost Nick the work), and claim a downloaded
installer that has since been cleaned out of the cache.

### Where the logic lives, and why
`UpdateWorker.describe()` returns `(label, kind, clickable)`; the window only
maps `kind` to a colour. That puts the decision in core where it is tested
without opening a window — the same reason `split_arrivals` lives there — and
means the button mirrors one source of truth rather than keeping its own idea
of what the updater is doing.

The worker gained only bookkeeping: `checking`, `last_check_at`, `last_error`,
`latest_version`, `download_pct`. **None of it changes a decision.** The
download percentage comes from a `progress_cb` the downloader already accepted
and nobody had ever passed.

## Entry 2 — a test that could fail one run in sixteen

While verifying, `test_receiver_server_refuses_everything_without_the_token`
failed on code I had not touched. It builds a "wrong token" as
`rx.token[:-1] + "0"` — and when the real token already ends in `0`, that IS
the real token, so the server correctly returned 200 and the test called it a
bug. A hex token ends in `0` one run in sixteen.

Fixed to change the character to one it demonstrably is not, with an assertion
that the tampered token really differs. Worth recording because the failure
mode is nasty: a test that fails rarely, on unrelated changes, teaches people to
re-run until it passes.

## Verification

- `tests/test_core.py` **96/96** (92 + 4): every button state including the
  percentage, an installer that vanished from the cache, the mid-batch refusal
  carrying its reason, and `manual_check` marking itself as checking.
- **Run, not read:** a smoke driving `MainWindow`'s own methods against a stub
  window — idle label, click reaching the worker, `Downloading 37%` and
  disabled, `Install v1.050`, the confirm answered No installing nothing, the
  confirm answered Yes starting the install, and a mid-batch click refusing
  with its reason in the log.
- The GUI itself is still not click-tested; what is proven is everything behind
  the button.

## Status — released

Nick: *"รีลิสเลย"*. **v1.050 is published**, and it carries everything since
v1.047: the LAN receiver (v1.048), the protocol alignment (v1.049) and this
button. The irony noted while it was held back is now resolved the only way it
could be — this is the last release that has to be installed by hand for anyone
sitting on v1.047.

### One thing went wrong in the release itself
The 90 MB asset upload ran past ten minutes and was killed, leaving a **public
release with no installer attached** for the few minutes it took to notice and
re-upload in the background.

Nobody could have been hurt by it — `check_for_update()` returns `None` when a
release has no matching asset, so every running copy saw "no update" and did
nothing — but that is safety by accident, not by design. `RELEASE.md` now says
to create the release as a **draft**, upload the asset, and only then publish,
and to run the upload detached because ten minutes is not enough.
