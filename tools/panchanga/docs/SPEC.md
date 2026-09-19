# Panchanga engine — specification

This document is the source of truth for *what* is being calculated and
*why*. Code should be disposable; this should not be. Anyone reimplementing
this in a different language in twenty years should be able to do it from
this file alone, without reading a line of the code.

Status: **v0.1 — foundational layer only.** Sunrise/sunset/moonrise/moonset,
accurate tithi and nakshatra with real boundary times, and a base
(non-viddha) Ekadashi flag are implemented and tested. Everything under
"Not yet built" below is scoped but not started.

## 1. Origin and why this rewrite exists

This package replaces a set of Turbo C programs (`EXP.C`, `EKADHASI.C`,
`TITHI-NI.C`, `TITH_EXP.CPP`, found in `TC_new_final.zip` /
`TC_EKADASHI_PROGRAM_MODIFIED.zip`) written for DOS in the early 1990s
through 2014. Those programs correctly identify *which* tithi is active
from lunar elongation (verified by running them), but:

- have no sunrise/sunset/moonrise/moonset calculation at all (confirmed by
  exhaustive grep for `sunrise|udaya|arunodaya` across every source file —
  zero matches). Every "time remaining in this tithi" figure they print
  was compared against sunrise **by hand**, outside the program.
- approximate Sun/Moon position with a handful of terms of a manually
  transcribed trigonometric table, calibrated (via hand-tuned "deemed
  correction" constants, different in each file) to an unstated date range
  and an unstated location.
- have two reproducible bugs: (a) `EKADHASI.C` calls its quadrant-folding
  `check()` function on an angle (`ssr`) without first wrapping it into
  [0,12) rashi, producing a negative "chara khanda" and a nonsensical
  result when `ssr` exceeds 12; (b) every variant (`EXP.C` included) uses
  the Moon's true longitude `cs` to index a 27-entry nakshatra name table
  *without* wrapping it, which reproducibly reads one past the end of the
  array once `cs` drifts to ≥ 12 rashi (observed live: `cs=12.125991` →
  index 28 into a 0–26 table).
- take no location or timezone input at all — the ahargana (day count) is
  a hardcoded constant edited by hand and the program recompiled per date.

The traditional method itself is preserved, bugs and all documented, in
`panchanga/legacy/exp_c_reference.py`, verified byte-for-byte against a
live compiled run of the original `EXP.C` (see that file's tests). It is
kept as a historical reference and as the eventual basis for a
"traditional/Siddhantic mode," not as the production engine.

## 2. Core astronomical layer

### 2.1 Why Swiss Ephemeris

`panchanga/ephemeris.py` wraps `pyswisseph`. Reasons:
- Gives Sun/Moon/planet positions to arc-second accuracy without this
  project re-deriving orbital theory.
- It is the de facto standard behind most production Hindu-calendar
  software, which matters for cross-checking our output against other
  tools.
- Ships built-in support for the ayanamsha systems different panchanga
  traditions actually use.
- Its built-in "Moshier" analytic model needs no external data files and
  is already accurate to a few arc-seconds for Sun/Moon over the last few
  centuries — file-based JPL ephemerides (for higher precision, e.g. exact
  eclipse contact timings) can be added later without changing any other
  module.

### 2.2 Ayanamsha — a policy choice, not a bug

Sidereal longitude = tropical longitude − ayanamsha. Different published
panchangas use different ayanamsha values (Lahiri/Chitrapaksha — the
Indian government standard — Raman, KP/Krishnamurti, and others), and they
disagree by up to roughly a degree, enough to shift a sankranti or a
tithi's sunrise-tithi status. `ephemeris.AYANAMSHA_MODES` exposes the
choice explicitly; `lahiri` is the default. **Any output must state which
ayanamsha it used.** This is not something to "fix" by picking one true
value — see §5.

### 2.3 Sunrise, sunset, moonrise, moonset

`panchanga/sunrise.py`, via `swe.rise_trans()`. Inputs: latitude,
longitude, elevation (meters), and the civil date's local midnight
expressed as a UT Julian Day (the caller — currently `cli.py` — does the
timezone conversion). Refraction and the body's angular radius are
included by Swiss Ephemeris; we do not model them separately.

### 2.4 Tithi

Tithi = ⌈elongation / 12°⌉, where elongation = (Moon's sidereal longitude
− Sun's sidereal longitude) mod 360°. Tithi 1 (Shukla Pratipada) is
elongation [0°,12°); tithi 15 (Purnima) is [168°,180°); tithi 16 (Krishna
Pratipada) is [180°,192°); tithi 30 (Amavasya) is [348°,360°).

The **end time** of the current tithi is found by bisecting the actual
elongation function to the next 12° boundary (`panchanga/angles.py`,
`find_boundary_crossing_jd`), not by linear extrapolation from the
instantaneous rate at one moment (which is what the original code did,
and which becomes increasingly wrong as tithi duration deviates from the
mean 59 ghatika value). This bisection is valid because neither the Sun
nor the Moon ever appears to retrograde, so elongation increases
monotonically within any given tithi.

**Tithi kṣaya**: because the Moon's angular speed varies (perigee vs.
apogee), a tithi can be short enough that it does not span *any* sunrise
in a given month, and (rarely) a tithi can be long enough to span two
consecutive sunrises. This is expected, correct behavior, not a bug — the
v0.1 test suite specifically checks that a full lunar month produces
exactly one skipped tithi index (confirmed for January 2026 at one test
location: Krishna Panchami and Shukla Chaturdashi were both absent at
sunrise that month). **This is also a primary source of real
cross-panchanga disagreement** — see §5.

### 2.5 Nakshatra

Nakshatra = ⌈Moon's sidereal longitude / (360/27)°⌉. Same boundary-time
bisection approach as tithi. This is exactly the calculation where the
original code's array-bounds bug lived (§1) — `panchanga/nakshatra.py`
wraps the Moon's longitude into [0,360) via `angles.normalize_deg` before
every use, in one place, specifically so that class of bug cannot recur.

## 3. Ahargana (traditional-mode only)

Ahargana is the count of mean solar days elapsed since the Kali Yuga
epoch, conventionally placed at Julian Day ≈ 588465.5 (mean sunrise,
proleptic Julian calendar, 18 February 3102 BCE) — though the exact
offset (by up to about a day) varies by which Siddhantic text or
panchanga tradition is being followed.

**This package's accurate/ephemeris-based engine (§2) does not use
Ahargana at all** — Swiss Ephemeris takes a Julian Day directly, computed
from the Gregorian calendar date via `swe.julday()`. Ahargana only matters
if/when a faithful "traditional Siddhantic mode" is built on top of
`panchanga/legacy/exp_c_reference.py`; at that point the exact epoch
offset needs to be empirically calibrated against a handful of
independently-known reference dates before being trusted, not taken from
a single textbook citation. **Not yet done — flagged, not solved.**

## 4. Ekadashi (and other tithi) observance-day determination

`panchanga/ekadashi.py` currently implements only the rule shared by every
tradition: the tithi *prevailing at sunrise* governs the civil day's
observance. This alone reproduces the base cases correctly. It does **not
yet** implement:

- **Viddha tie-breaking.** When Dashami tithi overlaps sunrise on the same
  day Ekadashi also occurs (or the symmetric case at the Ekadashi/Dwadashi
  boundary, which governs parana timing), different traditions resolve it
  differently. The exact thresholds must come from a citable source before
  they are encoded — this is explicitly not guessed at in v0.1.
- **The Smarta / Vaishnava (ISKCON) split** for both Ekadashi and Krishna
  Janmashtami. Janmashtami additionally requires the Rohini-nakshatra +
  Ashtami-tithi overlap condition, which the two traditions weight
  differently.

Every output from this module must be labeled with which rule produced it
(currently: "base sunrise rule, no viddha refinement") rather than
presented as a single unqualified verdict.

## 5. Why there is no single "correct" date — and what accuracy means here

Two independent sources of legitimate disagreement exist, and a serious
tool must expose both as explicit, labeled choices rather than resolve
them silently:

1. **Which astronomical model.** Traditional Vakya/Siddhantic panchangas
   and modern Drik (ephemeris-based) panchangas can disagree by minutes to
   hours on a tithi boundary near sunrise, which can flip a viddha
   decision. This package's accurate engine (§2) is a Drik-style
   calculation; the legacy module (§1) is a specific, buggy, single
   author's approximation of the traditional method, kept for reference
   only until a properly cited traditional mode is built.
2. **Which sampradaya's vrata rules.** Given the *same* correct tithi
   timing, Smarta and Vaishnava (and other) traditions can still choose
   different observance days (§4).

"Accuracy" therefore has two independent axes: (a) how close the computed
Sun/Moon position is to physical reality — this axis has an objectively
better answer (arc-seconds via Swiss Ephemeris beats arc-minutes via a
six-term table), and (b) which named tradition's rules are applied on top
— this axis has no universal answer and must be selectable and labeled,
never asserted as *the* answer.

## 6. Not yet built (roadmap)

Each of these becomes tractable once §2–§4 are solid, and none requires
re-deriving astronomy from scratch — Swiss Ephemeris / Skyfield already
solve the hard parts:

- **Other grahas** (Mercury, Venus, Mars, Jupiter, Saturn, Rahu/Ketu):
  positions via `ephemeris.sidereal_longitude()`, already wired for any
  body constant Swiss Ephemeris supports.
- **Vakra (retrograde) detection**: sign of the daily-motion (`speed`)
  value already returned by `sidereal_longitude()`.
- **Graha udaya/asta (heliacal rise/set)**: needs elongation-from-Sun +
  altitude-at-twilight modeling; Swiss Ephemeris has heliacal-event
  functions (`swe.heliacal_ut` family) — do not re-derive this by hand.
- **Grahana (eclipses)**: Swiss Ephemeris has eclipse-finding functions
  (`swe.sol_eclipse_when_glob`, `swe.lun_eclipse_when`, etc.) — likewise,
  use them rather than deriving conjunction/node geometry from scratch.
- **Rashi Sankramana**: zero-crossing of solar sidereal longitude mod 30°,
  found the same way tithi/nakshatra boundaries are (§2.4/2.5's bisection
  approach, generalized).
- **Ayana (solstices) / Vishuva (equinoxes)**: zero-crossing of solar
  *tropical* (not sidereal) longitude at 90°/270° and 0°/180°.
- **Named yogas** (Guru Pushya, Ravi Pushya, etc.): boolean combinations of
  (vara, nakshatra-at-sunrise) once those are correct — trivial once the
  base layer is trusted, but depends on §5's tradition choice for exactly
  which nakshatra-at-sunrise rule to use.
- **Upcoming-event notifications**: an application-layer scheduler diffing
  computed dates against "today" — not an astronomy problem.
- **Interface**: not yet started; needs a decision on hosting stack for
  the "DG project" this is destined for.

## 7. Testing philosophy

Every new calculation should get: (a) a self-consistency check (e.g. tithi
index advances by 0 or 1 each day, wrapping 30→1, as in
`tests/test_tithi.py`), and (b) where possible, a cross-check against the
legacy port for the *same underlying formula* (as in
`tests/test_legacy_reference.py`, which checks the ported traditional
engine against a live run of the actual compiled `EXP.C`) or against an
independent published reference for the *modern* engine. Do not merge a
new calculation with only (a).
