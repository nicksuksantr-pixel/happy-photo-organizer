"""
processor.py — Engine ที่ orchestrate ทุก step

Workflow V1.001 (ตาม feedback ของนิก):
  Phase 1 (LOCAL):  collect → group by date → resize → copy ไปโฟลเดอร์ temp
                    (โฟลเดอร์ชั่วคราวชื่อตามวันที่: "YYYY-MM-DD_session-N")
  Phase 2 (AI):     sample 1-3 รูปต่อโฟลเดอร์ → ส่ง Gemini → ได้ชื่องาน
  Phase 3 (USER):   review + edit ชื่องานในตาราง
  Phase 4 (COMMIT): rename โฟลเดอร์ตามชื่องานสุดท้าย

เหตุผล: ไม่ส่งรูปดิบ 1000 ใบให้ AI พร้อมกัน — AI จะตาย
"""
from __future__ import annotations

import re
import shutil
import threading
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import grouper as _grouper
from .analyzer import analyze_group
from .auth import create_client
from .catalog import JobCatalog
from .exif_reader import format_folder_date
from .image_io import collect_images
from .resizer import resize_to_target

# ─── safe filename ───
_INVALID_FN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(s: str, max_len: int = 80) -> str:
    s = _INVALID_FN_CHARS.sub(" ", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:max_len].strip()


# ─── dataclasses ───


@dataclass
class JobAssignment:
    """งาน 1 งาน = โฟลเดอร์ output 1 โฟลเดอร์"""
    job_name: str = ""
    folder_date: datetime = field(default_factory=datetime.now)
    original_date: datetime | None = None      # วันที่จาก EXIF เดิม (ก่อน shift)
    date_was_capped: bool = False               # True = เกินวันสิ้นเดือน → ใช้วันสุดท้าย
    images: list[Path] = field(default_factory=list)        # path ของรูปต้นฉบับ
    resized_paths: list[Path] = field(default_factory=list) # path หลัง resize (ใน temp folder)
    temp_folder: Path | None = None                          # โฟลเดอร์ชั่วคราว
    confidence: float = 0.0
    reasoning: str = ""
    is_new_suggestion: bool = False
    source_label: str = ""

    @property
    def folder_name(self) -> str:
        """ชื่อโฟลเดอร์สุดท้าย: DD-MM-YY [ชื่องาน]"""
        date_str = format_folder_date(self.folder_date)
        clean_job = sanitize_filename(self.job_name)
        return f"{date_str} {clean_job}"

    @property
    def needs_review(self) -> bool:
        return self.confidence < 0.7 or self.is_new_suggestion or self.date_was_capped

    @property
    def date_shifted(self) -> bool:
        return (
            self.original_date is not None
            and self.original_date.date() != self.folder_date.date()
        )


@dataclass
class Plan:
    assignments: list[JobAssignment] = field(default_factory=list)
    dest_root: Path = Path(".")
    total_images: int = 0
    total_resized: int = 0
    shifted_count: int = 0
    capped_count: int = 0
    pre_existing_dates: list[str] = field(default_factory=list)
    # Count of images that hit resizer fallback path (target_kb_max exceeded
    # even at lowest quality). Reported in the UI so Nick knows to spot-check.
    oversized_count: int = 0


@dataclass
class CommitResult:
    renamed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    output_folders: list[Path] = field(default_factory=list)


# ─── Date allocation helpers ───

# Pattern A — single day: "DD-MM-YY <space>"
_FOLDER_DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{2})\s")
# Pattern B — range with dot: "DD-DD.MM.YY <space>"  (เช่น "15-17.05.26 Job MD")
_FOLDER_DATE_RANGE_RE = re.compile(r"^(\d{2})-(\d{2})\.(\d{2})\.(\d{2})\s")


