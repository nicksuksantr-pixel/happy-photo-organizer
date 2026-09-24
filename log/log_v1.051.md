# Log — v1.051 (2026-09-24)

## Entry 1 — two buttons I added were never on screen

Nick, with screenshots: *"ปุ่มอัพเดทอยู่ไหน ปุ่มสเกนโดนทับ และเชื่อมต่อไม่ได้"*.

The header is a fixed 92 px (`height=92` + `pack_propagate(False)`). I stacked
four 30 px buttons in it, which needs 132. **Phone** was cut in half and
**Updates** was entirely below the fold — so the button I built yesterday to
make the updater visible was itself invisible.

I added those two buttons on two different days and never saw either of them,
because I do not open the window. Both times the code was correct and the
result was not.

Fixed by making the button area a grid: AI Health · Settings · Phone across the
top, and the update button spanning the full width beneath — which it needs
anyway, since `Up to date (1.050)` and `Downloading 37%` do not fit in 100 px
and a truncated status is the same as no status.

**The rule that follows:** a change to the window needs a screenshot from Nick
before it is called done. The mechanical check that catches a missing entry
point (`grep the UI layer`) says nothing about whether the thing is on screen.

## Entry 2 — "เชื่อมต่อไม่ได้" was the opposite of a connection failure

The log tells the real story:

    [13:18:02] [phone] 192.168.110.163 "GET /jobshot/v1/hello HTTP/1.1" 200
    [13:18:04] [phone] 192.168.110.163 "GET /jobshot/v1/hello HTTP/1.1" 200
    [13:18:05] [phone] 192.168.110.163 "GET /jobshot/v1/hello HTTP/1.1" 200

**The phone found the PC, paired, and was answered three times.** What it then
displayed was the `reason` added in v1.049:

> happy-photo-organizer 1.050 · Nick — not ready: no destination folder chosen
> on the PC yet

That message is accurate and it is doing its job. The failure is that the fix
for it lives on a screen the person is not looking at: they are looking at the
phone, or at the pairing dialog, and the destination picker is a button in
Step 1 behind the dialog.

So the pairing dialog now says which of the two things is missing —
*"Paired phones can find this PC, but nothing can be sent yet: no destination
folder is chosen"* in amber — and carries a **Choose the destination folder…**
button that sets it, remembers it for that vessel, and re-draws itself as
*"Ready for Nick → D:\...".*

A first pairing is exactly when there is no destination yet, so this is the
normal path, not an edge case.

## Verification

- `tests/test_core.py` **96/96**.
- The layout itself is **not** verified by me — it cannot be, from here. That is
  the point of Entry 1: Nick's screenshot is the test, and this build needs one.
