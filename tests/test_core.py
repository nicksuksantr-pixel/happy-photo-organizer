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

import json
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
from core import jobshot_index as _jobshot_index

# Never the real one: filing a job writes a receipt, and a test run must not
# leave receipts in Nick's config directory (the job-catalog lesson, v1.047).
_jobshot_index.INDEX_PATH = (
    Path(tempfile.gettempdir()) / "hpo_test_jobshot_filed.json")

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


def test_a_day_repeats_only_once_the_month_is_full():
    """Nick's rule, stated again on 2026-09-25 and relayed through two other
    apps: *a day may only be reused once the month is FULL — fill the month
    before repeating a day.* It was already the behaviour; this pins it, because
    a rule nobody tests is a rule waiting to be quietly optimised away.

    EMR takes every report's date from the folder name HPO chooses, so this
    decides what the whole archive is filed under.
    """
    from datetime import datetime as _dt

    # 29 of September's 30 days spoken for: the 30th must be used, not a repeat
    occupied = set(range(1, 30))
    assert processor._find_free_day_earliest(24, 30, occupied) == 30

    # every day taken — only now may a day repeat, and it keeps the job's own
    assert processor._find_free_day_earliest(24, 30, set(range(1, 31))) is None

    # and end to end: four jobs on one real day fan out over free days
    plan = processor.Plan(assignments=[
        processor.JobAssignment(folder_date=_dt(2026, 9, 24), job_name=f"Job {i}")
        for i in range(4)
    ])
    processor.assign_unique_dates(plan, used_days={24}, target_year_month=(2026, 9))
    days = sorted(a.folder_date.day for a in plan.assignments)
    assert days == [1, 2, 3, 4], days
    assert not any(a.date_was_capped for a in plan.assignments)


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


def test_no_record_carries_an_invisible_control_character():
    r"""A patch script lost its doubled backslashes writing a Windows path, so
    `\25` reached Python as an OCTAL escape and put byte 0x15 into a markdown
    file where "25" belonged (2026-09-26, and EMR hit the identical bug within
    the hour). It renders as nothing, it reads as a typo, and no diff shows it.

    Sibling of the BOM/CR check above, for the files that carry the records
    rather than the code. CR is allowed here: three files under memory/ are
    mirrors written by the PowerShell sync and are not ours to normalise.
    """
    skip = {"dist", "build", ".git", "__pycache__", ".venv", "_trash"}
    allowed = {9, 10, 13}                       # tab, newline, carriage return
    newline = 10
    offenders = []
    for pattern in ("*.md", "*.json", "*.spec"):
        for path in ROOT.rglob(pattern):
            if skip & set(path.relative_to(ROOT).parts):
                continue
            raw = path.read_bytes()
            for i, byte in enumerate(raw):
                if byte < 32 and byte not in allowed:
                    line = raw.count(newline, 0, i) + 1
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{line} byte {hex(byte)}")
                    break
    sep = chr(10) + "  "
    assert not offenders, "control characters in records:" + sep + sep.join(offenders)


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


# --- JobShot arrivals (phone -> HPO, R&D Director brief 2026-09-22) ---------
#
# The contract test for the arrival shape. Written before the receiver exists:
# a hand-made folder is the whole specification, so this is testable with no
# phone and no network.

def _have_pillow() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        print("     (skipped - Pillow not installed)")
        return False


def _noisy_jpeg(path: Path, size=(1600, 1200)) -> None:
    """A real photo-sized JPEG. Noise compresses badly on purpose - a flat
    image would already be under the 10 KB floor and prove nothing.

    frombytes(os.urandom(...)) rather than a Python loop over two million
    pixels: the loop version made this suite take minutes, and a suite nobody
    waits for is a suite nobody runs."""
    import os
    from PIL import Image
    w, h = size
    img = Image.frombytes("RGB", size, os.urandom(w * h * 3))
    img.save(path, "JPEG", quality=95)


def _arrival(tmp: Path, *, photos: int = 2, job="DG3 Turbo Inspection",
             work_date="2026-09-22", write_manifest: bool = True,
             job_id="20260922-094312-ab12cd", ship="ENA CRYSTAL",
             author="Nick", created_at="2026-09-22T09:43:12+07:00",
             plain: bool = False) -> Path:
    """One job in the shape JobShot pushes: originals + job.json written LAST.

    `plain=True` is v1 as of 2026-09-22 (photos[] is a list of file names);
    the default keeps the older object shape, which must still be read."""
    folder = tmp / "incoming" / job_id
    folder.mkdir(parents=True)
    entries = []
    for n in range(1, photos + 1):
        name = f"{n:04d}.jpg"
        _noisy_jpeg(folder / name)
        entries.append(name if plain else
                       {"file": name, "tag": "P" if n == 1 else "A",
                        "taken_at": f"2026-09-22T09:5{n}:03+07:00"})
    if write_manifest:
        manifest = {
            "jobshot": 1, "job_id": job_id, "created_at": created_at,
            "work_date": work_date, "ship": ship, "job_name": job,
            "from_catalog": True, "author": author, "device": "pixel9-nick",
            "photos": entries,
        }
        with (folder / "job.json").open("w", encoding="utf-8", newline="") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    return folder


def test_jobshot_arrival_is_filed_end_to_end():
    """THE contract test: an arrived folder lands as `DD-MM-YY <Job Name>`,
    resized into the band, renamed, with the manifest carried along."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        arrival = _arrival(tmp)
        dest = tmp / "dest"
        res = jobshot.import_job(arrival, dest)
        assert res.ok, f"{res.error} / {res.warnings}"

        out = dest / "22-09-26 DG3 Turbo Inspection"
        assert res.final_folder == out, res.final_folder
        assert out.is_dir(), sorted(p.name for p in dest.iterdir())

        photos = sorted(f for f in out.iterdir() if f.suffix == ".jpg")
        assert [f.name for f in photos] == [
            "22-09-26 DG3 Turbo Inspection_001.jpg",
            "22-09-26 DG3 Turbo Inspection_002.jpg",
        ], [f.name for f in photos]
        for f in photos:
            kb = f.stat().st_size / 1024
            assert 10 <= kb <= 25, f"{f.name} is {kb:.1f} KB, outside the band"

        # originals are not consumed - the phone's copy is the backup
        assert (arrival / "0001.jpg").is_file()


def test_jobshot_manifest_follows_the_photo_rename():
    """The silent-loss case the Director flagged: the commit renames every
    photo, so a tag pointing at `0001.jpg` would be orphaned."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        res = jobshot.import_job(_arrival(tmp), tmp / "dest")
        assert res.ok, res.error
        out = res.final_folder

        manifest = json.loads((out / "job.json").read_text(encoding="utf-8"))
        names = [e["file"] for e in manifest["photos"]]
        assert names == [
            "22-09-26 DG3 Turbo Inspection_001.jpg",
            "22-09-26 DG3 Turbo Inspection_002.jpg",
        ], names
        # every tag still points at a photo that is really there
        for entry in manifest["photos"]:
            assert (out / entry["file"]).is_file(), entry
        assert [e["tag"] for e in manifest["photos"]] == ["P", "A"]
        # and the job's own identity survived the trip
        assert manifest["job_name"] == "DG3 Turbo Inspection"
        assert manifest["work_date"] == "2026-09-22"


def test_jobshot_manifest_is_not_renamed_as_if_it_were_a_photo():
    """`rename_photos_for_folder` renames every file it is given. A manifest
    turned into `<job>_003.json` would destroy the marker itself."""
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td) / "pending"
        folder.mkdir()
        (folder / "img_001.jpg").write_bytes(b"x" * 10)
        (folder / "job.json").write_text("{}", encoding="utf-8")
        problems, renames = processor.rename_photos_for_folder(
            folder, Path(td) / "22-09-26 Job", "22-09-26 Job")
        assert problems == [], problems
        assert (folder / "job.json").is_file()
        assert renames == {"img_001.jpg": "22-09-26 Job_001.jpg"}, renames


def test_jobshot_folder_without_a_manifest_is_still_arriving():
    """job.json lands LAST. No manifest = a transfer in flight: do not touch."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        arrival = _arrival(tmp, write_manifest=False)
        dest = tmp / "dest"
        assert jobshot.is_complete(arrival) is False
        res = jobshot.import_job(arrival, dest)
        assert res.ok is False
        assert "flight" in res.error, res.error
        assert not dest.exists() or list(dest.iterdir()) == []
        assert (arrival / "0001.jpg").is_file()    # never deleted


def test_jobshot_obeys_the_archive_day_rule_and_records_the_shift():
    """Nick 2026-09-22: the unique-day rule wins over the phone's work_date.
    The date may therefore move - but work_date stays in the manifest and the
    move is written down, so it is adjusted, never silently."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        (dest / "22-09-26 Bow Thruster Overhaul").mkdir(parents=True)  # day 22 taken
        res = jobshot.import_job(_arrival(tmp), dest)
        assert res.ok, res.error
        assert res.date_shifted is True
        assert res.folder_date.day == 1, res.folder_date     # earliest free day
        assert res.final_folder.name == "01-09-26 DG3 Turbo Inspection"

        manifest = json.loads((res.final_folder / "job.json").read_text(encoding="utf-8"))
        assert manifest["work_date"] == "2026-09-22"          # truth untouched
        assert manifest["filed"]["date_shifted"] is True
        assert manifest["filed"]["folder_date"] == "01-09-26"


def test_jobshot_second_job_merging_in_keeps_the_first_manifest():
    """Two jobs can land in one folder (the merge is deliberate). The second
    manifest must not overwrite the first - that would erase a job's tags."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        first = jobshot.import_job(_arrival(tmp), dest)
        assert first.ok, first.error
        shutil.rmtree(tmp / "incoming")
        second = jobshot.import_job(_arrival(tmp), dest)   # same job, same day
        assert second.ok, second.error
        assert second.merged_into_existing is True
        assert second.manifest_name != "job.json", second.manifest_name
        out = first.final_folder
        assert (out / "job.json").is_file()
        assert (out / second.manifest_name).is_file()
        # 4 photos now, numbering continued rather than collided
        photos = sorted(f.name for f in out.iterdir() if f.suffix == ".jpg")
        assert len(photos) == 4 and photos[-1].endswith("_004.jpg"), photos
        # the second job's manifest points at the numbers it actually got
        manifest = json.loads((out / second.manifest_name).read_text(encoding="utf-8"))
        assert [e["file"] for e in manifest["photos"]] == photos[2:], manifest["photos"]


def test_jobshot_rejects_a_manifest_it_does_not_understand():
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td) / "incoming"
        folder.mkdir()
        for payload, expect in (
            ('{"jobshot": 2, "job_name": "x", "photos": [{"file": "a.jpg"}]}', "version"),
            ('{"jobshot": 1, "job_name": "", "photos": [{"file": "a.jpg"}]}', "job_name"),
            ('{"jobshot": 1, "job_name": "x", "photos": []}', "no photos"),
            ('not json at all', "not valid JSON"),
        ):
            (folder / "job.json").write_text(payload, encoding="utf-8")
            data, err = jobshot.read_manifest(folder)
            assert data is None and expect in err, (payload, err)


def test_jobshot_remembers_the_photo_folder_per_vessel():
    """Step 3: Nick picks the engine-room folder once per vessel, not per run."""
    from core import auth, jobshot
    store: dict = {}
    real_load, real_update = auth.load_config, auth.update_config
    try:
        auth.load_config = lambda: dict(store)

        def _update(updates):
            store.update(updates)
            return True

        auth.update_config = _update
        assert jobshot.get_dest_root("ENA CRYSTAL") is None
        assert jobshot.remember_dest_root("ENA CRYSTAL", Path("D:/Photos/ENA")) is True
        assert jobshot.get_dest_root("ena crystal") == Path("D:/Photos/ENA")  # case-free
        assert jobshot.get_dest_root("OTHER SHIP") is None
        assert jobshot.remember_dest_root("", Path("D:/x")) is False
    finally:
        auth.load_config, auth.update_config = real_load, real_update


# --- one real job = one folder (Nick 2026-09-22, arrival-time grouping) -----


def test_jobshot_finds_its_own_job_even_after_the_day_rule_moved_it():
    """The case the first cut got wrong. Engineer A's job is filed on day 1
    because day 22 was taken; engineer B sends the same job. Matching on the
    folder name alone would miss (B expects 22-09-26), the day rule would give
    B yet another day, and one real job would own two folders on two dates."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        (dest / "22-09-26 Bow Thruster Overhaul").mkdir(parents=True)   # day 22 gone

        first = jobshot.import_job(_arrival(tmp), dest)
        assert first.ok, first.error
        assert first.final_folder.name == "01-09-26 DG3 Turbo Inspection"
        assert first.date_shifted is True

        shutil.rmtree(tmp / "incoming")
        second = jobshot.import_job(_arrival(tmp), dest)
        assert second.ok, second.error
        assert second.merged_into_existing is True
        assert second.final_folder == first.final_folder, second.final_folder

        job_folders = sorted(f.name for f in dest.iterdir() if f.is_dir())
        assert job_folders == ["01-09-26 DG3 Turbo Inspection",
                               "22-09-26 Bow Thruster Overhaul"], job_folders
        photos = sorted(f.name for f in first.final_folder.iterdir()
                        if f.suffix == ".jpg")
        assert len(photos) == 4 and photos[-1].endswith("_004.jpg"), photos


