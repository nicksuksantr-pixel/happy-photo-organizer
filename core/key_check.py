"""
key_check.py — one real Gemini call with the built-in key, for the update drill.

House rule KEY_EMBED §7: a drill of a build that carries a key proves the key
works from the UPDATED build, with evidence = status 200 + the model's name.
`HappyPhotoOrganizer.exe --check-embedded-key` (drill mode only) runs this,
writes the result to ~/.happy-photo-organizer/logs/embedded-key-check.json and
exits: no window, no single-instance lock, so it can run beside the app.

The result carries the key's sha256 fingerprint (what the house registry
holds), never the key. Any error text is passed through keymask.redact.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import auth, keymask

RESULT_NAME = "embedded-key-check.json"
PROMPT = "Reply with the single word OK."


def result_path() -> Path:
    return auth.CONFIG_DIR / "logs" / RESULT_NAME


def run(out_path: Path | None = None, client_factory=None) -> dict:
    """Make the call, write the result, return it. Never raises, never
    returns or writes the key. `client_factory(key)` is for tests."""
    result: dict = {
        "app": keymask.EMBED_APP,
        "fp": None,
        "status": None,
        "model": None,
        "model_from_reply": None,
        "error": None,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    key = auth.get_bundled_key()
    if not key:
        result["error"] = "no built-in key in this build"
    else:
        result["fp"] = keymask.fingerprint(key)
        try:
            if client_factory is None:
                from google import genai
                client = genai.Client(api_key=key)
            else:
                client = client_factory(key)
            reply = client.models.generate_content(model=auth.DEFAULT_MODEL, contents=PROMPT)
            result["status"] = 200
            # The model the reply says served it, if the SDK reports one; else
            # the model asked for - and the evidence says which it is.
            served = getattr(reply, "model_version", None)
            result["model"] = served or auth.DEFAULT_MODEL
            result["model_from_reply"] = bool(served)
        except Exception as e:
            code = getattr(e, "code", None)
            result["status"] = code if isinstance(code, int) else None
            result["error"] = keymask.redact(str(e))[:300]
    out = out_path or result_path()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
    return result
