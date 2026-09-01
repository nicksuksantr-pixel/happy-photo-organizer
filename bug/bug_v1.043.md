# Bug Log — v1.043

## BUG-1: thumbnails never appeared in Step 3 (CustomTkinter 5.2.2 defect)
- **Reported by:** Nick, 2026-09-02, screenshot — every review row showed an empty box.
- **Root cause (library defect, worked around):** `ui/job_row.py` created the
  thumbnail button as `CTkButton(image=None, text="...")` and swapped the photo in
  later with `configure(image=img, text="")`. In CustomTkinter 5.2.2,
  `CTkButton.configure()` handles the `"image"` key by calling `_update_image()`,
  which is a **no-op while the internal `_image_label` is None** — and that label
  is created **only inside `_draw()`**. Unlike `"state"` / `"compound"` /
  `"anchor"`, the `"image"` key does **not** set `require_redraw=True`, so `_draw()`
  never re-runs. A button born with `image=None` can therefore never display an
  image assigned later. `text=""` still applied, which is why the box was blank
  rather than showing the "..." placeholder — and why the failure looked like
  "no photo" instead of "broken code".
- **Proved with:** a 3-variant repro (A `image=None`→configure = blank ✗ ·
  B placeholder image→configure = shows ✓ · C `require_redraw=True` = shows ✓).
- **Fix:** create the button with a real placeholder tile, so `_image_label` exists
  before the swap. (Chose the placeholder over `require_redraw=True` — it relies on
  no semi-private CTk parameter that a future version could drop.)

## BUG-2: the first review row's thumbnail never arrived (thread-unsafe `after`)
- **Found while verifying BUG-1** — hidden behind it, since nothing displayed at all.
- **Root cause:** the decode worker marshalled its result with
  `self.after(0, ...)` **from the worker thread**. Tkinter's `after()` is not
  thread-safe: rows are built as a batch, so the *first* row's decode finishes
  while the main thread is still constructing the remaining rows and has not
  entered `mainloop()`. That call is accepted and returns success — and the
  callback then never fires. Measured directly: row 1 `post_ok=True` with
  `apply_called` never recorded, while rows 2-4 applied normally.
- **Fix:** the worker now only fills a `queue.Queue`; the Tk thread collects it
  via an `after(100 ms)` poll it schedules for itself. Every Tk call is back on
  the Tk thread. Measured after the fix: all 4 rows deliver on the *first* poll.
- **Also:** thumbnail failures used to `except Exception: pass`, leaving a blank
  tile — indistinguishable from this very bug, which is how it hid for months.
  A missing/undecodable image now shows a visible "no preview" tile.

## BUG-3: the header badge reported a model the app was not using
- **Reported by:** Nick, 2026-09-02, screenshot — Settings set to
  `gemini-3.5-flash-lite` while the header still read "Gemini 3.1 Flash Lite".
- **Root cause:** the badge printed `tier.label` verbatim, and every tier preset
  hard-codes a model name in its label. API calls resolve the model separately via
  `auth.get_model()` (the Settings value), so the two could diverge freely. The
  *calls* were correct — only the badge lied.
- **Fix:** the badge now composes "<tier family> — <auth.get_model()>", reading the
  same source the analyzer calls with, so it cannot drift again.
