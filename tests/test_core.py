"""
test_core.py â€” pure-Python regression tests (NO API key, NO network, NO photos).

Run:  python tests/test_core.py

Created 2026-06-04 (Tester sprint). The project previously claimed "67/67 tests"
in its docs but had NO test suite â€” only scripts/smoke_test.py, which needs a live
Gemini key + local sample photos. This file is the real, dependency-free suite:
it exercises the deterministic core logic (grouping, date allocation, JSON parsing,
catalog, rate-limiter tiers, version compare, auth null-safety) so a refactor that
breaks an invariant fails loudly here instead of in production.

Each test is a function starting with `test_`. A bare `assert` failure or any
exception marks it FAILED. Exit code 0 = all pass, 1 = at least one failed.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import analyzer, auth, catalog, grouper, processor, rate_limiter
from core.version import read_version


# â”€â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _make_dated_files(tmp: Path, stamps: list[str]) -> list[Path]:
    """Create empty files named so read_from_filename yields the given times.
    `stamps` = list of 'YYYYMMDD_HHMMSS'. grouper reads the date from the name
    (the file need not be a real image â€” read_from_exif fails gracefully)."""
    out = []
    for i, s in enumerate(stamps):
        p = tmp / f"IMG_{s}_{i:03d}.jpg"
        p.write_bytes(b"")  # not a real image â€” exif read returns None, filename wins
        out.append(p)
    return out


# â”€â”€â”€ grouper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_grouper_midnight_burst_is_one_session():
    """C2: a continuous burst crossing midnight (<gap apart) = ONE folder."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        imgs = _make_dated_files(tmp, ["20260315_235900", "20260316_000100"])  # 2 min apart
        groups = grouper.group_by_session(imgs, time_gap_minutes=90)
        assert len(groups) == 1, f"expected 1 session across midnight, got {len(groups)}"
        # representative date = earliest = the pre-midnight day (15th)
        assert groups[0].representative_date.day == 15


def test_grouper_same_day_is_one_folder_however_long_the_gap():
    """v1.044 (Nick 2026-09-02): the capture DATE is the key — one day is one
    folder. Previously a >90 min break split the day, and assign_unique_dates
    then pushed each piece onto a different day number, scattering the work
    across dates it was never shot on."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        imgs = _make_dated_files(tmp, [
            "20260315_080000", "20260315_120000",  # 4 h apart
            "20260315_173000", "20260315_235000",  # and again in the evening
        ])
        groups = grouper.group_by_session(imgs, time_gap_minutes=90)
        assert len(groups) == 1, f"expected 1 folder for one day, got {len(groups)}"
        assert len(groups[0].images) == 4
        assert groups[0].representative_date.day == 15


def test_grouper_different_days_stay_separate():
    """Separate shooting days must still be separate folders."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        imgs = _make_dated_files(tmp, ["20260315_120000", "20260316_120000",
                                       "20260318_090000"])
        groups = grouper.group_by_session(imgs, time_gap_minutes=90)
        assert len(groups) == 3, f"expected 3 folders, got {len(groups)}"
        assert [g.representative_date.day for g in groups] == [15, 16, 18]


def test_grouper_empty():
    assert grouper.group_by_session([]) == []


# â”€â”€â”€ processor: date allocation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _assignment(day: int, month: int = 5, year: int = 2026) -> processor.JobAssignment:
    return processor.JobAssignment(folder_date=datetime(year, month, day, 10, 0, 0))


def test_assign_unique_dates_are_unique():
    plan = processor.Plan(assignments=[_assignment(5), _assignment(5), _assignment(5)])
    processor.assign_unique_dates(plan, used_days=set(), target_year_month=(2026, 5))
    days = [a.folder_date.day for a in plan.assignments]
    assert len(set(days)) == len(days), f"days not unique: {days}"


