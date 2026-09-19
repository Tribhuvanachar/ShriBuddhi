# panchanga

A sunrise-anchored tithi/nakshatra/Ekadashi engine, built to replace the
Turbo C `EXP.C`/`EKADHASI.C`/`TITHI-NI.C`/`TITH_EXP.CPP` programs found in
`TC_new_final.zip` / `TC_EKADASHI_PROGRAM_MODIFIED.zip`.

**Start with `docs/SPEC.md`** — it documents what is calculated, why, what
was wrong with the original code (with live-verified evidence), and what
is deliberately not yet built. This README is just how to run it.

## Status: v0.1, foundational layer

Done: sunrise/sunset/moonrise/moonset, accurate tithi and nakshatra
(Swiss-Ephemeris-based, with real boundary-crossing times via bisection),
and a base (non-viddha) Ekadashi flag. See `docs/SPEC.md` Sec 6 for
everything not yet built (other grahas, eclipses, sankranti, ayana/vishuva,
named yogas, sampradaya-specific viddha rules, an interface).

## Setup

```
pip install -r requirements.txt
```

## Usage

```
python -m panchanga.cli --date 2026-01-14 --lat 12.9716 --lon 77.5946 \
    --tz Asia/Kolkata --ayanamsha lahiri
```

## Tests

```
pip install pytest
python -m pytest tests/ -v
```

`tests/test_legacy_reference.py` cross-checks the ported traditional
engine (`panchanga/legacy/exp_c_reference.py`) against a live run of the
actual compiled original `EXP.C` — not just hand recomputation.
