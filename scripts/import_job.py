"""
import_job.py — file a job folder that came off the phone (JobShot), no UI.

The app has a drop zone for this, and it is the way to do it. This script is
the path that still works when the app will not start, when Nick is on a PC
without the installed build, or when something needs checking without a GUI in
the way.

    python scripts/import_job.py <job folder> [more folders ...] [--dest <folder>]

With no --dest, the destination remembered for the ship named in `job.json` is
used (see Settings / the app's destination picker). Add --remember to store the
--dest you passed against that ship for next time.

A folder with no `job.json` is a transfer still in flight: it is reported and
skipped, never processed and never deleted. Originals are never touched.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core import jobshot                                    # noqa: E402
from core.catalog import JobCatalog                          # noqa: E402


def _resolve_dest(folders: list[Path], dest: str | None) -> tuple[Path | None, str]:
    if dest:
        return Path(dest), ""
    for folder in folders:
        manifest, _err = jobshot.read_manifest(folder)
        if manifest is None:
            continue
        ship = str(manifest.get("ship", "") or "")
        remembered = jobshot.get_dest_root(ship)
        if remembered is not None:
            return remembered, ship
        if ship:
            return None, ship
    return None, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folders", nargs="+", help="job folder(s) pushed by JobShot")
    ap.add_argument("--dest", help="destination photo folder (default: the one "
                                   "remembered for this ship)")
    ap.add_argument("--remember", action="store_true",
                    help="remember --dest for this ship")
    args = ap.parse_args(argv)

    folders = [Path(f) for f in args.folders]
    missing = [f for f in folders if not f.is_dir()]
    if missing:
        for f in missing:
            print(f"  not a folder: {f}")
        return 2

    # Accept a parent folder too — copying the whole JobShot directory off the
    # phone is the normal way this arrives. Same rule as the app's drop zone.
    jobs, in_flight, rest = jobshot.split_arrivals(folders)
    for folder in in_flight:
        print(f"  {folder.name}: not ready yet (no job.json) — skipped")
    for folder in rest:
        print(f"  {folder.name}: no job.json in it or below it — skipped")
    if not jobs:
        print("Nothing to file.")
        return 0 if in_flight else 2

    dest, ship = _resolve_dest(jobs, args.dest)
    if dest is None:
        print("No destination. Pass --dest <folder>"
              + (f" (nothing remembered for {ship!r})" if ship else ""))
        return 2
    if args.remember and ship:
        jobshot.remember_dest_root(ship, dest)
        print(f"  remembered {dest} for {ship}")

    print(f"Filing {len(jobs)} job(s) into {dest}")
    catalog = JobCatalog()
    results = jobshot.import_batch(
        jobs, dest, catalog=catalog,
        progress_cb=lambda done, total, msg: print(f"  [{done}/{total}] {msg}"),
    )

    failed = 0
    for folder, r in zip(jobs, results):
        if not r.ok:
            failed += 1
            print(f"\n  {folder.name}: NOT FILED — {r.error}")
            continue
        where = "merged into" if r.merged_into_existing else "filed as"
        print(f"\n  {folder.name}: {where} {r.final_folder.name}")
        print(f"    {r.photos_filed} photo(s), manifest {r.manifest_name}")
        if r.date_shifted:
            print(f"    note: work date {r.work_date:%Y-%m-%d} — the archive's "
                  f"day rule filed it on {r.folder_date:%d-%m-%y}")
        if r.grouped_with:
            print(f"    grouped with: {', '.join(r.grouped_with)}")
        for w in r.warnings:
            print(f"    warning: {w}")

    print(f"\n{len(results) - failed}/{len(results)} filed"
          + (f", {failed} not filed" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