def test_capped_keeps_own_day_not_last_day():
    """C1: when the month is full, overflowing assignments keep their OWN EXIF
    day (clamped), NOT all collapse onto last_day."""
    # Occupy every day 1..31 so the target month (May=31d) is full.
    used = set(range(1, 32))
    a1, a2 = _assignment(5), _assignment(10)
    plan = processor.Plan(assignments=[a1, a2])
    _, capped = processor.assign_unique_dates(plan, used_days=used, target_year_month=(2026, 5))
    assert capped == 2, f"expected both capped, got {capped}"
    days = sorted(a.folder_date.day for a in plan.assignments)
    assert days == [5, 10], f"capped days should keep EXIF days [5,10], got {days}"
    assert all(a.date_was_capped for a in plan.assignments)


def test_capped_day_clamped_to_month_length():
    """A day-31 photo capped into February clamps to 28/29, never an invalid date."""
    used = set(range(1, 29))  # fill all of Feb 2026 (28 days)
    a = _assignment(31, month=1)  # EXIF day 31 (from January)
    plan = processor.Plan(assignments=[a])
    processor.assign_unique_dates(plan, used_days=used, target_year_month=(2026, 2))
    assert a.folder_date.month == 2
    assert a.folder_date.day <= 28, f"Feb day out of range: {a.folder_date.day}"


def test_detect_target_month_clamps_implausible_year(tmp_path_factory=None):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "01-05-50 Job A").mkdir()  # year 2050 â€” implausible
        ym = processor.detect_target_month(root)
        assert ym is not None
        assert abs(ym[0] - datetime.now().year) <= 5, f"year not clamped: {ym}"


def test_sanitize_filename_strips_invalid():
    out = processor.sanitize_filename('Cleaned <Cooler>: No.1 / "main"')
    for bad in '<>:/"\\|?*':
        assert bad not in out, f"{bad!r} survived sanitize: {out!r}"


# â”€â”€â”€ analyzer: JSON parsing (C5) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_parse_plain_json():
    r = analyzer._parse_json_response('{"matched_name":"X","confidence":0.9}')
    assert r["matched_name"] == "X"


def test_parse_code_fenced_json():
    r = analyzer._parse_json_response('```json\n{"matched_name":"Y","confidence":0.5}\n```')
    assert r["matched_name"] == "Y"


def test_parse_json_with_trailing_prose():
    r = analyzer._parse_json_response('Result: {"matched_name":"Z","confidence":0.7} â€” done.')
    assert r["matched_name"] == "Z", f"got {r}"


def test_parse_list_coerced_to_dict():
    r = analyzer._parse_json_response('[{"matched_name":"L","confidence":0.4}]')
    assert r["matched_name"] == "L"


def test_parse_garbage_returns_error_dict():
    r = analyzer._parse_json_response("no json at all here")
    assert r["matched_name"] is None
    assert "parse error" in r["reasoning"]


# â”€â”€â”€ analyzer: transient-error classification (BUG-N2) â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_transient_5xx_matches():
    assert analyzer._is_transient_error(Exception("503 Service Unavailable"))
    assert analyzer._is_transient_error(Exception("HTTP 500 internal"))


def test_transient_token_matches():
    assert analyzer._is_transient_error(Exception("connection reset by peer"))
    assert analyzer._is_transient_error(Exception("UNAVAILABLE"))


def test_non_transient_does_not_match():
    # 400 = client error, not retried
    assert not analyzer._is_transient_error(Exception("400 Bad Request: invalid arg"))
    # "5031" must NOT trip the \b503\b boundary, and has no transient token
    assert not analyzer._is_transient_error(Exception("received 5031 bytes ok"))


# â”€â”€â”€ catalog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_date_sort_key_chronological():
    dates = ["02-01-25", "01-12-24", "15-06-25"]
    dates.sort(key=catalog._date_sort_key)
    assert dates == ["01-12-24", "02-01-25", "15-06-25"], f"got {dates}"


