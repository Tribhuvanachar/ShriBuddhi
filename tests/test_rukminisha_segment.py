"""The Rukmiṇīśa Vijaya segmenter.

Its job is to address 1,240-odd verses across 19 sargas from page-shaped OCR,
and — just as importantly — to refuse to pretend it has them all.

The trap this encodes: data-layout="section-title" looks like the verse tag.
The first page examined had its verse under exactly that tag. There are 78 of
them in the whole book against ~2,480 verse markers, so trusting it yields a
37-verse mahakavya instead of 1,143. Sampling one page and generalising is the
failure these tests exist to catch.
"""
import importlib.util
import json
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "rukminisha" / "segment.py"
_spec = importlib.util.spec_from_file_location("rv_segment", TOOL)
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)


def page(*blocks):
    return "".join(f'<p data-layout="{k}">{v}</p>' for k, v in blocks)


def test_the_sarga_comes_from_the_running_header():
    pages = {1: page(("header", "प्रथमः सर्गः"), ("paragraph", "क ख ग ॥ १ ॥"))}
    r = rv.segment(pages)
    assert r["sargas"][0]["sarga"] == 1 and r["sargas"][0]["found"] == 1


def test_the_sarga_carries_forward_to_a_page_with_no_header():
    pages = {1: page(("header", "प्रथमः सर्गः"), ("paragraph", "अ ॥ १ ॥")),
             2: page(("paragraph", "आ ॥ २ ॥"))}
    assert rv.segment(pages)["verses_found"] == 2


def test_the_sixth_sarga_prints_without_a_visarga():
    """षष्ठ सर्गः, not षष्ठः — 20 page-headers in the real book."""
    assert rv.sarga_of("षष्ठ सर्गः") == 6
    assert rv.sarga_of("षष्ठः सर्गः") == 6


def test_an_ocr_mangled_header_is_still_recognised():
    """One page reads ससदशः for सप्तदशः."""
    assert rv.sarga_of("ससदशः सर्गः") == 17


def test_a_header_that_is_not_a_sarga_is_reported_not_guessed():
    pages = {1: page(("header", "कश्चित् सर्गः"), ("paragraph", "क ॥ १ ॥"))}
    r = rv.segment(pages)
    assert r["unknown_sarga_headers"] == {"कश्चित् सर्गः": 1}
    assert r["verses_found"] == 0


def test_devanagari_and_ascii_verse_numbers_both_count():
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "अ ॥ १ ॥"), ("paragraph", "आ ॥ 2 ॥"))}
    assert rv.segment(pages)["verses_found"] == 2


def test_commentary_is_not_mistaken_for_a_verse():
    """863 commentary blocks quote a verse number. Counting them would
    inflate the verse total with text that is not the mula."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "व्या : रुचिरेति ॥ १ ॥"))}
    r = rv.segment(pages)
    assert r["verses_found"] == 0
    assert r["commentary_blocks"] == 1


def test_gaps_are_reported_per_sarga():
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "अ ॥ १ ॥"), ("paragraph", "आ ॥ ३ ॥"))}
    s = rv.segment(pages, recover=False)["sargas"][0]
    assert s["missing"] == [2] and s["highest"] == 3


def test_a_number_closed_by_one_danda_still_counts():
    """...शरणं विरिञ्चम् ॥ ११  -- 17 verses close that way."""
    pages = {1: page(("header", "प्रथमः सर्गः"), ("paragraph", "अ आ इ ॥ ११"))}
    assert rv.segment(pages)["verses_found"] == 1


def test_a_number_mid_block_is_not_a_verse_marker():
    """VERSE_NUM_END is anchored to the block end so a quoted number is not
    mistaken for the verse's own."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "यथा ॥ ९ ॥ इत्युक्तम् अतः"))}
    # the strict ॥N॥ form still matches here; what must NOT happen is the
    # trailing "अतः" being read as closing verse 9's block.
    r = rv.segment(pages)
    assert [v["verse"] for v in r["verses"].values()] == [9]