def test_jobshot_different_job_on_the_same_day_keeps_its_own_folder():
    """Grouping is by the job's identity, not by the day — two different jobs
    on one day must not be swept into one folder."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        first = jobshot.import_job(_arrival(tmp), dest)
        assert first.ok, first.error
        shutil.rmtree(tmp / "incoming")
        other = jobshot.import_job(
            _arrival(tmp, job="Bow Thruster Overhaul"), dest)
        assert other.ok, other.error
        assert other.merged_into_existing is False
        assert other.final_folder != first.final_folder
        assert sorted(f.name for f in dest.iterdir() if f.is_dir()) == [
            "01-09-26 Bow Thruster Overhaul",
            "22-09-26 DG3 Turbo Inspection",
        ], sorted(f.name for f in dest.iterdir())


def test_jobshot_follows_a_folder_that_was_renamed_after_filing():
    """Nick renames folders by hand. The job still lives in that folder, so a
    later arrival belongs there too — not in a fresh one under the old name."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        first = jobshot.import_job(_arrival(tmp), dest)
        assert first.ok, first.error
        renamed = dest / "22-09-26 DG3 Turbo Inspection and gasket renewal"
        first.final_folder.rename(renamed)

        shutil.rmtree(tmp / "incoming")
        second = jobshot.import_job(_arrival(tmp), dest)
        assert second.ok, second.error
        assert second.final_folder == renamed, second.final_folder
        assert any("renamed after filing" in w for w in second.warnings), second.warnings
        assert sorted(f.name for f in dest.iterdir() if f.is_dir()) == [renamed.name]
        assert len([f for f in renamed.iterdir() if f.suffix == ".jpg"]) == 4


def test_jobshot_identity_ignores_the_ship_field():
    """dest_root is per vessel, so two jobs reaching one destination are on the
    same ship. Keeping `ship` in the key would let a vessel name typed
    differently on two phones split one real job into two folders."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        first = jobshot.import_job(_arrival(tmp), dest)          # ENA CRYSTAL
        assert first.ok, first.error
        second = jobshot.import_job(
            _arrival(tmp, job_id="20260922-101500-ff99aa", ship="Ena Crystal AHTS"),
            dest)
        assert second.ok, second.error
        assert second.final_folder == first.final_folder, second.final_folder
        assert len([f for f in dest.iterdir() if f.is_dir()]) == 1


def test_jobshot_reads_a_manifest_with_plain_file_names():
    """v1 as of 2026-09-22: photos[] is a list of names, not objects (the
    Before/After tags were cut — EMR owns that). Both shapes must file, and
    each manifest is written back in the shape it arrived in."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        res = jobshot.import_job(_arrival(tmp, plain=True), tmp / "dest")
        assert res.ok, f"{res.error} / {res.warnings}"
        manifest = json.loads(
            (res.final_folder / "job.json").read_text(encoding="utf-8"))
        assert manifest["photos"] == [
            "22-09-26 DG3 Turbo Inspection_001.jpg",
            "22-09-26 DG3 Turbo Inspection_002.jpg",
        ], manifest["photos"]
        for name in manifest["photos"]:
            assert (res.final_folder / name).is_file(), name


# --- the batch case: two arrivals of one job in a single send ---------------


def test_jobshot_batch_groups_two_arrivals_of_the_same_job():
    """Nick sends several jobs in one sitting and two engineers can pair to one
    PC, so two arrivals with the same job_name and work_date is a normal day.
    Filed separately they would take two days and two folders for one job."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        a = _arrival(tmp, job_id="20260922-094312-ab12cd",
                     created_at="2026-09-22T09:43:12+07:00")
        b = _arrival(tmp, job_id="20260922-101500-ff99aa", author="Somchai",
                     created_at="2026-09-22T10:15:00+07:00")

        results = jobshot.import_batch([a, b], dest)
        assert [r.ok for r in results] == [True, True], [r.error for r in results]

        folders = [f for f in dest.iterdir() if f.is_dir()]
        assert len(folders) == 1, sorted(f.name for f in folders)
        assert folders[0].name == "22-09-26 DG3 Turbo Inspection"
        assert results[0].final_folder == results[1].final_folder

        photos = sorted(f.name for f in folders[0].iterdir() if f.suffix == ".jpg")
        assert len(photos) == 4 and photos[-1].endswith("_004.jpg"), photos

        # each sender's own manifest survives, and says who it was filed with
        assert results[0].manifest_name == "job.json"
        assert results[1].manifest_name == "job-20260922-101500-ff99aa.json"
        assert results[0].grouped_with == ["20260922-101500-ff99aa"]
        assert results[1].grouped_with == ["20260922-094312-ab12cd"]


def test_jobshot_batch_photo_names_do_not_collide_between_arrivals():
    """Both phones send 0001.jpg. A single shared old->new map would have one
    arrival's entry overwrite the other's, and a manifest would point at
    someone else's photo."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        results = jobshot.import_batch([
            _arrival(tmp, job_id="20260922-094312-ab12cd",
                     created_at="2026-09-22T09:43:12+07:00"),
            _arrival(tmp, job_id="20260922-101500-ff99aa",
                     created_at="2026-09-22T10:15:00+07:00"),
        ], dest)
        assert all(r.ok for r in results), [r.error for r in results]

        first, second = results
        assert set(first.photo_renames) == {"0001.jpg", "0002.jpg"}
        assert set(second.photo_renames) == {"0001.jpg", "0002.jpg"}
        # the same sent name maps to different filed photos
        assert first.photo_renames["0001.jpg"] != second.photo_renames["0001.jpg"]
        filed = set(first.photo_renames.values()) | set(second.photo_renames.values())
        assert len(filed) == 4, filed
        for name in filed:
            assert (first.final_folder / name).is_file(), name


def test_jobshot_batch_keeps_different_jobs_in_their_own_folders():
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        results = jobshot.import_batch([
            _arrival(tmp, job_id="20260922-094312-ab12cd",
                     created_at="2026-09-22T09:43:12+07:00"),
            _arrival(tmp, job_id="20260922-101500-ff99aa",
                     job="Bow Thruster Overhaul",
                     created_at="2026-09-22T13:20:00+07:00"),
        ], dest)
        assert all(r.ok for r in results), [r.error for r in results]
        assert results[0].final_folder != results[1].final_folder
        # both were done on the 22nd and only one folder can hold that day: the
        # job created first on the phone keeps it, the later one is shifted by
        # the archive rule exactly as any other job would be
        assert sorted(f.name for f in dest.iterdir() if f.is_dir()) == [
            "01-09-26 Bow Thruster Overhaul",
            "22-09-26 DG3 Turbo Inspection",
        ], sorted(f.name for f in dest.iterdir())
        assert results[0].date_shifted is False
        assert results[1].date_shifted is True
        assert results[0].grouped_with == [] and results[1].grouped_with == []


def test_jobshot_batch_reports_a_bad_arrival_without_dropping_the_good_one():
    """One folder still in flight must not cost the rest of the send."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        good = _arrival(tmp, job_id="20260922-094312-ab12cd")
        in_flight = _arrival(tmp, job_id="20260922-999999-zzzzzz",
                             write_manifest=False)

        results = jobshot.import_batch([in_flight, good], dest)
        assert len(results) == 2
        assert results[0].ok is False and "flight" in results[0].error
        assert results[1].ok is True, results[1].error
        assert results[1].final_folder.is_dir()
        # the unfinished transfer is left exactly where it was
        assert (in_flight / "0001.jpg").is_file()


# --- the way in: what the drop zone and the "From phone" button do ---------


def test_jobshot_version_gate_rejects_every_wrong_shape():
    """A gate tested only with 1 and 2 proves nothing about true, [1] or 1.0.
    `True == 1` and `1.0 == 1` in Python, so a bare `!=` would pass a manifest
    written as `"jobshot": true` — precisely the sender bug the gate exists to
    catch (found by EMR in its own gate, 2026-09-22)."""
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td)
        for payload in ("true", "false", "[1]", '"1"', "null", "1.0", "2", "0"):
            (folder / "job.json").write_text(
                '{"jobshot": %s, "job_name": "x", "photos": ["a.jpg"]}' % payload,
                encoding="utf-8")
            data, err = jobshot.read_manifest(folder)
            assert data is None, f'"jobshot": {payload} was accepted'
            assert "version" in err, (payload, err)
        # and the one real version still works
        (folder / "job.json").write_text(
            '{"jobshot": 1, "job_name": "x", "photos": ["a.jpg"]}', encoding="utf-8")
        data, err = jobshot.read_manifest(folder)
        assert data is not None, err


def test_jobshot_split_arrivals_sorts_what_was_dropped():
    """A job folder, a parent holding several, a half-copied one, and an
    ordinary folder of photos all get dropped on the same zone."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        one = _arrival(tmp, job_id="job-A")

        # a parent holding two jobs, one of which is still being copied
        parent = tmp / "from phone"
        parent.mkdir()
        (parent / "job-B").mkdir()
        (parent / "job-B" / "job.json").write_text(
            '{"jobshot": 1, "job_name": "B", "photos": ["0001.jpg"]}',
            encoding="utf-8")
        (parent / "job-C-still-copying").mkdir()
        (parent / "job-C-still-copying" / "0001.jpg").write_bytes(b"partial")

        photos_folder = tmp / "card reader dump"
        photos_folder.mkdir()
        (photos_folder / "IMG_0001.jpg").write_bytes(b"x")
        loose_file = tmp / "loose.jpg"
        loose_file.write_bytes(b"x")

        jobs, in_flight, rest = jobshot.split_arrivals(
            [one, parent, photos_folder, loose_file])

        assert jobs == [one, parent / "job-B"], jobs
        assert in_flight == [parent / "job-C-still-copying"], in_flight
        # an ordinary folder of photos still belongs to the card-reader path
        assert rest == [photos_folder, loose_file], rest