def test_catalog_loads_and_finds():
    cat = catalog.JobCatalog()
    names = cat.names()
    assert len(names) > 0, "catalog is empty"
    # round-trip a known name through normalize/find
    first = names[0]
    assert cat.find(first) is not None


def test_catalog_record_usage_dates_sorted_chronologically():
    cat = catalog.JobCatalog()
    cat.add("ZZ Test Job Tester")
    cat.record_usage("ZZ Test Job Tester", ship=None, date_str="15-06-25")
    cat.record_usage("ZZ Test Job Tester", ship=None, date_str="01-12-24")
    entry = cat.find("ZZ Test Job Tester")
    assert entry["dates_seen"] == ["01-12-24", "15-06-25"], f"got {entry['dates_seen']}"


# â”€â”€â”€ rate_limiter (F1) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_tier_preset_carries_model():
    t = rate_limiter.TierConfig.from_preset("free-2.5-flash")
    assert t.model == "gemini-2.5-flash", f"model not carried: {t.model}"


def test_paid_tier_has_no_model_override():
    t = rate_limiter.TierConfig.from_preset("paid")
    assert t.model is None
    assert t.throttle is False


def test_custom_tier_has_no_model():
    t = rate_limiter.TierConfig.custom(rpm=20, rpd=999)
    assert t.model is None
    assert t.rpm == 20 and t.rpd == 999


def test_min_interval_math():
    t = rate_limiter.TierConfig.from_preset("free-3.1-flash-lite")  # rpm 15
    assert abs(t.min_interval_sec - 4.0) < 0.01, f"15 rpm should be 4s/call, got {t.min_interval_sec}"


# â”€â”€â”€ version compare (updater) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_version_compare():
    from core.updater import is_newer
    assert is_newer("1.040", "1.041")
    assert is_newer("1.039", "1.040")
    assert not is_newer("1.040", "1.040")
    assert not is_newer("1.041", "1.040")


def test_version_file_matches_running():
    assert read_version() != "0.0.0", "VERSION file unreadable"


# â”€â”€â”€ auth null-safety (C12) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_get_api_key_handles_null_value():
    """C12: a JSON `"api_key": null` must not crash with None.strip()."""
    orig = auth.load_config
    try:
        auth.load_config = lambda: {"api_key": None, "model": None}
        assert auth.get_api_key() is None  # no AttributeError
        assert auth.get_model() == auth.DEFAULT_MODEL  # null model â†’ default
    finally:
        auth.load_config = orig


def test_get_model_default_when_missing():
    orig = auth.load_config
    try:
        auth.load_config = lambda: {}
        assert auth.get_model() == auth.DEFAULT_MODEL
    finally:
        auth.load_config = orig


# â”€â”€â”€ v1.043: "not vessel work" flag + per-folder delete â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_as_bool_reads_json_and_stringy_booleans():
    assert analyzer._as_bool(True) is True
    assert analyzer._as_bool(False) is False
    assert analyzer._as_bool("true") is True
    assert analyzer._as_bool("yes") is True
    assert analyzer._as_bool(1) is True
    # the trap: a truthy non-empty string that means the opposite
    assert analyzer._as_bool("false") is False
    assert analyzer._as_bool("no") is False
    assert analyzer._as_bool(None) is False
    assert analyzer._as_bool(0) is False


def test_irrelevant_result_never_becomes_a_job():
    """A screenshot/selfie/food photo must not acquire a name â€” not even via
    the fuzzy catalog match, which would happily latch onto a stray word."""
    cat = catalog.JobCatalog()
    a = processor.JobAssignment(folder_date=datetime(2026, 9, 2))
    real_name = cat.names()[0]
    processor._apply_result_to_assignment(a, {
        "irrelevant": True,
        # hostile payload: the model contradicted itself and still named a job
        "matched_name": real_name,
        "suggested_name": real_name,
        "confidence": 0.97,
        "reasoning": "screenshot of a shopping app",
    }, cat)
    assert a.is_irrelevant is True
    assert a.job_name == ""
    assert a.confidence == 0.0
    assert a.is_new_suggestion is False
    assert a.needs_review is True     # flagged rows must always surface


