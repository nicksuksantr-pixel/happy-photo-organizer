"""
jobshot.py — file a job that was photographed on the phone (JobShot).

The phone captures what only the engineer standing at the machine knows: which
photos belong to one job, what the job is called, and which shots are Before and
which are After. It sends **originals** and does not name the final folder.
Everything after arrival is the pipeline HPO already has — resize, the date
rule, naming, merging.

Two things the card-reader path does are deliberately skipped here, because the
information they exist to reconstruct is supplied:

  • **grouping** — the person who did the work already separated the jobs. The
    grouper puts one shooting day in one folder (v1.044), which would quietly
    merge two different jobs done on the same day into a single folder with a
    single name. Nothing downstream could notice.
  • **the AI naming pass** — the job name is in `job.json`, picked from the
    catalog at the machine. Better data than a Vision guess, and free.

What is NOT skipped is the date rule (`scan_used_days` → `assign_unique_dates`):
Nick's decision, 2026-09-22 — the archive rule wins over the phone's
`work_date`, same as for every other folder. The rule can therefore move a job
off the day it was really done, so the manifest keeps `work_date` untouched and
the `filed` block it gains records where the job actually landed. The date is
adjusted, never silently.

`job.json` arrives LAST and is the completion marker: a folder without it is a
transfer still in flight — ignore it, never process it, never delete it.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .catalog import JobCatalog
from .catalog import _normalize as _normalize_name
from .exif_reader import format_folder_date
from .processor import (
    PENDING_MARKER,
    JobAssignment,
    Plan,
    assign_unique_dates,
    detect_target_month,
    phase4_rename_folders,
    sanitize_filename,
    scan_used_days,
)
from .resizer import resize_to_target
from .version import read_version

MANIFEST_NAME = "job.json"
SUPPORTED_MANIFEST_VERSION = 1

# job_id from the phone is used in a file name when a folder already holds a
# manifest — keep it to characters Windows accepts.
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class ImportResult:
    ok: bool = False
    error: str = ""
    job_id: str = ""
    job_name: str = ""
    ship: str = ""
    work_date: datetime | None = None      # what the phone said (the truth)
    folder_date: datetime | None = None    # where the archive rule put it
    date_shifted: bool = False
    final_folder: Path | None = None
    merged_into_existing: bool = False
    photos_filed: int = 0
    photo_renames: dict[str, str] = field(default_factory=dict)  # phone → final
    manifest_name: str = ""
    warnings: list[str] = field(default_factory=list)


# ─── manifest ───


def is_complete(job_folder: Path) -> bool:
    """True once the phone has written the manifest — i.e. the transfer is done.
    A folder without it is still arriving: leave it completely alone."""
    try:
        return (job_folder / MANIFEST_NAME).is_file()
    except OSError:
        return False


def read_manifest(job_folder: Path) -> tuple[dict | None, str]:
    """Return (manifest, error). Never raises — a half-written or hand-edited
    file must come back as a plain refusal, not a traceback."""
    path = job_folder / MANIFEST_NAME
    try:
        raw = path.read_text(encoding="utf-8-sig")   # BOM-tolerant (v1.044 lesson)
    except FileNotFoundError:
        return None, f"no {MANIFEST_NAME} — transfer still in flight"
    except OSError as e:
        return None, f"cannot read {MANIFEST_NAME}: {str(e)[:120]}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"{MANIFEST_NAME} is not valid JSON: {str(e)[:120]}"
    if not isinstance(data, dict):
        return None, f"{MANIFEST_NAME} is not an object"

    version = data.get("jobshot")
    if version != SUPPORTED_MANIFEST_VERSION:
        return None, (f"unsupported manifest version {version!r} "
                      f"(this build reads {SUPPORTED_MANIFEST_VERSION})")
    if not str(data.get("job_name", "")).strip():
        return None, "manifest has no job_name"
    if not isinstance(data.get("photos"), list) or not data["photos"]:
        return None, "manifest lists no photos"
    return data, ""


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        # fromisoformat handles both '2026-09-22' and a full offset stamp
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], fmt)
        except ValueError:
            continue
    return None


def _job_date(manifest: dict, warnings: list[str]) -> datetime | None:
    """work_date is the engineer's own answer to 'when was this done'. Fall back
    to created_at only if it is missing — never to the file's mtime, which is
    the transfer time, not the work."""
    dt = _parse_date(manifest.get("work_date"))
    if dt is not None:
        return dt
    dt = _parse_date(manifest.get("created_at"))
    if dt is not None:
        warnings.append("manifest had no usable work_date — used created_at")
        return dt
    return None


# ─── dest_root per vessel (step 3) ───


def get_dest_root(ship: str) -> Path | None:
    """The photo folder Nick picked on this vessel's PC, if one is remembered."""
    from . import auth  # local: keeps the module importable without a config

    roots = auth.load_config().get("dest_roots") or {}
    key = str(ship or "").strip().upper()
    value = roots.get(key) if isinstance(roots, dict) else None
    return Path(value) if value else None


