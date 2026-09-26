"""
jobshot_index.py — "have you already filed this job?", answerable later.

The receiver's reply is what makes a job safe to delete from the phone. That
puts the whole design on one fragile moment: **the upload can succeed and the
reply can still be lost.** A dropped Wi-Fi link between "filed" and "the phone
heard it" leaves the phone unable to tell *it never arrived* from *it arrived
and I missed the answer* — and the only recoveries are re-uploading twenty
megabytes over a vessel link, or keeping the job on the phone for ever.

So the answer has to outlive the request. This is the receipt book: `job_id` →
where it was filed, written when a job is filed by **any** route (the LAN, the
drop zone, the script — they all go through `_file_group`), and readable
afterwards by `GET /jobshot/v1/job/<job_id>`.

Two things it gets right on purpose:

  • **The index is a cache; the archive is the truth.** An entry is only
    believed while the folder it names still exists. If Nick renamed the folder
    the manifests are re-scanned and the new name is returned; if he deleted it,
    the honest answer is "not filed here", so the phone keeps its copy. Better a
    re-upload than a job deleted from the only device that still has it.
  • **A merged job is filed.** A second phone's copy of one job did not create
    the folder, but its photos are on disk — answering 404 there would make the
    phone re-send work that is already safe.

It lives in the config directory, not in `dest_root`: the question is "did THIS
PC file it", it must survive an update (the code tree is overwritten by the
installer — v1.044), and it must survive HPO restarting, which is precisely the
case it exists for.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path

from . import auth

INDEX_PATH = auth.CONFIG_DIR / "jobshot_filed.json"

# A receipt book, not an archive: enough that a phone offline for weeks still
# gets an answer, small enough to read and rewrite without thinking about it.
MAX_ENTRIES = 2000

# job_id comes off the wire, and here it is used as a dict key and compared to
# manifest contents. Never as a path — but keep it boring anyway.
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

_LOCK = threading.RLock()


def valid_job_id(job_id: str) -> bool:
    return bool(_JOB_ID_RE.match(str(job_id or "")))


def _load() -> dict:
    try:
        raw = INDEX_PATH.read_text(encoding="utf-8-sig")
    except (FileNotFoundError, OSError):
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        # A corrupt receipt book must not stop anything: the archive can still
        # answer by scan, and the next write rebuilds this.
        return {}
    jobs = data.get("jobs") if isinstance(data, dict) else None
    return jobs if isinstance(jobs, dict) else {}


def _save(jobs: dict) -> bool:
    if len(jobs) > MAX_ENTRIES:
        # keep the newest, by filed_at, which is what a late phone asks about
        ordered = sorted(jobs.items(),
                         key=lambda kv: str(kv[1].get("filed_at", "")),
                         reverse=True)
        jobs = dict(ordered[:MAX_ENTRIES])
    try:
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return auth.atomic_write_json(INDEX_PATH, {"version": 1, "jobs": jobs},
                                  lock_perms=False)


def record(job_id: str, folder: Path, photos: int,
           extras: list[str] | None = None) -> bool:
    """Write the receipt. Called for every job filed, by every route.

    `extras` is here because the phone decides whether a report draft is safe
    to delete from the reply's `extras`, and a lost reply sends it to §4
    instead — which could say the job was filed but not whether the draft was
    (CHAIN-2026-09-26-01, JobShot voted yes 2026-09-26).
    """
    if not valid_job_id(job_id) or folder is None:
        return False
    with _LOCK:
        jobs = _load()
        jobs[str(job_id)] = {
            "folder": folder.name,
            "folder_path": str(folder),
            "photos": int(photos),
            "extras": [str(e) for e in (extras or [])],
            "filed_at": datetime.now().isoformat(timespec="seconds"),
        }
        return _save(jobs)


def _scan(dest_root: Path, job_id: str) -> dict | None:
    """Ask the archive itself. Slower, and it is the truth: manifests travel
    with the folders, so this still works after the index is lost, after a
    reinstall, and after Nick has renamed things by hand."""
    from . import jobshot          # local import: jobshot imports nothing here

    try:
        folders = sorted(f for f in dest_root.iterdir() if f.is_dir())
    except OSError:
        return None
    for folder in folders:
        if jobshot.PENDING_MARKER in folder.name:
            continue
        for manifest in jobshot._manifests_in(folder):
            if str(manifest.get("job_id", "")) != str(job_id):
                continue
            photos = manifest.get("photos")
            block = manifest.get("filed") or {}
            # This manifest belongs to THIS job, so its `extras` are the files
            # this job filed — which is the right answer even in a merged
            # folder holding another job's draft as well.
            extras = block.get("extras")
            return {
                "folder": folder.name,
                "folder_path": str(folder),
                "photos": len(photos) if isinstance(photos, list) else 0,
                "extras": [str(e) for e in extras] if isinstance(extras, list) else [],
                "filed_at": str(block.get("filed_at", "")),
            }
    return None


def lookup(job_id: str, dest_root: Path | None = None) -> dict | None:
    """What this PC did with that job, or None if it has no record of it.

    The index answers first because it is fast; the answer is only returned if
    the folder it names is still there. Otherwise the archive is scanned, which
    covers a renamed folder, a lost index, and a PC that filed the job before
    this feature existed.
    """
    if not valid_job_id(job_id):
        return None
    with _LOCK:
        entry = _load().get(str(job_id))
    if entry:
        path = entry.get("folder_path")
        # An entry written before v1.054 has no `extras` KEY at all, which is
        # not the same as a job that filed none. Answering [] there would tell
        # the phone a draft it is holding was never confirmed, so let the
        # archive — which still has the manifest — answer instead.
        if path and Path(path).is_dir() and "extras" in entry:
            return entry
        # The folder is gone or moved: fall through and let the archive speak.

    if dest_root is None:
        return None
    found = _scan(Path(dest_root), job_id)
    if found is not None:
        with _LOCK:
            jobs = _load()
            jobs[str(job_id)] = found
            _save(jobs)
    return found


def forget_all() -> bool:
    """Only for tests and for a deliberate reset — never called on a failure."""
    with _LOCK:
        return _save({})