def test_jobshot_an_unfinished_transfer_is_never_touched():
    """The folder Nick copied while the phone was still sending: reported as
    not ready, left exactly as it was."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        arriving = _arrival(tmp, write_manifest=False)
        before = sorted(p.name for p in arriving.iterdir())

        jobs, in_flight, rest = jobshot.split_arrivals([arriving])
        assert jobs == [] and rest == [arriving]      # no manifest anywhere below
        assert in_flight == []

        res = jobshot.import_job(arriving, tmp / "dest")
        assert res.ok is False and "flight" in res.error
        assert sorted(p.name for p in arriving.iterdir()) == before


# --- the LAN receiver: hostile zips (item 6) --------------------------------
#
# A socket that writes files to disk, on a shared vessel Wi-Fi. Every test here
# is a zip nobody should be able to send twice.


def _zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            zf.writestr(name, payload)
    return buf.getvalue()


def _job_zip(tmp: Path, *, photos: int = 2, job="DG3 Turbo Inspection",
             ship="ENA CRYSTAL", nested: bool = True, manifest: bool = True,
             extra: list[tuple[str, bytes]] | None = None) -> bytes:
    """What the phone sends: the job folder, zipped."""
    staging = tmp / f"staging-{job}-{nested}"
    staging.mkdir(parents=True, exist_ok=True)
    entries = []
    names = []
    for n in range(1, photos + 1):
        name = f"{n:04d}.jpg"
        _noisy_jpeg(staging / name, size=(800, 600))
        prefix = "20260923-094312-ab12cd/" if nested else ""
        entries.append((prefix + name, (staging / name).read_bytes()))
        names.append(name)
    if manifest:
        payload = json.dumps({
            "jobshot": 1, "job_id": "20260923-094312-ab12cd", "job_name": job,
            "ship": ship, "author": "Nick",
            "created_at": "2026-09-23T09:43:12+07:00", "work_date": "2026-09-23",
            "photos": names,
        }).encode("utf-8")
        entries.append((("20260923-094312-ab12cd/" if nested else "") + "job.json",
                        payload))
    if extra:
        entries.extend(extra)
    return _zip_bytes(entries)


def test_receiver_refuses_zip_slip():
    """The highest-severity item in the whole feature: an entry named
    `..\\..\\Windows\\...` must never be written. Names inside an archive that
    arrived over a network are attacker-controlled strings, not paths."""
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        outside = tmp / "OUTSIDE.jpg"
        outside_txt = tmp / "OUTSIDE.txt"
        quarantine = tmp / "q"
        payload = b"pwned"
        # .jpg on purpose for half of these: a name the file-type rule would
        # otherwise welcome, so the path check is what has to catch it
        for name in ("../../OUTSIDE.jpg", r"..\..\OUTSIDE.jpg",
                     "a/../../OUTSIDE.jpg", "/OUTSIDE.jpg", "C:/OUTSIDE.jpg",
                     "../../OUTSIDE.txt", r"C:\Windows\System32\OUTSIDE.txt"):
            ok, err, warnings = recv.safe_extract(
                _zip_bytes([(name, payload)]), quarantine)
            assert ok is False, f"{name} was accepted"
            assert not outside.exists(), f"{name} escaped quarantine"
            assert not outside_txt.exists(), f"{name} escaped quarantine"
            assert any("refused entry" in w for w in warnings), (name, warnings)
        # nothing at all was left lying around outside the quarantine folder
        assert sorted(p.name for p in tmp.iterdir()) == ["q"]


def test_receiver_refuses_what_a_job_is_not_made_of():
    """A job is photos and a JSON manifest. Anything else does not belong in
    the archive, whatever it claims to be."""
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        quarantine = Path(td) / "q"
        for name in ("evil.exe", "setup.bat", "notes.txt", "payload.dll",
                     "photo.jpg.lnk", "CON.jpg", "deep/a/b/c/0001.jpg",
                     "0001.jpg:ads"):
            ok, err, warnings = recv.safe_extract(
                _zip_bytes([(name, b"x")]), quarantine)
            assert ok is False, f"{name} was accepted"


def test_receiver_refuses_a_zip_bomb_and_a_truncated_upload():
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        bomb = _zip_bytes([("0001.jpg", b"\0" * (12 * 1024 * 1024))])
        ok, err, _w = recv.safe_extract(bomb, tmp / "q1")
        assert ok is False and "zip bomb" in err, err

        good = _job_zip(tmp)
        ok, err, _w = recv.safe_extract(good[: len(good) // 2], tmp / "q2")
        assert ok is False and "zip" in err.lower(), err


def test_receiver_files_a_job_that_arrived_over_the_wire():
    """End to end from bytes: unpack, validate, and file through the same
    import_batch the drop zone uses."""
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        res = recv.receive_zip(_job_zip(tmp), dest,
                               quarantine_root=tmp / "quarantine")
        assert res.ok, f"{res.error} / {res.warnings}"
        assert len(res.filed) == 1, res.filed
        filed = res.filed[0]
        assert filed["folder"] == "23-09-26 DG3 Turbo Inspection", filed
        assert filed["photos"] == 2 and filed["merged"] is False

        out = dest / filed["folder"]
        photos = sorted(f.name for f in out.iterdir() if f.suffix == ".jpg")
        assert photos == ["23-09-26 DG3 Turbo Inspection_001.jpg",
                          "23-09-26 DG3 Turbo Inspection_002.jpg"], photos
        assert (out / "job.json").is_file()

        reply = res.to_reply()
        assert reply["jobshot"] == 1 and reply["ok"] is True
        assert reply["filed"][0]["folder"] == filed["folder"]
        # quarantine is scratch space and does not survive
        assert list((tmp / "quarantine").iterdir()) == []


def test_receiver_handles_a_zip_with_the_photos_at_the_top_level():
    """JobShot may zip the folder's contents rather than the folder."""
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        res = recv.receive_zip(_job_zip(tmp, nested=False), tmp / "dest",
                               quarantine_root=tmp / "q")
        assert res.ok, f"{res.error} / {res.warnings}"
        assert res.filed[0]["folder"] == "23-09-26 DG3 Turbo Inspection"


def test_receiver_refuses_an_upload_with_no_manifest():
    """Same rule as the drop zone: no job.json, nothing is filed."""
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        res = recv.receive_zip(_job_zip(tmp, manifest=False), dest,
                               quarantine_root=tmp / "q")
        assert res.ok is False
        assert "job.json" in res.error, res.error
        assert not dest.exists() or list(dest.iterdir()) == []


def test_receiver_refuses_a_job_from_another_vessel():
    """The guard that predates the LAN work: the QR says which ship this PC
    files for, and a job from another one is not filed here."""
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        res = recv.receive_zip(_job_zip(tmp, ship="ENA BOURBON"), dest,
                               quarantine_root=tmp / "q",
                               expected_ship="ENA CRYSTAL")
        assert res.ok is False, res.filed
        assert "vessel" in res.error, res.error
        assert res.skipped and "ship" in res.skipped[0]["reason"]
        assert not dest.exists() or list(dest.iterdir()) == []

        # the same ship, spelled with different spacing/case, is still this ship
        res = recv.receive_zip(_job_zip(tmp, ship="ena  crystal"), dest,
                               quarantine_root=tmp / "q",
                               expected_ship="ENA CRYSTAL")
        assert res.ok, f"{res.error} / {res.warnings}"


def test_receiver_requires_the_paired_token():
    """No token on the PC means nothing is accepted — never 'allow when
    unset', which is how a listening socket becomes everyone's."""
    from core import auth, jobshot_receive as recv
    store: dict = {}
    real_load, real_update = auth.load_config, auth.update_config
    try:
        auth.load_config = lambda: dict(store)

        def _update(updates):
            store.update(updates)
            return True

        auth.update_config = _update

        assert recv.get_token() == ""            # never paired
        assert recv.verify_token("") is False
        assert recv.verify_token("anything") is False

        token = recv.get_token(create=True)
        assert len(token) >= 32
        assert recv.get_token(create=True) == token      # stable once minted
        assert recv.verify_token(token) is True
        # one character different, and it must really be different: a fixed
        # "0" IS the real token whenever it already ends in 0. Same bug as the
        # one fixed in the server test on 2026-09-24 — I fixed that instance
        # and did not grep for its siblings, so this one failed the next day.
        assert recv.verify_token(
            token[:-1] + ("1" if token[-1] != "1" else "2")) is False
        assert recv.verify_token("") is False

        payload = recv.qr_payload("ENA CRYSTAL", port=8765, host="192.168.1.20")
        assert payload["jobshot"] == 1 and payload["token"] == token
        assert payload["ship"] == "ENA CRYSTAL" and payload["port"] == 8765
        assert payload["host"] == "192.168.1.20"
    finally:
        auth.load_config, auth.update_config = real_load, real_update


# --- the listening socket ---------------------------------------------------
#
# Real requests over a real socket on 127.0.0.1 — a mocked handler would prove
# nothing about the part that is actually exposed.


class _Receiver:
    """Start a receiver on a free loopback port with a stubbed token store."""

    def __init__(self, tmp: Path, *, ship="ENA CRYSTAL", dest=True):
        import socket as _s
        from core import auth, jobshot_receive as recv
        from core import jobshot_server as srv

        self.tmp = tmp
        self.dest = tmp / "dest" if dest else None
        self._store = {}
        self._auth = auth
        self._real = (auth.load_config, auth.update_config)
        auth.load_config = lambda: dict(self._store)

        def _update(updates):
            self._store.update(updates)
            return True

        auth.update_config = _update
        self.token = recv.get_token(create=True)

        probe = _s.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()

        self.logs: list[str] = []
        self.results: list = []
        self.server = srv.JobShotReceiver(
            dest_root=lambda: self.dest,
            ship=lambda: ship,
            quarantine_root=tmp / "quarantine",
            on_result=self.results.append,
            on_log=self.logs.append,
            port=port, host="127.0.0.1",
        )
        ok, err = self.server.start()
        assert ok, err
        self.base = f"http://127.0.0.1:{port}"

    def close(self):
        self.server.stop()
        self._auth.load_config, self._auth.update_config = self._real

    def post(self, body: bytes, *, token=None, path=None):
        import urllib.error
        import urllib.request
        from core import jobshot_receive as recv
        req = urllib.request.Request(
            self.base + (path or recv.UPLOAD_PATH), data=body, method="POST")
        if token is not False:
            # None = use the paired token; "" = send an empty one on purpose
            req.add_header(recv.TOKEN_HEADER,
                           self.token if token is None else token)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            return e.code, (json.loads(raw) if raw else {})

    def get(self, path, *, token=None):
        import urllib.error
        import urllib.request
        from core import jobshot_receive as recv
        req = urllib.request.Request(self.base + path)
        if token is not False:
            req.add_header(recv.TOKEN_HEADER,
                           self.token if token is None else token)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            return e.code, (json.loads(raw) if raw else {})


def test_receiver_server_files_an_upload_and_replies_with_the_folder():
    """The reply is the feature: until the PC names the folder it filed, the
    phone cannot know the job is safe to let go."""
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_job_zip(tmp))
            assert status == 200, reply
            assert reply["ok"] is True, reply
            assert reply["filed"][0]["folder"] == "23-09-26 DG3 Turbo Inspection"
            assert reply["filed"][0]["photos"] == 2
            assert (rx.dest / "23-09-26 DG3 Turbo Inspection").is_dir()
            assert rx.results and rx.results[0].ok      # the UI is told
        finally:
            rx.close()


def test_receiver_server_refuses_everything_without_the_token():
    """A listening socket on a shared vessel Wi-Fi. No token, no anything."""
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            # "the same token with one character changed" — and it has to
            # actually differ: appending a fixed "0" silently produced the REAL
            # token on any run where it already ended in 0, which is one run in
            # sixteen for a hex token. It happened on 2026-09-24 and the test
            # failed for a reason that had nothing to do with the code.
            tampered = rx.token[:-1] + ("1" if rx.token[-1] != "1" else "2")
            assert tampered != rx.token
            for token in (False, "", "not-the-token", tampered):
                status, _reply = rx.post(_job_zip(tmp), token=token)
                assert status == 401, (token, status)
            status, _reply = rx.get(recv.HELLO_PATH, token=False)
            assert status == 401
            # nothing was filed by any of those attempts
            assert not rx.dest.exists() or list(rx.dest.iterdir()) == []
        finally:
            rx.close()


def test_receiver_server_serves_nothing_but_its_two_routes():
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        rx = _Receiver(Path(td))
        try:
            for path in ("/", "/index.html", "/../core/auth.py",
                         "/jobshot/v1/", "/jobshot/v1/upload/x"):
                status, _r = rx.get(path)
                assert status == 404, (path, status)
            status, _r = rx.post(b"x", path="/jobshot/v1/other")
            assert status == 404
        finally:
            rx.close()


def test_receiver_server_answers_ping_so_the_phone_can_confirm_pairing():
    """Both spellings answer: `ping` is what JobShot published, `hello` is the
    alias, and a phone built against either must be able to pair rather than
    fail in a way that looks like a network fault."""
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        rx = _Receiver(Path(td))
        try:
            for path in recv.PING_PATHS:
                status, reply = rx.get(path)
                assert status == 200, (path, reply)
                assert reply["jobshot"] == 1
                assert reply["ship"] == "ENA CRYSTAL"
                # the identifier from LAN_PROTOCOL §2, not a display name —
                # the phone may compare this string
                assert reply["app"] == "happy-photo-organizer"
                assert reply["ready"] is True
        finally:
            rx.close()


def test_receiver_server_tells_an_old_client_where_the_routes_moved():
    """The path mismatch that nearly shipped: JobShot was built against
    /jobshot/ping and /jobshot/upload, this server serves /jobshot/v1/*. The
    version prefix is the point — but the refusal should say so."""
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        rx = _Receiver(Path(td))
        try:
            status, reply = rx.get("/jobshot/ping")
            assert status == 404, status
            assert reply.get("upload") == recv.UPLOAD_PATH, reply
            assert reply.get("ping") == recv.PING_PATH, reply
            status, reply = rx.post(b"x", path="/jobshot/upload")
            assert status == 404 and reply.get("upload") == recv.UPLOAD_PATH
        finally:
            rx.close()


