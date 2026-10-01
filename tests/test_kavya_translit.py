"""IAST -> Devanagari for the Kavya importer (tools/kavya/translit.py)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from kavya.translit import is_roman, to_devanagari  # noqa: E402


def test_basic_words():
    assert to_devanagari("vāgarthāviva saṃpṛktau") == "वागर्थाविव संपृक्तौ"
    assert to_devanagari("jagataḥ pitarau vande") == "जगतः पितरौ वन्दे"
    assert to_devanagari("śārṅgarava") == "शार्ङ्गरव"


def test_vowel_sequences_not_collapsed():
    # 'ā' + 'i' is two vowels, not a diphthong
    assert to_devanagari("mahāindra") == "महाइन्द्र"
    assert to_devanagari("aiśvarya") == "ऐश्वर्य"


def test_danda_and_avagraha():
    assert to_devanagari("rāmaḥ vanaṃ gacchati /") == "रामः वनं गच्छति ।"
    assert to_devanagari("a // ba").count("॥") == 1
    assert to_devanagari("so 'pi") == "सोऽपि"


def test_final_consonant_gets_virama():
    assert to_devanagari("tat") == "तत्"


def test_metre_annotation_lines_untouched():
    t = "% v - -| v| A pathyā"
    assert to_devanagari(t) == t
    assert to_devanagari("tat\n" + t) == "तत्\n" + t


def test_is_roman():
    assert is_roman("rāmaḥ")
    assert not is_roman("रामः")
    assert not is_roman("")
