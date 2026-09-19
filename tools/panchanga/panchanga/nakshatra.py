"""Nakshatra (lunar mansion) determination: one 27th of the ecliptic
(13 deg 20' = 360/27 degrees) of the Moon's own sidereal longitude.

This is the exact computation where the original code had its confirmed,
reproducible bug: cs (the Moon's true longitude) was used to index a
27-entry name table without first wrapping it into [0,360)/[0,12 rashi),
so a value that drifted to just past a full circle produced an
out-of-bounds array read (observed live: cs=12.125991 rashi ->
index 28 into a 27-entry table). normalize_deg() in angles.py, applied
before every use of an angle below, is the fix, applied at the single
place where every angle used for indexing is produced.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import ephemeris
from .angles import find_boundary_crossing_jd, normalize_deg

NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]

NAKSHATRA_ARC_DEG = 360.0 / 27.0
NAKSHATRA_COUNT = 27


@dataclass(frozen=True)
class NakshatraState:
    index: int              # 1..27
    name: str
    moon_longitude_deg: float
    fraction_elapsed: float
    ends_at_jd_ut: float


def _moon_longitude_deg(jd_ut: float) -> float:
    moon_long, _ = ephemeris.sidereal_longitude(ephemeris.MOON, jd_ut)
    return normalize_deg(moon_long)


def nakshatra_at(jd_ut: float) -> NakshatraState:
    longitude = _moon_longitude_deg(jd_ut)
    index0 = int(longitude // NAKSHATRA_ARC_DEG)
    index0 = min(index0, NAKSHATRA_COUNT - 1)
    fraction_elapsed = (longitude - index0 * NAKSHATRA_ARC_DEG) / NAKSHATRA_ARC_DEG
    boundary_deg = normalize_deg((index0 + 1) * NAKSHATRA_ARC_DEG)

    # The Moon crosses one nakshatra roughly every ~1 day (up to ~30h);
    # a 2-day bracket is generous. Monotonic because the Moon does not
    # retrograde (see angles.find_boundary_crossing_jd).
    ends_at = find_boundary_crossing_jd(
        _moon_longitude_deg, jd_ut, jd_ut + 2.0, boundary_deg,
    )
    return NakshatraState(
        index=index0 + 1,
        name=NAKSHATRA_NAMES[index0],
        moon_longitude_deg=longitude,
        fraction_elapsed=fraction_elapsed,
        ends_at_jd_ut=ends_at,
    )