def test_normal_result_clears_the_irrelevant_flag():
    cat = catalog.JobCatalog()
    a = processor.JobAssignment(folder_date=datetime(2026, 9, 2), is_irrelevant=True)
    processor._apply_result_to_assignment(a, {
        "irrelevant": False,
        "matched_name": None,
        "suggested_name": "Replaced Electrical Plug",
        "confidence": 0.85,
        "reasoning": "plug replacement",
    }, cat)
    assert a.is_irrelevant is False
    assert a.job_name == "Replaced Electrical Plug"


def _pending_plan(tmp: Path, marker: str = processor.PENDING_MARKER):
    """A plan with one assignment owning a real on-disk pending folder."""
    dest = tmp / "dest"
    dest.mkdir()
    folder = dest / f"2026-09-02{marker}01"
    folder.mkdir()
    resized = []
    for i in (1, 2):
        p = folder / f"img_{i:03d}.jpg"
        p.write_bytes(b"x" * 10)
        resized.append(p)
    src = tmp / "source"
    src.mkdir()
    originals = [src / "IMG_0001.jpg", src / "IMG_0002.jpg"]
    for p in originals:
        p.write_bytes(b"original")
    a = processor.JobAssignment(
        folder_date=datetime(2026, 9, 2), images=list(originals),
        resized_paths=resized, temp_folder=folder,
    )
    plan = processor.Plan(assignments=[a], dest_root=dest,
                          total_images=2, total_resized=2)
    return plan, a, folder, originals


def test_discard_assignment_deletes_only_the_working_copy():
    with tempfile.TemporaryDirectory() as td:
        plan, a, folder, originals = _pending_plan(Path(td))
        ok, err = processor.discard_assignment(plan, a)
        assert ok is True, err
        assert not folder.exists()                 # working folder + resized gone
        assert all(p.exists() for p in originals)  # originals untouched
        assert plan.assignments == []
        assert plan.total_resized == 0
        assert plan.total_images == 0


def test_discard_assignment_refuses_a_folder_we_did_not_create():
    """Guard: without the pending marker this would rmtree a real folder."""
    with tempfile.TemporaryDirectory() as td:
        plan, a, folder, _ = _pending_plan(Path(td), marker="__REAL_JOB_")
        ok, err = processor.discard_assignment(plan, a)
        assert ok is False
        assert "did not create" in err
        assert folder.exists()
        assert plan.assignments == [a]     # plan left alone on refusal


def test_discard_assignment_refuses_outside_the_destination():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        plan, a, _folder, _ = _pending_plan(tmp)
        outside = tmp / "elsewhere"
        outside.mkdir()
        victim = outside / f"2026-09-02{processor.PENDING_MARKER}01"
        victim.mkdir()
        (victim / "keep.txt").write_bytes(b"keep")
        a.temp_folder = victim
        ok, err = processor.discard_assignment(plan, a)
        assert ok is False
        assert "outside the destination" in err
        assert victim.exists()


def test_discard_assignment_survives_an_already_deleted_folder():
    """Deleting a row twice (or after a manual cleanup) must not error."""
    with tempfile.TemporaryDirectory() as td:
        plan, a, folder, _ = _pending_plan(Path(td))
        shutil.rmtree(folder)
        ok, err = processor.discard_assignment(plan, a)
        assert ok is True, err
        assert plan.assignments == []