def test_receiver_server_says_so_when_the_pc_has_no_destination_yet():
    """Better than filing into a guess: the phone keeps the job and Nick is
    told what to fix."""
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp, dest=False)
        try:
            status, reply = rx.post(_job_zip(tmp))
            assert status == 409, (status, reply)
            assert "destination" in reply["error"], reply
        finally:
            rx.close()


def test_receiver_server_refuses_an_oversize_upload_on_the_header():
    """Refused before the body is read — claiming a huge size must not make the
    PC hold it."""
    if not _have_pillow():
        return
    import urllib.error
    import urllib.request
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        rx = _Receiver(Path(td))
        try:
            req = urllib.request.Request(
                rx.base + recv.UPLOAD_PATH, data=b"x", method="POST")
            req.add_header(recv.TOKEN_HEADER, rx.token)
            req.add_header("Content-Length", str(recv.MAX_ZIP_BYTES + 1))
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    status = r.status
            except urllib.error.HTTPError as e:
                status = e.code
            assert status == 413, status
        finally:
            rx.close()


def test_receiver_server_survives_a_hostile_upload():
    """A zip-slip attempt over the wire is answered, not crashed on, and the
    server keeps serving afterwards."""
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_zip_bytes([("../../OUTSIDE.jpg", b"pwned")]))
            assert status == 422, (status, reply)
            assert reply["ok"] is False
            assert not (tmp / "OUTSIDE.jpg").exists()
            assert not (Path(td).parent / "OUTSIDE.jpg").exists()

            # still alive and still working
            status, reply = rx.post(_job_zip(tmp))
            assert status == 200 and reply["ok"] is True, reply
        finally:
            rx.close()


# --- the receipt book: "did you already file this?" (protocol §4) -----------
#
# The reply to an upload is what makes a job safe to delete from the phone, so
# a lost reply is the single point of failure in the whole design. These are
# the tests for the answer that outlives the request.


def _receipt(rx, job_id: str):
    from core import jobshot_receive as recv
    return rx.get(recv.JOB_PATH_PREFIX + job_id)


def test_receiver_falls_back_to_a_free_port_and_the_qr_follows():
    """A QR carrying the port we wanted rather than the one we got would pair
    the phone to nothing, and the failure would look like a network fault."""
    import socket as _s

    from core import auth, jobshot_receive as recv
    from core import jobshot_server as srv

    store = {}
    real_load, real_update = auth.load_config, auth.update_config
    blocker = _s.socket()
    try:
        auth.load_config = lambda: dict(store)

        def _update(updates):
            store.update(updates)
            return True

        auth.update_config = _update

        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        taken = blocker.getsockname()[1]

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            receiver = srv.JobShotReceiver(
                dest_root=lambda: tmp / "dest", ship=lambda: "ENA CRYSTAL",
                quarantine_root=tmp / "q", port=taken, host="127.0.0.1")
            ok, err = receiver.start()
            try:
                assert ok, err
                assert receiver.port != taken, "bound the port that was in use"
                assert receiver.port > 0
                payload = recv.qr_payload("ENA CRYSTAL", port=receiver.port,
                                          host="127.0.0.1")
                assert payload["port"] == receiver.port
                # and the port it reports is really the one it is serving on
                import urllib.request
                req = urllib.request.Request(
                    f"http://127.0.0.1:{receiver.port}{recv.PING_PATH}")
                req.add_header(recv.TOKEN_HEADER, recv.get_token(create=True))
                with urllib.request.urlopen(req, timeout=10) as r:
                    assert r.status == 200
            finally:
                receiver.stop()
    finally:
        blocker.close()
        auth.load_config, auth.update_config = real_load, real_update


def test_receipt_answers_for_a_job_that_was_filed():
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_job_zip(tmp))
            assert status == 200, reply
            job_id = reply["filed"][0]["job_id"]

            status, receipt = _receipt(rx, job_id)
            assert status == 200, receipt
            assert receipt["filed"] is True
            assert receipt["folder"] == "23-09-26 DG3 Turbo Inspection"
            assert receipt["photos"] == 2
            assert receipt["filed_at"]
        finally:
            rx.close()


def test_receipt_says_no_for_a_job_this_pc_has_never_seen():
    """404 means "not filed here", so the phone keeps its copy — the safe
    direction to be wrong in."""
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        rx = _Receiver(Path(td))
        try:
            status, receipt = _receipt(rx, "20260923-999999-nothere")
            assert status == 404, receipt
            assert receipt["filed"] is False
        finally:
            rx.close()


def test_receipt_counts_a_merged_job_as_filed():
    """A second phone's copy of one job did not create the folder, but its
    photos are on disk. Answering 404 would make it re-send work already safe."""
    if not _have_pillow():
        return
    from core import jobshot_index
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            rx.post(_job_zip(tmp))
            second = _job_zip(tmp, photos=1)
            # same job name and work_date, a different sender
            import io
            import zipfile
            rebuilt = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(second)) as src, \
                    zipfile.ZipFile(rebuilt, "w") as dst:
                for info in src.infolist():
                    data = src.read(info.filename)
                    if info.filename.endswith("job.json"):
                        m = json.loads(data.decode("utf-8"))
                        m["job_id"] = "20260923-141500-second"
                        data = json.dumps(m).encode("utf-8")
                    dst.writestr(info.filename, data)
            status, reply = rx.post(rebuilt.getvalue())
            assert status == 200, reply
            assert reply["filed"][0]["merged"] is True, reply

            status, receipt = _receipt(rx, "20260923-141500-second")
            assert status == 200, receipt
            assert receipt["filed"] is True
            assert receipt["folder"] == "23-09-26 DG3 Turbo Inspection"
        finally:
            rx.close()
            jobshot_index.forget_all()


def test_receipt_survives_losing_the_index_because_the_archive_is_the_truth():
    """The index is a cache. Manifests travel with the folders, so a lost or
    corrupt receipt book still answers — which also covers a reinstall."""
    if not _have_pillow():
        return
    from core import jobshot_index
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_job_zip(tmp))
            job_id = reply["filed"][0]["job_id"]

            jobshot_index.INDEX_PATH.write_text("{ not json", encoding="utf-8")
            status, receipt = _receipt(rx, job_id)
            assert status == 200, receipt
            assert receipt["folder"] == "23-09-26 DG3 Turbo Inspection"

            jobshot_index.INDEX_PATH.unlink()
            status, receipt = _receipt(rx, job_id)
            assert status == 200, receipt
            assert receipt["photos"] == 2, receipt
        finally:
            rx.close()
            jobshot_index.forget_all()


def test_receipt_follows_a_folder_nick_renamed_and_forgets_one_he_deleted():
    if not _have_pillow():
        return
    from core import jobshot_index
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_job_zip(tmp))
            job_id = reply["filed"][0]["job_id"]
            folder = rx.dest / reply["filed"][0]["folder"]

            renamed = rx.dest / "23-09-26 DG3 Turbo Inspection and gasket"
            folder.rename(renamed)
            status, receipt = _receipt(rx, job_id)
            assert status == 200, receipt
            assert receipt["folder"] == renamed.name, receipt

            shutil.rmtree(renamed)
            status, receipt = _receipt(rx, job_id)
            assert status == 404, receipt      # gone means gone: keep your copy
            assert receipt["filed"] is False
        finally:
            rx.close()
            jobshot_index.forget_all()


def test_receipt_needs_the_token_and_refuses_a_hostile_job_id():
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        rx = _Receiver(Path(td))
        try:
            status, _r = rx.get(recv.JOB_PATH_PREFIX + "anything", token=False)
            assert status == 401

            for job_id in ("../../../auth.json", "..%2F..%2Fauth.json",
                           "a" * 400, "", "x/y"):
                status, receipt = rx.get(recv.JOB_PATH_PREFIX + job_id)
                assert status == 404, (job_id, status)
                assert receipt.get("filed") is False, (job_id, receipt)
        finally:
            rx.close()


def test_receipt_is_written_by_the_manual_routes_too():
    """A job imported by cable this morning must answer just as well as one
    that arrived over Wi-Fi — the phone cannot tell how it got there."""
    if not _have_pillow():
        return
    from core import jobshot, jobshot_index
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        try:
            res = jobshot.import_job(_arrival(tmp, job_id="cable-import-1"),
                                     tmp / "dest")
            assert res.ok, res.error
            entry = jobshot_index.lookup("cable-import-1", tmp / "dest")
            assert entry is not None, "the drop-zone route wrote no receipt"
            assert entry["folder"] == res.final_folder.name
            assert entry["photos"] == 2
        finally:
            jobshot_index.forget_all()


# --- the wire contract, pinned ----------------------------------------------
#
# These do not test behaviour. They pin the SHAPE of what goes on the wire,
# because the one defect that reached JobShot was invisible to both sides
# reading: `filed` is a list here and a bool in the receipt, and a client that
# read the word without the type reported a perfect upload as a refusal.
#
# If one of these fails, the question is not "fix the test" — it is "has the
# other half of the contract moved yet". LAN_PROTOCOL.md in the JobShot repo is
# the shared document; this is its enforcement on the HPO side.


def test_contract_upload_reply_shape_is_frozen():
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_job_zip(tmp))
            assert status == 200, reply

            assert set(reply) == {"jobshot", "ok", "error", "filed",
                                  "skipped", "warnings"}, sorted(reply)
            assert isinstance(reply["jobshot"], int)
            assert isinstance(reply["ok"], bool)      # the outcome
            assert isinstance(reply["error"], str)
            assert isinstance(reply["filed"], list)   # NOT a bool — §3
            assert isinstance(reply["skipped"], list)
            assert isinstance(reply["warnings"], list)

            job = reply["filed"][0]
            # work_date added 2026-09-24 so the phone can explain a folder the
            # day rule moved. Additive: a reader that ignores unknown keys is
            # unaffected, which is why it did not need JobShot to move first.
            # extras added 2026-09-25 for JobShot's emr.json. Additive again:
            # a reader that ignores unknown keys is unaffected.
            assert set(job) == {"job_id", "job_name", "folder", "photos",
                                "merged", "manifest", "date_shifted",
                                "work_date", "extras"}, sorted(job)
            assert isinstance(job["extras"], list)
            assert job["work_date"] == "2026-09-23", job["work_date"]
            assert isinstance(job["job_id"], str)
            assert isinstance(job["folder"], str) and job["folder"]
            assert isinstance(job["photos"], int)
            assert isinstance(job["merged"], bool)
            assert isinstance(job["date_shifted"], bool)
        finally:
            rx.close()


def test_contract_ping_and_receipt_shapes_are_frozen():
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, hello = rx.get(recv.PING_PATH)
            assert status == 200, hello
            assert set(hello) == {"jobshot", "app", "version", "ship",
                                  "ready"}, sorted(hello)
            # an identifier the phone may compare, not a display name (§2)
            assert hello["app"] == "happy-photo-organizer", hello["app"]
            assert isinstance(hello["ready"], bool)

            status, reply = rx.post(_job_zip(tmp))
            job_id = reply["filed"][0]["job_id"]
            status, receipt = rx.get(recv.JOB_PATH_PREFIX + job_id)
            assert status == 200, receipt
            # here `filed` is a BOOL — the same word, the other type, which is
            # exactly the trap that bit the client once already
            assert set(receipt) == {"jobshot", "filed", "job_id", "folder",
                                    "photos", "extras", "filed_at"}, sorted(receipt)
            assert isinstance(receipt["filed"], bool) and receipt["filed"] is True
            assert isinstance(receipt["folder"], str) and receipt["folder"]
            assert isinstance(receipt["photos"], int)
            # extras added v1.054 on JobShot's vote (CHAIN-2026-09-26-01): the
            # route that answers a lost reply must be able to say whether the
            # report draft was filed, not only the photos.
            assert isinstance(receipt["extras"], list)
            assert isinstance(receipt["filed_at"], str)
        finally:
            rx.close()


def test_contract_not_ready_says_why():
    """§2: `ready: false` carries a reason, so the phone can tell Nick what to
    fix instead of just refusing to send."""
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        rx = _Receiver(Path(td), dest=False)
        try:
            status, hello = rx.get(recv.PING_PATH)
            assert status == 200, hello
            assert hello["ready"] is False
            assert "destination" in hello.get("reason", ""), hello
        finally:
            rx.close()


