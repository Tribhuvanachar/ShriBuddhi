import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date, timedelta

from panchanga import ephemeris
from panchanga.cli import _local_midnight_to_jd_ut
from panchanga.ekadashi import classify_day
from panchanga.sunrise import Place

BANGALORE = Place(12.9716, 77.5946, 900)


def _sunrise_tithi_sequence(start: date, days: int, tz: str = "Asia/Kolkata"):
    ephemeris.set_ayanamsha("lahiri")
    out = []
    d = start
    for _ in range(days):
        jd = _local_midnight_to_jd_ut(d.isoformat(), tz)
        report = classify_day(jd, BANGALORE, d.isoformat())
        out.append(report.tithi_at_sunrise.index)
        d += timedelta(days=1)
    return out


def test_tithi_index_advances_monotonically_allowing_kshaya():
    # Day-to-day tithi-at-sunrise normally advances by 0 (unusual, but
    # possible right at a boundary) or 1. A jump of exactly 2 is expected
    # roughly once a month: "tithi kshaya" -- a tithi so short (due to the
    # Moon's variable speed) that it does not span any sunrise at all that
    # month (see docs/SPEC.md Sec 2.4). A jump of 2 should therefore be
    # rare, not the common case, and never larger than 2.
    seq = _sunrise_tithi_sequence(date(2026, 1, 1), 32)
    skip_count = 0
    for a, b in zip(seq, seq[1:]):
        step = (b - a) % 30
        assert step in (0, 1, 2), (a, b)
        if step == 2:
            skip_count += 1
    assert skip_count <= 2  # at most a couple of kshaya tithis in ~1 month


def test_two_ekadashis_per_lunar_month():
    seq = _sunrise_tithi_sequence(date(2026, 1, 1), 32)
    assert seq.count(11) >= 1  # Shukla Ekadashi
    assert seq.count(26) >= 1  # Krishna Ekadashi


def test_tithi_boundary_time_is_after_the_query_instant():
    ephemeris.set_ayanamsha("lahiri")
    from panchanga.tithi import tithi_at
    jd = _local_midnight_to_jd_ut("2026-01-15", "Asia/Kolkata")
    state = tithi_at(jd)
    assert state.ends_at_jd_ut > jd
    assert 0.0 <= state.fraction_elapsed < 1.0
