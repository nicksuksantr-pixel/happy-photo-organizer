"""
gen_assets.py — สร้าง logo + icon ของ Happy Photo Organizer
รันครั้งเดียวเพื่อ generate assets/happy_logo.png + happy_icon.ico
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

# HAPPY theme colors
ORANGE = (0xFB, 0x92, 0x3C)
PINK = (0xEC, 0x48, 0x99)
WHITE = (0xFF, 0xFF, 0xFF)


def _gradient_circle(size: int) -> Image.Image:
    """Circle with radial-ish gradient ส้ม → ชมพู"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    center = size // 2
    max_radius = size // 2 - 4

    # draw from outer to inner — pink outside, orange inside
    for r in range(max_radius, 0, -1):
        ratio = 1 - (r / max_radius)  # 0 outer → 1 center
        # interpolate orange (center) ↔ pink (outer)
        rr = int(PINK[0] * (1 - ratio) + ORANGE[0] * ratio)
        gg = int(PINK[1] * (1 - ratio) + ORANGE[1] * ratio)
        bb = int(PINK[2] * (1 - ratio) + ORANGE[2] * ratio)
        draw.ellipse(
            (center - r, center - r, center + r, center + r),
            fill=(rr, gg, bb, 255),
        )
    return img


def _draw_camera_glyph(img: Image.Image) -> None:
    """วาดสัญลักษณ์กล้องตรงกลาง (ใช้ shape primitives ไม่ต้องพึ่ง font)"""
    size = img.size[0]
    draw = ImageDraw.Draw(img)
    center = size // 2

    # camera body — rounded rect
    body_w = int(size * 0.50)
    body_h = int(size * 0.35)
    body_left = center - body_w // 2
    body_top = center - body_h // 2 + int(size * 0.04)
    body_right = body_left + body_w
    body_bottom = body_top + body_h
    radius = int(size * 0.05)
    draw.rounded_rectangle(
        (body_left, body_top, body_right, body_bottom),
        radius=radius, fill=WHITE,
    )

    # viewfinder bump (top)
    bump_w = int(body_w * 0.32)
    bump_h = int(size * 0.06)
    bump_left = center - bump_w // 2
    bump_top = body_top - bump_h + 2
    draw.rounded_rectangle(
        (bump_left, bump_top, bump_left + bump_w, body_top + 6),
        radius=int(size * 0.025), fill=WHITE,
    )

    # lens ring — outer circle
    lens_r_outer = int(size * 0.13)
    draw.ellipse(
        (center - lens_r_outer, body_top + body_h // 2 - lens_r_outer + 4,
         center + lens_r_outer, body_top + body_h // 2 + lens_r_outer + 4),
        fill=PINK,
    )
    # lens inner — orange dot
    lens_r_inner = int(size * 0.08)
    draw.ellipse(
        (center - lens_r_inner, body_top + body_h // 2 - lens_r_inner + 4,
         center + lens_r_inner, body_top + body_h // 2 + lens_r_inner + 4),
        fill=ORANGE,
    )
    # flash dot (top-right corner)
    flash_r = int(size * 0.02)
    fx = body_right - int(body_w * 0.13)
    fy = body_top + int(body_h * 0.18)
    draw.ellipse(
        (fx - flash_r, fy - flash_r, fx + flash_r, fy + flash_r),
        fill=ORANGE,
    )


def _add_sparkle(img: Image.Image) -> None:
    """เพิ่ม sparkle จุดขาวเล็กๆ ขอบบนซ้าย"""
    size = img.size[0]
    draw = ImageDraw.Draw(img)
    # one big sparkle
    sx, sy = int(size * 0.22), int(size * 0.22)
    for offset, alpha in [(2, 255), (4, 180), (7, 120)]:
        draw.ellipse(
            (sx - offset, sy - offset, sx + offset, sy + offset),
            fill=(255, 255, 255, alpha),
        )


def make_logo(size: int = 256) -> Image.Image:
    img = _gradient_circle(size)
    # subtle inner glow — slight blur of bright circle
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse(
        (int(size * 0.18), int(size * 0.18), int(size * 0.55), int(size * 0.55)),
        fill=(255, 240, 220, 60),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size // 18))
    img = Image.alpha_composite(img, glow)

    _draw_camera_glyph(img)
    _add_sparkle(img)
    return img


def main() -> int:
    print("Generating logo + icon...")
    # Big logo PNG
    logo = make_logo(256)
    png_path = ASSETS_DIR / "happy_logo.png"
    logo.save(png_path, "PNG")
    print(f"  ✓ {png_path}  ({png_path.stat().st_size // 1024} KB)")

    # Small variant for header
    small = make_logo(80)
    small_png = ASSETS_DIR / "happy_logo_small.png"
    small.save(small_png, "PNG")
    print(f"  ✓ {small_png}  ({small_png.stat().st_size // 1024} KB)")

    # Multi-resolution ICO
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_path = ASSETS_DIR / "happy_icon.ico"
    # PIL Image.save with .ico needs base image + sizes list
    logo.save(ico_path, format="ICO", sizes=ico_sizes)
    print(f"  ✓ {ico_path}  ({ico_path.stat().st_size // 1024} KB) — {len(ico_sizes)} resolutions")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