def test_contract_counts_the_jobs_the_sender_claimed():
    """§3: a job that appears in neither list is unconfirmed — which is only
    detectable if the count the sender declared is checked."""
    if not _have_pillow():
        return
    import urllib.request
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            body = _job_zip(tmp)
            req = urllib.request.Request(rx.base + recv.UPLOAD_PATH,
                                         data=body, method="POST")
            req.add_header(recv.TOKEN_HEADER, rx.token)
            req.add_header("X-JobShot-Jobs", "3")      # zip really holds 1
            with urllib.request.urlopen(req, timeout=60) as r:
                reply = json.loads(r.read().decode("utf-8"))
            assert reply["ok"] is True
            assert any("3 job(s)" in w for w in reply["warnings"]), reply["warnings"]
        finally:
            rx.close()


# --- the update button says what the updater is doing -----------------------
#
# Nick, 2026-09-24: "ทำปุ่มกดระบบอัพเดทหน่อย ไม่รู้ไม่เห็นอะไรเลย กดก็ไม่ได้".
# The updater worked and was invisible: the only way to ask was a right-click
# on the tray icon, and the only answer was a line scrolling past in the log.
# `describe()` is what the button shows, and it lives in core precisely so it
# can be tested without opening a window.


class _FakeUpdateHost:
    """The five things UpdateWorker asks of its host."""

    def __init__(self):
        self.logs = []
        self.is_batch_running = False

    def after(self, _ms, fn=None, *a):
        if fn is not None:
            fn(*a)
        return "after-id"

    def after_cancel(self, _id):
        pass

    def log(self, msg, level="ok"):
        self.logs.append((level, msg))

    def on_before_install(self):
        pass


def _worker(tmp: Path):
    from core.update_worker import UpdateWorker
    return UpdateWorker(_FakeUpdateHost(), "1.049")


def test_update_button_describes_every_state_it_can_be_in():
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        w = _worker(tmp)

        # never checked — the button has to invite the click, not claim health
        label, kind, clickable = w.describe()
        assert (kind, clickable) == ("idle", True), (label, kind)
        assert label == "Check for updates"

        w.checking = True
        label, kind, clickable = w.describe()
        assert kind == "checking" and clickable is False, label

        w.checking = False
        w.last_check_at = 1.0
        label, kind, clickable = w.describe()
        assert kind == "uptodate" and clickable is True
        assert "1.049" in label, label      # says WHICH version is current

        w.last_error = "GitHub unreachable"
        label, kind, _c = w.describe()
        assert kind == "offline", label
        w.last_error = ""

        w.pending_info = SimpleNamespace(version="1.050", tag="v1.050")
        label, kind, clickable = w.describe()
        assert kind == "available" and clickable is True
        assert "1.050" in label, label

        w.in_progress = True
        w.download_pct = 42
        label, kind, clickable = w.describe()
        assert kind == "downloading" and clickable is False
        assert "42%" in label, label        # a download must be visible
        w.in_progress = False

        installer = tmp / "HappyPhotoOrganizerSetup-v1.050.exe"
        installer.write_bytes(b"x")
        w.pending_installer = installer
        w.pending_installer_version = "1.050"
        label, kind, clickable = w.describe()
        assert kind == "ready" and clickable is True
        assert label == "Install v1.050", label


def test_update_button_does_not_offer_an_installer_that_is_gone():
    """The cache is cleaned between runs. Offering "Install" for a file that
    no longer exists would fail with nothing to explain it."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        w = _worker(tmp)
        installer = tmp / "gone.exe"
        installer.write_bytes(b"x")
        w.pending_installer = installer
        w.pending_installer_version = "1.050"
        assert w.describe()[1] == "ready"

        installer.unlink()
        assert w.describe()[1] != "ready", w.describe()


def test_install_now_refuses_mid_batch_and_says_why():
    """A batch is the one time an update must not restart the app: Nick would
    lose the run. The refusal carries its reason so the button can show it."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        w = _worker(tmp)
        installer = tmp / "HappyPhotoOrganizerSetup-v1.050.exe"
        installer.write_bytes(b"x")
        w.pending_installer = installer
        w.pending_installer_version = "1.050"

        w.host.is_batch_running = True
        started, why = w.install_pending_now()
        assert started is False and "batch" in why, why

        w.host.is_batch_running = False
        w.pending_installer = None
        started, why = w.install_pending_now()
        assert started is False and "downloaded" in why, why


def test_manual_check_marks_itself_as_checking():
    """Without this the button stays on its old label while a check runs, and
    the click looks like it did nothing — which is the original complaint."""
    import time as _t
    with tempfile.TemporaryDirectory() as td:
        w = _worker(Path(td))
        w.manual_check()
        # `checking` is set on the calling thread, before the poll thread runs
        deadline = _t.time() + 10
        saw_reset = False
        while _t.time() < deadline:
            if not w.checking:
                saw_reset = True
                break
            _t.sleep(0.2)
        # it either already finished or is still going; what matters is that
        # the flag is managed at all, and that a finished check stamps a time
        assert saw_reset or w.checking
        if saw_reset:
            assert w.last_check_at is not None


# --- the report draft rides along (JobShot's emr.json, 2026-09-25) ----------
#
# The phone may put a third kind of file in a job folder: `emr.json`, the
# maintenance-report draft the engineer typed at the machine. EMR reads it out
# of the folder HPO builds. Before this, the extraction dropped it with a
# warning and the receipt still said "filed" — so Nick could delete the only
# copy of a draft that never arrived.


def _job_zip_with_draft(tmp: Path, *, job_id="20260925-090000-draft1",
                        job_name="DG3 Turbo Inspection", draft=b'{"emr": 1, "problem": ["leak"]}'):
    import io
    import zipfile
    buf = io.BytesIO()
    names = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n in (1, 2):
            name = f"{n:04d}.jpg"
            src = tmp / f"_src{n}.jpg"
            _noisy_jpeg(src)
            zf.writestr(f"{job_id}/{name}", src.read_bytes())
            names.append(name)
        if draft is not None:
            zf.writestr(f"{job_id}/emr.json", draft)      # before the manifest
        zf.writestr(f"{job_id}/job.json", json.dumps({
            "jobshot": 1, "job_id": job_id, "job_name": job_name,
            "ship": "ENA CRYSTAL", "created_at": "2026-09-25T09:00:00+07:00",
            "work_date": "2026-09-25", "photos": names,
        }))
    return buf.getvalue()


def test_a_report_draft_reaches_the_archive_folder_untouched():
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            draft = b'{"emr": 1, "problem": ["seal leaking"], "action": ["renewed"]}'
            status, reply = rx.post(_job_zip_with_draft(tmp, draft=draft))
            assert status == 200, reply
            job = reply["filed"][0]

            # the receipt names it — the phone shows "safe to delete" on this
            assert job["extras"] == ["emr.json"], job

            landed = rx.dest / job["folder"] / "emr.json"
            assert landed.is_file(), sorted(p.name for p in (rx.dest / job["folder"]).iterdir())
            assert landed.read_bytes() == draft, "the draft was altered in transit"

            # and it is not mistaken for a photo or for the manifest
            manifest = json.loads(
                (rx.dest / job["folder"] / "job.json").read_text(encoding="utf-8"))
            assert "emr.json" not in [_photo_name_of(e) for e in manifest["photos"]]
            assert manifest["filed"]["extras"] == ["emr.json"], manifest["filed"]
        finally:
            rx.close()


def _photo_name_of(entry):
    return entry if isinstance(entry, str) else entry.get("file", "")


def test_a_job_with_no_draft_says_so_rather_than_inventing_one():
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_job_zip_with_draft(tmp, draft=None))
            assert status == 200, reply
            assert reply["filed"][0]["extras"] == [], reply["filed"][0]
        finally:
            rx.close()


def test_a_second_draft_never_overwrites_the_first():
    """Two jobs can merge into one folder. Their drafts describe different
    work, so the second must not land on top of the first."""
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            first = b'{"emr": 1, "problem": ["first"]}'
            second = b'{"emr": 1, "problem": ["second"]}'
            status, reply1 = rx.post(_job_zip_with_draft(tmp, draft=first))
            assert status == 200, reply1
            status, reply2 = rx.post(_job_zip_with_draft(
                tmp, job_id="20260925-100000-draft2", draft=second))
            assert status == 200, reply2

            folder = rx.dest / reply2["filed"][0]["folder"]
            assert reply2["filed"][0]["merged"] is True, reply2
            assert (folder / "emr.json").read_bytes() == first
            second_name = reply2["filed"][0]["extras"][0]
            assert second_name != "emr.json", second_name
            assert (folder / second_name).read_bytes() == second
        finally:
            rx.close()


def test_the_archive_still_takes_only_photos_and_json():
    """Widening the gate for a sidecar must not widen it for anything else:
    this is a socket on a shared vessel network."""
    import io
    import zipfile
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name in ("notes.txt", "run.exe", "setup.bat", "photo.jpg.exe"):
            assert recv._bad_entry(f"job/{name}"), f"{name} should be refused"
        for name in ("0001.jpg", "job.json", "emr.json", "parts.json"):
            assert recv._bad_entry(f"job/{name}") == "", f"{name} should be allowed"
        # traversal is unaffected by the wider leaf rule
        assert recv._bad_entry("job/../evil.json")
        assert recv._bad_entry("C:/Windows/System32/evil.json")


# â”€â”€â”€ runner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# --- a draft aboard a job whose manifest does not survive (CHAIN sheet §3) ---
#
# JobShot asked it exactly: what happens to a job that arrives with emr.json but
# whose job.json is rejected? The draft must not be filed, must not be left
# lying in the archive or in quarantine, and above all the reply must not name
# it — `extras` is what the phone turns into "safe to delete from the phone".


def _draft_zip_with_broken_manifest(tmp: Path, *, job_id, manifest_path=None,
                                    manifest_bytes=None):
    import io
    import zipfile
    buf = io.BytesIO()
    names = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n in (1, 2):
            name = f"{n:04d}.jpg"
            src = tmp / f"_bm{n}.jpg"
            _noisy_jpeg(src)
            zf.writestr(f"{job_id}/{name}", src.read_bytes())
            names.append(name)
        zf.writestr(f"{job_id}/emr.json", b'{"emr": 1, "problem": ["orphan"]}')
        if manifest_bytes is None:
            manifest_bytes = json.dumps({
                "jobshot": 1, "job_id": job_id, "job_name": "Orphan Draft",
                "ship": "ENA CRYSTAL", "work_date": "2026-09-26",
                "photos": names,
            }).encode()
        zf.writestr(manifest_path or f"{job_id}/job.json", manifest_bytes)
    return buf.getvalue()


def _no_draft_survived(rx, reply):
    """The draft is nowhere on this PC, and nothing claims it was filed."""
    for root in (rx.dest, rx.tmp / "quarantine"):
        if root and root.exists():
            strays = [str(f) for f in root.rglob("*") if "emr" in f.name.lower()]
            assert not strays, strays
    assert not reply.get("filed"), reply
    for job in reply.get("filed", []):
        assert job.get("extras") == [], job


def test_a_refused_manifest_takes_its_draft_with_it():
    """job.json nested deep enough for the gate to refuse it: the folder then
    holds photos and a draft and no manifest, which is not a job."""
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            jid = "20260926-081000-gated"
            status, reply = rx.post(_draft_zip_with_broken_manifest(
                tmp, job_id=jid, manifest_path=f"{jid}/a/b/job.json"))
            assert status == 422, (status, reply)
            assert "job.json" in (reply.get("error") or ""), reply
            assert any("refused entry" in w for w in reply.get("warnings", [])), reply
            _no_draft_survived(rx, reply)
        finally:
            rx.close()


def test_a_corrupt_manifest_takes_its_draft_with_it():
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_draft_zip_with_broken_manifest(
                tmp, job_id="20260926-082000-corrupt",
                manifest_bytes=b"{ this is not json"))
            assert status == 422, (status, reply)
            assert any("valid JSON" in str(s.get("reason", ""))
                       for s in reply.get("skipped", [])), reply
            _no_draft_survived(rx, reply)
        finally:
            rx.close()


def test_a_manifest_from_a_newer_protocol_takes_its_draft_with_it():
    """The version gate is the one place a future JobShot will meet this build
    first. It must fail closed, and the phone must keep the draft."""
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            newer = json.dumps({
                "jobshot": 2, "job_id": "20260926-083000-v2",
                "job_name": "From A Newer Phone", "ship": "ENA CRYSTAL",
                "work_date": "2026-09-26", "photos": ["0001.jpg", "0002.jpg"],
            }).encode()
            status, reply = rx.post(_draft_zip_with_broken_manifest(
                tmp, job_id="20260926-083000-v2", manifest_bytes=newer))
            assert status == 422, (status, reply)
            assert any("version" in str(s.get("reason", "")).lower()
                       for s in reply.get("skipped", [])), reply
            _no_draft_survived(rx, reply)
        finally:
            rx.close()


