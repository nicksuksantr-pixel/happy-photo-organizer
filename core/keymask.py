"""
keymask.py — mask / unmask the built-in Gemini key.

The app ships with a free Gemini key so nobody has to make one (Nick,
2026-10-31). The key is NEVER in git — the repo is public. The build reads it
from `secrets/gemini_key.txt` (gitignored) and bundles it masked as
`data/gemini.key`.

The mask is NOT protection: anyone holding the installer can undo it in a
minute. It only keeps the plain key out of string scanners and grep. If the key
is abused, the fix is a new key and a new release, not a stronger mask.

No imports beyond the standard library: the PyInstaller spec imports this file
at build time, before any of the app's dependencies are on the path.
"""
from __future__ import annotations

import base64
import re

BUNDLED_KEY_NAME = "gemini.key"
SECRET_KEY_PATH = ("secrets", "gemini_key.txt")   # relative to the repo root

_PAD = b"HappyPhotoOrganizer:built-in-key"
# A Gemini (Google API) key is printable ASCII with no spaces. Anything else
# coming out of unmask means the file was damaged or is not ours.
_PLAUSIBLE = re.compile(r"[\x21-\x7e]{20,200}")


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
