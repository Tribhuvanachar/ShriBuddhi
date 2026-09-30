"""The WordNet builder must write NFC, and merge spellings that collapse under NFC.

data/_wordnet/B_a.json once held the word भड़्ग twice: written ड + nukta
(U+0921 U+093C) and as the single character U+095C, which Unicode excludes from
composition, so NFC splits it. Both spellings are one word. normalize_nfc.py
refuses to merge keys (it would be guessing), which failed the CI gate; the
builder is where two spellings should become one key.
"""
import os
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_wordnet as bw  # noqa: E402

DECOMPOSED = "भड़्ग"   # ड + nukta (the NFC form)
EXCLUDED = "भड़्ग"            # U+095C, composition-excluded


def test_the_two_spellings_are_different_strings_but_one_nfc_word():
    assert DECOMPOSED != EXCLUDED
    assert unicodedata.normalize("NFC", EXCLUDED) == DECOMPOSED


def test_nfc_helper_normalises_nested_structures_and_leaves_other_types():
    rec = ["n", EXCLUDED, [EXCLUDED, "x"], 5]
    out = bw._nfc(rec)
    assert out == ["n", DECOMPOSED, [DECOMPOSED, "x"], 5]
    assert all(unicodedata.normalize("NFC", s) == s
               for s in (out[1], out[2][0], out[2][1]))


def test_keys_for_normalised_words_coincide():
    k1 = bw.keys_for(unicodedata.normalize("NFC", DECOMPOSED + "ः"))
    k2 = bw.keys_for(unicodedata.normalize("NFC", EXCLUDED + "ः"))
    assert k1 == k2
