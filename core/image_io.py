"""
image_io.py — รวม image format support
รองรับสกุลไฟล์จากหลาย source:
  - iOS:      HEIC, HEIF (default ตั้งแต่ iOS 11), JPG, PNG
  - Android:  JPG, WEBP, HEIF (บางรุ่น)
  - กล้องจีน: JPG, HEIC, DNG, WEBP
  - กล้องโปร: JPG, TIFF, RAW (CR2/NEF/ARW/DNG — V2)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

# ─── เปิดใช้ HEIC/HEIF support ────────────────────────────────
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_OK = True
except Exception:
    HEIF_OK = False


# ─── Supported extensions ────────────────────────────────────
# All consumer formats that Pillow + pillow-heif can read
SUPPORTED_EXTS = {
    # Common
    ".jpg", ".jpeg", ".jpe", ".jfif",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    # Tiff (กล้องโปร)
    ".tiff", ".tif",
    # iOS / Apple
    ".heic", ".heif",
    # Older Apple/iOS variants
    ".heics", ".heifs",
}

# Subset ที่ใช้บ่อยใน mobile photos
MOBILE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

# Formats ที่ AI Vision รับโดยตรง — อันอื่นต้อง convert เป็น JPEG ก่อน
AI_VISION_NATIVE = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTS


def get_mime_type(path: Path) -> str:
    """คืน MIME type จากนามสกุล — ใช้ส่งให้ Gemini"""
    ext = path.suffix.lower()
    mapping = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".jpe": "image/jpeg", ".jfif": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
        ".tiff": "image/tiff", ".tif": "image/tiff",
        ".heic": "image/heic", ".heics": "image/heic",
        ".heif": "image/heif", ".heifs": "image/heif",
    }
    return mapping.get(ext, "image/jpeg")


def open_image(path: Path) -> Image.Image:
    """
    เปิดรูปแบบไหนก็ได้ — return Pillow Image
    Pillow + pillow-heif รับสกุลที่ระบุใน SUPPORTED_EXTS
    """
    return Image.open(path)


def collect_images(folder: Path, recursive: bool = True) -> list[Path]:
    """รวมไฟล์รูปทุกสกุลที่รองรับจากโฟลเดอร์"""
    if not folder.exists():
        return []
    candidates = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(
        p for p in candidates
        if p.is_file() and is_supported_image(p)
    )


def format_summary() -> str:
    """สำหรับแสดงใน UI"""
    n = len(SUPPORTED_EXTS)
    heic = "✓ HEIC" if HEIF_OK else "✗ HEIC (pillow-heif missing)"
    return f"{n} formats ({heic})"
