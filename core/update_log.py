"""
update_log.py — the one file that says what an update did (UPDATE_DRILL §3.3).

    ~/.happy-photo-organizer/logs/update.log

    <ISO time> UPDATE <STAGE> <version> <detail>
    <ISO time> STARTED <version> <exe path>

Written by the app (CHECK … HANDOVER, CLEANED, STARTED) and by the installer
(STAGED, SWAPPED, FAILED), so it lives in the user's data folder, which both
can reach and which an update never replaces. Before v1.066 the install stage
reported with `print()` from a windowed exe — nowhere at all — and the app's
breadcrumbs went to %TEMP%, which nobody reads and Windows cleans.

The drill reads the version and every outcome from here, and so does the next
bug report from the ship. So a line is one line (newlines in a detail are
flattened) and writing never raises: losing a log line must not lose an update.

`<version>` is the version the line is about: the running one for CHECK,
CLEANED and STARTED; the offered one for FOUND … HANDOVER; the one being
installed for STAGED, SWAPPED and FAILED.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

STAGES = ("CHECK", "FOUND", "DOWNLOADED", "VERIFIED", "REFUSED", "STAGED",
          "HANDOVER", "SWAPPED", "CLEANED", "FAILED")

_LOCK = threading.Lock()
_MAX_BYTES = 1_000_000
_ENABLED = True


def set_enabled(on: bool) -> None:
    """Off only for the drill's reference install (`--fresh-into`), which is
    not an update and must not read like one."""
    global _ENABLED
    _ENABLED = bool(on)


def log_path() -> Path:
    """The update log every stage appends to: ~/.happy-photo-organizer/logs/update.log."""
    return Path.home() / ".happy-photo-organizer" / "logs" / "update.log"


def _now() -> str:
    # local time with its offset: read on a ship by a person, parsed by a drill
    t = time.localtime()
    off = time.strftime("%z", t)                     # "+0700"
    off = f"{off[:3]}:{off[3:]}" if len(off) == 5 else "Z"
    return time.strftime("%Y-%m-%dT%H:%M:%S", t) + off


def _one_line(s: object) -> str:
    return " ".join(str(s).split())


def _append(line: str) -> None:
    if not _ENABLED:
        return
    try:
        p = log_path()
        with _LOCK:
            p.parent.mkdir(parents=True, exist_ok=True)
            try:
                if p.stat().st_size > _MAX_BYTES:
                    rolled = p.with_suffix(".log.1")
                    rolled.unlink(missing_ok=True)
                    p.rename(rolled)
            except OSError:
                pass
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


def log(stage: str, version: str, detail: str = "") -> None:
    """`<ISO> UPDATE <STAGE> <version> <detail>` — never raises."""
    if stage not in STAGES:
        detail = f"(unknown stage {stage}) {detail}"
        stage = "FAILED"
    _append(f"{_now()} UPDATE {stage} {_one_line(version) or '?'} {_one_line(detail)}".rstrip())


def started(version: str, exe: str) -> None:
    """`<ISO> STARTED <version> <exe path>` — on every start (§3.3)."""
    _append(f"{_now()} STARTED {_one_line(version) or '?'} {exe}")


# ─── the install in flight (v1.066) ───
#
# A failed install used to leave nothing the app could act on. The installer
# rolled back and relaunched the old build, which found the same release,
# downloaded it again and handed over again: on a PC where that install cannot
# succeed (a path too long, a file held open, a full disk) the app closed
# itself every few minutes, for good. So the app writes down what it hands
# over, and the next start settles it. The build that came up is the one asked
# for → done. Any other → that version's install failed, and it is not tried
# again by itself. Failure is assumed until success is seen, so an installer
# that never ran at all (blocked, crashed) counts too: it cannot write a word.

# An installer relaunching an app older than v1.066 points that one session's
# update checks here: such an app cannot remember a failure, and would hand
# over again at once. (`HAPPY_UPDATE_REPO`, which every build reads at start.)
# It must name NO repo, ever (R3, reviver round 1): those builds check no
# digest and run the first .exe of whatever release they find, and the first
# value, "update-paused/after-a-failed-install", was a GitHub name anyone could
# register. A space is not allowed in a GitHub name, and http.client refuses
# the URL before DNS or a connection (measured on v1.065's own updater): the
# app says "offline" for that session.
PAUSED_REPO = "update paused/after a failed install"


def attempt_path() -> Path:
    """The record of the install in flight, update-attempt.json beside update.log."""
    return log_path().parent / "update-attempt.json"


def _vkey(v: object) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(v))) or (0,)


def read_attempt() -> dict | None:
    """The recorded install attempt, or None when there is none or it is unreadable - never raises."""
    try:
        d = json.loads(attempt_path().read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return d if isinstance(d, dict) and d.get("version") else None


def _write_attempt(d: dict) -> bool:
    try:
        p = attempt_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(d), encoding="utf-8")
        os.replace(tmp, p)
        return True
    except Exception:
        return False


def clear_attempt() -> None:
    """Delete the recorded install attempt, if any - never raises."""
    try:
        attempt_path().unlink(missing_ok=True)
    except OSError:
        pass


def begin_attempt(version: str) -> None:
    """The app, at HANDOVER: `version` is about to be installed."""
    _write_attempt({"version": _one_line(version), "state": "handover",
                    "at": _now(), "reason": ""})


def note_attempt_failed(version: str, reason: str) -> bool:
    """The installer, when it gives up. False when no app wrote an attempt for
    `version` — the app that handed over predates v1.066."""
    d = read_attempt()
    had = d is not None and str(d.get("version")) == _one_line(version)
    _write_attempt({"version": _one_line(version), "state": "failed",
                    "at": _now(), "reason": _one_line(reason)[:300]})
    return had


def settle_attempt(running_version: str) -> dict | None:
    """The app, at start. None when nothing was in flight, or when it came up
    (or something newer has since); else the failed attempt
    `{version, state, at, reason}`, which stays until a newer build starts or
    the user asks for that version again."""
    d = read_attempt()
    if d is None:
        return None
    if _vkey(d.get("version")) <= _vkey(running_version):
        clear_attempt()
        return None
    if d.get("state") != "failed":
        # the installer wrote nothing: it never ran, or died before it could
        d["state"] = "failed"
        d["reason"] = (f"v{running_version} started instead; the installer did not "
                       f"finish (blocked, closed or crashed before it logged anything)")
        _write_attempt(d)
        log("FAILED", str(d.get("version")), d["reason"])
    return d