def scan_used_days(dest_root: Path) -> set[int]:
    """Scan dest_root → คืน set ของ 'day numbers' (1-31) ที่ปรากฏแล้ว
    (ไม่ filter ตาม month — Nick's rule: เลขวันต้อง unique across all months)

    รองรับ 2 patterns:
      • DD-MM-YY <space>          (เช่น "13-05-26 DG3 Inspection")
      • DD-DD.MM.YY <space>       (เช่น "15-17.05.26 Job MD") → expand เป็นทุกวันใน range
    """
    if not dest_root.exists() or not dest_root.is_dir():
        return set()
    used: set[int] = set()
    for sub in dest_root.iterdir():
        if not sub.is_dir():
            continue
        name = sub.name

        # Pattern B (check ก่อนเพราะ DD-DD.MM.YY มี hyphen เหมือน DD-MM-YY)
        mr = _FOLDER_DATE_RANGE_RE.match(name)
        if mr:
            try:
                d_start = int(mr.group(1))
                d_end = int(mr.group(2))
                if 1 <= d_start <= 31 and 1 <= d_end <= 31 and d_start <= d_end:
                    for d in range(d_start, d_end + 1):
                        used.add(d)
                    continue
            except ValueError:
                pass

        # Pattern A
        m = _FOLDER_DATE_RE.match(name)
        if m:
            try:
                d = int(m.group(1))
                if 1 <= d <= 31:
                    used.add(d)
            except ValueError:
                pass
    return used


def detect_target_month(dest_root: Path) -> tuple[int, int] | None:
    """หา (year, month) ที่ปรากฏมากที่สุดจากชื่อ folders ใน dest_root.
    คืน None ถ้า dest_root ว่าง / ไม่มี folder ตรง pattern.
    """
    if not dest_root.exists() or not dest_root.is_dir():
        return None
    counts: dict[tuple[int, int], int] = {}
    for sub in dest_root.iterdir():
        if not sub.is_dir():
            continue
        name = sub.name
        mr = _FOLDER_DATE_RANGE_RE.match(name)
        if mr:
            try:
                mm = int(mr.group(3))
                yy = int(mr.group(4))
                year = 2000 + yy if yy < 100 else yy
                if 1 <= mm <= 12:
                    key = (year, mm)
                    counts[key] = counts.get(key, 0) + 1
                continue
            except ValueError:
                pass
        m = _FOLDER_DATE_RE.match(name)
        if m:
            try:
                mm = int(m.group(2))
                yy = int(m.group(3))
                year = 2000 + yy if yy < 100 else yy
                if 1 <= mm <= 12:
                    key = (year, mm)
                    counts[key] = counts.get(key, 0) + 1
            except ValueError:
                pass
    if not counts:
        return None
    # most common (mode) — tie-break by latest (year, month)
    return max(counts.items(), key=lambda x: (x[1], x[0]))[0]


def _find_free_day_earliest(
    base_day: int,
    last_day: int,
    occupied_days: set[int],
) -> int | None:
    """หาวันว่างใน [1, last_day]
    • ถ้า base_day ว่าง → ใช้ตรงๆ (รักษา EXIF day)
    • ถ้าไม่ → scan จาก day 1 ขึ้นไป → คืน gap แรกที่เจอ (fill earliest gap)
    • ถ้าทั้งเดือนเต็ม → None
    """
    if 1 <= base_day <= last_day and base_day not in occupied_days:
        return base_day
    for d in range(1, last_day + 1):
        if d not in occupied_days:
            return d
    return None


