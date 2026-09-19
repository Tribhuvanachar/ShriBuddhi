"""Panchanga engine: sunrise/moonrise-aware tithi, nakshatra, and Ekadashi
determination, built on the Swiss Ephemeris.

See docs/SPEC.md for the algorithm, the unit conventions, and citations for
every constant used here. This package intentionally does not reproduce the
1990s-era truncated trigonometric approximations found in the original
Turbo C programs (see panchanga/legacy/) as its primary engine: those are
kept only as a documented historical reference.
"""
