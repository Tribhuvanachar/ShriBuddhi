"""Cross-check panchanga.legacy.exp_c_reference against a LIVE run of the
actual compiled EXP.C (m=702), not just against hand recomputation.

Reference values below were captured by compiling TC_new_final's EXP.C
with a modern C compiler (stubbing conio.h's clrscr/getch, and casting the
double array indices to int since standard C forbids non-integer
subscripts) and running the resulting binary. See the analysis notes for
the exact commands.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panchanga.legacy.exp_c_reference import compute

EXP_C_LIVE_RUN_M702 = {
    "tithi_index": 27,
    "tithi_name": "k.dwadashi",
    "tithi_remaining": (43, 22),
    "nakshatra_index": 22,
    "nakshatra_name": "shravana",
    "nakshatra_remaining": (28, 46),
}


def test_matches_live_compiled_exp_c_at_m702():
    result = compute(702)
    assert result.tithi_index == EXP_C_LIVE_RUN_M702["tithi_index"]
    assert result.tithi_name == EXP_C_LIVE_RUN_M702["tithi_name"]
    assert (result.tithi_remaining_ghatika, result.tithi_remaining_vighatika) == \
        EXP_C_LIVE_RUN_M702["tithi_remaining"]
    assert result.nakshatra_index == EXP_C_LIVE_RUN_M702["nakshatra_index"]
    assert result.nakshatra_name == EXP_C_LIVE_RUN_M702["nakshatra_name"]
    assert (result.nakshatra_remaining_ghatika, result.nakshatra_remaining_vighatika) == \
        EXP_C_LIVE_RUN_M702["nakshatra_remaining"]


def test_tithi_and_nakshatra_indices_always_in_range():
    # Bugfix regression: the original could read nk_name[27] (out of
    # bounds for a 27-entry table) when cs drifted >= 12 rashi. Sweep a
    # range of ahargana values to make sure the clamp holds.
    for m in range(500, 2000, 37):
        result = compute(m)
        assert 1 <= result.tithi_index <= 30
        assert 1 <= result.nakshatra_index <= 27
