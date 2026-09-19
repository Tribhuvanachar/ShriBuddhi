"""Thin, documented wrapper around the Swiss Ephemeris (pyswisseph).

Why Swiss Ephemeris: it is the de-facto standard library behind most
production Hindu-calendar ("panchanga") software. It gives Sun/Moon/planet
positions accurate to arc-seconds without requiring us to re-derive orbital
theory, and it ships built-in support for the ayanamsha systems different
panchanga traditions actually use (Lahiri/Chitrapaksha, Raman, KP, ...).

Precision mode: by default this module uses Swiss Ephemeris's built-in
"Moshier" semi-analytic model (SEFLG_MOSEPH), which needs no external data
files and is accurate to a few arc-seconds for the Sun and Moon over the
last few centuries -- more than sufficient for tithi/nakshatra timing,
where the practically relevant question is "when does elongation cross a
12-degree boundary," not sub-arcsecond astrometry. If sub-arcsecond
precision (e.g. for eclipse contact timings) is later required, download
the JPL DE-series ephemeris files from Astrodienst and point
`swe.set_ephe_path()` at them; the rest of this codebase does not need to
change.
"""
from __future__ import annotations

import swisseph as swe

SUN = swe.SUN
MOON = swe.MOON
MERCURY = swe.MERCURY
VENUS = swe.VENUS
MARS = swe.MARS
JUPITER = swe.JUPITER
SATURN = swe.SATURN
MEAN_NODE = swe.MEAN_NODE  # Rahu (mean); Ketu = MEAN_NODE + 180 deg
TRUE_NODE = swe.TRUE_NODE

# Ayanamsha choices, keyed by the name a caller will pass in. This is not
# an exhaustive list -- add more from swe.SIDM_* as traditions require it.
# See docs/SPEC.md "Ayanamsha" for why the choice of ayanamsha is a policy
# decision, not a bug to be "fixed."
AYANAMSHA_MODES = {
    "lahiri": swe.SIDM_LAHIRI,       # Indian government (Chitrapaksha) standard
    "raman": swe.SIDM_RAMAN,
    "kp": swe.SIDM_KRISHNAMURTI,
    "true_chitra": swe.SIDM_TRUE_CITRA,
    "surya_siddhanta": swe.SIDM_SURYASIDDHANTA,
}

DEFAULT_AYANAMSHA = "lahiri"

_CALC_FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
_FALLBACK_FLAGS = swe.FLG_MOSEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED


def set_ayanamsha(mode: str = DEFAULT_AYANAMSHA) -> None:
    if mode not in AYANAMSHA_MODES:
        raise ValueError(
            f"Unknown ayanamsha {mode!r}; known modes: {sorted(AYANAMSHA_MODES)}"
        )
    swe.set_sid_mode(AYANAMSHA_MODES[mode])


def julian_day_ut(year: int, month: int, day: int, ut_hour: float) -> float:
    """Julian Day Number for a UTC calendar date/time.

    Deliberately delegates to Swiss Ephemeris's own Gregorian calendar
    arithmetic (swe.julday) rather than a hand-rolled formula, so this
    codebase carries exactly one implementation of calendar-to-JD
    conversion, already validated by a widely used library.
    """
    return swe.julday(year, month, day, ut_hour, swe.GREG_CAL)


def sidereal_longitude(body: int, jd_ut: float) -> tuple[float, float]:
    """Sidereal ecliptic longitude (degrees, 0-360) and daily motion
    (degrees/day) of `body` at Julian Day `jd_ut`, under whatever
    ayanamsha was last selected with set_ayanamsha().

    Falls back from the Swiss Ephemeris file-based model to the built-in
    Moshier model automatically if no ephemeris data files are installed.
    """
    try:
        values, ret_flag = swe.calc_ut(jd_ut, body, _CALC_FLAGS)
    except swe.Error:
        values, ret_flag = swe.calc_ut(jd_ut, body, _FALLBACK_FLAGS)
    longitude, _latitude, _distance, speed_long, *_ = values
    return longitude % 360.0, speed_long


def ayanamsha_value(jd_ut: float) -> float:
    """Current ayanamsha (degrees) at Julian Day `jd_ut`, for display/audit."""
    return swe.get_ayanamsa_ut(jd_ut)
