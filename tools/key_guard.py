"""
key_guard.py — never let a Gemini key reach git (Nick, 2026-10-31; house rule
KEY_EMBED). The repo is PUBLIC.

What it looks for, in bytes:
  - either key shape Google issues (`AIza`+35, `AQ.`+40 or more);
  - the registered key itself, from %USERPROFILE%\\.embed-keys\\<repo>.json, in
    case a future key has a shape nobody has seen yet;
  - that key MASKED the way the build bundles it (core/keymask.mask): the pad
    is in this public repo, so a masked key is a key.

Where:
  --index          the STAGED blobs (`git ls-files -s` + `git cat-file
                   --batch`), i.e. what the commit will hold, not the working
                   tree, which can differ from it (a staged file deleted or
                   edited afterwards).
  --message FILE   a commit message (the commit-msg hook).

It FAILS CLOSED: any error of its own exits 1, because a guard that waves a
commit through when it cannot run is not a guard. It never prints a key, only
file names. Standard library + core/keymask.py only, so a broken import
anywhere else in the tree cannot switch it off.

    python tools/key_guard.py --index
    python tools/key_guard.py --message .git/COMMIT_EDITMSG
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import keymask  # noqa: E402  (stdlib-only module)


def needles() -> list[bytes]:
    """The registered key, plain and masked, as bytes ([] where there is no
    embed-key file, e.g. a cloud checkout)."""
    real = keymask.read_embed_key()
    if not real:
        return []
    return [real.encode("ascii"), keymask.mask(real)]


def holds_key(raw: bytes, extra: list[bytes] | None = None) -> bool:
    if keymask.KEY_SHAPE_BYTES_RE.search(raw):
        return True
    return any(n and n in raw for n in (needles() if extra is None else extra))


def scan_index(root: Path = ROOT) -> list[str]:
    """Paths whose STAGED content holds a key. Raises on any git failure."""
    listed = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=root,
                            capture_output=True, check=True).stdout
    entries = []                                   # (sha, path)
    for rec in filter(None, listed.split(b"\0")):
        meta, _, path = rec.partition(b"\t")
        parts = meta.split()
        if len(parts) >= 2 and not parts[0].startswith(b"160000"):   # skip submodules
            entries.append((parts[1].decode("ascii"), path.decode("utf-8")))
    if not entries:
        return []
    batch = subprocess.run(["git", "cat-file", "--batch"], cwd=root,
                           input=b"".join(sha.encode() + b"\n" for sha, _ in entries),
                           capture_output=True, check=True).stdout
    extra = needles()
    hits, pos = [], 0
    for sha, path in entries:
        nl = batch.index(b"\n", pos)
        header = batch[pos:nl].split()
        if len(header) != 3 or header[0].decode() != sha:
            raise RuntimeError(f"git cat-file answered {header!r} for {path}")
        size = int(header[2])
        body = batch[nl + 1: nl + 1 + size]
        pos = nl + 1 + size + 1                    # the body is followed by a newline
        if holds_key(body, extra):
            hits.append(path)
    return hits


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["--index"]:
            hits = scan_index()
            where = "staged files"
        elif argv[:1] == ["--message"] and len(argv) == 2:
            hits = ["the commit message"] if holds_key(Path(argv[1]).read_bytes()) else []
            where = "the commit message"
        else:
            print(__doc__)
            return 2
    except Exception as e:                         # fail CLOSED
        print(f"key guard REFUSED: it could not run ({type(e).__name__}: {e}).")
        print("Fix the guard rather than --no-verify.")
        return 1
    if hits:
        print(f"key guard REFUSED: a Gemini key in {where}:")
        for h in hits:
            print(f"  {h}")
        print("The key lives only in %USERPROFILE%\\.embed-keys\\Happy-Photo-Organizer.json,")
        print("outside the repo. Remove it here; if it was ever pushed, it must be rotated.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