def assign_unique_dates(
    plan: Plan,
    used_days: set[int],
    target_year_month: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """ปรับ folder_date ของแต่ละ assignment.
    Strategy:
      • Consolidate ทุก assignment ไปยัง target month/year (ถ้ามี) เพื่อให้
        ผลลัพธ์อยู่ในเดือนเดียวกัน
      • Earliest-gap-first — ถ้า EXIF day ตรงกับวันว่าง → ใช้, ไม่งั้น fill gap แรก
      • เลขวัน unique across เดือน (ตาม Nick's rule)
      • ถ้า target month เต็มจริง → cap วันสุดท้าย, flag date_was_capped

    Args:
      plan: Plan ที่มี assignments
      used_days: set ของเลขวัน 1-31 ที่ใช้แล้วใน dest_root (ทุกเดือน)
      target_year_month: (year, month) สำหรับ consolidate. ถ้า None → ใช้ EXIF month/year ของแต่ละ assignment

    Returns: (shifted_count, capped_count)
    """
    occupied = set(used_days)
    shifted = 0
    capped = 0

    plan.assignments.sort(key=lambda a: a.folder_date)

    for a in plan.assignments:
        base = a.folder_date
        a.original_date = base

        # เลือก year/month เป้าหมาย
        if target_year_month:
            tgt_year, tgt_month = target_year_month
        else:
            tgt_year, tgt_month = base.year, base.month

        last_day = monthrange(tgt_year, tgt_month)[1]
        free_day = _find_free_day_earliest(base.day, last_day, occupied)

        if free_day is None:
            # ทั้งเดือนเต็ม → ใช้วันสุดท้าย (ยอมซ้ำ, แก้มือ)
            new_day = last_day
            a.date_was_capped = True
            capped += 1
        else:
            new_day = free_day
            occupied.add(free_day)

        # build new datetime — ใช้ tgt year/month + new_day, keep time จาก EXIF
        try:
            a.folder_date = base.replace(year=tgt_year, month=tgt_month, day=new_day)
        except ValueError:
            # base วันเกินกว่า last_day ของเดือนใหม่ — fallback ใช้ time-only
            a.folder_date = datetime(
                tgt_year, tgt_month, new_day,
                base.hour, base.minute, base.second,
            )

        if (a.folder_date.year != base.year
                or a.folder_date.month != base.month
                or a.folder_date.day != base.day):
            shifted += 1

    return shifted, capped


# ─── PHASE 1: Resize + Group ───


def phase1_resize_and_group(
    sources: list[Path],
    dest_root: Path,
    *,
    target_kb_min: int = 10,
    target_kb_max: int = 25,
    max_dim: int = 1280,
    time_gap_minutes: int = 90,
    progress_cb: Callable[[int, int, str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> Plan:
    """
    1. รวบรวมรูปจาก sources
    2. group ตามวันที่ + time gap
    3. resize + copy ลง dest_root/<temp_folder_name>/
    """
    plan = Plan(dest_root=dest_root)

    # collect from each source
    items: list[tuple[Path, str]] = []  # (image_path, source_label)
    for src in sources:
        if src.is_file():
            items.append((src, src.parent.name))
        elif src.is_dir():
            for img in collect_images(src, recursive=True):
                items.append((img, src.name))

    plan.total_images = len(items)
    if not items:
        return plan

    # group all images by date+time across all sources
    all_imgs = [img for img, _ in items]
    label_map = {img: lbl for img, lbl in items}
    groups = _grouper.group_by_session(all_imgs, time_gap_minutes=time_gap_minutes)

    # process each group → temp folder
    total = sum(len(g) for g in groups)
    done = 0

    for idx, g in enumerate(groups, 1):
        if cancel_event and cancel_event.is_set():
            break

        # temp folder name = "YYYY-MM-DD_session-N"
        date_part = g.representative_date.strftime("%Y-%m-%d")
        temp_name = f"{date_part}__pending_{idx:02d}"
        temp_folder = dest_root / temp_name
        temp_folder.mkdir(parents=True, exist_ok=True)

        assignment = JobAssignment(
            folder_date=g.representative_date,
            images=list(g.images),
            temp_folder=temp_folder,
            source_label=label_map.get(g.images[0], "") if g.images else "",
        )

        for seq, img in enumerate(sorted(g.images), 1):
            if cancel_event and cancel_event.is_set():
                break
            done += 1
            if progress_cb:
                progress_cb(done, total, f"Resizing {img.name}")

            dst = temp_folder / f"img_{seq:03d}.jpg"
            ok, info = resize_to_target(
                img, dst,
                target_kb_min=target_kb_min,
                target_kb_max=target_kb_max,
                max_dim=max_dim,
            )
            if ok:
                assignment.resized_paths.append(dst)
                plan.total_resized += 1
                # Resizer returns ok=True with a 'warning' field when it fell
                # back to lowest-quality save and the file still exceeded
                # target_kb_max. Surface the count via the Plan so the UI can
                # report it after Phase 1 (previously: silent — warning swallowed).
                if info.get("warning"):
                    plan.oversized_count += 1

        plan.assignments.append(assignment)

    # Auto-assign unique dates — หลีกเลี่ยงเลขวันซ้ำ + consolidate to dominant month
    used_days = scan_used_days(dest_root)
    target_ym = detect_target_month(dest_root)
    # Empty-dest defensive default: if there are no existing folders to anchor
    # against, use the current month/year as the target instead of inheriting
    # EXIF dates blindly. Prevents misconfigured-camera-clock photos (e.g. EXIF
    # year 2050) from landing as `01-05-50` folders (round-3 BUG-3-6).
    if target_ym is None:
        now = datetime.now()
        target_ym = (now.year, now.month)
    plan.pre_existing_dates = sorted(f"{d:02d}" for d in used_days)
    plan.shifted_count, plan.capped_count = assign_unique_dates(
        plan, used_days, target_year_month=target_ym,
    )

    return plan


# ─── PHASE 2: AI sample per folder ───


def _apply_result_to_assignment(
    assignment: "JobAssignment",
    result: dict,
    catalog: JobCatalog,
) -> None:
    """Apply AI result → mutate assignment in place. Safe to call from main thread."""
    matched = result.get("matched_name")
    suggested = result.get("suggested_name")
    confidence = float(result.get("confidence") or 0.0)

    # fuzzy fallback เผื่อ AI สะกดต่าง
    resolved = None
    for candidate in (matched, suggested):
        if not candidate:
            continue
        entry, sim = catalog.find_fuzzy(candidate)
        if entry and sim >= 0.85:
            resolved = entry["name"]
            break

    if resolved:
        assignment.job_name = resolved
        assignment.is_new_suggestion = False
    elif suggested:
        assignment.job_name = suggested
        assignment.is_new_suggestion = True
    else:
        assignment.job_name = ""
        assignment.is_new_suggestion = True

    assignment.confidence = confidence
    assignment.reasoning = result.get("reasoning", "")


def phase2_ai_analyze(
    plan: Plan,
    catalog: JobCatalog,
    *,
    sample_size: int = 3,
    max_workers: int = 4,
    progress_cb: Callable[[int, int, str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> Plan:
    """
    Phase 2: ส่ง 1-3 รูปต่อโฟลเดอร์ให้ Gemini วิเคราะห์ — parallel ผ่าน ThreadPoolExecutor
    Rate limiter ภายใน analyze_group() เป็น thread-safe — handle quota เอง
    """
    client, err = create_client()
    if err:
        for a in plan.assignments:
            a.reasoning = f"AI error: {err}"
            a.is_new_suggestion = True
        return plan

    names = catalog.names()
    total = len(plan.assignments)
    if total == 0:
        return plan

    # Filter assignments ที่มี sample จริงๆ
    work_items: list[tuple[int, JobAssignment, list[Path]]] = []
    for idx, a in enumerate(plan.assignments):
        pool = a.resized_paths if a.resized_paths else a.images
        if pool:
            work_items.append((idx, a, pool))

    completed = {"n": 0}
    completed_lock = threading.Lock()

    def _worker(item: tuple[int, JobAssignment, list[Path]]) -> tuple[int, dict]:
        idx, _a, pool = item
        if cancel_event and cancel_event.is_set():
            return idx, {}
        # Pass cancel_event so analyze_group can short-circuit during throttle
        # sleep (free tier = 4 s/call → up to 4 s of quota burn per worker
        # without this).
        result = analyze_group(
            pool, names, client=client, sample_size=sample_size,
            cancel_event=cancel_event,
        )
        return idx, result

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="phase2") as ex:
        futures = {ex.submit(_worker, item): item for item in work_items}
        for fut in as_completed(futures):
            if cancel_event and cancel_event.is_set():
                # cancel remaining
                for f in futures:
                    f.cancel()
                break
            try:
                idx, result = fut.result()
            except Exception as e:
                idx, _a, _ = futures[fut]
                result = {
                    "matched_name": None, "suggested_name": None,
                    "confidence": 0.0, "reasoning": f"worker error: {str(e)[:200]}",
                }

            if result:
                _apply_result_to_assignment(plan.assignments[idx], catalog=catalog, result=result)

            with completed_lock:
                completed["n"] += 1
                done = completed["n"]
            if progress_cb:
                src_item = futures[fut]
                photos_n = len(src_item[2])
                progress_cb(done, len(work_items), f"Analyzed folder {done}/{len(work_items)} ({photos_n} photos)")

    return plan


# ─── PHASE 4: Rename temp folders → final folder names ───


def phase4_rename_folders(
    plan: Plan,
    *,
    progress_cb: Callable[[int, int, str], None] | None = None,
    cancel_event: threading.Event | None = None,
    catalog: JobCatalog | None = None,
) -> CommitResult:
    """
    Rename temp folders ('YYYY-MM-DD__pending_NN') → final ('DD-MM-YY [ชื่องาน]')
    """
    result = CommitResult()
    total = len(plan.assignments)
    # Cap on collision-suffix counter to avoid O(N²) when a target folder
    # already holds many img_NNN_M files (round-3 BUG-3-5)
    _COLLISION_CAP = 9999

    for i, a in enumerate(plan.assignments, 1):
        if cancel_event and cancel_event.is_set():
            break

        if not a.job_name.strip() or not a.temp_folder:
            result.skipped += 1
            # Still report progress so the bar reaches 100% on skip-only runs
            if progress_cb:
                progress_cb(i, total, f"Skipped {i}/{total} (no job name)")
            continue

        target = plan.dest_root / a.folder_name
        # ถ้าโฟลเดอร์ปลายทางมีอยู่แล้ว → merge (move files)
        try:
            if target.exists() and target != a.temp_folder:
                # merge: ย้ายไฟล์ทั้งหมดจาก temp → target แล้วลบ temp
                target.mkdir(parents=True, exist_ok=True)
                for f in a.temp_folder.iterdir():
                    dst_file = target / f.name
                    cnt = 2
                    while dst_file.exists() and cnt <= _COLLISION_CAP:
                        dst_file = target / f"{f.stem}_{cnt}{f.suffix}"
                        cnt += 1
                    if dst_file.exists():
                        # Cap hit — fall back to a unique suffix
                        import uuid as _uuid
                        dst_file = target / f"{f.stem}_{_uuid.uuid4().hex[:8]}{f.suffix}"
                    shutil.move(str(f), str(dst_file))
                try:
                    a.temp_folder.rmdir()
                except OSError:
                    # Folder not empty (e.g. Thumbs.db created mid-operation).
                    # Not fatal — surfaced via .errors instead of silent skip.
                    leftovers = [p.name for p in a.temp_folder.iterdir()]
                    if leftovers:
                        result.errors.append(
                            f"temp folder not empty after merge: "
                            f"{a.temp_folder.name} (leftover: {leftovers[:3]})"
                        )
            else:
                a.temp_folder.rename(target)

            if target not in result.output_folders:
                result.output_folders.append(target)
            result.renamed += 1

            # update catalog — wrap in try so a catalog failure doesn't fail the rename
            if catalog is not None:
                try:
                    catalog.record_usage(
                        a.job_name,
                        ship=None,
                        date_str=format_folder_date(a.folder_date),
                    )
                except Exception as e:
                    result.errors.append(f"catalog record failed for {a.job_name}: {str(e)[:120]}")
        except Exception as e:
            result.errors.append(f"{a.temp_folder.name} → {a.folder_name}: {str(e)[:200]}")

        # Report progress AFTER the actual work so % doesn't run ahead
        # (round-3 BUG-3-4)
        if progress_cb:
            progress_cb(i, total, f"Renamed {i}/{total}")

    if catalog is not None:
        try:
            catalog.save()
        except Exception:
            pass

    return result
