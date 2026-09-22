"""
jobshot.py — file a job that was photographed on the phone (JobShot).

The phone captures what only the engineer standing at the machine knows: which
photos belong to one job and what the job is called. It sends **originals** and
does not name the final folder. Everything after arrival is the pipeline HPO
already has — resize, the date rule, naming, merging.

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
the `filed` block it gains records where the job actually landed. `work_date` is
a record, never an instruction.

One real job = one folder (Nick, same day). An arrival is matched to the folder
its job already lives in — `job_name` + `work_date`, read back out of the
manifests left in the filed folders — whatever day the rule gave that folder.
Arrivals that land in the same batch are grouped on the same key *before* the
assigner runs, so a pair gets one day and one folder rather than two. `ship` is
no part of the key: `dest_root` is per vessel, so two jobs reaching the same
`dest_root` are already on the same ship.

`job.json` arrives LAST and is the completion marker: a folder without it is a
transfer still in flight — ignore it, never process it, never delete it. Its
`photos[]` may be plain file names (v1 as of 2026-09-22, after Before/After tags
and notes were cut — EMR already owns that) or the older `{"file": …}` objects;
both are read, and each manifest is written back in the shape it arrived in.
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
    grouped_with: list[str] = field(default_factory=list)   # job_ids filed together
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


def _photo_name(entry: object) -> str:
    """`photos[]` holds plain file names in v1; the older shape was
    `{"file": …}`. Read both — the phone and the PC update separately."""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return str(entry.get("file", "") or "")
    return ""


def _renamed_entry(entry: object, new_name: str) -> object:
    """Write the entry back in the shape it arrived in."""
    if isinstance(entry, dict):
        out = dict(entry)
        out["file"] = new_name
        return out
    return new_name


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


def job_key(job_name: str, work_date: datetime) -> tuple[str, str]:
    """What makes two arrivals the same job: its name and the day it was done.

    Not `ship` — `dest_root` is per vessel, so two jobs reaching the same
    destination are already on the same ship, and a vessel name typed slightly
    differently on two phones must not split one job into two folders.
    """
    return _normalize_name(job_name), work_date.strftime("%Y-%m-%d")


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


def find_filed_job(dest_root: Path, job_name: str,
                   work_date: datetime) -> Path | None:
    """The folder this job already lives in, if it has been filed before.

    Nick 2026-09-22: one real job = one folder, even when the archive's day
    rule filed the first arrival on a day that is not its `work_date`. Two
    engineers photographing the same job would otherwise produce two folders on
    two different dates and spend two day numbers on a single job — the day
    rule and merge-on-name-collision are in tension, and matching on the job's
    own identity is what resolves it.

    The match is read back out of the manifests HPO leaves in the folders. That
    is the second reason `job.json` is carried into the final folder: it is what
    lets a job arriving days later find its own folder, whatever day the rule
    gave it.
    """
    want = job_key(job_name, work_date)
    if not want[0]:
        return None
    try:
        folders = sorted(f for f in dest_root.iterdir() if f.is_dir())
    except OSError:
        return None

    for folder in folders:
        if PENDING_MARKER in folder.name:
            continue
        for data in _manifests_in(folder):
            filed_date = _parse_date(data.get("work_date"))
            if filed_date is None:
                continue
            if job_key(str(data.get("job_name", "")), filed_date) == want:
                return folder
    return None


# ─── the headless import (steps 1 + 2) ───


@dataclass
class _Arrival:
    """One folder the phone pushed, parsed and ready to file."""
    folder: Path
    manifest: dict
    work_date: datetime
    photos: list[tuple[object, Path]]      # (manifest entry as given, source file)
    result: ImportResult


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


def _read_arrival(job_folder: Path) -> _Arrival | ImportResult:
    """Parse one arrival. Returns a failed ImportResult rather than raising —
    one unreadable folder must never stop a batch."""
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

    photos: list[tuple[object, Path]] = []
    for entry in manifest["photos"]:
        name = _photo_name(entry)
        src = job_folder / name
        if not name or "/" in name or "\\" in name or not src.is_file():
            result.warnings.append(f"listed photo is missing: {name!r}")
            continue
        photos.append((entry, src))
    if not photos:
        result.error = "none of the photos listed in the manifest are present"
        return result

    return _Arrival(folder=job_folder, manifest=manifest, work_date=work_date,
                    photos=photos, result=result)


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

    No UI, no AI, no re-grouping. Testable by hand-making the arrival folder,
    which is why this exists before any networking.
    """
    arrival = _read_arrival(job_folder)
    if isinstance(arrival, ImportResult):
        return arrival
    _file_group([arrival], dest_root,
                target_kb_min=target_kb_min, target_kb_max=target_kb_max,
                max_dim=max_dim, catalog=catalog, progress_cb=progress_cb)
    return arrival.result