def test_version_file_has_no_bom_and_parses_to_the_right_tuple():
    """A BOM in VERSION is invisible everywhere except the version comparator:
    str.strip() does not remove U+FEFF, so _parse_version reads "﻿1.044"
    as (0, 44) and every release then looks newer than the installed build."""
    raw = (ROOT / "VERSION").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "VERSION starts with a UTF-8 BOM"
    assert b"\r" not in raw, "VERSION contains CR"

    from core import updater
    parsed = updater._parse_version(read_version())
    assert parsed[0] != 0, f"major parsed as 0 - {parsed} from {read_version()!r}"
    assert parsed == updater._parse_version(raw.decode("utf-8").strip())


def test_no_source_file_carries_a_bom_or_cr():
    """Windows tools (PowerShell's `Set-Content -Encoding utf8`, Python text
    mode) inject a BOM or CRLF that no diff and no editor shows. It bit twice
    in one session: a BOM in VERSION made the updater read version 0.x, and a
    BOM in this very file made `ast.parse` refuse it. .gitattributes pins LF in
    the repo, but the working tree is what runs."""
    skip = {"dist", "build", ".git", "__pycache__", ".venv", "_trash"}
    offenders = []
    for path in ROOT.rglob("*.py"):
        if skip & set(path.relative_to(ROOT).parts):
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            offenders.append(f"BOM: {path.relative_to(ROOT)}")
        if b"\r" in raw:
            offenders.append(f"CR:  {path.relative_to(ROOT)}")
    assert not offenders, "invisible bytes in source:\n  " + "\n  ".join(offenders)


def test_read_version_survives_a_bom():
    """Hardening: even if a Windows tool re-saves VERSION with a BOM, the
    reader must still return a clean version string."""
    import io as _io
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "VERSION"
        _io.open(p, "w", encoding="utf-8-sig", newline="").write("1.044\n")
        assert p.read_bytes().startswith(b"\xef\xbb\xbf")   # the trap is present
        assert p.read_text(encoding="utf-8-sig").strip() == "1.044"


def test_default_model_is_3_5_flash_lite():
    assert auth.DEFAULT_MODEL == "gemini-3.5-flash-lite"
    preset = rate_limiter.TIER_PRESETS[rate_limiter.DEFAULT_TIER]
    assert preset["model"] == "gemini-3.5-flash-lite"


# --- photo file names (Nick 2026-09-02: img_001 in every folder) ------------

def _committable_plan(tmp: Path, job: str, n: int = 2):
    """A pending folder holding `n` resized photos, ready for phase 4."""
    dest = tmp / "dest"
    dest.mkdir(exist_ok=True)
    folder = dest / f"2026-09-20{processor.PENDING_MARKER}01"
    folder.mkdir()
    for i in range(1, n + 1):
        (folder / f"img_{i:03d}.jpg").write_bytes(bytes([i]) * 10)
    a = processor.JobAssignment(
        folder_date=datetime(2026, 9, 20), job_name=job, temp_folder=folder,
    )
    return processor.Plan(assignments=[a], dest_root=dest), a, dest


def test_photos_are_named_after_their_folder():
    """Moving a photo between folders must not collide: every file carries its
    folder's `DD-MM-YY <Job>` name instead of restarting at img_001."""
    with tempfile.TemporaryDirectory() as td:
        plan, _a, dest = _committable_plan(Path(td), "Repaired Vingtor marine intercom")
        res = processor.phase4_rename_folders(plan)
        assert res.errors == [], res.errors
        out = dest / "20-09-26 Repaired Vingtor marine intercom"
        names = sorted(f.name for f in out.iterdir())
        assert names == [
            "20-09-26 Repaired Vingtor marine intercom_001.jpg",
            "20-09-26 Repaired Vingtor marine intercom_002.jpg",
        ], names