def test_any_json_sidecar_rides_along_except_a_manifest():
    """HPO never interprets a sidecar, so a new one (parts.json) needs no
    change here. The exception is the trap worth knowing: `job-*.json` is read
    as a manifest variant and is deliberately NOT carried as an extra."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        arrival = tmp / "arrival" / "20260926-090000-side"
        arrival.mkdir(parents=True)
        names = []
        for n in (1, 2):
            _noisy_jpeg(arrival / f"{n:04d}.jpg")
            names.append(f"{n:04d}.jpg")
        for name in ("emr.json", "parts.json", "job-backup.json"):
            (arrival / name).write_text('{"x": 1}', encoding="utf-8")
        (arrival / "job.json").write_text(json.dumps({
            "jobshot": 1, "job_id": "20260926-090000-side",
            "job_name": "Sidecar Test", "ship": "ENA CRYSTAL",
            "work_date": "2026-09-26", "photos": names,
        }), encoding="utf-8")
        result = jobshot.import_job(arrival, tmp / "dest")
        assert result.ok, result.error
        assert result.extras == ["emr.json", "parts.json"], result.extras
        assert not (result.final_folder / "job-backup.json").exists()
        # copied, never moved: the sender keeps everything it sent
        for name in ("emr.json", "parts.json", "job-backup.json"):
            assert (arrival / name).is_file(), name


# --- v1.054: the lost-reply route can speak about the draft too -------------
#
# JobShot decides "safe to delete from the phone" from `extras`. When the §3
# reply is lost the phone asks §4 instead, and until now §4 could say the job
# was filed while staying silent about the one file Nick typed by hand.


def test_the_receipt_route_names_the_draft_it_filed():
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_job_zip_with_draft(tmp))
            assert status == 200, reply
            job_id = reply["filed"][0]["job_id"]
            assert reply["filed"][0]["extras"] == ["emr.json"]

            # the phone never saw that reply — this is all it has
            status, receipt = rx.get(recv.JOB_PATH_PREFIX + job_id)
            assert status == 200, receipt
            assert receipt["extras"] == ["emr.json"], receipt
        finally:
            rx.close()


def test_the_receipt_route_answers_for_a_job_filed_before_this_version():
    """An index entry written by v1.053 has no `extras` key at all. Answering
    [] there would tell the phone a draft it is still holding was never
    confirmed — so the archive, which kept the manifest, answers instead."""
    if not _have_pillow():
        return
    from core import jobshot_index as index
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, reply = rx.post(_job_zip_with_draft(tmp))
            assert status == 200, reply
            job_id = reply["filed"][0]["job_id"]

            # rewrite the receipt book the way v1.053 wrote it
            with index._LOCK:
                jobs = index._load()
                entry = jobs[job_id]
                entry.pop("extras")
                jobs[job_id] = entry
                index._save(jobs)
            assert "extras" not in index._load()[job_id]

            status, receipt = rx.get(recv.JOB_PATH_PREFIX + job_id)
            assert status == 200, receipt
            assert receipt["extras"] == ["emr.json"], receipt
        finally:
            rx.close()


def test_the_receipt_route_gives_each_merged_job_its_own_draft_name():
    """Two jobs in one folder means two drafts describing different work. The
    second one is filed as emr-<job_id>.json, and §4 must say so — a phone told
    "emr.json" would look for a file that belongs to the other job."""
    if not _have_pillow():
        return
    from core import jobshot_receive as recv
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            status, first = rx.post(_job_zip_with_draft(
                tmp, draft=b'{"emr": 1, "problem": ["first"]}'))
            assert status == 200, first
            status, second = rx.post(_job_zip_with_draft(
                tmp, job_id="20260925-100000-draft2",
                draft=b'{"emr": 1, "problem": ["second"]}'))
            assert status == 200, second
            assert second["filed"][0]["merged"] is True, second

            for reply in (first, second):
                job_id = reply["filed"][0]["job_id"]
                status, receipt = rx.get(recv.JOB_PATH_PREFIX + job_id)
                assert status == 200, receipt
                assert receipt["extras"] == reply["filed"][0]["extras"], receipt
                for name in receipt["extras"]:
                    assert (rx.dest / receipt["folder"] / name).is_file(), name
            assert first["filed"][0]["extras"] != second["filed"][0]["extras"]
        finally:
            rx.close()


def test_a_skipped_job_is_told_what_to_do_about_it():
    """JobShot prints the reason verbatim after "The PC skipped this job:".
    "not a job" reads as final; the truth is nearly always "send it again"."""
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rx = _Receiver(tmp)
        try:
            jid = "20260926-081000-gated"
            status, reply = rx.post(_draft_zip_with_broken_manifest(
                tmp, job_id=jid, manifest_path=f"{jid}/a/b/job.json"))
            assert status == 422, (status, reply)
            reason = reply["skipped"][0]["reason"]
            sentence = f"The PC skipped this job: {reason}."
            assert "send the job again" in reason, sentence
            assert "not a job" != reason, sentence
            assert "send the job again" in reply["error"], reply["error"]
        finally:
            rx.close()


# --- v1.055: emr.json names the phone's photos, the folder holds the archive's --
#
# HPO renames photos on filing (v1.045) and carries emr.json byte-for-byte
# (v1.053), so every photo name inside the draft matches nothing in the folder.
# EMR measured it: zero matches, skipped in silence, a report filled in with no
# photos while the status line said the draft had been applied. The map that
# fixes it already existed at filing time and was thrown away.


def _drop_job(root: Path, job_id: str, job_name: str, draft: bytes | None,
              photos: int = 2) -> Path:
    """One arrival folder, the way a phone leaves it: photos numbered from 1."""
    folder = root / job_id
    folder.mkdir(parents=True)
    names = []
    for n in range(1, photos + 1):
        _noisy_jpeg(folder / f"{n:04d}.jpg")
        names.append(f"{n:04d}.jpg")
    if draft is not None:
        (folder / "emr.json").write_bytes(draft)
    (folder / "job.json").write_text(json.dumps({
        "jobshot": 1, "job_id": job_id, "job_name": job_name,
        "ship": "ENA CRYSTAL", "work_date": "2026-09-26", "photos": names,
    }), encoding="utf-8")
    return folder


def _manifests(folder: Path) -> dict:
    return {m.name: json.loads(m.read_text(encoding="utf-8"))
            for m in sorted(folder.glob("job*.json"))}


def test_contract_the_filed_block_shape_is_frozen():
    """EMR reads `filed.extras`, `filed.renamed` and `filed.folder` out of every
    `job*.json` in the folder. Their own contract document said "job.json is not
    read at all" until 2026-09-26, so a refactor here could have killed every
    photo tag on the printed report while every text box still filled in.

    Frozen like the wire shapes in §2/§3/§4: if one of these keys moves or
    changes type, the question is not "fix the test", it is "has EMR been told".
    """
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        arrival = tmp / "arr" / "20260926-160000-frozen"
        arrival.mkdir(parents=True)
        names = []
        for n in (1, 2):
            _noisy_jpeg(arrival / f"{n:04d}.jpg")
            names.append(f"{n:04d}.jpg")
        (arrival / "emr.json").write_bytes(b'{"emr": 1}')
        (arrival / "job.json").write_text(json.dumps({
            "jobshot": 1, "job_id": "20260926-160000-frozen",
            "job_name": "Frozen Shape", "ship": "ENA TEST",
            "work_date": "2026-09-26", "photos": names,
        }), encoding="utf-8")
        result = jobshot.import_job(arrival, tmp / "dest")
        assert result.ok, result.error

        filed = json.loads((result.final_folder / "job.json")
                           .read_text(encoding="utf-8"))["filed"]
        assert set(filed) == {
            "folder", "folder_date", "work_date", "date_shifted",
            "merged_into_existing_folder", "grouped_with", "extras",
            "renamed", "hpo_version", "filed_at"}, sorted(filed)

        # the three EMR named as load-bearing, with their types
        assert isinstance(filed["folder"], str) and filed["folder"]
        assert isinstance(filed["extras"], list)
        assert isinstance(filed["renamed"], dict)
        assert all(isinstance(k, str) and isinstance(v, str)
                   for k, v in filed["renamed"].items()), filed["renamed"]
        # and they describe what is actually on disk
        assert filed["extras"] == ["emr.json"]
        for phone_name, archive_name in filed["renamed"].items():
            assert (result.final_folder / archive_name).is_file(), archive_name
        assert (tmp / "dest" / filed["folder"]).is_dir()


def test_a_draft_can_be_resolved_to_the_photos_actually_on_disk():
    """The whole point: a name out of emr.json, through the map, to a file."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        draft = {"emr": 1, "parts": [{"photo": "0002.jpg"}], "before": "0001.jpg"}
        arrival = _drop_job(tmp / "arr", "20260926-100000-res", "Pump Overhaul",
                            json.dumps(draft).encode())
        result = jobshot.import_job(arrival, tmp / "dest")
        assert result.ok, result.error

        filed = json.loads((result.final_folder / "job.json")
                           .read_text(encoding="utf-8"))["filed"]
        renamed = filed["renamed"]
        # the draft is untouched, so it still says 0001.jpg / 0002.jpg
        carried = json.loads((result.final_folder / "emr.json")
                             .read_text(encoding="utf-8"))
        assert carried == draft, "the draft must not be rewritten"
        for phone_name in ("0001.jpg", "0002.jpg"):
            assert phone_name in renamed, renamed
            assert (result.final_folder / renamed[phone_name]).is_file()
        # and the archive names really are different, or none of this matters
        assert set(renamed) != set(renamed.values()), renamed


