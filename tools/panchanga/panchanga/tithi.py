"""Tithi (lunar day) determination.

Core relation (unchanged from the traditional method, and correctly
implemented in the original exp.c/tithi_ni.c/tith_exp.cpp): a tithi is one
30th of a synodic month, i.e. one 12-degree step of lunar elongation
(Moon's sidereal longitude minus Sun's sidereal longitude). Tithi 1
(Shukla Pratipada) covers elongation [0,12); tithi 15 (Purnima) covers
[168,180); tithi 16 (Krishna Pratipada) covers [180,192); tithi 30
(Amavasya) covers [348,360).

What changes from the original code:
  - Elongation comes from Swiss Ephemeris sidereal positions, not a
    5-6-term trigonometric table, so it is accurate to arc-seconds rather
    than (unverified, likely) arc-minutes.
  - The end-time of the current tithi is found by bisecting the actual
    elongation function to its exact 12-degree boundary (angles.py),
    instead of a linear extrapolation from the daily motion at one instant
    -- this matters because elongation rate is not constant.
  - The Moon never retrogrades, and neither does the Sun, so elongation
    increases monotonically through an entire tithi; the bisection in
    angles.py is safe for exactly this reason (documented there).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import ephemeris
from .angles import find_boundary_crossing_jd, normalize_deg

TITHI_NAMES = [
    "Shukla Pratipada", "Shukla Dwitiya", "Shukla Tritiya", "Shukla Chaturthi",
    "Shukla Panchami", "Shukla Shashthi", "Shukla Saptami", "Shukla Ashtami",
    "Shukla Navami", "Shukla Dashami", "Shukla Ekadashi", "Shukla Dwadashi",
    "Shukla Trayodashi", "Shukla Chaturdashi", "Purnima",
    "Krishna Pratipada", "Krishna Dwitiya", "Krishna Tritiya", "Krishna Chaturthi",
    "Krishna Panchami", "Krishna Shashthi", "Krishna Saptami", "Krishna Ashtami",
    "Krishna Navami", "Krishna Dashami", "Krishna Ekadashi", "Krishna Dwadashi",
    "Krishna Trayodashi", "Krishna Chaturdashi", "Amavasya",
]

TITHI_ARC_DEG = 12.0
TITHI_COUNT = 30


@dataclass(frozen=True)
class TithiState:
    index: int              # 1..30
    name: str
    elongation_deg: float   # current Moon-minus-Sun elongation, 0-360
    fraction_elapsed: float  # 0..1 through the current tithi
    ends_at_jd_ut: float    # Julian Day (UT) the current tithi ends


def _elongation_deg(jd_ut: float) -> float:
    sun_long, _ = ephemeris.sidereal_longitude(ephemeris.SUN, jd_ut)
    moon_long, _ = ephemeris.sidereal_longitude(ephemeris.MOON, jd_ut)
    return normalize_deg(moon_long - sun_long)


def tithi_at(jd_ut: float) -> TithiState:
    elongation = _elongation_deg(jd_ut)
    index0 = int(elongation // TITHI_ARC_DEG)  # 0..29
    index0 = min(index0, TITHI_COUNT - 1)
    fraction_elapsed = (elongation - index0 * TITHI_ARC_DEG) / TITHI_ARC_DEG
    boundary_deg = normalize_deg((index0 + 1) * TITHI_ARC_DEG)

    # Tithis run 19h to 26h; search a generous +/-2-day bracket for the
    # boundary crossing. See angles.find_boundary_crossing_jd for why this
    # bisection is valid (elongation is monotonically increasing).
    ends_at = find_boundary_crossing_jd(
        _elongation_deg, jd_ut, jd_ut + 2.0, boundary_deg,
    )
    return TithiState(
        index=index0 + 1,
        name=TITHI_NAMES[index0],
        elongation_deg=elongation,
        fraction_elapsed=fraction_elapsed,
        ends_at_jd_ut=ends_at,
    )


def is_ekadashi(state: TithiState) -> bool:
    return state.index in (11, 26)
