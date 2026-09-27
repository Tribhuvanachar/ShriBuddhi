"""The Pāṣaṇḍakhaṇḍanam segmenter.

पाषण्डखण्डनम् of Vādirāja Tīrtha with Surottama Tīrtha's vyākhyā, 50 pages,
129 verses in one continuous run.

The trap this encodes: SEVERAL BLOCKS CLOSE ON THE SAME NUMBER. Page 15 has
three on ॥ २६ ॥ — 794 characters of gloss, then the 84-character verse, then
437 more of gloss. Which block is the verse cannot be decided as each arrives:
taking the FIRST made the 794 the verse and filed the real one as commentary,
and taking the SHORTEST breaks verse 24, whose verse is 85 characters and whose
gloss tail is 46. It is the first VERSE-SHAPED closer.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "pk_segment", ROOT / "tools/pasandakhandana/segment.py")
pk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pk)

STAGED = ROOT / "data/ocr_staging/pasandakhandanam_vad__mentary_surottama_tirtha"
OPEN = "अथ पाषण्डखण्डनं सव्याख्यम्"


def page(*texts):
    return "".join(f'<p data-layout="paragraph">{t}</p>' for t in texts)


def test_the_verse_is_the_first_verse_shaped_closer():
    long_gloss = "टीकापाठोऽयम् " * 40 + "॥ २ ॥"
    pages = {1: page(OPEN, "प्रथमः श्लोकोऽयं वर्तते सुदीर्घतरः ॥ १ ॥",
                     long_gloss,
                     "द्वितीयः श्लोकोऽयं वर्तते सुदीर्घतरः ॥ २ ॥",
                     "टीका द्वितीये ॥ २ ॥")}
    r = pk.segment(pages)
    assert r["verses_found"] == 2
    assert r["verses"][2]["text"].startswith("द्वितीयः"), \
        "the long gloss became the verse"
    assert "टीकापाठोऽयम्" in r["verses"][2]["commentary"]


def test_the_shortest_closer_is_not_the_verse():
    """Verse 24's verse is 85 characters and its gloss tail is 46."""
    pages = {1: page(OPEN,
                     "चतुर्विंशः श्लोकोऽयमत्र वर्तते सुदीर्घतरः सुन्दरश्च ॥ २४ ॥",
                     "तदिति॥ २४॥")}
    r = pk.segment(pages)
    assert r["verses"][24]["text"].startswith("चतुर्विंशः")
    assert r["verses"][24]["commentary"] == "तदिति॥ २४॥"


def test_a_verse_whose_marker_was_lost_is_taken_from_the_run_above_its_gloss():
    """93 is स्वयं सञ्चरतो वायोः… with only the gloss carrying ॥ ९३ ॥."""
    pages = {1: page(OPEN, "प्रथमः श्लोकोऽयं वर्तते सुदीर्घः ॥ १ ॥",
                     "स्वयं सञ्चरतो वायोः स्रवन्तीनां च सन्ततम्।",
                     "ननु जडस्यापि स्वतःप्रवृत्तिर्दृष्टा " * 6 + "॥ २ ॥")}
    r = pk.segment(pages)
    assert r["verses"][2]["text"] == "स्वयं सञ्चरतो वायोः स्रवन्तीनां च सन्ततम्।"


def test_a_quoted_earlier_verse_does_not_restart_the_run():
    pages = {1: page(OPEN, "प्रथमः श्लोकोऽयं वर्तते सुदीर्घः ॥ ९२ ॥",
                     "चलन्तीनां नियन्तारो देवाः सन्ति सतां मताः ॥ १३ ॥",
                     "त्रिनवतितमः श्लोकोऽयं वर्तते सुदीर्घः ॥ ९३ ॥")}
    r = pk.segment(pages)
    assert sorted(r["verses"]) == [92, 93], "the quotation opened a verse 13"


def test_the_front_matter_is_not_part_of_verse_one():
    """Verse 1 came out carrying the half-title, the imprint and the series
    note — 354 characters of front matter."""
    pages = {1: page("हृदयवाणी", "श्रीभण्डारकेरिमठः", OPEN,
                     "॥ श्रीहयग्रीवाय नमः ॥ ॥ अथ श्रीमद्वादिराजतीर्थविरचितं पाषण्डखण्डनम् ॥",
                     "ॐ संसेवे हंसहंसार्च्यमिन्दिरेन्दिन्दिरप्रियम् ॥ १ ॥")}
    r = pk.segment(pages)
    assert r["verses"][1]["text"].startswith("ॐ संसेवे")
    assert "हृदयवाणी" not in r["verses"][1]["text"]
    assert "विरचितं" not in r["verses"][1]["text"]


# --- the real book ---------------------------------------------------------

def _real():
    if not STAGED.is_dir():
        import pytest
        pytest.skip("Pāṣaṇḍakhaṇḍana staging not present")
    import sys
    sys.path.insert(0, str(ROOT / "tools/ocr_common"))
    import staged as S
    return pk.segment(S.load_sarvam(str(STAGED)))


def test_the_real_staged_book_is_complete():
    r = _real()
    assert r["pages"] == 50 and r["page_range"] == [4, 53] and r["page_gaps"] == []
    assert r["verses_found"] == 129
    assert r["highest"] == 129
    assert r["missing"] == []
    assert r["with_commentary"] == 128
    assert r["stats"]["quotations"] == 2


def test_the_addressed_verses_are_actually_verse_SHAPED():
    """A count of addresses says nothing about what stands under them.
    Rukmiṇīśa Vijaya landed on its counts at 71% plausible: 287 of its verses
    were nothing but a verse number, and only the screenshot showed it."""
    r = _real()
    V = r["verses"]
    lengths = [len(v["text"]) for v in V.values()]
    assert min(lengths) >= 40
    assert max(lengths) <= 250, "commentary swept into the mūla slot"
    assert len({v["text"] for v in V.values()}) == len(V)
    comms = [v["commentary"] for v in V.values() if v.get("commentary")]
    assert len(set(comms)) == len(comms), "one gloss under two verses"
    assert not [v for v in V.values()
                if v.get("commentary", "").strip() == v["text"].strip()]
