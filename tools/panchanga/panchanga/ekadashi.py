"""Ekadashi (and, by the same mechanism, any other named tithi's)
observance-day determination.

IMPORTANT - READ BEFORE TRUSTING THIS MODULE'S OUTPUT:

This implements only the base, largely uncontested rule shared by every
tradition: the tithi PREVAILING AT SUNRISE governs which civil day a tithi
observance falls on (not the tithi at midnight, and not "whichever day
most of the tithi falls in"). That rule alone is enough for the common
case, and is what `tithi_governing_sunrise()` / `classify_day()` compute.

What is deliberately NOT yet implemented, because it varies by sampradaya
and needs sourcing rather than guessing:
  - "Viddha" tie-breaking when a tithi is unusually short or long, e.g.
    whether a small overlap of Dashami into sunrise disqualifies that day
    for Vaishnava Ekadashi observance even though Ekadashi is also present
    that day ("Dashami-vyapini" disqualification), or the symmetric
    question at the Ekadashi/Dwadashi boundary that governs parana timing.
  - The Smarta/Vaishnava split itself: Vaishnava tradition is generally
    stricter about excluding any Dashami overlap at sunrise than Smarta
    tradition is. The exact thresholds need a citable source before they
    go into code -- do not hardcode a specific tolerance here without one.
  - Krishna Janmashtami's analogous (and distinct) Rohini-nakshatra +
    Ashtami-tithi overlap conditions, which differ again between Smarta
    and Vaishnava/ISKCON reckoning.

Treat `classify_day()`'s output as "which tithi is at sunrise," labelled
plainly as such, not as a final vrata verdict, until the viddha rules
above are added with citations and reviewed.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import sunrise as sunrise_mod
from . import tithi as tithi_mod
from .sunrise import Place


@dataclass(frozen=True)
class DayTithiReport:
    civil_date: str                 # ISO date, for display
    sunrise_jd_ut: float | None
    tithi_at_sunrise: tithi_mod.TithiState | None
    is_ekadashi_by_sunrise_rule: bool
    note: str


def classify_day(jd_midnight_ut: float, place: Place, civil_date_label: str) -> DayTithiReport:
    """`jd_midnight_ut` should be the JD for that civil date's 00:00 in the
    place's own local time, expressed as UT (i.e. already timezone-shifted
    by the caller -- see cli.py)."""
    events = sunrise_mod.sun_moon_events(jd_midnight_ut, place)
    sunrise_jd = events["sunrise"]
    if sunrise_jd is None:
        return DayTithiReport(
            civil_date=civil_date_label,
            sunrise_jd_ut=None,
            tithi_at_sunrise=None,
            is_ekadashi_by_sunrise_rule=False,
            note="No sunrise this civil day at this location (polar case?).",
        )
    state = tithi_mod.tithi_at(sunrise_jd)
    return DayTithiReport(
        civil_date=civil_date_label,
        sunrise_jd_ut=sunrise_jd,
        tithi_at_sunrise=state,
        is_ekadashi_by_sunrise_rule=tithi_mod.is_ekadashi(state),
        note=(
            "Base sunrise-tithi rule only; viddha/sampradaya refinement "
            "not yet applied -- see module docstring."
        ),
    )