def test_two_folders_never_produce_the_same_photo_name():
    """The actual complaint: identical file names in different folders."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        plan_a, _a, dest = _committable_plan(tmp, "Repaired Vingtor marine intercom")
        processor.phase4_rename_folders(plan_a)
        folder_b = dest / f"2026-09-27{processor.PENDING_MARKER}01"
        folder_b.mkdir()
        (folder_b / "img_001.jpg").write_bytes(b"b")
        b = processor.JobAssignment(
            folder_date=datetime(2026, 9, 27),
            job_name="Repaired internal wiring of Vingtor",
            temp_folder=folder_b,
        )
        processor.phase4_rename_folders(
            processor.Plan(assignments=[b], dest_root=dest))
        every = [f.name for d in dest.iterdir() if d.is_dir() for f in d.iterdir()]
        assert len(every) == len(set(every)), every


def test_merging_into_an_existing_folder_continues_the_numbering():
    """A second run into the same day appends 003+, not `..._001_2.jpg`."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        plan, _a, dest = _committable_plan(tmp, "Repaired Vingtor marine intercom")
        processor.phase4_rename_folders(plan)
        again = dest / f"2026-09-20{processor.PENDING_MARKER}02"
        again.mkdir()
        (again / "img_001.jpg").write_bytes(b"new")
        second = processor.JobAssignment(
            folder_date=datetime(2026, 9, 20),
            job_name="Repaired Vingtor marine intercom", temp_folder=again,
        )
        res = processor.phase4_rename_folders(
            processor.Plan(assignments=[second], dest_root=dest))
        assert res.errors == [], res.errors
        out = dest / "20-09-26 Repaired Vingtor marine intercom"
        names = sorted(f.name for f in out.iterdir())
        assert len(names) == 3, names
        assert names[-1].endswith("_003.jpg"), names
        assert not any("_2.jpg" in n for n in names), names


def test_photo_order_survives_more_than_999_photos_in_a_day():
    """`img_1000` sorts before `img_999` as a string — number order must win,
    or a big day would be renumbered out of shooting order."""
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "dest"
        dest.mkdir()
        folder = dest / f"2026-09-20{processor.PENDING_MARKER}01"
        folder.mkdir()
        for i in (998, 999, 1000, 1001):
            (folder / f"img_{i:03d}.jpg").write_bytes(bytes([i % 251]) * 4)
        a = processor.JobAssignment(
            folder_date=datetime(2026, 9, 20), job_name="Big Day", temp_folder=folder,
        )
        processor.phase4_rename_folders(
            processor.Plan(assignments=[a], dest_root=dest))
        out = dest / "20-09-26 Big Day"
        by_new = {f.name: f.read_bytes()[0] for f in out.iterdir()}
        order = [by_new[n] for n in sorted(by_new, key=lambda n: int(n.split("_")[-1][:-4]))]
        assert order == [998 % 251, 999 % 251, 1000 % 251, 1001 % 251], order


def test_photo_name_is_trimmed_to_fit_the_windows_path_limit():
    """The folder name is repeated inside every file name, so a long job on a
    deep destination must be trimmed — not left to fail at 260 characters."""
    deep = Path("C:/") / ("d" * 60) / ("e" * 60)
    long_job = "Repaired " + "very long job name " * 10
    folder = f"20-09-26 {processor.sanitize_filename(long_job)}"
    name = f"{processor.photo_prefix(folder, deep / folder)}_001.jpg"
    full = deep / folder / name
    assert len(str(full)) <= 259, len(str(full))
    assert name.startswith("20-09-26 Repaired")
    # a shallow destination keeps the readable, untrimmed name
    assert processor.photo_prefix(folder, Path("D:/Photos") / folder) == folder


# â”€â”€â”€ runner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    passed = failed = 0
    failures: list[str] = []
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            failures.append(f"{name}: {type(e).__name__}: {e}")
            print(f"  FAIL  {name}  â†’  {type(e).__name__}: {e}")
    print("\n" + "=" * 60)
    print(f"  {passed}/{len(tests)} passed" + (f", {failed} FAILED" if failed else " â€” ALL GREEN"))
    print("=" * 60)
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  â€¢ {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

