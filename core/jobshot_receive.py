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
import stat
import threading
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
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
# POST /jobshot/v1/sidecar — LAN_PROTOCOL v1.1. Replace a sidecar on a job that
# is ALREADY FILED, in place, without re-sending a single photograph.
#
# It exists because the alternative measured badly: re-uploading the whole job to
# fix three lines of typed text duplicated every photo (7 became 14) and left the
# folder with two drafts, which EMR refuses to choose between — so a correction
# took the folder from one usable draft to none. Measured 2026-10-02, chain sheet
# §3 addendum 7.
#
# Kept as a SEPARATE route rather than a flag on the upload, on JobShot's
# argument: an upload can overwrite and delete photographs, this replaces one
# JSON file named by that job's own record. Two endpoints mean the dangerous one
# is used only when something dangerous is being asked for — and the common case,
# correcting wording, is the one Nick does most often.
SIDECAR_PATH = "/jobshot/v1/sidecar"
TOKEN_HEADER = "X-JobShot-Token"
DEFAULT_PORT = 8765

# ─── limits ───
# Generous for a real job (a day's photos at phone resolution) and nowhere near
# enough to fill a disk. A vessel PC is not a server.
MAX_ZIP_BYTES = 512 * 1024 * 1024          # what we will read off the socket
MAX_UNPACKED_BYTES = 1024 * 1024 * 1024    # what it may become
MAX_ENTRIES = 5000
MAX_RATIO = 200                            # unpacked / compressed, zip-bomb guard

# A report draft is a few KB of typed text. These caps are generous for that and
# nowhere near enough to be interesting to an attacker who has the token.
MAX_SIDECAR_FILES = 4
MAX_SIDECAR_BYTES = 1024 * 1024            # per file, serialised
# 2 MiB, not 4: at 4 the total was exactly MAX_SIDECAR_FILES x MAX_SIDECAR_BYTES,
# so the per-file check always fired first and this one could never execute.
# Two reviewers called it dead code and they were right - measured.
MAX_SIDECAR_TOTAL = 2 * 1024 * 1024

# One correction at a time, per process. `ThreadingHTTPServer` really does run
# requests concurrently, and the sidecar path is a read-modify-write of a
# manifest: two corrections to the same job interleaved and one overwrote the
# other's `sidecar_updated_at` (a reviewer measured ~15% wrong answers under
# concurrency). Corrections are rare and tiny, so a single lock costs nothing
# and removes the whole class.
_SIDECAR_LOCK = threading.RLock()


def _discard(path: Path) -> None:
    """Delete one of our own scratch files, and mean it.

    `shutil.copy2` copies the read-only attribute along with the bytes, so a
    backup of a read-only draft could not be unlinked on Windows and was left
    in Nick's archive - found by this route's own rollback test. Clear the bit,
    then delete, and never raise: this only ever runs on paths we created.
    """
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    try:
        path.unlink()
    except OSError:
        pass

_JSON_NAME_RE = re.compile(r"^job(-[A-Za-z0-9._-]+)?\.json$")
# A job folder may also carry sidecars the phone wrote for somebody else to
# read — `emr.json` is the maintenance-report draft the engineer typed at the
# machine, which Engine Maintenance Report picks up out of the filed folder.
# Before this, such an entry was dropped with a warning while the receipt still
# said "filed", so Nick could delete the only copy of a draft that never
# arrived (JobShot, 2026-09-25). Data only: images and JSON, nothing else.
_SIDECAR_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}\.json$")
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


