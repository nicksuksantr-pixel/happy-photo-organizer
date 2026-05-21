"""
resizer.py — ย่อรูป target 20-50 KB
Strategy:
  1. ลด resolution ก่อน (ถ้าใหญ่กว่า max_dim)
  2. Iterative reduce JPEG quality 95 → 50 จนได้ขนาดที่ต้องการ
  3. ถ้ายังเกิน — ลด resolution อีก แล้ว retry
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

from .image_io import open_image  # registers HEIF opener on import

DEFAULT_TARGET_KB_MIN = 10
DEFAULT_TARGET_KB_MAX = 25
DEFAULT_MAX_DIM = 1280  # longest edge (ลดจาก 1920 เพื่อ output เล็กขึ้น)

QUALITY_STEPS = [90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20]


def _save_jpeg_bytes(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    # convert to RGB ถ้ายังไม่ใช่ (RGBA / P → RGB)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def _scale_image(img: Image.Image, max_dim: int) -> Image.Image:
    w, h = img.size
    longest = max(w, h)
    if longest <= max_dim:
        return img
    scale = max_dim / longest
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.LANCZOS)


def resize_to_target(
    src_path: Path,
    dst_path: Path,
    *,
    target_kb_min: int = DEFAULT_TARGET_KB_MIN,
    target_kb_max: int = DEFAULT_TARGET_KB_MAX,
    max_dim: int = DEFAULT_MAX_DIM,
) -> tuple[bool, dict]:
    """
    ย่อรูปลงให้ขนาดอยู่ระหว่าง target_kb_min ถึง target_kb_max
    คืน (success, info_dict)
    """
    try:
        original_size = src_path.stat().st_size
        with open_image(src_path) as raw:
            # honor EXIF orientation
            img = ImageOps.exif_transpose(raw)
            current_max_dim = max_dim

            for attempt in range(4):
                scaled = _scale_image(img, current_max_dim)

                # binary-ish search ผ่าน quality steps
                best_data = None
                best_quality = None
                for q in QUALITY_STEPS:
                    data = _save_jpeg_bytes(scaled, q)
                    size_kb = len(data) / 1024
                    if size_kb <= target_kb_max:
                        best_data = data
                        best_quality = q
                        if size_kb >= target_kb_min:
                            # อยู่ในช่วง sweet spot — หยุด
                            break

                if best_data is not None:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    dst_path.write_bytes(best_data)
                    return True, {
                        "original_size_kb": original_size / 1024,
                        "final_size_kb": len(best_data) / 1024,
                        "quality": best_quality,
                        "max_dim_used": current_max_dim,
                        "attempts": attempt + 1,
                    }

                # ถ้ายัง > target — ลด dim ลงครึ่งหนึ่ง แล้ว retry
                current_max_dim = max(current_max_dim // 2, 320)

            # ถ้ายังไม่ได้ผ่าน 4 รอบ — save ที่ quality ต่ำสุดไปก่อน
            data = _save_jpeg_bytes(_scale_image(img, current_max_dim), QUALITY_STEPS[-1])
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_path.write_bytes(data)
            return True, {
                "original_size_kb": original_size / 1024,
                "final_size_kb": len(data) / 1024,
                "quality": QUALITY_STEPS[-1],
                "max_dim_used": current_max_dim,
                "attempts": 4,
                "warning": "เกิน target — ใช้ quality ต่ำสุด",
            }
    except Exception as e:
        return False, {"error": str(e)[:200]}
