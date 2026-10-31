"""
keymask.py — the built-in Gemini key: where it is kept, how it is bundled,
how it is recognised.

The app ships with a free Gemini key so nobody has to make one (Nick,
2026-10-31; house rule KEY_EMBED: a free key may be built in, a paid key
never). The key is NEVER in the repo — the repo is public, and an ignore rule
is one `git add -f` away from a leak. It lives in
`%USERPROFILE%\\.embed-keys\\Happy-Photo-Organizer.json` as
`{"GEMINI_KEY": "<key>"}`; the build reads it there and bundles it masked as
`data/gemini.key`.

The mask is NOT protection: anyone holding the installer can undo it in a
minute. It only keeps the plain key out of string scanners and grep. If the key
is abused, it is deleted in the Google console and the next release carries a
new one (#28) — not a stronger mask.

No imports beyond the standard library: the PyInstaller spec imports this file
at build time, before any of the app's dependencies are on the path.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

BUNDLED_KEY_NAME = "gemini.key"
EMBED_APP = "Happy-Photo-Organizer"          # the repo folder's name (KEY_EMBED)

_PAD = b"HappyPhotoOrganizer:built-in-key"
# A Gemini (Google API) key is printable ASCII with no spaces. Anything else
# coming out of unmask means the file was damaged or is not ours.
_PLAUSIBLE = re.compile(r"[\x21-\x7e]{20,200}")

# Both key shapes Google issues: the classic `AIza` + 35, and the newer `AQ.`
# + about 47 that AI Studio now hands out. A scan for one shape only is wrong.
KEY_SHAPE = r"AIza[0-9A-Za-z_\-]{35}|AQ\.[0-9A-Za-z_\-]{40,}"
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


def _xor(data: bytes) -> bytes:
    return bytes(b ^ _PAD[i % len(_PAD)] for i, b in enumerate(data))


def mask(key: str) -> bytes:
    return base64.b64encode(_xor(key.strip().encode("ascii")))


def unmask(blob: bytes) -> str | None:
    """The key, or None when the blob is damaged — never raises."""
    try:
        key = _xor(base64.b64decode(blob.strip(), validate=True)).decode("ascii")
    except Exception:
        return None
    return key if _PLAUSIBLE.fullmatch(key) else None


def fingerprint(key: str) -> str:
    """sha256 of the key — what a receipt or a registry may carry, never the key."""
    return hashlib.sha256(key.strip().encode("ascii")).hexdigest()


def redact(text: str) -> str:
    """`text` with anything shaped like a key replaced — for messages and logs."""
    return KEY_SHAPE_RE.sub("<key>", text)