@dataclass
class SidecarResult:
    """The answer to a sidecar replacement. `status` is the HTTP code the server
    should send, so the decision lives here with the rest of the dangerous
    thinking rather than in the socket layer."""
    ok: bool = False
    status: int = 500
    error: str = ""
    job_id: str = ""
    replaced: list[str] = field(default_factory=list)
    folder: str = ""
    photos: int = 0
    extras: list[str] = field(default_factory=list)
    filed_at: str = ""

    def to_reply(self) -> dict:
        if not self.ok:
            body = {"jobshot": PROTOCOL, "error": self.error,
                    "job_id": self.job_id}
            if self.status == 404:
                # §4's word, and the same direction of safety: the phone keeps
                # its copy and tells the engineer, rather than treating this as
                # an error worth retrying. A PC too old to have this route at
                # all answers 404 as well, which is deliberate.
                body["filed"] = False
            if self.extras:
                # A name this job did not file is refused WITH the names it did,
                # so the phone can say something useful instead of "rejected".
                body["extras"] = list(self.extras)
            return body
        return {
            "jobshot": PROTOCOL,
            "filed": True,
            "job_id": self.job_id,
            "folder": self.folder,
            "photos": self.photos,
            "extras": list(self.extras),
            "filed_at": self.filed_at,
            # The point of the reply: the phone may only stop warning the
            # engineer about a name that comes back in here.
            "replaced": list(self.replaced),
            # The draft was replaced but a later step did not finish - the
            # manifest note, or the receipt. Reported rather than swallowed:
            # this branch USED to compose a careful message that `to_reply`
            # then dropped on the floor, so a failed step 5 reached the phone
            # as a clean 200. Found by all three reviewers, 2026-10-02.
            "warnings": [self.error] if self.error else [],
        }


