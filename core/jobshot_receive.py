"""
jobshot_receive.py — take a job zip that arrived over the LAN and make it safe.

This is the half of the receiver that has nothing to do with sockets: given the
bytes of a zip, prove they are a job and nothing else, unpack them somewhere
harmless, and hand the result to the importer that already exists.

It is separated from the server on purpose. A socket is hard to test and easy to
get wrong in boring ways; **this** is where the dangerous decisions live, and
every one of them is testable by calling a function with a hostile zip.

The standard it has to meet is the importer's: a bad input is refused with a
reason, never raises, never leaves anything half-written, and never touches what
it did not create. The importer earned that over three rounds of review; this
file is new code with none of that history, so it assumes the worst:

  • **zip-slip is the headline risk.** An entry named `..\\..\\Windows\\System32\\x`
    must never be written. Entry names inside an archive that arrived over a
    network are attacker-controlled strings, not paths. Every name is validated
    and every destination is re-checked against the quarantine root after
    resolution — `ZipFile.extract` does sanitise, but "the library probably
    handles it" is not a security argument.
  • **a zip is a promise about size, not a fact.** Caps on the archive, the
    unpacked total, the entry count and the compression ratio, all checked
    before anything is written.
  • **only the two kinds of file a job is made of** — images and the JSON
    manifest. An archive carrying anything else is not a job.
  • **quarantine first.** Nothing reaches dest_root until it has been unpacked,
    validated, and recognised as a job by the same rules the drop zone uses.

Nothing here executes anything, opens anything with a shell, or trusts a name.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import socket
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import jobshot
from .catalog import JobCatalog
from .image_io import is_supported_image

# ─── the wire contract (agreed with the JobShot app) ───

PROTOCOL = 1
UPLOAD_PATH = "/jobshot/v1/upload"
# `ping` is canonical — it is the word JobShot published in its protocol doc,
# and between two spellings of the same thing the one already written down
# wins. `hello` is accepted as an alias: the endpoint costs nothing, and a
# phone built against either word still pairs instead of failing in a way that
# looks like a network fault.
PING_PATH = "/jobshot/v1/ping"
HELLO_PATH = "/jobshot/v1/hello"
PING_PATHS = (PING_PATH, HELLO_PATH)
# GET /jobshot/v1/job/<job_id> — "did you already file this?", so a lost reply
# costs a question instead of a re-upload, and a resend can be skipped entirely.
JOB_PATH_PREFIX = "/jobshot/v1/job/"
TOKEN_HEADER = "X-JobShot-Token"
DEFAULT_PORT = 8765

# ─── limits ───
# Generous for a real job (a day's photos at phone resolution) and nowhere near
# enough to fill a disk. A vessel PC is not a server.
MAX_ZIP_BYTES = 512 * 1024 * 1024          # what we will read off the socket
MAX_UNPACKED_BYTES = 1024 * 1024 * 1024    # what it may become
MAX_ENTRIES = 5000
MAX_RATIO = 200                            # unpacked / compressed, zip-bomb guard

_JSON_NAME_RE = re.compile(r"^job(-[A-Za-z0-9._-]+)?\.json$")
_SAFE_SEGMENT_RE = re.compile(r"^[^\x00-\x1f<>:\"|?*\\/]+$")


@dataclass
class ReceiveResult:
    ok: bool = False
    error: str = ""
    filed: list[dict] = field(default_factory=list)      # one per job filed
    skipped: list[dict] = field(default_factory=list)    # still arriving / not a job
    warnings: list[str] = field(default_factory=list)

    def to_reply(self) -> dict:
        """What the phone gets back. The reply is the point of the whole
        feature: until the PC can say 'filed as <folder>', the phone cannot
        know it is safe to let the job go."""
        return {
            "jobshot": PROTOCOL,
            "ok": self.ok,
            "error": self.error,
            "filed": self.filed,
            "skipped": self.skipped,
            "warnings": self.warnings,
        }


# ─── pairing ───


def get_token(*, create: bool = False) -> str:
    """The token the QR carries and every upload must present.

    Stored with the rest of the app's settings. `create=True` mints one the
    first time the QR is shown — a PC that has never been paired has no token,
    so an upload cannot be accepted by accident.
    """
    from . import auth

    token = str(auth.load_config().get("jobshot_token", "") or "")
    if token or not create:
        return token
    token = secrets.token_hex(16)
    auth.update_config({"jobshot_token": token})
    return token


def verify_token(presented: str) -> bool:
    """Constant-time compare against the paired token. No token on the PC means
    nothing is accepted — never 'allow when unset'."""
    expected = get_token()
    if not expected or not presented:
        return False
    return secrets.compare_digest(str(presented), expected)


def local_ip() -> str:
    """The address the phone should dial. Asks the OS which interface it would
    use to reach the LAN, rather than guessing from the hostname (which on
    Windows often answers with a VPN or a loopback)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))     # no packet is sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def qr_payload(ship: str, *, port: int = DEFAULT_PORT, host: str = "") -> dict:
    """What the pairing QR encodes.

    `ship` is in here for a reason that predates the LAN work: it is what stops
    a job photographed on one vessel being filed into another vessel's tree.
    The phone remembers the ship it paired with, and the PC checks it again on
    arrival — neither side is trusted alone.
    """
    return {
        "jobshot": PROTOCOL,
        "host": host or local_ip(),
        "port": int(port),
        "ship": str(ship or ""),
        "token": get_token(create=True),
        "pc": socket.gethostname(),
    }


