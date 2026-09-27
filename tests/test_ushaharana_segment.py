"""The Uṣāharaṇa segmenter, and the shared verse+commentary reading it uses.

उषाहरणम् of Trivikrama Paṇḍitācārya, a mahākāvya in nine sargas with the
Rasikarañjanī commentary, 534 pages.

Three things this encodes, each of which cost a measurement:

  * THE RUNNING HEADER LAGS THE SARGA, so the ॥ अथ N सर्गः ॥ opener is the
    signal. A header-only reading lost verses 1 and 2 of every sarga.
  * A LINE WAITING FOR ITS MARKER CAN BE A WHOLE VERSE HERE (median 108
    characters), because this edition sets a verse in one block rather than a
    pāda at a time. With the pāda-sized cap 108 addresses came out empty.
  * ONLY A VERSE-SHAPED BLOCK MAY ADVANCE THE RUNNING MAXIMUM. One commentary
    block closes with a misread ॥ ७१ ॥, and letting it advance the maximum
    made every real verse from 7.58 to 7.70 look like a quotation.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


uh = _load("uh_segment", "tools/ushaharana/segment.py")
VC = _load("verse_commentary", "tools/ocr_common/verse_commentary.py")
STAGED = ROOT / "data/ocr_staging/usha_harna_trivikram__irtha_vadirajacharya_l_s"


def page(*blocks):
    return "".join(f'<p data-layout="{k}">{v}</p>' for k, v in blocks)


def test_the_sarga_opener_beats_the_lagging_header():
    assert uh.section_of("section-title", "॥ अथ तृतीयः सर्गः ॥") == 3
    assert uh.section_of("headline", "॥ अथ सप्तमः सर्गः ॥") == 7
    assert uh.section_of("header", "प्रथमः सर्गः") == 1
    assert uh.section_of("header", "सार्धश्लोकानुक्रमणिका") is None


def test_a_link_sentence_is_not_part_of_the_verse():
    """नृसिंहभावं स्तौति- introduces the verse about to be quoted. Short enough
    to look like a verse line, it was prepended to 38 of them."""
    assert uh.TITLE_LINE.search("नृसिंहभावं स्तौति-")
    assert uh.TITLE_LINE.search("वन्दामह इति ।।")
    assert not uh.TITLE_LINE.search("नीलोत्पलदलश्याममिन्दिरा यमनिन्दिता ।")


def test_a_bare_marker_block_is_not_a_verse():
    """78 of this work's addresses came out as five characters -- the marker
    and nothing else -- before verse_commentary grew a floor."""
    pages = {1: page(("section-title", "॥ अथ प्रथमः सर्गः ॥"),
                     ("paragraph", "श्लोकपाठोऽयमत्र वर्तते सुदीर्घतरः सुन्दरश्च"),
                     ("paragraph", "॥ १ ॥"))}
    r = uh.segment(pages)
    # Prefix chosen to survive sandhi: श्लोकपाठोऽयम् + अत्र writes as
    # श्लोकपाठोऽयमत्र, with no virāma left to match on.
    assert r["units"][(1, 1)]["text"].startswith("श्लोकपाठ")
    assert len(r["units"][(1, 1)]["text"]) > 20, "the bare marker became the verse"


def test_only_a_verse_shaped_block_advances_the_running_maximum():
    """A 627-character gloss closing with a misread ॥ ७१ ॥ made verses 58-70
    look like quotations. Thirteen vanished on one bad digit."""
    gloss = "टीकापाठोऽयम् " * 50 + "॥ ७१ ॥"
    pages = {1: page(("section-title", "॥ अथ सप्तमः सर्गः ॥"),
                     ("paragraph", "श्लोकपाठः सप्तपञ्चाशत्तमोऽयं वर्तते ॥ ५७ ॥"),
                     ("paragraph", gloss),
                     ("paragraph", "श्लोकपाठोऽष्टपञ्चाशत्तमोऽयं वर्तते ॥ ५८ ॥"))}
    r = uh.segment(pages)
    assert (7, 58) in r["units"], "the misread number swallowed the next verse"


# --- the real book ---------------------------------------------------------

def _real():
    if not STAGED.is_dir():
        import pytest
        pytest.skip("Uṣāharaṇa staging not present")
    import sys
    sys.path.insert(0, str(ROOT / "tools/ocr_common"))
    import staged as S
    return uh.segment(S.load_sarvam(str(STAGED)))


def test_the_real_staged_book_is_complete_in_pages():
    r = _real()
    assert r["pages"] == 534 and r["page_range"] == [6, 539] and r["page_gaps"] == []
    assert len(r["sections"]) == 9
    assert r["verses_found"] == 726
    assert r["verses_missing"] == 18
    assert r["with_commentary"] == 720


def test_the_addressed_verses_are_actually_verse_SHAPED():
    r = _real()
    q = VC.quality(r["units"])
    assert q["empty"] == 0
    assert q["long"] == 0
    assert q["plausible_pct"] >= 99
    assert q["duplicate_text"] == 0
    assert q["duplicate_commentary"] == 0
    assert q["commentary_equals_verse"] == 0
    assert q["len_min"] >= 25
