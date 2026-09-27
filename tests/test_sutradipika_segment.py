"""The Brahmasūtradīpikā segmenter.

ब्रह्मसूत्रदीपिका of Śrī Jagannātha Yati, 238 pages, edited with an English
gist by Panchamukhi.

Three things this encodes:

  * BOTH ENGINES ARE NEEDED. Sarvam covers 25-238, Vision 1-238, and the first
    24 pages hold adhyāya 1 pāda 1 — अथातो ब्रह्मजिज्ञासा and the 30 sūtras
    after it. Reading Sarvam alone loses the opening pāda of the Brahma Sūtras.
  * THE SANDHI TRAP, for the third time in this corpus. `अधिकरणम्` has no
    literal अ inside `अन्वयाधिकरणम्`: it is absorbed into the ा of या. A
    pattern written around अधिकरणम् matches none of the 196 headings.
  * THE PRINTED NUMBER IS PREFERRED BUT NOT TRUSTED. Nine sūtras are printed
    with another's pāda-relative number and overwrote it. Numbering purely by
    reading order instead looked perfect — 500 sūtras, no gaps — and was
    wrong, because one missed line shifts every address after it.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "sd_segment", ROOT / "tools/sutradipika/segment.py")
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)

STAGED = ROOT / "data/ocr_staging/brahma_sutra_dipika_jagannatha_tirtha_panchamukhi"

# Madhva's division of the Brahma Sūtras, for checking the addressing against
# something outside the scan.
CANONICAL = {(1, 1): 31, (1, 2): 32, (1, 3): 43, (1, 4): 28,
             (2, 1): 38, (2, 2): 45, (2, 3): 53, (2, 4): 23,
             (3, 1): 27, (3, 2): 43, (3, 3): 66, (3, 4): 52,
             (4, 1): 19, (4, 2): 21, (4, 3): 16, (4, 4): 22}


def test_the_adhikarana_heading_is_matched_from_inside_the_word():
    """`अधिकरणम्` has no literal अ in `अन्वयाधिकरणम्` — the vowel is absorbed
    into the ा of या. Written around the whole word the pattern finds none of
    the 196 headings."""
    import re
    assert not re.search("अधिकरणम्", "॥ अन्वयाधिकरणम् ॥ १० ॥")
    for t, name, num in [
            ("॥ अन्वयाधिकरणम् ॥ १० ॥", "अन्वयाधिकरणम्", "१०"),
            ("।। छन्दोऽभिधानाधिकरणम् ।। ११ ।।", "छन्दोऽभिधानाधिकरणम्", "११"),
            ("॥ जिज्ञासाधिकरणम् ॥ १ ॥", "जिज्ञासाधिकरणम्", "१")]:
        m = sd.ADHIKARANA.search(t)
        assert m and m.group(1) == name and m.group(2) == num, t


def test_a_sutra_is_recognised_by_its_om_wrapper():
    m = sd.SUTRA.search("३९. ।। ॐ सम्भोगप्राप्तिरिति चेन्न वैशेष्यात् ॐ।।८॥")
    assert m and m.group(2) == "८"
    assert "सम्भोगप्राप्तिरिति" in m.group(1)
    # Vision writes it without a running number and with a doubled ॐ.
    m2 = sd.SUTRA.search("॥ ॐ ॐ अथातो ब्रह्मजिज्ञासा ॐ ॥ १ ॥")
    assert m2 and m2.group(1).strip() == "अथातो ब्रह्मजिज्ञासा"


def test_the_running_number_opens_the_line():
    assert sd.RUNNING.match("३९. ।। ॐ").group(1) == "३९"
    assert sd.RUNNING.match("॥ ॐ ॐ अथातो") is None


# --- the real book ---------------------------------------------------------

def _real():
    if not STAGED.is_dir():
        import pytest
        pytest.skip("Brahmasūtradīpikā staging not present")
    return sd.segment(str(STAGED))


def test_both_engines_are_used_and_vision_supplies_the_opening_pada():
    r = _real()
    assert r["stats"]["vision_only_pages"] == 24
    assert r["from_vision"] == 31, "the opening pāda came from Vision"
    assert (1, 1, 1) in r["sutras"]
    assert r["sutras"][(1, 1, 1)]["sa"] == "अथातो ब्रह्मजिज्ञासा"
    assert r["sutras"][(1, 1, 1)]["engine"] == "vision"
    assert r["sutras"][(1, 1, 2)]["sa"] == "जन्माद्यस्य यतः"


def test_the_real_staged_book_is_complete_to_where_the_volume_ends():
    """The PDF is 238 pages and the last sūtra set is running number 530 of
    564, so 4.3.6 onward and the whole of 4.4 are not in this book."""
    r = _real()
    assert r["pages"] == 238 and r["page_gaps"] == []
    assert r["sutras_found"] == 500
    assert r["sutras_missing"] == 29
    assert r["with_commentary"] == 500
    assert [(x["adhyaya"], x["pada"]) for x in r["padas"]][-1] == (4, 3)
    assert not [x for x in r["padas"] if (x["adhyaya"], x["pada"]) == (4, 4)]


def test_the_addressing_agrees_with_the_canonical_division():
    """The check from outside the scan. Every pāda's highest number must land
    on Madhva's count, or within two of it — the slack being the sūtra lines
    the OCR lost. 4.3 is short because the volume stops inside it."""
    r = _real()
    for x in r["padas"]:
        key = (x["adhyaya"], x["pada"])
        if key == (4, 3):
            continue
        assert abs(x["highest"] - CANONICAL[key]) <= 2, (key, x["highest"])


def test_a_sutra_set_twice_is_merged_not_addressed_twice():
    """Some sūtras are set as a display line and again at the head of their
    commentary, same running number, slightly different OCR."""
    r = _real()
    assert r["stats"]["set_twice_merged"] == 9
    texts = [v["sa"] for v in r["sutras"].values()]
    # The Brahma Sūtras really do repeat short phrases — दर्शनाच्च occurs four
    # times — so duplicate TEXT is expected; duplicate ADDRESSES are not.
    assert len(r["sutras"]) == len(set(r["sutras"]))


def test_the_sutras_are_sutra_shaped():
    r = _real()
    lens = [len(v["sa"]) for v in r["sutras"].values()]
    # आपः is a real one-word sūtra at 2.3.11; the longest are still short.
    assert min(lens) >= 3 and max(lens) <= 240
    assert not [v for v in r["sutras"].values() if not v["sa"].strip()]
    comms = [v["commentary"] for v in r["sutras"].values() if v["commentary"]]
    assert len(set(comms)) == len(comms), "one gloss under two sūtras"
