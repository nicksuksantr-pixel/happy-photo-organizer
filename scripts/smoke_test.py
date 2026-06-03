"""
smoke_test.py — LIVE integration smoke test (real Gemini call).

Run:  python scripts/smoke_test.py

Unlike tests/test_core.py (pure logic, no key/network), this script exercises the
REAL pipeline end-to-end including a live Gemini Vision call, so it needs:
  • a configured API key (~/.happy-photo-organizer/auth.json), and
  • sample photos.

Sample photos are resolved in this order (Tester 2026-06-04 — the old hard-coded
absolute D-drive sample paths broke when that drive was unmounted):
  1. $env:HAPPY_TEST_PHOTOS  (a folder of .jpg/.png/.heic)
  2. <project>/tests/_assets/ (if it exists)
  3. a SYNTHETIC image generated on the fly (so the AI round-trip is still
     testable without any of Nick's real photos — it just won't match a job).

Set HAPPY_SKIP_AI=1 to skip the live Gemini call (auth + local pipeline only).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import auth, catalog, exif_reader, resizer, grouper, analyzer
from core.image_io import collect_images


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _resolve_sample_photos() -> tuple[list[Path], bool]:
    """Return (image_paths, is_synthetic). Falls back to a generated image."""
    # 1) env var
    env = os.environ.get("HAPPY_TEST_PHOTOS", "").strip()
    if env and Path(env).is_dir():
        imgs = collect_images(Path(env), recursive=True)[:5]
        if imgs:
            print(f"  using sample photos from HAPPY_TEST_PHOTOS: {env} ({len(imgs)} found)")
            return imgs, False
    # 2) project tests/_assets
    assets = ROOT / "tests" / "_assets"
    if assets.is_dir():
        imgs = collect_images(assets, recursive=True)[:5]
        if imgs:
            print(f"  using sample photos from tests/_assets ({len(imgs)} found)")
            return imgs, True
    # 3) synthetic — generate a simple labelled image
    print("  no real sample photos found → generating a synthetic test image")
    from PIL import Image, ImageDraw
    tmp = Path(tempfile.gettempdir()) / "happy_smoke_sample.jpg"
    img = Image.new("RGB", (1024, 768), (40, 70, 120))
    d = ImageDraw.Draw(img)
    d.rectangle([200, 200, 800, 560], fill=(180, 180, 180))
    d.text((230, 360), "SMOKE TEST IMAGE - mechanical part", fill=(20, 20, 20))
    img.save(tmp, "JPEG", quality=85)
    return [tmp], True


def test_auth() -> bool:
    section("1. AUTH")
    key = auth.get_api_key()
    if not key:
        print("X no API key configured (~/.happy-photo-organizer/auth.json)")
        return False
    # E1 (Tester 2026-06-04): don't print the key's tail — show presence + a
    # short non-identifying prefix only.
    print(f"+ key present (starts {key[:4]}…, length {len(key)})")
    print(f"+ model: {auth.get_model()}")

    client, err = auth.create_client()
    if err:
        print(f"X {err}")
        return False
    print("+ client created")

    ok, msg = auth.test_connection(client)
    print(f"{'+' if ok else 'X'} {msg}")
    if ok:
        models = auth.list_vision_models(client)
        print(f"+ vision models: {len(models)}")
        for m in models[:5]:
            print(f"   - {m}")
    return ok


def test_catalog() -> bool:
    section("2. CATALOG")
    cat = catalog.JobCatalog()
    names = cat.names()
    print(f"+ loaded {len(names)} job names")
    for n in names[:5]:
        print(f"   - {n}")
    if not names:
        print("X catalog empty")
        return False
    # find round-trips on a real name
    found = cat.find(names[0])
    print(f"{'+' if found else 'X'} find('{names[0]}') → {'hit' if found else 'miss'}")
    return found is not None


def test_exif(samples: list[Path]) -> bool:
    section("3. EXIF READER")
    for img in samples[:3]:
        dt, src = exif_reader.get_capture_date(img)
        print(f"+ {img.name} → {dt.isoformat()} (source: {src})")
    return bool(samples)


def test_resizer(samples: list[Path]) -> bool:
    section("4. RESIZER")
    src = samples[0]
    dst = Path(tempfile.gettempdir()) / "_happy_smoke_resized.jpg"
    ok, info = resizer.resize_to_target(src, dst)
    if not ok:
        print(f"X {info}")
        return False
    print(f"+ {src.name} ({info['original_size_kb']:.1f} KB) → "
          f"{info['final_size_kb']:.1f} KB @ Q{info['quality']} "
          f"(dim={info['max_dim_used']}, attempts={info['attempts']})")
    if "warning" in info:
        print(f"  ! {info['warning']}")
    dst.unlink(missing_ok=True)
    return True


def test_grouper(samples: list[Path]) -> bool:
    section("5. GROUPER")
    groups = grouper.group_by_session(samples)
    print(f"+ {len(samples)} image(s) → {len(groups)} session(s)")
    for i, g in enumerate(groups[:5], 1):
        print(f"   {i}. {g.start_date.strftime('%Y-%m-%d %H:%M')} → {len(g)} photo(s)")
    return len(groups) >= 1


def test_analyzer(samples: list[Path]) -> bool:
    section("6. ANALYZER (live Gemini Vision)")
    if os.environ.get("HAPPY_SKIP_AI", "").strip() in ("1", "true", "yes"):
        print("  (skipped via HAPPY_SKIP_AI)")
        return True
    cat = catalog.JobCatalog()
    names = cat.names()[:30]  # cap prompt size
    img = samples[0]
    print(f"  sending {img.name} + {len(names)} job names to Gemini…")
    result = analyzer.analyze_image(img, names)
    reasoning = (result.get("reasoning") or "")
    print(f"+ matched_name : {result.get('matched_name')}")
    print(f"+ suggested    : {result.get('suggested_name')}")
    print(f"+ confidence   : {result.get('confidence'):.2f}")
    print(f"+ reasoning    : {reasoning[:160]}")
    # Round-trip is healthy if we got a dict with the schema keys and NO hard
    # error / quota message. (A synthetic image legitimately won't match a job,
    # so matched_name=None is fine — we're testing connectivity + parsing.)
    bad = reasoning.lower().startswith(("error:", "quota exceeded", "api key", "could not"))
    if bad:
        print(f"X AI call did not succeed: {reasoning[:160]}")
        return False
    if not all(k in result for k in ("matched_name", "suggested_name", "confidence")):
        print("X result missing schema keys")
        return False
    print("+ AI round-trip OK (key + model + JSON parse verified)")
    return True


def main() -> int:
    samples, synthetic = _resolve_sample_photos()
    if synthetic:
        print("  NOTE: using synthetic/sample image — AI match result is not meaningful, "
              "only connectivity is verified.")

    results = [
        ("auth", lambda: test_auth()),
        ("catalog", lambda: test_catalog()),
        ("exif", lambda: test_exif(samples)),
        ("resizer", lambda: test_resizer(samples)),
        ("grouper", lambda: test_grouper(samples)),
        ("analyzer", lambda: test_analyzer(samples)),
    ]
    summary = []
    for name, fn in results:
        try:
            ok = fn()
        except Exception as e:
            print(f"X {name}: EXCEPTION → {type(e).__name__}: {e}")
            ok = False
        summary.append((name, ok))

    section("SUMMARY")
    for name, ok in summary:
        print(f"  {'+' if ok else 'X'} {name}")
    failed = [n for n, ok in summary if not ok]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
