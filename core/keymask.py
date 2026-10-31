"""
keymask.py — the built-in Gemini key: where it is kept, how it is recognised.

The app ships with a free Gemini key so nobody has to make one (Nick,
2026-10-31; house rule KEY_EMBED, memory/KEY_EMBED.md: a free key may be built
in, a paid key never). The key is NEVER in the repo — the repo is public, and an
ignore rule is one `git add -f` away from a leak. It lives in
`%USERPROFILE%\\.embed-keys\\Happy-Photo-Organizer.json` as
`{"GEMINI_KEY": "<key>"}`; the build reads it there and bundles it as
`data/gemini.key`.

In PLAIN text, by the house standard (KEY_EMBED §1): hiding it would only beat
casual scanners, and the house gate is one of them — a masked key is invisible
to its byte scan, so a paid key masked in by mistake would pass. What protects
Nick is the model: no billing account behind the key, one key per app, and a
key that is deleted in the Google console and replaced in the next release
(#28) if it is ever abused.

No imports beyond the standard library: the PyInstaller spec and
tools/key_guard.py import this file before any of the app's dependencies.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

BUNDLED_KEY_NAME = "gemini.key"
EMBED_APP = "Happy-Photo-Organizer"          # the repo folder's name (KEY_EMBED §2)

# A Gemini (Google API) key is printable ASCII with no spaces.
_PLAUSIBLE = re.compile(r"[\x21-\x7e]{20,200}")

# Both key shapes Google issues, as the house gate matches them
# (tools/release-gate.mjs KEY_SHAPES): the classic `AIza` + 35, and the newer
# `AQ.` + 30 or more that AI Studio now hands out. A scan for one shape only
# is wrong.
KEY_SHAPE = r"AIza[0-9A-Za-z_\-]{35}|(?<![0-9A-Za-z_\-])AQ\.[0-9A-Za-z_\-]{30,}"
KEY_SHAPE_RE = re.compile(KEY_SHAPE)
KEY_SHAPE_BYTES_RE = re.compile(KEY_SHAPE.encode("ascii"))


def embed_key_file() -> Path:
    return Path.home() / ".embed-keys" / f"{EMBED_APP}.json"


def read_embed_key(path: Path | None = None) -> str | None:
    """The key from the embed-key file, or None — never raises."""
    try:
        data = json.loads((path or embed_key_file()).read_text(encoding="utf-8-sig"))
        key = str(data.get("GEMINI_KEY") or "").strip()
    except Exception:
        return None
    return key if _PLAUSIBLE.fullmatch(key) else None


def read_bundled_key(path: Path) -> str | None:
    """The key from the bundled `data/gemini.key`, or None — never raises."""
    try:
        key = path.read_bytes().decode("ascii").strip()
    except Exception:
        return None
    return key if _PLAUSIBLE.fullmatch(key) else None


def fingerprint(key: str) -> str:
    """sha256 of the key — what a receipt or the house registry carries
    (register-key.mjs fpOf), never the key."""
    return hashlib.sha256(key.strip().encode("ascii")).hexdigest()


def redact(text: str) -> str:
    """`text` with anything shaped like a key replaced — for messages and logs."""
    return KEY_SHAPE_RE.sub("<key>", text)