def test_an_unnumbered_block_between_neighbours_is_placed():
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "अ ॥ १ ॥"),
                     ("paragraph", "व्या : gloss on 1"),
                     ("paragraph", "the lost verse"),
                     ("paragraph", "व्या : gloss on 2"),
                     ("paragraph", "इ ॥ ३ ॥"))}
    r = rv.segment(pages)
    assert r["verses_missing"] == 0
    assert r["verses"][(1, 2)]["text"] == "the lost verse"
    assert r["verses"][(1, 2)]["how"] == "position"
    assert r["verses_by_position"] == 1


def test_it_refuses_when_two_blocks_compete_for_one_slot():
    """20 of the real gaps look like this. It could be a verse split across a
    page break, or a verse plus a stray line -- and a wrong address is worse
    than a visible hole."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "अ ॥ १ ॥"),
                     ("paragraph", "candidate one"),
                     ("paragraph", "candidate two"),
                     ("paragraph", "इ ॥ ३ ॥"))}
    r = rv.segment(pages)
    assert r["verses_missing"] == 1 and r["verses_by_position"] == 0


def test_two_missing_against_two_blocks_maps_in_order():
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "अ ॥ １ ॥".replace("１", "१")),
                     ("paragraph", "verse two"),
                     ("paragraph", "verse three"),
                     ("paragraph", "ई ॥ ४ ॥"))}
    r = rv.segment(pages)
    assert r["verses"][(1, 2)]["text"] == "verse two"
    assert r["verses"][(1, 3)]["text"] == "verse three"


def test_recovery_never_crosses_a_sarga_boundary():
    pages = {1: page(("header", "प्रथमः सर्गः"), ("paragraph", "अ ॥ ६६ ॥"),
                     ("paragraph", "orphan")),
             2: page(("header", "द्वितीयः सर्गः"), ("paragraph", "आ ॥ २ ॥"))}
    r = rv.segment(pages)
    assert r["verses_by_position"] == 0


def test_a_page_delivered_twice_is_not_counted_twice(tmp_path):
    """Dispatch ranges overlap and failed pages get re-sent, so the same page
    appears in several staged files."""
    for name, ok in (("a.json", False), ("b.json", True)):
        (tmp_path / name).write_text(json.dumps({"pages": [
            {"page": 5, "ok": ok, "html": page(("header", "प्रथमः सर्गः"),
                                               ("paragraph", "अ ॥ १ ॥")) if ok else ""}]}),
            encoding="utf-8")
    pages = rv.load_pages(str(tmp_path))
    assert list(pages) == [5]
    assert rv.segment(pages)["verses_found"] == 1


def test_a_failed_page_never_overwrites_a_delivered_one(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"pages": [
        {"page": 5, "ok": True, "html": page(("paragraph", "real"))}]}), encoding="utf-8")
    (tmp_path / "z.json").write_text(json.dumps({"pages": [
        {"page": 5, "ok": False, "error": "HTTP Error 402: Payment Required"}]}),
        encoding="utf-8")
    assert "real" in rv.load_pages(str(tmp_path))[5]


def test_br_becomes_a_line_break_not_a_join():
    assert rv.untag("अ<br>आ") == "अ\nआ"


def test_the_real_staged_book_is_complete_in_pages_and_short_in_verses():
    """The state this tool was written to establish, asserted so a later run
    that changes it is noticed. 694 pages, no gaps; 1,143 verses, 97 short."""
    d = Path(__file__).resolve().parents[1] / "data/ocr_staging/rukminisha_vijaya"
    if not d.is_dir():
        import pytest
        pytest.skip("Rukminisha Vijaya staging not present")
    r = rv.segment(rv.load_pages(str(d)))
    assert r["pages"] == 694 and r["page_gaps"] == []
    assert len(r["sargas"]) == 19
    assert r["verses_by_marker"] == 1160
    assert r["verses_by_position"] == 35
    assert r["verses_found"] == 1195
    assert r["verses_missing"] == 46
