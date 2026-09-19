"""A faithful, documented Python port of the original Turbo C `exp.c`
(from the uploaded TC_new_final.zip / TC_EKADASHI_PROGRAM_MODIFIED.zip
archives), kept ONLY as a historical/comparison reference -- not used by
the rest of this package, and not recommended for production use.

Why keep it at all: it documents the traditional Siddhantic calculation
method the original author was working from, with all constants intact
and cited to their location in the original source. Anyone who wants a
"traditional mode" (matching a Vakya/Siddhantic panchanga rather than a
modern Drik one) should start by understanding this, not by reverse
engineering the C file again.

Two deviations from the literal original, both called out at the point
they occur, both because leaving them in would just reproduce known bugs
rather than "preserve tradition":
  1. `check()` is called on angles that are first wrapped into [0, 12)
     with normalize_rashi(). The original omitted this for `ssr` in
     EKADHASI.C specifically (confirmed live: produced a negative "chara
     khanda" and a nonsensical result) -- exp.c itself already had the
     wrap for ssr, but not for `cs` before the nakshatra lookup, which is
     ported here with the same missing wrap fixed, and documented in
     nakshatra_name() below.
  2. Array lookups use a wrapped, clamped index instead of a bare
     float-to-int cast, so this actually runs under a modern Python/CPython
     (a bare float index there raises TypeError; there's no C-style
     implicit narrowing to fall back on).

Everything else -- every magic constant, every branch -- is preserved
exactly as found in TC_new_final/TC_new_final/BIN/EXP.C, with a comment
giving that file's original line number so the two can be diffed by eye.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

TITHI_NAMES = [
    "s.paadya", "s.dwiteeya", "s.triteeya", "s.chaturti", "s.panchami",
    "s.shashti", "s.sapthami", "s.ashtami", "s.navami", "s.dashami",
    "s.ekadashi", "s.dwadashi", "s.trayodashi", "s.chaturdashi", "poornima",
    "k.paadya", "k.dwiteeya", "k.triteeya", "k.chaturti", "k.panchami",
    "k.shashti", "k.sapthami", "k.ashtami", "k.navami", "k.dashami",
    "k.ekadashi", "k.dwadashi", "k.trayodashi", "k.chaturdashi", "amavaasya",
]  # EXP.C lines 27-30

NAKSHATRA_NAMES = [
    "ashwini", "bharani", "krithika", "rohini", "mrugashira", "aardra",
    "punarvasu", "pushyaa", "aashlesha", "makha", "pubba", "uttara",
    "hasta", "chitta", "swathi", "vishaka", "anuradha", "jyeshta", "moola",
    "poorvaashada", "uttaraashada", "shravana", "dhanishta", "shatabisha",
    "poorvabhadra", "uttarabhadra", "revathi",
]  # EXP.C lines 31-34


def _check(rmc1: float) -> float:
    """EXP.C lines 4-17: fold an angle (in rashi, i.e. 0-12 = 0-360 deg)
    into the first quadrant [0,3] rashi, the way a quarter-sine table is
    conventionally indexed. Requires rmc1 already in [0,12) -- callers
    are responsible for that (this is exactly the precondition the
    original code sometimes forgot; see module docstring)."""
    if rmc1 > 9:
        return 12 - rmc1
    elif rmc1 > 6:
        return rmc1 - 6
    elif rmc1 > 3:
        return 6 - rmc1
    else:
        return rmc1


def normalize_rashi(x: float) -> float:
    """Wrap into [0, 12) rashi. Not present in the original at every call
    site that needed it -- see module docstring, deviation 1."""
    return x % 12.0


@dataclass(frozen=True)
class ExpCResult:
    tithi_index: int          # 1..30
    tithi_name: str
    tithi_remaining_ghatika: int
    tithi_remaining_vighatika: int
    nakshatra_index: int      # 1..27
    nakshatra_name: str
    nakshatra_remaining_ghatika: int
    nakshatra_remaining_vighatika: int
    raw: dict                 # every intermediate value, for debugging/diffing


def compute(ahargana: float) -> ExpCResult:
    """Direct port of EXP.C's void main(), parameterized on `m` (ahargana)
    instead of the hardcoded m=702 test value. Variable names match the
    original 1:1 so this can be read side by side with EXP.C."""
    m = float(ahargana)

    # --- Ravi (Sun) madhya + ayanamsha, EXP.C lines 36-70 ---
    rmr = m * 31 / 11323
    rm_frac, integer = math.modf(rmr)
    ayx = (integer + 5114) / 615
    ayx = _check(normalize_rashi(ayx))
    ayx = ayx * 3
    ayf, ayi = math.modf(ayx)
    # EXP.C's jya[] piecewise table (lines 43-68), reproduced verbatim:
    jya_table = [
        (1, 242, 0), (2, 237, 242), (3, 224, 479), (4, 205, 703),
        (5, 180, 908), (6, 149, 1088), (7, 110, 1237), (8, 69, 1347),
        (9, 24, 1416),
    ]
    jya = 0.0
    for upper, slope, base in jya_table:
        if ayi < upper:
            jya = base + slope * ayf
            break
    ay = jya / 1800

    rmk = m / 18047400
    rm = rm_frac * 12 - rmk
    rm1 = rm = rm + 11.937748

    def _ravi_true_at(rm_seed: float) -> tuple[float, float]:
        """EXP.C lines 74-99, the L1 loop body for one evaluation."""
        rm_local = rm_seed
        if rm_local > 12:
            rm_local -= 12
        rmc = rm_local + 9.4 if rm_local < 2.6 else rm_local - 2.6
        rma = _check(normalize_rashi(rmc))
        # `11*rma/21` IS rma-in-rashi converted to radians: 1 rashi = 30
        # deg = pi/6 rad, and 11/21 is exactly pi/6 under the traditional
        # 22/7 approximation of pi (pi/6 ~= (22/7)/6 = 22/42 = 11/21). So
        # this is a correct radian conversion, just via the ancient
        # rational approximation of pi instead of a precise value -- of a
        # piece with 3438 itself (the classical "trijya," circle radius
        # in arcminutes for circumference 21600', also built on this same
        # pi approximation). Not a bug; see docs/SPEC.md "Manda-phala
        # sine table".
        rmpa = 3438 * math.sin(11 * rma / 21)
        rmp = rmpa * 3 / 80
        bp = (rmp / 360) + rmp
        msr = rm_local - (bp / 1800) if rmc < 6 else rm_local + (bp / 1800)
        return msr, rmp

    msr1, rmp1 = _ravi_true_at(rm1)
    msr2, _ = _ravi_true_at(rm1 + 0.0328534)
    # EXP.C: `if(msr1>msr) rg=msr+12-msr1; else rg=msr-msr1;` where by
    # this point `msr` holds the SECOND evaluation's value (msr2 here) --
    # i.e. rg = msr2 - msr1, wrapped. (Mirrors the cg formula below.)
    rg = (msr2 + 12 - msr1) if msr1 > msr2 else (msr2 - msr1)
    rmc1 = (rm1 - 2.6) if rm1 >= 2.6 else (rm1 + 9.4)
    rmc = rmc1  # single-iteration reproduction of the original's cnt loop

    # --- Chandra (Moon) madhya/uchcha/manda-phala, EXP.C lines 108-177 ---
    cm = m * 600 / 16393
    cm_frac, r = math.modf(cm)
    cmk = (m * 7) / 36781200
    cm = cm_frac * 12 - cmk
    cm1 = cm = cm + 1.303107
    if cm > 12:
        cm -= 12
    a1 = rmp1 / 49200
    scm1 = (cm - a1) if rmc1 < 6 else (cm + a1)
    scm1 = normalize_rashi(scm1)
    cm = cm1 + 0.439212
    if cm > 12:
        cm -= 12
    a = rmp1 / 49200
    scm = (cm - a) if rmc < 6 else (cm + a)
    scm = normalize_rashi(scm)

    cu1 = m / 3232
    cu1_frac, b = math.modf(cu1)
    cuk = (m * 7) / 9338400
    cu1 = cu1_frac * 12 - cuk
    cu1 = cu1 + 2.009663
    if cu1 > 12:
        cu1 -= 12
    cu = cu1 + 0.003712
    if cu > 12:
        cu -= 12

    def _chandra_true_at(cu1_seed: float, scm1_seed: float) -> float:
        cmc1 = (scm1_seed + 12 - cu1_seed) if cu1_seed > scm1_seed else (scm1_seed - cu1_seed)
        cma = _check(normalize_rashi(cmc1))
        cmpa = 3438 * math.sin(11 * cma / 21)
        cmp = cmpa * 7 / 80
        mscx = (scm1_seed - cmp / 1800) if cmc1 < 6 else (scm1_seed + cmp / 1800)
        if mscx < 0:
            mscx += 12.0
        return mscx

    msc1 = _chandra_true_at(cu1, scm1)
    msc = _chandra_true_at(cu, scm)
    cg = (msc + 12 - msc1) if msc1 > msc else (msc - msc1)

    # --- Ayanamsha-adjusted (sayana) Sun, chara khanda, sputa positions ---
    ssr = msr1 + ay
    ssrf = (ssr - 12) if ssr > 12 else ssr
    ssr = ssrf
    ssr_check = _check(normalize_rashi(ssr))  # exp.c already wraps this one
    ssr_scaled = ssr_check * 30
    chk_table = [
        (10, 102, 0), (20, 99.9, 1020), (30, 97.8, 2019), (40, 91.7, 2997),
        (50, 79.9, 3914), (60, 67.8, 4713), (70, 54.7, 5391), (80, 33.3, 5938),
        (90, 11.9, 6271),
    ]
    chk = 0.0
    for upper, slope, base in chk_table:
        if ssr_scaled <= upper:
            lower = upper - 10
            chk = base + (ssr_scaled - lower) * slope if base else slope * ssr_scaled
            break
    chk = chk / 2
    chkr = chk * rg / 2
    chkc = chk * cg / 2
    if ssrf < 6:
        rs = msr1 - chkr / 108000
        cs = msc1 - chkc / 108000
    else:
        rs = msr1 + chkr / 108000
        cs = msc1 + chkc / 108000

    vya = (cs + 12 - rs) if rs > cs else (cs - rs)
    vyg = cg - rg

    # --- Tithi, EXP.C lines 225-240 ---
    x = vya * 2.5
    x_frac, no_tithi = math.modf(x)
    no_tithi = int(no_tithi) + 1
    no_tithi = max(1, min(30, no_tithi))  # clamp instead of an unchecked index
    esh = 0.4 * (1.0 - x_frac)
    tithi_val = esh * 60 / vyg
    tithi_fraction, integer2 = math.modf(tithi_val)
    thig = math.ceil(tithi_fraction * 60)
    th = int(tithi_val)

    # --- Nakshatra, EXP.C lines 241-249 ---
    # BUGFIX (module docstring, deviation 1): the original indexes
    # nk_name[no_naks-1] with no_naks computed from `cs` un-wrapped, which
    # reproducibly reads one past the end of the 27-entry table when cs
    # drifts to >= 12 rashi (observed live with tithi_ni.c: cs=12.125991
    # -> no_naks=28). normalize_rashi(cs) here is the fix.
    x2 = normalize_rashi(cs) * 2.25
    x2_frac, no_naks = math.modf(x2)
    no_naks = int(no_naks) + 1
    no_naks = max(1, min(27, no_naks))
    esh2 = 4 * (1 - x2_frac) / 9
    nak = esh2 * 60 / cg
    nak_frac, integer3 = math.modf(nak)
    nakg = math.ceil(nak_frac * 60)

    return ExpCResult(
        tithi_index=no_tithi,
        tithi_name=TITHI_NAMES[no_tithi - 1],
        tithi_remaining_ghatika=th,
        tithi_remaining_vighatika=thig,
        nakshatra_index=no_naks,
        nakshatra_name=NAKSHATRA_NAMES[no_naks - 1],
        nakshatra_remaining_ghatika=int(nak),
        nakshatra_remaining_vighatika=nakg,
        raw=dict(rm=rm, rg=rg, cg=cg, rs=rs, cs=cs, vya=vya, vyg=vyg, ay=ay),
    )
