# Log — v1.057 (2026-09-26)

## Entry 1 — the folder it never remembered

Nick: *"เวลาเปิดปิดหรืออัพเดทโปรแกรม ช่องโฟเดอร์ที่เลือกไว้ไม่จำ เลยต้องเลือกใหม่ทุกครั้ง เลยทำให้งานๆอื่นๆงงไปด้วยว่าทำไมส่งไม่ได้"*
— close, reopen or update HPO and the destination box is empty again, which then
makes everything else look broken, the phone included.

Three places choose a destination: the Step 1 **Choose Destination** button, the
pairing dialog, and the drop-zone JobShot import. **Only the last two ever wrote
it down** — and nothing read it back. `__init__` set `self.dest_root = None` and
left it there.

The second half of his sentence is the expensive half. The LAN receiver is built
with `dest_root=lambda: self.dest_root`, so after every restart the phone was
told *"no destination folder chosen on the PC yet"* — an honest report of an
empty variable, about a folder that had never moved. That is why sending failed
for no visible reason, and why the fix belongs in the same release as the thing
it breaks.

### What shipped
- One `_set_dest()` that every picker calls, so all three remember.
- It writes **two** keys: the per-vessel `dest_roots[SHIP]` and a ship-independent
  `last_dest_root`. The second one is there because **Nick renamed his vessel
  today**, from "Nick" to "ENA Test" — with only the per-vessel key, renaming a
  ship loses a folder that never moved.
- `_restore_dest()` at startup: per-vessel first, then the PC-wide fallback,
  and **never a folder that is not there any more** — an unplugged drive says so
  on the label in amber rather than coming up "ready" and failing on the first job.

**The update case is safe**, and it was checked rather than assumed: the config
lives in `~/.happy-photo-organizer/auth.json` while the installer only extracts
into `%LOCALAPPDATA%\HappyPhotoOrganizer`. It is not in the blast radius that ate
14 job names in v1.044 — that was `job_catalog.json`, which sits inside the
install tree.

## Entry 2 — the review, and the regression I had just written

Two of the three reviewers refused to ship it, and the first finding was mine,
one hour old.

**Restoring the destination broke the per-vessel destination.** `_jobshot_dest`
opens with `if self.dest_root: return self.dest_root`. That was harmless while
`dest_root` was None on every fresh start — the next line read the job's own
manifest and used *that vessel's* remembered folder. The moment startup began
restoring a value, the early return swallowed the lookup: a job handed over on a
USB stick from another vessel would have been filed into **this** PC's tree,
silently. The Wi-Fi path refuses a foreign ship outright (*"ship X — this PC
files for Y"*); the hand-drop path has no such guard, so the destination was the
only thing standing up. It now reads the job's vessel first, files into that
vessel's folder when it has one, says so, and **does not** adopt it as this PC's
destination.

**A save that fails now says so.** `auth.update_config` and
`jobshot.remember_dest_root` *return* failure — they do not raise it — so the
`try/except` I wrapped them in was dead code and both return values were
discarded. On a locked or read-only config the app would have logged a green
"Destination set" and forgotten it again: Nick's original bug, wearing a success
message.

**And the two tests I wrote first did not pin the wiring.** They call
`_restore_dest` and `_set_dest` directly, so deleting the call from `__init__`
brings his exact bug back with both green. The structural check is in now, over
`__init__` and both pickers.

## Verification
- `tests/test_core.py` **132 → 134**. Every new test proven **red** first: the
  remembered-destination pair against the old code (`KeyError 'dest_roots'` —
  nothing was ever written), and the foreign-vessel test against the ordering as
  it stood an hour ago (it filed ENA Challenger's job into this PC's folder).
- Still not verified, and it is a window change: **Nick has not seen it.**
