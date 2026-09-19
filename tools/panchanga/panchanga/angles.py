"""Angle-wrapping and boundary-crossing-time utilities shared by tithi.py
and nakshatra.py.

This is where the original code's two confirmed bugs lived (missing
mod-360 wraps before array indexing / before calling its quadrant-folding
`check()` function). `normalize_deg` below exists specifically so every
angle used for indexing or comparison in this codebase is wrapped exactly
once, in exactly one place, instead of ad hoc at each call site.
"""
from __future__ import annotations

from typing import Callable


def normalize_deg(angle_deg: float) -> float:
    """Wrap an angle into [0, 360)."""
    return angle_deg % 360.0


def find_boundary_crossing_jd(
    angle_at_jd: Callable[[float], float],
    jd_low: float,
    jd_high: float,
    boundary_deg: float,
    tolerance_days: float = 1e-6,
) -> float:
    """Bisect for the Julian Day in [jd_low, jd_high] at which
    `angle_at_jd(jd) % 360` crosses `boundary_deg`, given that
    `angle_at_jd` increases monotonically (mod 360, without wrapping more
    than once) over that interval -- true for solar/lunar elongation and
    for the Moon's own longitude over spans of a few hours to ~1.5 days,
    which is the only regime this is used in (see tithi.py / nakshatra.py).

    tolerance_days=1e-6 is about 0.09 seconds -- far tighter than the
    underlying ephemeris's absolute accuracy, chosen only so the bisection
    itself never limits precision.
    """
    def signed_offset(jd: float) -> float:
        # Offset of the angle from the boundary, unwrapped to (-180, 180]
        # so bisection sees a monotonic, sign-changing function rather
        # than a sawtooth.
        return ((angle_at_jd(jd) - boundary_deg + 180.0) % 360.0) - 180.0

    low, high = jd_low, jd_high
    f_low = signed_offset(low)
    f_high = signed_offset(high)
    if f_low == 0.0:
        return low
    if f_low > 0 > f_high or f_low < 0 < f_high:
        pass  # sign change present, as expected
    else:
        raise ValueError(
            "No sign change in [jd_low, jd_high]; boundary is not crossed "
            "in this interval (widen the search window)."
        )

    while (high - low) > tolerance_days:
        mid = (low + high) / 2.0
        f_mid = signed_offset(mid)
        if (f_mid > 0) == (f_low > 0):
            low, f_low = mid, f_mid
        else:
            high, f_high = mid, f_mid
    return (low + high) / 2.0
