"""
exif_reader.py — ดึงวันที่ถ่ายจากรูป
Priority: EXIF DateTimeOriginal > filename pattern > file mtime
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from PIL import Image, ExifTags

# EXIF tag id ของ DateTimeOriginal = 36867
DATETIME_ORIGINAL_TAG = 36867
DATETIME_TAG = 306  # fallback

# Patterns สำหรับ extract วันที่จากชื่อไฟล์
# PXL_20260319_024041506.jpg → 2026-03-19 02:40:41
# Happy_Ena_2026-04-30_09-24-14.jpg → 2026-04-30 09:24:14
# IMG_20260319_024041.jpg
FILENAME_PATTERNS = [
    re.compile(r"(\d{4})-(\d{2})-(\d{2})[_\s](\d{2})-(\d{2})-(\d{2})"),  # YYYY-MM-DD_HH-MM-SS
    re.compile(r"(\d{4})(\d{2})(\d{2})[_\s](\d{2})(\d{2})(\d{2})"),       # YYYYMMDD_HHMMSS
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),                                # YYYY-MM-DD
    re.compile(r"(\d{4})(\d{2})(\d{2})"),                                  # YYYYMMDD
]


def _parse_exif_datetime(s: str) -> datetime | None:
    """EXIF datetime format: 'YYYY:MM:DD HH:MM:SS'"""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def read_from_exif(path: Path) -> datetime | None:
    """อ่าน EXIF DateTimeOriginal จากไฟล์รูป"""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            # ลอง DateTimeOriginal ก่อน (SubIFD)
            try:
                sub = exif.get_ifd(0x8769)  # ExifIFD
                if sub and DATETIME_ORIGINAL_TAG in sub:
                    dt = _parse_exif_datetime(str(sub[DATETIME_ORIGINAL_TAG]))
                    if dt:
                        return dt
            except Exception:
                pass
            # fallback DateTime (root IFD)
            if DATETIME_TAG in exif:
                dt = _parse_exif_datetime(str(exif[DATETIME_TAG]))
                if dt:
                    return dt
    except Exception:
        pass
    return None


def read_from_filename(path: Path) -> datetime | None:
    """พยายามดึงวันที่จากชื่อไฟล์"""
    name = path.stem
    for pat in FILENAME_PATTERNS:
        m = pat.search(name)
        if not m:
            continue
        groups = m.groups()
        try:
            if len(groups) == 6:
                y, mo, d, h, mi, s = (int(g) for g in groups)
                return datetime(y, mo, d, h, mi, s)
            if len(groups) == 3:
                y, mo, d = (int(g) for g in groups)
                return datetime(y, mo, d)
        except ValueError:
            continue
    return None


def read_from_mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except Exception:
        return None


def get_capture_date(path: Path) -> tuple[datetime, str]:
    """
    คืน (datetime, source) — source = 'exif' | 'filename' | 'mtime'
    """
    dt = read_from_exif(path)
    if dt:
        return dt, "exif"
    dt = read_from_filename(path)
    if dt:
        return dt, "filename"
    dt = read_from_mtime(path)
    if dt:
        return dt, "mtime"
    # ultimate fallback
    return datetime.now(), "now"


def format_folder_date(dt: datetime) -> str:
    """Format วันที่สำหรับชื่อโฟลเดอร์: DD-MM-YY"""
    return dt.strftime("%d-%m-%y")


def format_file_timestamp(dt: datetime) -> str:
    """Format สำหรับ rename ไฟล์ Happy_Ena_YYYY-MM-DD_HH-MM-SS"""
    return dt.strftime("%Y-%m-%d_%H-%M-%S")