def remember_dest_root(ship: str, dest_root: Path) -> bool:
    """Remember it per vessel, so an arriving job files itself into the right
    tree instead of asking again every run."""
    from . import auth

    key = str(ship or "").strip().upper()
    if not key:
        return False
    roots = auth.load_config().get("dest_roots")
    roots = dict(roots) if isinstance(roots, dict) else {}
    roots[key] = str(dest_root)
    return auth.update_config({"dest_roots": roots})


# ─── one real job = one folder ───

# A filed folder is "DD-MM-YY <job name>".
_FILED_FOLDER_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{2})\s+(.+)$")


def _folder_identity(folder_name: str) -> tuple[datetime | None, str]:
    """Split a filed folder's name back into (date, job name)."""
    m = _FILED_FOLDER_RE.match(folder_name)
    if not m:
        return None, ""
    dd, mm, yy, job = m.groups()
    try:
        return datetime(2000 + int(yy), int(mm), int(dd)), job.strip()
    except ValueError:
        return None, ""


def _manifests_in(folder: Path) -> list[dict]:
    """Every JobShot manifest a folder holds — `job.json`, plus the
    `job-<id>.json` copies written when more than one job landed there."""
    found: list[dict] = []
    try:
        entries = list(folder.iterdir())
    except OSError:
        return found
    for f in entries:
        if f.suffix.lower() != ".json":
            continue
        if f.name != MANIFEST_NAME and not f.name.startswith("job-"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and data.get("jobshot"):
            found.append(data)
    return found


def find_filed_job(dest_root: Path, ship: str, job_name: str,
                   work_date: datetime) -> Path | None:
    """The folder this job already lives in, if it has been filed before.

    Nick 2026-09-22: one real job = one folder, even when the archive's day
    rule filed the first arrival on a day that is not its `work_date`. Two
    engineers photographing the same job would otherwise produce two folders on
    two different dates and spend two day numbers on a single job — the day
    rule and merge-on-name-collision are in tension, and matching on the job's
    own identity is what resolves it.

    Identity = ship + job_name + work_date, read back out of the manifests HPO
    leaves in the folders. That is the second reason `job.json` is carried into
    the final folder: it is what lets a job arriving days later find its own
    folder, whatever day the rule gave it.
    """
    want_job = _normalize_name(job_name)
    want_ship = _normalize_name(ship or "")
    want_day = work_date.date()
    if not want_job:
        return None
    try:
        folders = sorted(f for f in dest_root.iterdir() if f.is_dir())
    except OSError:
        return None

    for folder in folders:
        if PENDING_MARKER in folder.name:
            continue
        for data in _manifests_in(folder):
            if _normalize_name(str(data.get("job_name", ""))) != want_job:
                continue
            # A missing ship on either side must not block the match — it is
            # metadata, not identity. Only a genuine disagreement does.
            filed_ship = _normalize_name(str(data.get("ship", "")))
            if want_ship and filed_ship and filed_ship != want_ship:
                continue
            filed_date = _parse_date(data.get("work_date"))
            if filed_date is None or filed_date.date() != want_day:
                continue
            return folder
    return None


# ─── the headless import (steps 1 + 2) ───


def _new_temp_folder(dest_root: Path, work_date: datetime) -> Path:
    """A pending folder, carrying PENDING_MARKER so the existing delete guard
    still recognises it as ours."""
    stem = f"{work_date:%Y-%m-%d}{PENDING_MARKER}js"
    for n in range(1, 1000):
        candidate = dest_root / f"{stem}{n:02d}"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise OSError("no free pending folder name")


def import_job(
    job_folder: Path,
    dest_root: Path,
    *,
    target_kb_min: int = 10,
    target_kb_max: int = 25,
    max_dim: int = 1280,
    catalog: JobCatalog | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> ImportResult:
    """Take one arrived JobShot folder and file it — resize, date rule, commit,
    manifest carried into the final folder with its photo names rewritten.

    No UI, no AI, no grouping. Testable by hand-making the arrival folder, which
    is why this exists before any networking.
    """
    result = ImportResult()

    manifest, err = read_manifest(job_folder)
    if manifest is None:
        result.error = err
        return result

    result.job_id = str(manifest.get("job_id", "") or "")
    result.job_name = str(manifest["job_name"]).strip()
    result.ship = str(manifest.get("ship", "") or "")

    work_date = _job_date(manifest, result.warnings)
    if work_date is None:
        result.error = "manifest has no usable work_date or created_at"
        return result
    result.work_date = work_date

    # photos, in the order the engineer shot them
    entries: list[tuple[dict, Path]] = []
    for entry in manifest["photos"]:
        if not isinstance(entry, dict):
            result.warnings.append(f"ignored a malformed photos[] entry: {entry!r:.60}")
            continue
        name = str(entry.get("file", "") or "")
        src = job_folder / name
        if not name or "/" in name or "\\" in name or not src.is_file():
            result.warnings.append(f"listed photo is missing: {name!r}")
            continue
        entries.append((entry, src))
    if not entries:
        result.error = "none of the photos listed in the manifest are present"
        return result

    try:
        dest_root.mkdir(parents=True, exist_ok=True)
        temp_folder = _new_temp_folder(dest_root, work_date)
    except OSError as e:
        result.error = f"cannot create the working folder: {str(e)[:120]}"
        return result

    # resize into the pending folder — same band and same naming as Phase 1
    temp_for_phone: dict[str, str] = {}     # phone name → temp name
    resized: list[Path] = []
    for seq, (entry, src) in enumerate(entries, 1):
        if progress_cb:
            progress_cb(seq, len(entries), f"Resizing {src.name}")
        dst = temp_folder / f"img_{seq:03d}.jpg"
        ok, info = resize_to_target(
            src, dst,
            target_kb_min=target_kb_min, target_kb_max=target_kb_max,
            max_dim=max_dim,
        )
        if not ok:
            result.warnings.append(
                f"could not resize {src.name}: {str(info.get('error', ''))[:80]}")
            continue
        if info.get("warning"):
            result.warnings.append(f"{src.name} stayed above {target_kb_max} KB")
        temp_for_phone[str(entry.get("file"))] = dst.name
        resized.append(dst)

    if not resized:
        shutil.rmtree(temp_folder, ignore_errors=True)
        result.error = "every photo failed to resize — nothing was filed"
        return result

    assignment = JobAssignment(
        job_name=result.job_name,
        folder_date=work_date,
        images=[src for _e, src in entries],
        resized_paths=resized,
        temp_folder=temp_folder,
        confidence=1.0,                       # a person chose this name
        reasoning="named on the phone (JobShot)",
        source_label=result.ship,
    )
    plan = Plan(assignments=[assignment], dest_root=dest_root,
                total_images=len(entries), total_resized=len(resized))

    # Does this job already have a folder? If it does, this arrival belongs in
    # it — whatever day the rule gave that folder (Nick 2026-09-22).
    existing = find_filed_job(dest_root, result.ship, result.job_name, work_date)
    if existing is None:
        # No manifest matched. A folder filed by the card-reader path has none
        # to match, so fall back to its name: same job, same day, same folder.
        # Only when it really has no manifest — if it has one and it did not
        # match, that is an answer (a different vessel, a different work date),
        # not a gap to paper over with the name.
        by_name = dest_root / assignment.folder_name
        if by_name.is_dir() and not _manifests_in(by_name):
            existing = by_name

    filed_date, filed_job = _folder_identity(existing.name) if existing else (None, "")
    if existing is not None and filed_date is not None:
        assignment.folder_date = filed_date
        if filed_job and filed_job != sanitize_filename(result.job_name):
            # the folder was renamed by hand after it was filed — the job lives
            # there now, so follow it rather than starting a second folder
            result.warnings.append(
                f"merged into '{existing.name}', which was renamed after filing")
            assignment.job_name = filed_job
        result.merged_into_existing = True
    else:
        # The archive rule — unchanged, and it wins. It may file the job on a
        # day that is not its work_date; that is the rule working, not a
        # conflict, so work_date is left alone and the `filed` block records
        # where the job actually landed.
        target_ym = detect_target_month(dest_root) or (work_date.year, work_date.month)
        assign_unique_dates(plan, scan_used_days(dest_root), target_year_month=target_ym)

    final_folder = dest_root / assignment.folder_name
    result.folder_date = assignment.folder_date
    result.date_shifted = assignment.folder_date.date() != work_date.date()
    if not result.merged_into_existing:
        result.merged_into_existing = final_folder.exists()

    commit = phase4_rename_folders(plan, catalog=catalog)
    if commit.renamed != 1:
        detail = "; ".join(commit.errors) or "the commit skipped this job"
        result.error = f"filing failed: {detail[:200]}"
        return result
    result.warnings.extend(commit.errors)
    result.final_folder = final_folder

    # phone name → final name, composed through the temp name
    result.photo_renames = {
        phone: assignment.photo_renames.get(temp, temp)
        for phone, temp in temp_for_phone.items()
    }
    result.photos_filed = len(result.photo_renames)

    _write_manifest(manifest, result)
    result.ok = True
    return result


def _write_manifest(manifest: dict, result: ImportResult) -> None:
    """Carry `job.json` into the final folder with `photos[].file` pointing at
    the names the photos now have.

    This is the step that keeps the Before/After tags usable: the commit renames
    every photo, and without this rewrite each tag would point at a file that no
    longer exists — the information Nick collected at the machine would be lost
    with nothing to notice it.
    """
    folder = result.final_folder
    if folder is None:
        return

    out = dict(manifest)
    photos = []
    for entry in manifest.get("photos", []):
        if not isinstance(entry, dict):
            continue
        item = dict(entry)
        old = str(item.get("file", ""))
        if old in result.photo_renames:
            item["file"] = result.photo_renames[old]
            photos.append(item)
        else:
            # not filed (missing or failed to resize) — drop it rather than
            # leave a tag pointing at a photo that is not in the folder
            result.warnings.append(f"manifest entry dropped (not filed): {old}")
    out["photos"] = photos
    out["filed"] = {
        "folder": folder.name,
        "folder_date": format_folder_date(result.folder_date or datetime.now()),
        "work_date": result.work_date.strftime("%Y-%m-%d") if result.work_date else "",
        # True = the archive's unique-day rule moved this job off the day it was
        # really done. work_date above stays the truth.
        "date_shifted": result.date_shifted,
        "merged_into_existing_folder": result.merged_into_existing,
        "hpo_version": read_version(),
        "filed_at": datetime.now().isoformat(timespec="seconds"),
    }

    name = MANIFEST_NAME
    if (folder / name).exists():
        # a second job merged into this folder — never overwrite the first one's
        # manifest, and say so
        safe = _SAFE_ID_RE.sub("-", result.job_id) or "second"
        name = f"job-{safe}.json"
        result.warnings.append(
            f"folder already had a {MANIFEST_NAME} — this job's manifest was "
            f"written as {name}")
    try:
        with (folder / name).open("w", encoding="utf-8", newline="") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        result.manifest_name = name
    except OSError as e:
        result.warnings.append(f"could not write {name}: {str(e)[:120]}")