def replace_sidecars(job_id: str, files: dict, dest_root: Path | None) -> SidecarResult:
    """Replace one or more sidecars on a job this PC has already filed.

    Every check runs before a single byte is written. The order is the spec's
    (§3.5) and each step is a refusal, never a best effort:

      1. the job must be one THIS PC filed — `jobshot_index.lookup`, which
         answers from the receipt book and falls back to scanning the archive,
         so it still works after a rename, a reinstall or a lost index;
      2. every name must appear in **that job's own `filed.extras`** — not in a
         listing of the folder. This is the whole safety argument: a job can
         only replace a file it filed itself, can never invent a new name, and
         **can never touch another job's draft in a merged folder**;
      3. the job's manifest is found by `job_id` and OVERWRITTEN — never a
         second one, because EMR's guard counts manifests.

    It does not touch a photograph. Not one, ever. That is why it is separate
    from the upload path.
    """
    from . import jobshot_index          # local: jobshot_index imports us

    result = SidecarResult(job_id=str(job_id or ""))

    if not jobshot_index.valid_job_id(job_id):
        result.status, result.error = 409, "job_id is not a job id"
        return result
    if not isinstance(files, dict) or not files:
        result.status, result.error = 422, "files must be a non-empty object"
        return result
    if len(files) > MAX_SIDECAR_FILES:
        result.status, result.error = 422, (
            f"at most {MAX_SIDECAR_FILES} files per request, got {len(files)}")
        return result

    entry = jobshot_index.lookup(job_id, dest_root)
    if entry is None:
        result.status = 404
        result.error = "this PC has no record of that job"
        return result

    folder = Path(str(entry.get("folder_path") or ""))
    if not folder.is_dir():
        # lookup only returns an entry whose folder exists, so this is a race
        # (Nick moved it between the two calls) rather than a stale index.
        result.status, result.error = 404, "the filed folder is no longer there"
        return result

    # The job's OWN record of what it filed. Not a listing of the folder — in a
    # merged folder a listing would include the other job's draft.
    manifest_path = jobshot.find_manifest_path(folder, job_id)
    if manifest_path is None:
        result.status, result.error = 409, (
            "the filed folder holds no manifest for that job")
        return result
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, ValueError) as e:
        result.status, result.error = 409, f"cannot read the job's manifest: {str(e)[:100]}"
        return result
    block = manifest.get("filed") if isinstance(manifest, dict) else None
    if not isinstance(block, dict):
        # A hand-edited manifest whose `filed` is a list or a string used to
        # reach `.get` on it and raise AttributeError straight out of this
        # function - against this module's own standard that a bad input is
        # refused with a reason and never raises. All three reviewers.
        result.status, result.error = 409, (
            "the job's manifest has no usable `filed` record")
        return result
    filed_extras = [str(x) for x in block.get("extras") or []]
    result.extras = list(filed_extras)

    # ── validate every name and every body BEFORE writing anything ──
    staged: list[tuple[Path, bytes]] = []
    total = 0
    for name, body in files.items():
        name = str(name)
        if not _SIDECAR_NAME_RE.match(name):
            result.status, result.error = 409, f"{name!r} is not a sidecar name"
            return result
        if name not in filed_extras:
            # The gate. A name this job did not file is refused even though the
            # file may well be sitting in the folder — it belongs to another job.
            result.status, result.error = 409, (
                f"this job did not file {name!r}")
            return result
        if not isinstance(body, dict):
            # §3.5 says "the new content as a JSON object". A list was accepted
            # here, which no sidecar has ever been and which the spec does not
            # allow - two reviewers flagged the divergence, and the spec is the
            # contract JobShot builds against, so the code moves.
            result.status, result.error = 422, (
                f"{name!r} must be a JSON object, not {type(body).__name__}")
            return result
        try:
            raw = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        except (TypeError, ValueError) as e:
            result.status, result.error = 422, f"{name!r} is not serialisable: {str(e)[:80]}"
            return result
        if len(raw) > MAX_SIDECAR_BYTES:
            result.status, result.error = 413, (
                f"{name!r} is {len(raw) // 1024} KB, over the "
                f"{MAX_SIDECAR_BYTES // 1024} KB limit")
            return result
        total += len(raw)
        if total > MAX_SIDECAR_TOTAL:
            result.status, result.error = 413, "the request is over the total limit"
            return result
        target = (folder / name).resolve()
        # Belt and braces over the name regex: wherever the name claimed to go,
        # the resolved destination must still be in the job's own folder.
        if target.parent != folder.resolve():
            result.status, result.error = 409, f"{name!r} does not resolve inside the folder"
            return result
        staged.append((folder / name, raw))

    # Refuse before writing anything if a target or the manifest cannot be
    # written. `os.access` reads the attribute and the ACL, not a lock, so the
    # rollback below is still needed for the surprises - but this turns the
    # COMMON case (Nick marked a draft read-only, or the archive is on
    # read-only media) from a rollback into a clean refusal that never touches
    # the folder at all.
    unwritable = [t.name for t, _r in staged
                  if t.exists() and not os.access(t, os.W_OK)]
    if unwritable:
        result.status, result.error = 409, (
            f"cannot be written on this PC: {', '.join(sorted(unwritable))}")
        return result

    # ── write: all-or-nothing, for real this time ──
    #
    # The first version wrote every temp and then replaced them in a loop, with
    # a comment admitting the GROUP was not atomic. Three reviewers measured
    # what that cost: with two sidecars and the second one read-only, the first
    # replace succeeded, the second raised, and the reply came back 500 with
    # `replaced` CLEARED - telling the phone nothing had happened while one
    # draft's only copy had already been overwritten. §3.5 promises "nothing
    # partial", and a reply that is wrong in that direction is worse than the
    # failure it hides.
    #
    # So every target that exists is backed up first, and any failure rolls the
    # whole set back. `replaced` is then honest either way.
    with _SIDECAR_LOCK:
        temps: list[tuple[Path, Path]] = []
        backups: list[tuple[Path, Path]] = []
        try:
            for target, raw in staged:
                tmp = folder / f".hpo-sidecar-{secrets.token_hex(6)}"
                with tmp.open("wb") as fh:
                    fh.write(raw)
                    fh.flush()
                    os.fsync(fh.fileno())
                temps.append((tmp, target))
            for _tmp, target in temps:
                if target.exists():
                    keep = folder / f".hpo-was-{secrets.token_hex(6)}"
                    shutil.copy2(str(target), str(keep))
                    backups.append((keep, target))
            for tmp, target in temps:
                os.replace(str(tmp), str(target))
                result.replaced.append(target.name)
        except OSError as e:
            for keep, target in backups:            # put it all back
                try:
                    os.replace(str(keep), str(target))
                except OSError:
                    pass
            for tmp, _t in temps:
                _discard(tmp)
            result.status = 500
            # `strerror` and not `str(e)`: the OSError text carries the absolute
            # archive path, and this reply crosses the LAN. Two reviewers.
            result.error = ("could not write the sidecar: "
                            f"{e.strerror or type(e).__name__}")
            result.replaced = []
            return result
        finally:
            # Unconditional: a backup is our scratch, and one left in the
            # archive is litter in the only copy of Nick's work.
            for keep, _t in backups:
                if keep.exists():
                    _discard(keep)

        # ── the job's own manifest: OVERWRITE it, never a second file ──
        #
        # Written the same way as the drafts, which the first version did not
        # do: `open("w")` TRUNCATES before the new bytes exist, so an
        # interruption left job.json half-written - and a half-written manifest
        # is unfindable, which makes the job look unfiled, which makes the phone
        # re-upload it and duplicate every photograph. Exactly the harm this
        # route exists to prevent. All three reviewers found it; one rated it
        # critical and was right: the manifest matters MORE than the draft
        # beside it, because EMR reads it and `find_manifest_path` depends on it.
        block["sidecar_updated_at"] = datetime.now().isoformat(timespec="seconds")
        # `extras` is deliberately unchanged: the names did not change, only the
        # contents. A route that rewrote `extras` here could drop a sibling
        # job's entry, and EMR reads that list to decide which draft is this
        # job's.
        mtmp = folder / f".hpo-manifest-{secrets.token_hex(6)}"
        try:
            with mtmp.open("w", encoding="utf-8", newline="") as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(str(mtmp), str(manifest_path))
        except OSError as e:
            # The draft IS replaced; only the note about it failed. Said in the
            # reply now rather than composed and discarded.
            result.error = ("sidecar replaced, but the manifest note failed: "
                            f"{e.strerror or type(e).__name__}")
        finally:
            # The temp was written before the replace, so a failed replace used
            # to leave `.hpo-manifest-*` sitting in the job folder for ever.
            # Caught by this route's own test, not by review.
            if mtmp.exists():
                _discard(mtmp)

        try:
            # `filed_at` preserved: this is a correction, not a filing. Passing
            # nothing used to stamp now() and make §4 report the time of the
            # typo fix as the time the job was filed.
            if not jobshot_index.record(job_id, folder,
                                        int(entry.get("photos") or 0),
                                        filed_extras,
                                        filed_at=str(entry.get("filed_at") or "")):
                result.error = result.error or (
                    f"receipt not updated in {jobshot_index.INDEX_PATH.name} - "
                    f"lookups will scan the archive instead")
        except Exception as e:                  # a receipt is a cache, not truth
            result.error = result.error or f"receipt not updated: {str(e)[:90]}"

    result.ok = True
    result.status = 200
    result.folder = folder.name
    result.photos = int(entry.get("photos") or 0)
    result.filed_at = str(entry.get("filed_at") or "")
    return result


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
    if not (is_supported_image(leaf) or _SIDECAR_NAME_RE.match(leaf.name)):
        return "not a photo or a JSON file"
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
                # JobShot prints this verbatim after "The PC skipped this job:",
                # so it has to be a fragment that reads as a sentence AND says
                # what to do. "not a job" read as final; the truth here is
                # nearly always a manifest that did not arrive (CHAIN sheet §3).
                result.skipped.append({
                    "folder": folder.name,
                    "reason": "no job.json in it — send the job again"})
        if not jobs:
            result.error = "no job.json in the upload — send the job again"
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
                # The day the work was actually done. `folder` may carry a
                # different date: the archive's rule is one day number per
                # folder, so the second job of a day is moved to a free one
                # (Nick's rule, confirmed twice). Without this field the phone
                # can only say "filed as 18-09-26" for work done on the 24th,
                # which reads as a bug rather than as the rule working.
                "work_date": r.work_date.strftime("%Y-%m-%d") if r.work_date else "",
                # Files carried through that are neither photos nor the
                # manifest, under the names they were filed as. The phone shows
                # a job as safe to delete on the strength of this reply, so
                # anything it carried has to be accounted for by name.
                "extras": list(r.extras),
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