# ─── unpacking, safely ───


def _bad_entry(name: str) -> str:
    """Why this entry name may not be written, or '' if it is acceptable.

    Deliberately a whitelist. The interesting attacks are all things that look
    like a path but are not the path you think: `..\\..\\x`, `C:\\x`, `/x`,
    `a/../../x`, a NUL to truncate the name in a C API below us, an NTFS
    alternate data stream (`a.jpg:evil`), a reserved device name (`CON`).
    """
    if not name or name.endswith(("/", "\\")):
        return ""                                   # a directory entry: ignored
    if "\x00" in name:
        return "contains a NUL"
    if len(name) > 200:
        return "name too long"
    normalised = name.replace("\\", "/")
    if normalised.startswith("/"):
        return "absolute path"
    if re.match(r"^[A-Za-z]:", normalised):
        return "drive letter"
    segments = [seg for seg in normalised.split("/") if seg]
    if not segments:
        return "empty path"
    # `..` is checked before the depth limit so the refusal reason names the
    # real problem — a log that says "too deep" about a traversal attempt is a
    # log that gets misread later.
    for seg in segments:
        if seg in (".", ".."):
            return "relative segment (..)"
    if len(segments) > 3:
        return "nested too deep for a job"
    for seg in segments:
        if not _SAFE_SEGMENT_RE.match(seg):
            return "illegal characters in a path segment"
        if seg.upper().split(".")[0] in (
                "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                "LPT1", "LPT2", "LPT3"):
            return "reserved device name"
    leaf = Path(segments[-1])
    if not (is_supported_image(leaf) or _JSON_NAME_RE.match(leaf.name)):
        return "not a photo or a job manifest"
    return ""


def safe_extract(data: bytes, quarantine: Path) -> tuple[bool, str, list[str]]:
    """Unpack a received zip into `quarantine`. Returns (ok, error, warnings).

    Every check happens before a byte is written, and each destination is
    re-resolved against the quarantine root before opening it — belt and braces,
    because the cost of being wrong here is writing an attacker's file anywhere
    on Nick's PC.
    """
    warnings: list[str] = []
    if len(data) > MAX_ZIP_BYTES:
        return False, f"too big ({len(data) // 1048576} MB)", warnings

    quarantine.mkdir(parents=True, exist_ok=True)
    root = quarantine.resolve()

    try:
        with zipfile.ZipFile(io_bytes(data)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ENTRIES:
                return False, f"too many entries ({len(infos)})", warnings

            unpacked = sum(i.file_size for i in infos)
            if unpacked > MAX_UNPACKED_BYTES:
                return False, f"unpacks to too much ({unpacked // 1048576} MB)", warnings
            compressed = sum(i.compress_size for i in infos) or 1
            if unpacked / compressed > MAX_RATIO:
                return False, "compression ratio looks like a zip bomb", warnings

            wrote = 0
            for info in infos:
                reason = _bad_entry(info.filename)
                if reason:
                    if info.is_dir() or info.filename.endswith(("/", "\\")):
                        continue
                    warnings.append(f"refused entry {info.filename!r}: {reason}")
                    continue

                relative = Path(info.filename.replace("\\", "/"))
                target = (root / relative).resolve()
                # The check that matters: wherever the name claimed to go, the
                # resolved destination must still be inside quarantine.
                if not str(target).startswith(str(root) + os.sep):
                    warnings.append(f"refused entry {info.filename!r}: escapes quarantine")
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 64)
                wrote += 1

            if wrote == 0:
                return False, "the zip held nothing that belongs to a job", warnings
    except zipfile.BadZipFile:
        # Also the truncated-upload case: a half-sent zip does not open, so a
        # broken transfer is refused rather than half-imported. That is why the
        # phone sends a zip rather than loose files.
        return False, "not a readable zip (truncated or corrupt?)", warnings
    except OSError as e:
        return False, f"could not unpack: {str(e)[:120]}", warnings

    return True, "", warnings


def io_bytes(data: bytes):
    """Small helper so the zip is read from memory — a received upload is never
    written to disk before it has been proven to be a zip."""
    import io

    return io.BytesIO(data)


# ─── receive → file ───


def receive_zip(
    data: bytes,
    dest_root: Path,
    *,
    quarantine_root: Path,
    expected_ship: str = "",
    catalog: JobCatalog | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> ReceiveResult:
    """The whole receiving side, minus the socket: validate, unpack, file.

    Filing itself is `import_batch` — the same code the drop zone and the script
    use. A job that arrives over Wi-Fi is filed by exactly the path that has
    been in production since v1.047; the network only changes how it got here.
    """
    result = ReceiveResult()
    work = quarantine_root / f"recv-{secrets.token_hex(6)}"

    ok, error, warnings = safe_extract(data, work)
    result.warnings.extend(warnings)
    if not ok:
        result.error = error
        shutil.rmtree(work, ignore_errors=True)
        return result

    try:
        jobs, in_flight, rest = jobshot.split_arrivals(
            sorted(p for p in work.iterdir()))
        # A zip with the photos at its top level is one job, not a parent.
        if not jobs and not in_flight and jobshot.is_complete(work):
            jobs = [work]

        for folder in in_flight:
            result.skipped.append({"folder": folder.name,
                                   "reason": "no job.json — incomplete upload"})
        for folder in rest:
            if folder.is_dir():
                result.skipped.append({"folder": folder.name,
                                       "reason": "not a job"})
        if not jobs:
            result.error = "no job.json in the upload"
            return result

        # The vessel guard, checked again here: the phone paired with this PC
        # for one ship, and a job from another one does not belong in this tree.
        if expected_ship:
            wanted = _norm_ship(expected_ship)
            kept = []
            for folder in jobs:
                manifest, _err = jobshot.read_manifest(folder)
                got = _norm_ship(str((manifest or {}).get("ship", "")))
                if got and got != wanted:
                    result.skipped.append({
                        "folder": folder.name,
                        "reason": f"ship {got!r} — this PC files for {wanted!r}",
                    })
                else:
                    kept.append(folder)
            jobs = kept
            if not jobs:
                result.error = "nothing in the upload belongs to this vessel"
                return result

        results = jobshot.import_batch(jobs, dest_root, catalog=catalog,
                                       progress_cb=progress_cb)
        for r in results:
            if not r.ok:
                result.skipped.append({"job_id": r.job_id, "job_name": r.job_name,
                                       "reason": r.error})
                continue
            result.filed.append({
                "job_id": r.job_id,
                "job_name": r.job_name,
                "folder": r.final_folder.name if r.final_folder else "",
                "photos": r.photos_filed,
                "merged": r.merged_into_existing,
                "manifest": r.manifest_name,
                "date_shifted": r.date_shifted,
            })
            result.warnings.extend(r.warnings)
        result.ok = bool(result.filed)
        if not result.ok and not result.error:
            result.error = "nothing could be filed"
    finally:
        # Quarantine is scratch space: the photos that mattered were copied into
        # dest_root by the importer, and the originals still live on the phone.
        shutil.rmtree(work, ignore_errors=True)

    return result


def _norm_ship(name: str) -> str:
    return " ".join(str(name or "").split()).upper()


def load_reply(raw: bytes) -> dict:
    """Parse a reply (for the tests and for anyone debugging the phone side)."""
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
