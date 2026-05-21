"""
build_catalog.py
สแกนโฟลเดอร์ Photo ของทั้ง Conquest + Crystal → ดึงชื่องาน → บันทึก JSON catalog
รัน: python scripts/build_catalog.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Windows console เป็น cp1252 — ดัน utf-8 เพื่อให้ print emoji/ไทยได้
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ===== CONFIG =====
SOURCES = [
    {
        "ship": "Conquest",
        "path": Path(r"D:\+++++Nick folder+++++\ENA\Conquest\Photo EE"),
    },
    {
        "ship": "Crystal",
        "path": Path(r"D:\+++++Nick folder+++++\ENA\Crystal\Photo"),
    },
]
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "job_catalog.json"

# จับ "N." หรือ "N. " ที่นำหน้า (เลขลำดับ — มีหรือไม่มี space ก็ได้)
SEQ_PREFIX = re.compile(r"^\d+\.\s*")

# จับ DD-MM-YY หรือ DD-MM-YYYY หลังเลขลำดับ (ถ้ามี)
DATE_PREFIX = re.compile(
    r"""^
    (\d{2})-(\d{2})-(\d{2,4})  # date DD-MM-YY[YY]
    \s+
    """,
    re.VERBOSE,
)


def extract_job_name(folder_name: str) -> tuple[str, str | None]:
    """ตัดเลขลำดับ + วันที่นำหน้าออก คืนชื่องานสะอาด + วันที่ (ถ้ามี)"""
    s = folder_name
    # ตัดเลขลำดับ "1." / "38. " ก่อน
    s = SEQ_PREFIX.sub("", s)
    # ลองจับวันที่
    match = DATE_PREFIX.match(s)
    if match:
        dd, mm, yy = match.groups()
        if len(yy) == 2:
            yy = "20" + yy
        date_str = f"{yy}-{mm}-{dd}"
        job_name = s[match.end():].strip()
        return job_name, date_str
    return s.strip(), None


def normalize(name: str) -> str:
    """normalize ชื่อสำหรับ deduplicate — lowercase, ลบ extra space, normalize 'No.'"""
    s = name.lower().strip()
    s = re.sub(r"\s+", " ", s)               # multiple spaces → 1
    s = re.sub(r"no\.\s*(\d)", r"no.\1", s)  # "No. 1" / "No.1" → "no.1"
    s = re.sub(r"no\s+(\d)", r"no.\1", s)    # "No 1" → "no.1"
    s = s.rstrip(".")                        # ลบ . ท้าย
    return s


def extract_keywords(name: str) -> list[str]:
    """ดึง keyword หลักจากชื่องาน — ใช้สำหรับ AI matching"""
    tokens = re.findall(r"[a-zA-Z]+", name.lower())
    stop = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "at"}
    return [t for t in tokens if t not in stop and len(t) > 1]


def is_month_folder(name: str) -> bool:
    """เช็คว่าเป็นโฟลเดอร์ระดับเดือนมั้ย เช่น 'May 26', 'DEC 2025', 'JAN 2026'"""
    return bool(re.match(r"^[A-Za-z]{3,9}\s+\d{2,4}$", name.strip()))


def scan_source(source: dict, jobs: dict) -> int:
    """สแกน 1 source — return จำนวน job dirs ที่เจอ"""
    ship = source["ship"]
    root = source["path"]
    if not root.exists():
        print(f"⚠️  ไม่พบ {ship}: {root}")
        return 0

    print(f"\n📂 {ship}: {root}")
    count = 0

    # iterate ทุก level — โฟลเดอร์ลูกที่ไม่ใช่ "month folder" จะถือว่าเป็น job dir
    # ส่วน month folder จะ dive เข้าไปอีก 1 level
    for sub in root.iterdir():
        if not sub.is_dir():
            continue

        if is_month_folder(sub.name):
            # dive into month folder
            for job_dir in sub.iterdir():
                if job_dir.is_dir():
                    register_job(job_dir.name, ship, sub.name, jobs)
                    count += 1
        else:
            # โฟลเดอร์ทั่วไป (เช่น "Battery", "งาน") = job dir ตรงๆ
            register_job(sub.name, ship, None, jobs)
            count += 1

    print(f"   เจอ {count} job folders")
    return count


def register_job(raw_name: str, ship: str, month: str | None, jobs: dict) -> None:
    """ลงทะเบียน 1 job dir ลงใน jobs catalog"""
    clean_name, date_str = extract_job_name(raw_name)
    if not clean_name:
        return

    norm = normalize(clean_name)
    entry = jobs[norm]

    # เลือกชื่อที่ "อ่านสวยที่สุด" — คือสั้นที่สุดและไม่ใช่ตัวพิมพ์เล็กทั้งหมด
    candidate_score = (len(clean_name), -sum(1 for c in clean_name if c.isupper()))
    if not entry["name"] or candidate_score < entry["_score"]:
        entry["name"] = clean_name
        entry["_score"] = candidate_score

    entry["occurrences"] += 1
    entry["ships"].add(ship)
    if month:
        entry["months_seen"].add(f"{ship}/{month}")
    if date_str:
        entry["dates_seen"].add(date_str)
    entry["variants"].add(raw_name)


def main() -> int:
    jobs: dict[str, dict] = defaultdict(
        lambda: {
            "name": "",
            "_score": (10**9, 0),
            "occurrences": 0,
            "ships": set(),
            "months_seen": set(),
            "dates_seen": set(),
            "variants": set(),
        }
    )

    total = 0
    for source in SOURCES:
        total += scan_source(source, jobs)

    # แปลง set → sorted list, ลบ field ภายใน
    catalog_jobs = []
    for norm, info in sorted(jobs.items()):
        catalog_jobs.append(
            {
                "name": info["name"],
                "normalized": norm,
                "occurrences": info["occurrences"],
                "ships": sorted(info["ships"]),
                "months_seen": sorted(info["months_seen"]),
                "dates_seen": sorted(info["dates_seen"]),
                "variants": sorted(info["variants"]),
                "keywords": extract_keywords(info["name"]),
            }
        )

    catalog = {
        "version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": [{"ship": s["ship"], "path": str(s["path"])} for s in SOURCES],
        "total_job_dirs_scanned": total,
        "unique_job_count": len(catalog_jobs),
        "jobs": catalog_jobs,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"\n✅ บันทึก catalog ที่ {OUTPUT_PATH}")
    print(f"   สแกนรวม {total} job folders")
    print(f"   ชื่องาน unique {len(catalog_jobs)} ชื่อ")
    print("\n📋 Top 15 งานที่เจอบ่อยที่สุด:")
    top = sorted(catalog_jobs, key=lambda x: -x["occurrences"])[:15]
    for i, job in enumerate(top, 1):
        ships = ",".join(job["ships"])
        print(f"   {i:2d}. ({job['occurrences']}x) [{ships}] {job['name']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
