"""
build_installer.py — Build pipeline for installer.exe

Steps:
  1. Build main app (HappyPhotoOrganizer.exe) — assumes already built in ../dist/
  2. Zip the entire HappyPhotoOrganizer/ folder → dist/HappyPhotoOrganizer.zip (payload)
  3. PyInstaller installer.py with payload bundled

Run from project root:
  python installer/build_installer.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
APP_DIST = ROOT / "dist" / "HappyPhotoOrganizer"
PAYLOAD_ZIP = ROOT / "dist" / "HappyPhotoOrganizer.zip"


def zip_payload() -> None:
    if not APP_DIST.exists():
        print(f"[!] Main app not built at {APP_DIST}")
        print("    Run: pyinstaller HappyPhotoOrganizer.spec --noconfirm")
        sys.exit(1)

    if PAYLOAD_ZIP.exists():
        PAYLOAD_ZIP.unlink()

    print(f"[*] Zipping {APP_DIST}  →  {PAYLOAD_ZIP}")
    with zipfile.ZipFile(PAYLOAD_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in APP_DIST.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(APP_DIST.parent)
                zf.write(path, arcname)
    size_mb = PAYLOAD_ZIP.stat().st_size / (1024 * 1024)
    print(f"    Payload size: {size_mb:.1f} MB")


def build_installer() -> None:
    spec = ROOT / "installer" / "HappyPhotoOrganizerSetup.spec"
    print(f"[*] Building installer with {spec.name}")
    result = subprocess.run(
        ["pyinstaller", str(spec), "--noconfirm", "--clean"],
        cwd=str(ROOT),
        capture_output=True, text=True,
    )
    print(result.stdout[-2000:])
    if result.returncode != 0:
        print(result.stderr[-2000:])
        sys.exit(result.returncode)
    print("[*] Installer built — dist/HappyPhotoOrganizerSetup.exe")


def main() -> int:
    zip_payload()
    build_installer()
    out = ROOT / "dist" / "HappyPhotoOrganizerSetup.exe"
    if out.exists():
        size_mb = out.stat().st_size / (1024 * 1024)
        print(f"\n✓ DONE — {out}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