def test_each_job_keeps_its_own_rename_map_in_a_merged_folder():
    """Every phone numbers its own job from 0001, so a folder-level map would
    have one slot for "0001.jpg" and would point one job's report at the other
    job's pictures — the emr-<job_id>.json problem one layer down."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        first = jobshot.import_job(
            _drop_job(tmp / "a1", "20260926-100000-a", "Pump Overhaul",
                      b'{"emr": 1, "photo": "0001.jpg"}'), dest)
        second = jobshot.import_job(
            _drop_job(tmp / "a2", "20260926-110000-b", "Pump Overhaul",
                      b'{"emr": 1, "photo": "0001.jpg"}'), dest)
        assert second.merged_into_existing, "the test needs a merge"
        assert first.final_folder == second.final_folder

        manifests = _manifests(second.final_folder)
        assert set(manifests) == {"job.json", "job-20260926-110000-b.json"}, \
            sorted(manifests)
        maps = {name: m["filed"]["renamed"] for name, m in manifests.items()}
        a, b = maps["job.json"], maps["job-20260926-110000-b.json"]
        # the same key in both, and it must NOT resolve to the same file
        assert a["0001.jpg"] != b["0001.jpg"], maps
        for m in (a, b):
            for archive_name in m.values():
                assert (second.final_folder / archive_name).is_file(), archive_name
        assert not set(a.values()) & set(b.values()), maps


def test_a_draft_belongs_to_the_manifest_that_names_it_not_to_a_matching_filename():
    """Pairing emr-<id>.json with job-<id>.json looks safe and is not: when the
    FIRST job files no draft, the second job's draft keeps the plain name
    `emr.json` while its manifest is `job-<id>.json`. `filed.extras` is the only
    correct link, which is why it is written next to `filed.renamed`."""
    if not _have_pillow():
        return
    from core import jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "dest"
        first = jobshot.import_job(
            _drop_job(tmp / "a1", "20260926-100000-a", "Pump Overhaul", None), dest)
        second = jobshot.import_job(
            _drop_job(tmp / "a2", "20260926-110000-b", "Pump Overhaul",
                      b'{"emr": 1, "photo": "0001.jpg"}'), dest)
        assert second.merged_into_existing
        assert first.extras == [] and second.extras == ["emr.json"], \
            (first.extras, second.extras)

        manifests = _manifests(second.final_folder)
        # the trap: the plain-named draft belongs to the job with the SUFFIXED
        # manifest, so matching names would hand it the wrong photos
        assert manifests["job.json"]["filed"]["extras"] == []
        by_name = manifests["job-20260926-110000-b.json"]["filed"]
        assert by_name["extras"] == ["emr.json"], by_name

        owner = [m for m in manifests.values() if "emr.json" in m["filed"]["extras"]]
        assert len(owner) == 1
        renamed = owner[0]["filed"]["renamed"]
        assert (second.final_folder / renamed["0001.jpg"]).is_file()
        # and that is the second job's picture, not the first job's
        assert renamed["0001.jpg"] not in \
            manifests["job.json"]["filed"]["renamed"].values()


# --- v1.056: a finished batch can be cleared, and not committed twice -------
#
# Nick, 2026-09-26: "เวลาสร้างงานเสร็จแล้วเคลียงานจากลิสเพื่อทำใหม่ไม่ได้ ต้องปิดโปรแกรมเปิดใหม่".
# Diagnosis in bug/bug_v1.055.md: no control existed, the commit left the plan
# armed, and it left source_paths full while the drop zone appended to them.


def _two_row_plan(tmp: Path, *, second_named: bool = True):
    """One pending folder per row, the way Phase 1 leaves them."""
    dest = tmp / "dest"
    dest.mkdir(exist_ok=True)
    rows = []
    for idx, name in enumerate(("Pump Overhaul", "Valve Repair" if second_named else ""), 1):
        folder = dest / f"2026-09-2{idx}{processor.PENDING_MARKER}0{idx}"
        folder.mkdir()
        (folder / f"img_{idx:03d}.jpg").write_bytes(bytes([idx]) * 10)
        rows.append(processor.JobAssignment(
            folder_date=datetime(2026, 9, 20 + idx), job_name=name,
            temp_folder=folder))
    return processor.Plan(assignments=rows, dest_root=dest), rows, dest


def test_committing_the_same_plan_twice_files_nothing_and_errors_nothing():
    """The commit button used to re-arm on any truthy plan. Pressing it again
    walked folders that had been renamed away and reported an error for every
    row of a run that had in fact succeeded."""
    with tempfile.TemporaryDirectory() as td:
        plan, rows, dest = _two_row_plan(Path(td))

        first = processor.phase4_rename_folders(plan)
        assert first.renamed == 2, (first.renamed, first.errors)
        assert first.errors == [], first.errors
        assert all(a.committed for a in rows)
        filed = sorted(f.name for f in dest.iterdir())

        second = processor.phase4_rename_folders(plan)
        assert second.renamed == 0, second.renamed
        assert second.already_done == 2, second.already_done
        assert second.errors == [], second.errors
        assert second.skipped == 0, second.skipped
        # and nothing on disk moved
        assert sorted(f.name for f in dest.iterdir()) == filed


def test_a_row_skipped_for_want_of_a_name_can_still_be_committed_afterwards():
    """The real reason the button must not simply be disabled after a commit:
    Nick names the row that was skipped and commits again. Only that row moves,
    and the ones already filed are reported as such rather than as errors."""
    with tempfile.TemporaryDirectory() as td:
        plan, rows, dest = _two_row_plan(Path(td), second_named=False)

        first = processor.phase4_rename_folders(plan)
        assert (first.renamed, first.skipped) == (1, 1), (first.renamed, first.skipped)
        assert rows[0].committed is True
        assert rows[1].committed is False, "a skipped row is not committed"

        rows[1].job_name = "Valve Repair"
        second = processor.phase4_rename_folders(plan)
        assert second.renamed == 1, (second.renamed, second.errors)
        assert second.already_done == 1, second.already_done
        assert second.errors == [], second.errors
        assert (dest / "22-09-26 Valve Repair").is_dir()
        assert (dest / "21-09-26 Pump Overhaul").is_dir()


def test_an_errored_row_is_not_marked_committed():
    """committed must mean "this folder is in the archive", not "we tried"."""
    with tempfile.TemporaryDirectory() as td:
        plan, rows, dest = _two_row_plan(Path(td))
        # make the second row impossible: its pending folder is gone
        import shutil as _sh
        _sh.rmtree(rows[1].temp_folder)

        res = processor.phase4_rename_folders(plan)
        assert res.renamed == 1, res.renamed
        assert res.errors, "the missing folder must be reported"
        assert rows[0].committed is True
        assert rows[1].committed is False


def test_the_window_has_a_way_to_clear_a_finished_batch():
    """Mechanical, not a judgement call: the v1.047/v1.048 lesson is that a
    finished feature with no entry point is not finished, and grep is what
    catches it. Reads main.py as source - no window is opened."""
    import ast
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    window = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    methods = {n.name: n for n in window.body if isinstance(n, ast.FunctionDef)}

    for name in ("_reset_batch", "_on_new_batch"):
        assert name in methods, f"{name} is missing"

    def calls_in(fn_name):
        return {n.func.attr for n in ast.walk(methods[fn_name])
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    # the button exists AND is wired to the handler
    assert "new_batch_btn" in src, "no new-batch button"
    assert "command=self._on_new_batch" in src, "the button calls nothing"
    assert "_reset_batch" in calls_in("_on_new_batch"), "the button resets nothing"
    # and the analysis path shares the one implementation, so they cannot drift
    assert "_reset_batch" in calls_in("_start_phase12"), \
        "_start_phase12 still clears the batch its own way"


def _have_ctk() -> bool:
    try:
        import customtkinter  # noqa: F401
        return True
    except Exception:
        return False


class _FakeWidget:
    """Enough of a CTk widget for the window's own logic to run headless."""

    def __init__(self):
        self.state = "normal"
        self.text = ""
        self.children = []
        self.mapped = True
        self.filed = False

    def configure(self, **kw):
        if "state" in kw:
            self.state = kw["state"]
        if "text" in kw:
            self.text = kw["text"]

    def winfo_children(self):
        return list(self.children)

    def winfo_ismapped(self):
        return self.mapped

    def destroy(self):
        self.destroyed = True

    def pack(self, **kw):
        self.mapped = True

    def pack_forget(self):
        self.mapped = False

    def mark_filed(self, final_folder=None):
        self.filed = True
        self.filed_folder = final_folder


class _Silent:
    """messagebox with the dialogs taken out. Records what was asked."""

    def __init__(self, answer=True):
        self.answer = answer
        self.asked = []
        self.shown = []

    def askyesno(self, title, message, **kw):
        self.asked.append((title, message))
        return self.answer

    def showinfo(self, title, message="", **kw):
        self.shown.append((title, message))

    def showwarning(self, title, message="", **kw):
        self.shown.append((title, message))


class _no_dialogs:
    """with _no_dialogs() as box: ... - swaps main.messagebox for the duration."""

    def __init__(self, answer=True):
        self.box = _Silent(answer)

    def __enter__(self):
        import main as _app
        self._app = _app
        self._real = _app.messagebox
        _app.messagebox = self.box
        return self.box

    def __exit__(self, *exc):
        self._app.messagebox = self._real
        return False


class _StubWindow:
    """Drives the REAL MainWindow methods without opening a window.

    Only the attributes those methods touch. Anything missing raises, which is
    the point: a method that starts reaching for new state fails loudly here
    instead of passing a test that never exercised it.
    """

    def __init__(self, plan=None, sources=None, busy=False):
        import types
        self.plan = plan
        self.source_paths = list(sources or [])
        self._committed_sources = list(sources or [])
        self.dest_root = Path("D:/archive")
        self.worker = types.SimpleNamespace(is_alive=lambda: busy) if busy else None
        self._rename_done = False
        self._phase_start = 1.0
        self._batch_running = True
        self.table_scroll = _FakeWidget()
        self.review_summary = _FakeWidget()
        self.status_detail = _FakeWidget()
        self.phase4_btn = _FakeWidget()
        self.phase12_btn = _FakeWidget()
        self.cancel_btn = _FakeWidget()
        self.new_batch_btn = _FakeWidget()
        self.delete_flagged_btn = _FakeWidget()
        self.sources_label = _FakeWidget()
        self.logs = []
        self.boxes = []
        for name in ("step1", "step2", "step3"):
            w = _FakeWidget()
            w.set_status = lambda v, _w=w: setattr(_w, "status", v)
            setattr(self, name, w)
        self.update_worker = types.SimpleNamespace(resume_deferred=lambda: None)

    # the few helpers the methods under test call back into
    def _log(self, msg, level="info"):
        self.logs.append(msg)

    def _refresh_sources(self):
        pass

    def _set_progress(self, ratio, label=""):
        if label:
            self.status_detail.configure(text=label)

    def __getattr__(self, name):
        """Bind any other MainWindow method to this stub on first use."""
        import main as _app
        fn = getattr(_app.MainWindow, name, None)
        if fn is None or not callable(fn):
            raise AttributeError(name)
        return fn.__get__(self)


def _plan_rows(tmp: Path, names=("Pump Overhaul", "Valve Repair")):
    dest = tmp / "dest"
    dest.mkdir(exist_ok=True)
    rows = []
    for idx, name in enumerate(names, 1):
        folder = dest / f"2026-09-2{idx}{processor.PENDING_MARKER}0{idx}"
        folder.mkdir()
        (folder / f"img_{idx:03d}.jpg").write_bytes(bytes([idx]) * 10)
        rows.append(processor.JobAssignment(
            folder_date=datetime(2026, 9, 20 + idx), job_name=name,
            temp_folder=folder))
    return processor.Plan(assignments=rows, dest_root=dest), rows, dest


def test_commit_is_not_re_armed_over_a_batch_that_is_fully_filed():
    """BUG-2, behaviourally: after a clean commit there is nothing to commit."""
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, rows, _dest = _plan_rows(Path(td))
        processor.phase4_rename_folders(plan)
        w = _StubWindow(plan=plan)
        w._reset_buttons()
        assert w.phase4_btn.state == "disabled", w.phase4_btn.state


def test_commit_comes_back_for_a_row_that_was_skipped_then_named():
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, rows, _dest = _plan_rows(Path(td), names=("Pump Overhaul", ""))
        processor.phase4_rename_folders(plan)
        w = _StubWindow(plan=plan)
        w._reset_buttons()
        assert w.phase4_btn.state == "normal", "the unnamed row still needs committing"
        rows[1].job_name = "Valve Repair"
        processor.phase4_rename_folders(plan)
        w._reset_buttons()
        assert w.phase4_btn.state == "disabled", w.phase4_btn.state


def test_deleting_the_last_unfiled_row_disarms_commit():
    """The review's finding: _reset_buttons was not the only thing that armed
    the button, so removing the last pending row left it live over nothing."""
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, rows, _dest = _plan_rows(Path(td), names=("Pump Overhaul", ""))
        processor.phase4_rename_folders(plan)      # row 2 skipped, row 1 filed
        w = _StubWindow(plan=plan)
        w._reset_buttons()
        assert w.phase4_btn.state == "normal"
        plan.assignments.remove(rows[1])           # the per-row Delete
        w._sync_commit_button()
        assert w.phase4_btn.state == "disabled", w.phase4_btn.state


def test_a_finished_commit_clears_only_the_sources_it_consumed():
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, rows, _dest = _plan_rows(Path(td))
        res = processor.phase4_rename_folders(plan)
        spent = Path("C:/photos/job-A")
        w = _StubWindow(plan=plan, sources=[spent])
        # a folder Nick queued WHILE the commit was running
        queued = Path("C:/photos/job-B")
        w.source_paths.append(queued)
        with _no_dialogs():
            w._on_rename_done(res)
        assert w.source_paths == [queued], w.source_paths
        assert w._rename_done is True
        assert any("Sources cleared" in m for m in w.logs), w.logs


def test_a_commit_that_left_work_behind_keeps_the_sources_and_is_not_done():
    """Cancelled or errored: `renamed` was non-zero, but rows are still unfiled.
    Reading `renamed` alone used to clear his sources and flip Step 3 to done."""
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, rows, _dest = _plan_rows(Path(td), names=("Pump Overhaul", ""))
        res = processor.phase4_rename_folders(plan)   # 1 filed, 1 skipped
        assert res.renamed == 1 and res.skipped == 1
        spent = Path("C:/photos/job-A")
        w = _StubWindow(plan=plan, sources=[spent])
        with _no_dialogs():
            w._on_rename_done(res)
        assert w.source_paths == [spent], "a half-done batch still needs its sources"
        assert w._rename_done is False, "Step 3 must not read as done"
        assert w.step3.status != "done"


