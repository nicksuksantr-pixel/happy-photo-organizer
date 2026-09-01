"""
grouper.py — จับกลุ่มรูปก่อนส่งให้ AI วิเคราะห์
Strategy (Nick 2026-09-02):
  วันที่ถ่าย = ตัวหลักในการจัดโฟลเดอร์ — รูปที่ถ่ายวันเดียวกัน = โฟลเดอร์เดียว
  time gap ไม่ตัดกลางวันอีกแล้ว ใช้เชื่อมเฉพาะชุดที่ถ่ายคร่อมเที่ยงคืน
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .exif_reader import get_capture_date
from .image_io import collect_images as _collect

# Only bridges a burst that runs past midnight — it no longer splits a day.
DEFAULT_TIME_GAP_MINUTES = 90


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
    จับกลุ่มรูป: 1 วันที่ถ่าย = 1 กลุ่ม (= 1 โฟลเดอร์)
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
        # v1.044 (Nick 2026-09-02): THE CAPTURE DATE IS THE KEY. A job is shot
        # within one day, so every photo from the same calendar day belongs in
        # the same folder — the time gap must not split a day any more. The old
        # gap-only rule cut one day's work into several groups, and
        # assign_unique_dates then pushed each of those onto a DIFFERENT day
        # number, which is what scattered 46 folders across dates that were
        # never the shooting date (43 of them shifted).
        #
        # The gap still does one job: bridging a burst that runs past midnight
        # (23:59 → 00:01). Items are sorted ascending, so "different day but
        # within the gap" is exactly that case, and it stays with the earlier
        # day (representative_date = min(dates)). Keeps the v1.041 midnight fix.
        same_day = dt.date() == last_dt.date()
        midnight_burst = (dt - last_dt) <= gap
        if same_day or midnight_burst:
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
