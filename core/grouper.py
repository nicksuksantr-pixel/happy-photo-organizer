"""
grouper.py — จับกลุ่มรูปก่อนส่งให้ AI วิเคราะห์
Strategy:
  1. Group by capture date (ปกติงาน 1 งาน = วันเดียวกัน)
  2. ภายใน 1 วัน group by time gap — รูปที่ถ่ายห่างกัน > THRESHOLD = คนละ session
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .exif_reader import get_capture_date
from .image_io import collect_images as _collect

DEFAULT_TIME_GAP_MINUTES = 90  # รูปที่ถ่ายห่างกันเกินนี้ → คนละ session


@dataclass
class PhotoGroup:
    """กลุ่มของรูปที่น่าจะเป็นงานเดียวกัน"""
    images: list[Path] = field(default_factory=list)
    dates: list[datetime] = field(default_factory=list)
    date_sources: list[str] = field(default_factory=list)

    @property
    def start_date(self) -> datetime:
        return min(self.dates) if self.dates else datetime.now()

    @property
    def end_date(self) -> datetime:
        return max(self.dates) if self.dates else datetime.now()

    @property
    def representative_date(self) -> datetime:
        """วันที่ตัวแทนของกลุ่ม — ใช้ตัวที่เก่าที่สุด"""
        return self.start_date

    def __len__(self) -> int:
        return len(self.images)


def collect_images(folder: Path, recursive: bool = True) -> list[Path]:
    """รวบรวมไฟล์รูปจากโฟลเดอร์ — ใช้ image_io เพื่อรองรับสกุลครบ"""
    return _collect(folder, recursive=recursive)


def group_by_session(
    images: list[Path],
    time_gap_minutes: int = DEFAULT_TIME_GAP_MINUTES,
) -> list[PhotoGroup]:
    """
    จับกลุ่มรูปตามวันที่ + time gap
    คืน list ของ PhotoGroup ที่เรียงตามวันที่
    """
    if not images:
        return []

    # อ่านวันที่ของทุกใบก่อน
    items = []
    for img in images:
        dt, src = get_capture_date(img)
        items.append((dt, src, img))

    # sort ตามเวลา
    items.sort(key=lambda x: x[0])

    groups: list[PhotoGroup] = []
    current = PhotoGroup()
    gap = timedelta(minutes=time_gap_minutes)

    for dt, src, img in items:
        if not current.images:
            current.images.append(img)
            current.dates.append(dt)
            current.date_sources.append(src)
            continue

        last_dt = current.dates[-1]
        # Session = continuous shooting activity. Use the time-gap ALONE to
        # decide session membership — do NOT also require same calendar day.
        # Bug (Tester 2026-06-04): the old `same_day and within_gap` rule split
        # a continuous burst that crossed midnight (e.g. 23:59 → 00:01, 2 min
        # apart) into two folders, because the calendar day flipped. Items are
        # sorted ascending, so the only case where within_gap is True but the
        # day differs is exactly a near-midnight burst — which belongs in one
        # session. A genuine next-day shoot is always > gap apart and still
        # splits. representative_date = min(dates) keeps the folder dated by
        # the session's first photo (the pre-midnight day).
        within_gap = (dt - last_dt) <= gap
        if within_gap:
            current.images.append(img)
            current.dates.append(dt)
            current.date_sources.append(src)
        else:
            groups.append(current)
            current = PhotoGroup(
                images=[img], dates=[dt], date_sources=[src]
            )

    if current.images:
        groups.append(current)

    return groups