def test_a_filed_row_stops_looking_editable():
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, rows, _dest = _plan_rows(Path(td), names=("Pump Overhaul", ""))
        res = processor.phase4_rename_folders(plan)
        w = _StubWindow(plan=plan, sources=[Path("C:/photos/job-A")])
        filed_row, open_row = _FakeWidget(), _FakeWidget()
        filed_row.assignment, open_row.assignment = rows[0], rows[1]
        w.table_scroll.children = [filed_row, open_row]
        with _no_dialogs():
            w._on_rename_done(res)
        assert filed_row.filed is True, "a committed row must be marked"
        assert filed_row.filed_folder is not None,             "and told where it went, or its thumbnail opens the folder that was renamed away"
        assert open_row.filed is False, "a row still to file must stay editable"


def test_the_window_can_clear_a_finished_batch():
    """Behavioural version of the entry-point check: the button's own handler,
    on a finished batch, leaves nothing behind."""
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, _rows, _dest = _plan_rows(Path(td))
        processor.phase4_rename_folders(plan)
        w = _StubWindow(plan=plan, sources=[Path("C:/photos/job-A")])
        w.table_scroll.children = [_FakeWidget(), _FakeWidget()]
        with _no_dialogs() as box:
            w._on_new_batch()
        assert box.asked == [], "a fully filed batch must clear without a question"
        assert w.plan is None
        assert w._rename_done is False
        assert w.phase4_btn.state == "disabled"
        # the job list is what this button clears; Step 1 has its own Clear, and
        # a folder queued during the last commit must survive this click
        assert w.source_paths == [Path("C:/photos/job-A")], w.source_paths


def test_clearing_a_batch_that_is_not_filed_asks_first():
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, _rows, _dest = _plan_rows(Path(td))
        w = _StubWindow(plan=plan)
        with _no_dialogs(answer=False) as box:
            w._on_new_batch()
        assert box.asked, "an uncommitted batch must not vanish silently"
        assert "__pending_" in box.asked[0][1], box.asked[0][1]
        assert w.plan is plan, "answering No must change nothing"


def test_the_new_batch_button_comes_alive_when_there_is_something_to_clear():
    """The whole point of the release. Without this, main.py could hard-code
    the button to "disabled" and every other test would still pass."""
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, _rows, _dest = _plan_rows(Path(td))

        idle = _StubWindow()
        idle._refresh_step_states()
        assert idle.new_batch_btn.state == "disabled", "nothing to clear yet"

        dropped = _StubWindow(sources=[Path("C:/photos/job-A")])
        dropped._refresh_step_states()
        assert dropped.new_batch_btn.state == "normal", "sources are clearable"

        analysed = _StubWindow(plan=plan)
        analysed._refresh_step_states()
        assert analysed.new_batch_btn.state == "normal", "a plan is clearable"

        processor.phase4_rename_folders(plan)
        done = _StubWindow(plan=plan)
        done._rename_done = True
        done._refresh_step_states()
        assert done.new_batch_btn.state == "normal", \
            "THE reported bug: a finished batch must be clearable"


def test_emptying_the_list_by_deleting_rows_disarms_commit():
    """_render_plan returns early on an empty plan; that early return used to
    jump over the commit-button sync, so the bulk-delete path left it armed."""
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, rows, _dest = _plan_rows(Path(td))
        w = _StubWindow(plan=plan)
        w._sync_commit_button()
        assert w.phase4_btn.state == "normal"
        plan.assignments.clear()
        w._render_plan(plan)
        assert w.phase4_btn.state == "disabled", w.phase4_btn.state


def test_the_update_cache_is_emptied_whatever_is_in_it():
    """The Director asked three times whether a stranded `.part` from a failed
    resume could survive for ever. Today it cannot exist - the download writes
    straight to its final `.exe` name and resumes by reading that file's size -
    but a suffix filter that covers nothing is one refactor away from covering
    nothing while looking like it covers something. The sweep takes everything
    except the installer being kept."""
    from core import updater
    with tempfile.TemporaryDirectory() as td:
        cache = Path(td) / "updates"
        cache.mkdir()
        real = updater.cache_dir
        updater.cache_dir = lambda: cache
        try:
            keep = "HappyPhotoOrganizerSetup-v1.057.exe"
            for name in (keep,
                         "HappyPhotoOrganizerSetup-v1.056.exe",
                         "HappyPhotoOrganizerSetup-v1.058.exe.part",
                         "HappyPhotoOrganizerSetup-v1.058.tmp",
                         "download.crdownload",
                         "stray"):
                (cache / name).write_bytes(b"x" * 8)
            updater.cleanup_old_installers(keep=keep)
            left = sorted(f.name for f in cache.iterdir())
            assert left == [keep], left
        finally:
            updater.cache_dir = real


def test_the_destination_is_remembered_across_a_restart():
    """Nick, 2026-09-26: "เวลาเปิดปิดหรืออัพเดทโปรแกรม ช่องโฟเดอร์ที่เลือกไว้ไม่จำ เลยต้องเลือกใหม่ทุกครั้ง".
    Only the pairing dialog ever wrote the destination down, so after a restart
    Step 1 came up empty AND the phone was told there was no destination - for a
    folder that had never moved."""
    if not _have_ctk():
        return
    import main as _app
    from core import auth, jobshot
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "archive"
        dest.mkdir()
        store = {"jobshot_ship": "ENA TEST"}
        real = (auth.load_config, auth.update_config)
        auth.load_config = lambda: dict(store)

        def _update(updates):
            store.update(updates)
            return True

        auth.update_config = _update
        try:
            # 1. he picks a folder in the main window
            w = _StubWindow()
            w.dest_label = _FakeWidget()
            w._set_dest(dest)
            assert w.dest_root == dest
            # both keys, so a renamed vessel cannot lose it
            assert store["dest_roots"]["ENA TEST"] == str(dest), store.get("dest_roots")
            assert store["last_dest_root"] == str(dest), store.get("last_dest_root")
            assert jobshot.get_dest_root("ENA TEST") == dest

            # 2. he closes the app and opens it again
            fresh = _StubWindow()
            fresh.dest_label = _FakeWidget()
            fresh.dest_root = None
            fresh._restore_dest()
            assert fresh.dest_root == dest, "the destination was not remembered"
            assert str(dest) in fresh.dest_label.text, fresh.dest_label.text

            # 3. and the vessel gets renamed - the folder did not move
            store["jobshot_ship"] = "ENA CHALLENGER"
            renamed = _StubWindow()
            renamed.dest_label = _FakeWidget()
            renamed.dest_root = None
            renamed._restore_dest()
            assert renamed.dest_root == dest, "a renamed vessel lost the folder"
        finally:
            auth.load_config, auth.update_config = real


def test_the_startup_path_really_restores_the_destination():
    """The two tests above call _restore_dest directly, so deleting its call
    from __init__ would bring Nick's bug back with both of them green. This is
    the wiring check that the behaviour tests cannot make."""
    import ast
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    window = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    methods = {n.name: n for n in window.body if isinstance(n, ast.FunctionDef)}

    def calls_in(fn):
        return {n.func.attr for n in ast.walk(methods[fn])
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    assert "_restore_dest" in calls_in("__init__"),         "__init__ no longer restores the destination"
    # and every picker goes through the one door that remembers
    for picker in ("_pick_dest", "_choose_dest_for_phone"):
        assert "_set_dest" in calls_in(picker),             f"{picker} sets the destination without remembering it"


def test_a_job_from_another_vessel_is_not_filed_into_this_pc_tree():
    """Restoring dest_root at startup made _jobshot_dest's early return swallow
    the per-vessel lookup, so a hand-dropped job from another ship would have
    been filed here. The Wi-Fi path refuses a foreign ship outright; this path
    has no guard at all, so the destination is the only thing standing up."""
    if not _have_ctk():
        return
    import json as _json
    from core import auth, jobshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        mine, theirs = tmp / "mine", tmp / "theirs"
        mine.mkdir()
        theirs.mkdir()
        store = {"jobshot_ship": "ENA TEST",
                 "dest_roots": {"ENA TEST": str(mine),
                                "ENA CHALLENGER": str(theirs)}}
        real = (auth.load_config, auth.update_config)
        auth.load_config = lambda: dict(store)
        auth.update_config = lambda u: (store.update(u), True)[1]
        try:
            job = tmp / "20260926-120000-abc"
            job.mkdir()
            (job / "0001.jpg").write_bytes(b"x" * 10)
            (job / "job.json").write_text(_json.dumps({
                "jobshot": 1, "job_id": "20260926-120000-abc",
                "job_name": "Bow Thruster", "ship": "ENA Challenger",
                "work_date": "2026-09-26", "photos": ["0001.jpg"],
            }), encoding="utf-8")

            w = _StubWindow()
            w.dest_label = _FakeWidget()
            w._restore_dest()
            assert w.dest_root == mine, "this PC files for ENA TEST"

            chosen = w._jobshot_dest([job])
            assert chosen == theirs, (
                f"a job from ENA Challenger was going to be filed into {chosen}")
            assert w.dest_root == mine,                 "and it must not have changed this PC's own destination"
            assert any("not this PC's vessel" in m for m in w.logs), w.logs
        finally:
            auth.load_config, auth.update_config = real


def test_a_destination_that_is_gone_is_not_restored():
    """An unplugged drive must not come back as "ready" and fail on the first
    job - it has to ask again, and say why."""
    if not _have_ctk():
        return
    from core import auth
    with tempfile.TemporaryDirectory() as td:
        missing = Path(td) / "not-there"
        store = {"jobshot_ship": "", "last_dest_root": str(missing)}
        real = (auth.load_config, auth.update_config)
        auth.load_config = lambda: dict(store)
        auth.update_config = lambda u: (store.update(u), True)[1]
        try:
            w = _StubWindow()
            w.dest_label = _FakeWidget()
            w.dest_root = None
            w._restore_dest()
            assert w.dest_root is None, "restored a folder that is not there"
            assert any("gone" in m for m in w.logs), w.logs
        finally:
            auth.load_config, auth.update_config = real


def test_a_reset_is_refused_while_a_worker_is_running():
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, _rows, _dest = _plan_rows(Path(td))
        w = _StubWindow(plan=plan, sources=[Path("C:/photos/job-A")], busy=True)
        assert w._reset_batch() is False
        assert w.plan is plan and w.source_paths
        w._refresh_step_states()
        assert w.new_batch_btn.state == "disabled"


def test_the_analysis_path_resets_the_batch_but_keeps_its_sources():
    """_start_phase12 shares one reset with the button so the two cannot drift,
    but it must keep the sources it is about to read."""
    if not _have_ctk():
        return
    with tempfile.TemporaryDirectory() as td:
        plan, _rows, _dest = _plan_rows(Path(td))
        src = Path("C:/photos/job-A")
        w = _StubWindow(plan=plan, sources=[src])
        w.table_scroll.children = [_FakeWidget(), _FakeWidget()]
        assert w._reset_batch(keep_sources=True) is True
        assert w.source_paths == [src], w.source_paths
        assert w.plan is None
        assert w.dest_root == Path("D:/archive"), "the destination must survive"
        assert all(getattr(c, "destroyed", False) for c in w.table_scroll.children)


def test_phase1_never_walks_into_an_abandoned_pending_folder():
    """A batch cleared before its commit leaves its `__pending_` folder behind.
    Reusing that name would file the abandoned photos under the next job's
    name, and the only sign would be a photo count that looked large.

    The orphan must be dated the same day the new group will land on, or the
    names cannot collide and the test proves nothing — which is exactly what
    the first version of it did.
    """
    if not _have_pillow():
        return
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "dest"
        dest.mkdir()
        src = Path(td) / "src"
        src.mkdir()
        for i in range(1, 3):
            _noisy_jpeg(src / f"new_{i}.jpg")

        # what Phase 1 would have called this group, had nothing been there
        probe = processor.phase1_resize_and_group([src], dest)
        taken = probe.assignments[0].temp_folder
        assert processor.PENDING_MARKER in taken.name
        for f in taken.iterdir():
            f.unlink()
        taken.rmdir()

        # now plant an abandoned batch under exactly that name
        orphan = dest / taken.name
        orphan.mkdir()
        (orphan / "left_behind.jpg").write_bytes(b"x" * 10)

        plan = processor.phase1_resize_and_group([src], dest)
        folders = [a.temp_folder for a in plan.assignments]
        assert orphan not in folders, (
            f"phase 1 walked into the abandoned folder {orphan.name}")
        assert (orphan / "left_behind.jpg").is_file(), "and must not touch it"
        # the new batch's photos are somewhere else entirely
        assert all(processor.PENDING_MARKER in f.name for f in folders)
        assert not any((f / "left_behind.jpg").exists() for f in folders)


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