def import_batch(
    job_folders: list[Path],
    dest_root: Path,
    *,
    target_kb_min: int = 10,
    target_kb_max: int = 25,
    max_dim: int = 1280,
    catalog: JobCatalog | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> list[ImportResult]:
    """File several arrivals at once, grouping the ones that are the same job
    **before** the day rule runs.

    Nick works by collecting a few jobs and sending them in one sitting, and two
    engineers paired to the same PC can interleave their sends — so two arrivals
    with the same `job_name` and `work_date` in one batch is a normal day, not
    an edge case. Filing them separately would hand the pair two days and two
    folders for one real job; grouping first gives them one of each.

    Returns one result per input folder, in the order given, so a receive log
    can say what happened to each.
    """
    arrivals: list[_Arrival] = []
    results: dict[int, ImportResult] = {}
    for i, folder in enumerate(job_folders):
        parsed = _read_arrival(folder)
        if isinstance(parsed, ImportResult):
            results[i] = parsed          # unreadable — reported, never fatal
        else:
            arrivals.append(parsed)
            results[i] = parsed.result

    groups: dict[tuple[str, str], list[_Arrival]] = {}
    for arrival in arrivals:
        groups.setdefault(
            job_key(arrival.result.job_name, arrival.work_date), []).append(arrival)

    # Oldest work first, so the archive fills in the order the work happened.
    # Within one work_date the tie-break is when the job was created on the
    # phone: jobs sharing a day cannot all keep it, and the one done first has
    # the better claim to it than whichever name sorts lower.
    def _order(item: tuple[tuple[str, str], list[_Arrival]]):
        (name_key, date_key), group = item
        created = min(str(a.manifest.get("created_at", "")) for a in group)
        return date_key, created, name_key

    for _key, group in sorted(groups.items(), key=_order):
        _file_group(group, dest_root,
                    target_kb_min=target_kb_min, target_kb_max=target_kb_max,
                    max_dim=max_dim, catalog=catalog, progress_cb=progress_cb)

    return [results[i] for i in range(len(job_folders))]


def _file_group(
    arrivals: list[_Arrival],
    dest_root: Path,
    *,
    target_kb_min: int,
    target_kb_max: int,
    max_dim: int,
    catalog: JobCatalog | None,
    progress_cb: Callable[[int, int, str], None] | None,
) -> None:
    """File one job — which may have arrived as several folders — into one
    folder, on one day. Fills each arrival's ImportResult in place."""
    if not arrivals:
        return

    # deterministic order: when the job was created on the phone, then the
    # folder name, so photo numbering follows the work rather than the disk
    arrivals.sort(key=lambda a: (str(a.manifest.get("created_at", "")), a.folder.name))
    lead = arrivals[0]
    job_name = lead.result.job_name
    work_date = lead.work_date
    results = [a.result for a in arrivals]
    all_ids = [a.result.job_id for a in arrivals if a.result.job_id]

    def fail(message: str) -> None:
        for r in results:
            r.ok = False
            r.error = message

    try:
        dest_root.mkdir(parents=True, exist_ok=True)
        temp_folder = _new_temp_folder(dest_root, work_date)
    except OSError as e:
        fail(f"cannot create the working folder: {str(e)[:120]}")
        return

    # resize into the pending folder — same band and same naming as Phase 1.
    # The map is per arrival: two phones both send `0001.jpg`, so a single
    # shared map would have one overwrite the other.
    temp_for_phone: list[dict[str, str]] = [{} for _ in arrivals]
    resized: list[Path] = []
    sources: list[Path] = []
    total = sum(len(a.photos) for a in arrivals)
    seq = 0
    for idx, arrival in enumerate(arrivals):
        for entry, src in arrival.photos:
            seq += 1
            if progress_cb:
                progress_cb(seq, total, f"Resizing {src.name}")
            dst = temp_folder / f"img_{seq:03d}.jpg"
            ok, info = resize_to_target(
                src, dst,
                target_kb_min=target_kb_min, target_kb_max=target_kb_max,
                max_dim=max_dim,
            )
            if not ok:
                arrival.result.warnings.append(
                    f"could not resize {src.name}: {str(info.get('error', ''))[:80]}")
                continue
            if info.get("warning"):
                arrival.result.warnings.append(
                    f"{src.name} stayed above {target_kb_max} KB")
            temp_for_phone[idx][_photo_name(entry)] = dst.name
            resized.append(dst)
            sources.append(src)

    if not resized:
        shutil.rmtree(temp_folder, ignore_errors=True)
        fail("every photo failed to resize — nothing was filed")
        return

    assignment = JobAssignment(
        job_name=job_name,
        folder_date=work_date,
        images=sources,
        resized_paths=resized,
        temp_folder=temp_folder,
        confidence=1.0,                       # a person chose this name
        reasoning="named on the phone (JobShot)",
        source_label=lead.result.ship,
    )
    plan = Plan(assignments=[assignment], dest_root=dest_root,
                total_images=total, total_resized=len(resized))

    # Does this job already have a folder? If it does, this arrival belongs in
    # it — whatever day the rule gave that folder (Nick 2026-09-22).
    existing = find_filed_job(dest_root, job_name, work_date)
    if existing is None:
        # No manifest matched. A folder filed by the card-reader path has none
        # to match, so fall back to its name: same job, same day, same folder.
        # Only when it really has no manifest — if it has one and it did not
        # match, that is an answer (a different work date), not a gap to paper
        # over with the name.
        by_name = dest_root / assignment.folder_name
        if by_name.is_dir() and not _manifests_in(by_name):
            existing = by_name

    filed_date, filed_job = _folder_identity(existing.name) if existing else (None, "")
    merged = existing is not None and filed_date is not None
    if merged:
        assignment.folder_date = filed_date
        if filed_job and filed_job != sanitize_filename(job_name):
            # the folder was renamed by hand after it was filed — the job lives
            # there now, so follow it rather than starting a second folder
            for r in results:
                r.warnings.append(
                    f"merged into '{existing.name}', which was renamed after filing")
            assignment.job_name = filed_job
    else:
        # The archive rule — unchanged, and it wins. It may file the job on a
        # day that is not its work_date; that is the rule working, not a
        # conflict, so work_date is left alone and the `filed` block records
        # where the job actually landed.
        target_ym = detect_target_month(dest_root) or (work_date.year, work_date.month)
        assign_unique_dates(plan, scan_used_days(dest_root), target_year_month=target_ym)

    final_folder = dest_root / assignment.folder_name
    merged = merged or final_folder.exists()

    commit = phase4_rename_folders(plan, catalog=catalog)
    if commit.renamed != 1:
        detail = "; ".join(commit.errors) or "the commit skipped this job"
        fail(f"filing failed: {detail[:200]}")
        return

    for idx, arrival in enumerate(arrivals):
        r = arrival.result
        r.warnings.extend(commit.errors)
        r.final_folder = final_folder
        r.folder_date = assignment.folder_date
        r.date_shifted = assignment.folder_date.date() != arrival.work_date.date()
        r.merged_into_existing = merged
        r.grouped_with = [j for j in all_ids if j != r.job_id]
        r.photo_renames = {
            phone: assignment.photo_renames.get(temp, temp)
            for phone, temp in temp_for_phone[idx].items()
        }
        r.photos_filed = len(r.photo_renames)
        _write_manifest(arrival)
        r.ok = True


def _write_manifest(arrival: _Arrival) -> None:
    """Carry `job.json` into the final folder with its `photos[]` pointing at
    the names the photos now have.

    The rewrite is no longer load-bearing for the report — Before/After tags
    were cut from the manifest on 2026-09-22, EMR owns that — but it is what
    lets a receive log say which sent file became which filed file, and a
    manifest that lists names no longer in the folder is a trap for whoever
    reads it next.
    """
    result = arrival.result
    folder = result.final_folder
    if folder is None:
        return

    out = dict(arrival.manifest)
    photos: list[object] = []
    for entry in arrival.manifest.get("photos", []):
        old = _photo_name(entry)
        if old in result.photo_renames:
            photos.append(_renamed_entry(entry, result.photo_renames[old]))
        else:
            # not filed (missing or failed to resize) — drop it rather than
            # leave the manifest pointing at a photo that is not in the folder
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
        "grouped_with": list(result.grouped_with),
        "hpo_version": read_version(),
        "filed_at": datetime.now().isoformat(timespec="seconds"),
    }

    name = MANIFEST_NAME
    if (folder / name).exists():
        # another job's manifest is already here — never overwrite it, that
        # would erase the first job's record of what it sent
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
