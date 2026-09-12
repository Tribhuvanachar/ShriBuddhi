"""The Indic-script fold in build_search_index.py (31 Aug 2026).

The Kannada-script Yuktimallika (DvaitaVedanta/Itara/DasaSahitya/vyasakuta/vadiraja_tirtha,
5,542 units) was dropped wholesale by the has_devanagari stub gate, so
स्तुत्या could never find its opening ಭಕ್ತ್ಯಾ ಸ್ತುತ್ಯಾ. These tests pin the
fold's contract: aligned Indic blocks transpose to Devanagari for indexing,
Devanagari passes through untouched, and genuinely non-Indic text still
reads as a stub.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "build_search_index", ROOT / "build_search_index.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def test_kannada_folds_to_identical_devanagari():
    folded = B.fold_indic_to_devanagari("ಭಕ್ತ್ಯಾ ಸ್ತುತ್ಯಾ ವಿರಕ್ತ್ಯಾ")
    assert folded == "भक्त्या स्तुत्या विरक्त्या"
    assert B.has_devanagari(folded)


def test_telugu_folds():
    assert B.fold_indic_to_devanagari("రామ") == "राम"


def test_devanagari_passes_through():
    text = "वृद्धिरादैच् ॥१॥"
    assert B.fold_indic_to_devanagari(text) == text


def test_latin_stub_still_a_stub():
    folded = B.fold_indic_to_devanagari("Sanskrit text goes here...")
    assert not B.has_devanagari(folded)


def test_pkey_parity_with_devanagari_query():
    """The folded Kannada text must produce the same phonetic key a
    Devanagari query produces -- that equality is what makes the word
    index find the unit."""
    from search_toolkit_pkg.translit import to_slp1
    from search_toolkit_pkg.normalize import phonetic_key
    kn = B.fold_indic_to_devanagari("ಸ್ತುತ್ಯಾ")
    assert phonetic_key(to_slp1(kn, "devanagari")) == \
        phonetic_key(to_slp1("स्तुत्या", "devanagari"))
