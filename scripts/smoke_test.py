"""
smoke_test.py — ทดสอบ core modules ครบทุกตัว
รัน: python scripts/smoke_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# เพิ่ม project root ลง path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import auth, catalog, exif_reader, resizer, grouper, analyzer


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def test_auth() -> bool:
    section("1. AUTH")
    key = auth.get_api_key()
    if not key:
        print("✗ ไม่เจอ API key")
        return False
    print(f"✓ key: {key[:8]}...{key[-4:]}")
    print(f"✓ model: {auth.get_model()}")

    client, err = auth.create_client()
    if err:
        print(f"✗ {err}")
        return False
    print("✓ สร้าง client ได้")

    ok, msg = auth.test_connection(client)
    print(f"{'✓' if ok else '✗'} {msg}")
    if ok:
        models = auth.list_vision_models(client)
        print(f"✓ Vision models: {len(models)}")
        for m in models[:5]:
            print(f"   - {m}")
    return ok


def test_catalog() -> bool:
    section("2. CATALOG")
    cat = catalog.JobCatalog()
    print(f"✓ load catalog ได้ {len(cat.names())} ชื่องาน")
    print("ตัวอย่าง 5 ชื่อแรก:")
    for n in cat.names()[:5]:
        print(f"   - {n}")

    found = cat.find("cleaned cooler provision no.1")
    if found:
        print(f"✓ find() เจอ: {found['name']} (occurrences={found['occurrences']})")
    else:
        print("✗ find() ไม่เจอ")
        return False

    return True


def test_exif() -> bool:
    section("3. EXIF READER")
    # หารูปใน Photo EE มาทดสอบ
    sample_root = Path(r"D:\+++++Nick folder+++++\ENA\Conquest\Photo EE\May 26\01-05-26 Cleaned Cooler Main AC No. 1")
    if not sample_root.exists():
        print(f"✗ ไม่เจอ sample folder: {sample_root}")
        return False
    images = list(sample_root.glob("*.jpg"))[:3]
    for img in images:
        dt, src = exif_reader.get_capture_date(img)
        print(f"✓ {img.name} → {dt.isoformat()} (source: {src})")
    return bool(images)


def test_resizer() -> bool:
    section("4. RESIZER")
    sample_root = Path(r"D:\+++++Nick folder+++++\ENA\Conquest\Photo EE\Apr 26\Cleaned Cooler Main AC No. 1")
    if not sample_root.exists():
        print(f"✗ ไม่เจอ sample folder")
        return False
    src = next(sample_root.glob("*.jpg"), None)
    if not src:
        print("✗ ไม่เจอรูปใน sample folder")
        return False

    dst = ROOT / "data" / "_test_resized.jpg"
    ok, info = resizer.resize_to_target(src, dst)
    if not ok:
        print(f"✗ {info}")
        return False
    print(f"✓ src: {src.name} ({info['original_size_kb']:.1f} KB)")
    print(f"✓ dst: {info['final_size_kb']:.1f} KB @ Q{info['quality']} (dim={info['max_dim_used']}, attempts={info['attempts']})")
    if "warning" in info:
        print(f"  ⚠ {info['warning']}")
    dst.unlink(missing_ok=True)
    return True


def test_grouper() -> bool:
    section("5. GROUPER")
    sample_root = Path(r"D:\+++++Nick folder+++++\ENA\Conquest\Photo EE\Apr 26")
    if not sample_root.exists():
        print(f"✗ ไม่เจอ sample folder")
        return False
    images = grouper.collect_images(sample_root, recursive=True)[:30]
    if not images:
        print("✗ ไม่เจอรูป")
        return False
    print(f"รวมรูป {len(images)} ใบ → group...")
    groups = grouper.group_by_session(images)
    print(f"✓ ได้ {len(groups)} sessions")
    for i, g in enumerate(groups[:5], 1):
        print(f"   {i}. {g.start_date.strftime('%Y-%m-%d %H:%M')} → {len(g)} รูป")
    return True


def test_analyzer() -> bool:
    section("6. ANALYZER (Gemini Vision)")
    sample_root = Path(r"D:\+++++Nick folder+++++\ENA\Conquest\Photo EE\May 26\01-05-26 Cleaned Cooler Main AC No. 1")
    if not sample_root.exists():
        print(f"✗ ไม่เจอ sample folder")
        return False
    img = next(sample_root.glob("*.jpg"), None)
    if not img:
        print("✗ ไม่เจอรูป")
        return False

    cat = catalog.JobCatalog()
    names = cat.names()[:30]  # จำกัด 30 เพื่อให้ prompt ไม่ยาวเกินไป
    print(f"ส่งรูป {img.name} ไป Gemini พร้อม {len(names)} ชื่องาน...")
    result = analyzer.analyze_image(img, names)
    print(f"✓ matched_name: {result.get('matched_name')}")
    print(f"✓ suggested_name: {result.get('suggested_name')}")
    print(f"✓ confidence: {result.get('confidence'):.2f}")
    print(f"✓ reasoning: {result.get('reasoning')[:200]}")
    return True


def main() -> int:
    results = []
    for name, fn in [
        ("auth", test_auth),
        ("catalog", test_catalog),
        ("exif", test_exif),
        ("resizer", test_resizer),
        ("grouper", test_grouper),
        ("analyzer", test_analyzer),
    ]:
        try:
            ok = fn()
        except Exception as e:
            print(f"✗ {name}: EXCEPTION → {e}")
            ok = False
        results.append((name, ok))

    section("SUMMARY")
    for name, ok in results:
        print(f"  {'✓' if ok else '✗'} {name}")
    failed = [n for n, ok in results if not ok]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
