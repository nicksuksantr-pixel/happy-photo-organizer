"""
test_core.py — pure-Python regression tests (NO API key, NO network, NO photos).

Run:  python tests/test_core.py

Created 2026-06-04 (Tester sprint). The project previously claimed "67/67 tests"
in its docs but had NO test suite — only scripts/smoke_test.py, which needs a live
Gemini key + local sample photos. This file is the real, dependency-free suite:
it exercises the deterministic core logic (grouping, date allocation, JSON parsing,
catalog, rate-limiter tiers, version compare, auth null-safety) so a refactor that
breaks an invariant fails loudly here instead of in production.

Each test is a function starting with `test_`. A bare `assert` failure or any
exception marks it FAILED. Exit code 0 = all pass, 1 = at least one failed.
"""
from __future__ import annotations

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


# ─── helpers ───────────────────────────────────────────────────

def _make_dated_files(tmp: Path, stamps: list[str]) -> list[Path]:
    """Create empty files named so read_from_filename yields the given times.
    `stamps` = list of 'YYYYMMDD_HHMMSS'. grouper reads the date from the name
    (the file need not be a real image — read_from_exif fails gracefully)."""
    out = []
    for i, s in enumerate(stamps):
        p = tmp / f"IMG_{s}_{i:03d}.jpg"
        p.write_bytes(b"")  # not a real image — exif read returns None, filename wins
        out.append(p)
    return out


# ─── grouper ───────────────────────────────────────────────────

def test_grouper_midnight_burst_is_one_session():
    """C2: a continuous burst crossing midnight (<gap apart) = ONE folder."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        imgs = _make_dated_files(tmp, ["20260315_235900", "20260316_000100"])  # 2 min apart
        groups = grouper.group_by_session(imgs, time_gap_minutes=90)
        assert len(groups) == 1, f"expected 1 session across midnight, got {len(groups)}"
        # representative date = earliest = the pre-midnight day (15th)
        assert groups[0].representative_date.day == 15


def test_grouper_large_gap_same_day_splits():
    """A genuine >gap break on the same day still splits into two sessions."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        imgs = _make_dated_files(tmp, ["20260315_120000", "20260315_140000"])  # 2 h apart
        groups = grouper.group_by_session(imgs, time_gap_minutes=90)
        assert len(groups) == 2, f"expected 2 sessions, got {len(groups)}"


def test_grouper_empty():
    assert grouper.group_by_session([]) == []


# ─── processor: date allocation ────────────────────────────────

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
        (root / "01-05-50 Job A").mkdir()  # year 2050 — implausible
        ym = processor.detect_target_month(root)
        assert ym is not None
        assert abs(ym[0] - datetime.now().year) <= 5, f"year not clamped: {ym}"


def test_sanitize_filename_strips_invalid():
    out = processor.sanitize_filename('Cleaned <Cooler>: No.1 / "main"')
    for bad in '<>:/"\\|?*':
        assert bad not in out, f"{bad!r} survived sanitize: {out!r}"


# ─── analyzer: JSON parsing (C5) ───────────────────────────────

def test_parse_plain_json():
    r = analyzer._parse_json_response('{"matched_name":"X","confidence":0.9}')
    assert r["matched_name"] == "X"


def test_parse_code_fenced_json():
    r = analyzer._parse_json_response('```json\n{"matched_name":"Y","confidence":0.5}\n```')
    assert r["matched_name"] == "Y"


def test_parse_json_with_trailing_prose():
    r = analyzer._parse_json_response('Result: {"matched_name":"Z","confidence":0.7} — done.')
    assert r["matched_name"] == "Z", f"got {r}"


def test_parse_list_coerced_to_dict():
    r = analyzer._parse_json_response('[{"matched_name":"L","confidence":0.4}]')
    assert r["matched_name"] == "L"


def test_parse_garbage_returns_error_dict():
    r = analyzer._parse_json_response("no json at all here")
    assert r["matched_name"] is None
    assert "parse error" in r["reasoning"]


# ─── analyzer: transient-error classification (BUG-N2) ─────────

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


# ─── catalog ───────────────────────────────────────────────────

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


# ─── rate_limiter (F1) ─────────────────────────────────────────

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


# ─── version compare (updater) ─────────────────────────────────

def test_version_compare():
    from core.updater import is_newer
    assert is_newer("1.040", "1.041")
    assert is_newer("1.039", "1.040")
    assert not is_newer("1.040", "1.040")
    assert not is_newer("1.041", "1.040")


def test_version_file_matches_running():
    assert read_version() != "0.0.0", "VERSION file unreadable"


# ─── auth null-safety (C12) ────────────────────────────────────

def test_get_api_key_handles_null_value():
    """C12: a JSON `"api_key": null` must not crash with None.strip()."""
    orig = auth.load_config
    try:
        auth.load_config = lambda: {"api_key": None, "model": None}
        assert auth.get_api_key() is None  # no AttributeError
        assert auth.get_model() == auth.DEFAULT_MODEL  # null model → default
    finally:
        auth.load_config = orig


def test_get_model_default_when_missing():
    orig = auth.load_config
    try:
        auth.load_config = lambda: {}
        assert auth.get_model() == auth.DEFAULT_MODEL
    finally:
        auth.load_config = orig


# ─── runner ────────────────────────────────────────────────────

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
            print(f"  FAIL  {name}  →  {type(e).__name__}: {e}")
    print("\n" + "=" * 60)
    print(f"  {passed}/{len(tests)} passed" + (f", {failed} FAILED" if failed else " — ALL GREEN"))
    print("=" * 60)
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  • {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
