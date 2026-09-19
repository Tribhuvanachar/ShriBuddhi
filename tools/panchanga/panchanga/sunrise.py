"""Sunrise, sunset, moonrise, moonset for a given place and civil date.

This is the module that was entirely absent from the original Turbo C
programs (verified by exhaustive grep across every .C/.CPP/.BAK/.TXT/.DOC
file in the supplied archives: no "sunrise", "udaya", or "arunodaya" term,
and no rise/set computation of any kind). Every tithi-boundary time those
programs printed was an elapsed ghatika-vighatika count from an implicit,
never-computed reference instant, compared against sunrise by hand by
whoever ran the program. That manual step is what this module replaces.

Sunrise/sunset/moonrise/moonset are location-dependent (latitude,
longitude, elevation) and date-dependent (the Sun's declination changes
through the year). Swiss Ephemeris's swe.rise_trans() solves the real
spherical-astronomy problem -- including atmospheric refraction and the
body's angular radius -- rather than approximating it with a fixed
per-location table, which is what the original code's fixed "chara
khanda" coefficients effectively (and silently) assumed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import swisseph as swe

from . import ephemeris


@dataclass(frozen=True)
class Place:
    latitude_deg: float   # +north
    longitude_deg: float  # +east
    elevation_m: float = 0.0


def _rise_trans(jd_start_ut: float, body: int, place: Place, event: int) -> float | None:
    """Returns the JD (UT) of the next `event` for `body` after `jd_start_ut`,
    or None if the body does not rise/set that day (polar cases)."""
    geopos = (place.longitude_deg, place.latitude_deg, place.elevation_m)
    ret, times = swe.rise_trans(jd_start_ut, body, event, geopos)
    if ret != 0:
        return None
    return times[0]


def sun_moon_events(jd_midnight_ut: float, place: Place) -> dict[str, float | None]:
    """Sunrise/sunset/moonrise/moonset (Julian Day, UT) for the civil day
    that starts at `jd_midnight_ut` (i.e. pass the JD for 00:00 UT of the
    date you care about, adjusted by the place's timezone offset by the
    caller -- see cli.py for the end-to-end example)."""
    return {
        "sunrise": _rise_trans(jd_midnight_ut, ephemeris.SUN, place, swe.CALC_RISE),
        "sunset": _rise_trans(jd_midnight_ut, ephemeris.SUN, place, swe.CALC_SET),
        "moonrise": _rise_trans(jd_midnight_ut, ephemeris.MOON, place, swe.CALC_RISE),
        "moonset": _rise_trans(jd_midnight_ut, ephemeris.MOON, place, swe.CALC_SET),
    }


def jd_to_utc_datetime(jd_ut: float) -> datetime:
    year, month, day, ut_hour = swe.revjul(jd_ut, swe.GREG_CAL)
    hour = int(ut_hour)
    minute_float = (ut_hour - hour) * 60
    minute = int(minute_float)
    second = (minute_float - minute) * 60
    return datetime(year, month, day, hour, minute, int(second), tzinfo=timezone.utc)
