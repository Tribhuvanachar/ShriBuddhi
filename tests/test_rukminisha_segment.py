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
    """A verse's marker CLOSES its block. A number quoted mid-sentence, with
    prose running on after it, addresses nothing.

    This is stricter than it used to be, deliberately. The old version read
    every number anywhere in a block, so this block became verse 9 with
    "इत्युक्तम् अतः" as part of the verse."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "यथा ॥ ९ ॥ इत्युक्तम् अतः"))}
    assert rv.segment(pages)["verses_found"] == 0


def test_an_unnumbered_block_between_neighbours_is_placed():
    """Positional recovery, with no commentary in the way."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "अ ॥ १ ॥"),
                     ("paragraph", "the lost verse"),
                     ("paragraph", "इ ॥ ३ ॥"))}
    r = rv.segment(pages)
    assert r["verses_missing"] == 0
    assert r["verses"][(1, 2)]["text"] == "the lost verse"
    assert r["verses"][(1, 2)]["how"] == "position"
    assert r["verses_by_position"] == 1


# --- commentary is a REGION, not a property of one block ------------------
# The gloss on one verse runs over many blocks and across page breaks, and only
# the first says व्या. An earlier version tested each block in isolation, so
# every continuation block was eligible to be a verse. Landed, that produced
# 287 verses that were nothing but a verse number and prose in the mūla slot,
# at 71% plausible -- which the counts did not show and a screenshot did.

def test_a_gloss_continuation_block_is_not_a_verse():
    """The second block of the gloss carries the closing ॥ २ ॥. It is still
    gloss, so verse 2 must not be that block."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "मूलम् एकम् ॥ १ ॥"),
                     ("paragraph", "व्या : एकमिति । gloss begins here"),
                     ("paragraph", "gloss runs on and closes ॥ १ ॥"),
                     ("paragraph", "मूलम् द्वितीयम् ॥ २ ॥"),
                     ("paragraph", "व्या : द्वितीयमिति । second gloss"),
                     ("paragraph", "still the second gloss ॥ २ ॥"))}
    r = rv.segment(pages)
    assert r["verses_found"] == 2
    assert r["verses"][(1, 1)]["text"] == "मूलम् एकम् ॥ १ ॥"
    assert r["verses"][(1, 2)]["text"] == "मूलम् द्वितीयम् ॥ २ ॥"


def test_a_bare_marker_numbers_the_block_above_it():
    """341 blocks in the real book hold nothing but ॥ N ॥, 340 of them directly
    after an unnumbered text block. Reading one as a verse in its own right is
    what produced the empty verses."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "the verse itself, long enough to be one"),
                     ("paragraph", "॥ ७ ॥"))}
    r = rv.segment(pages)
    assert r["verses_found"] == 1
    assert r["verses"][(1, 7)]["text"] == "the verse itself, long enough to be one"


def test_a_verse_printed_one_pada_per_block_is_joined():
    """Four blocks of a quarter-verse each, then the marker. Keeping only the
    numbered block leaves a quarter of a verse -- the 62 "fragments"."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "पादः प्रथमः"),
                     ("paragraph", "पादो द्वितीयः"),
                     ("paragraph", "पादस्तृतीयः"),
                     ("paragraph", "पादश्चतुर्थः"),
                     ("paragraph", "॥ ५ ॥"))}
    r = rv.segment(pages)
    assert r["verses"][(1, 5)]["text"] == (
        "पादः प्रथमः\nपादो द्वितीयः\nपादस्तृतीयः\nपादश्चतुर्थः")


def test_a_gloss_closing_number_addresses_a_verse_whose_marker_was_lost():
    """The gloss on verse N ends with ॥ N ॥ and sits directly beneath the verse.
    So the edition names the address even when the verse's own marker is gone."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "अ ॥ १ ॥"),
                     ("paragraph", "व्या : gloss on one ॥ १ ॥"),
                     ("paragraph", "the verse whose own marker the OCR dropped"),
                     ("paragraph", "व्या : gloss on two ॥ २ ॥"))}
    r = rv.segment(pages)
    assert r["verses"][(1, 2)]["text"] == "the verse whose own marker the OCR dropped"
    assert r["verses"][(1, 2)]["how"] == "gloss-close"


def test_a_gloss_without_va_still_opens_a_region():
    """9 blocks in the book open '<pratika>ति ।' with the व्या lost by the OCR,
    and all 9 are gloss. Without this, छत्रमिति । stood as mūla verse 13.1."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "छत्रमिति । the gloss, with no व्या at all ॥ १ ॥"))}
    assert rv.segment(pages)["verses_found"] == 0


# --- the closing colophon -------------------------------------------------

def test_a_colophon_is_not_a_verse_and_names_the_sarga_that_ended():
    """॥ इति ... चतुर्दशः सर्गः ॥ १४ ॥ closes sarga 14. Its trailing number is
    the SARGA number; read as a verse it invents one."""
    col = "॥ इति श्रीमद्वादिराजतीर्थविरचिते महाकाव्ये चतुर्दशः सर्गः ॥ १४ ॥"
    assert rv.colophon_sarga(col) == 14
    assert rv.colophon_sarga("प्रथमः सर्गः") is None
    pages = {1: page(("header", "चतुर्दशः सर्गः"),
                     ("paragraph", "the last verse of the sarga ॥ ६९ ॥"),
                     ("paragraph", col))}
    r = rv.segment(pages)
    assert [v["verse"] for v in r["verses"].values()] == [69]


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


def _real_book():
    d = Path(__file__).resolve().parents[1] / "data/ocr_staging/rukminisha_vijaya"
    if not d.is_dir():
        import pytest
        pytest.skip("Rukminisha Vijaya staging not present")
    return rv.segment(rv.load_pages(str(d)))


def test_the_real_staged_book_is_complete_in_pages_and_short_in_verses():
    """The measured state of the book, asserted so a later run that changes it
    is noticed. 725 pages, no gaps: the front matter (1-18) and back matter
    (713-725) were fetched, 31 pages no run had ever asked for."""
    r = _real_book()
    assert r["pages"] == 725 and r["page_gaps"] == []
    assert len(r["sargas"]) == 19
    assert r["verses_by_marker"] == 1066
    assert r["verses_by_gloss_close"] == 88
    assert r["verses_by_position"] == 11
    assert r["verses_by_pratika"] == 1
    assert r["verses_found"] == 1166
    assert r["verses_missing"] == 74


def test_the_addressed_verses_are_actually_verse_SHAPED():
    """THE TEST THAT WAS MISSING, and the reason this file needed rewriting.

    The previous segmenter reported 1,211 verses and 29 gaps -- better-looking
    numbers than the 1,166 and 74 above -- and was landed on that basis. The
    screenshot then showed what the counts could not:

        857  plausible verse length (40-600 chars)     71%
        287  EMPTY -- only the verse number survived   24%
         52  under 40 characters, fragments
         15  over 600 characters, prose not verse

    A count of addresses says nothing about what stands under them. So the
    shape of the text is asserted here, and a regression that trades quality
    for coverage fails even though its totals look better.
    """
    r = _real_book()
    vs = r["verses"]
    lengths = [len(v["text"]) for v in vs.values()]

    assert min(lengths) >= 30, "an empty or near-empty verse is back"
    assert sum(1 for n in lengths if n < 40) <= 3, "fragments are back"
    assert sum(1 for n in lengths if n > 600) <= 1, "prose in the mūla slot"
    plausible = sum(1 for n in lengths if 40 <= n <= 600)
    assert plausible / len(vs) >= 0.98, f"only {plausible}/{len(vs)} verse-shaped"

    # Nothing that is recognisably commentary may stand as mūla.
    assert not [v for v in vs.values() if v["text"].lstrip().startswith("व्या")]
    assert not [v for v in vs.values()
                if rv.GLOSS_OPEN_BARE.match(v["text"].replace("\n", " "))]
    assert not [v for v in vs.values() if rv.colophon_sarga(v["text"])]

    # And no verse's text may stand under a second address. 13 pages of this
    # scan are printed twice, two leaves apart, so this is a live risk rather
    # than a theoretical one: two addresses holding the same verse means one of
    # them is wrong and nothing downstream can tell which.
    assert len({v["text"] for v in vs.values()}) == len(vs)


def test_no_verse_number_exceeds_its_sarga_by_a_wide_margin():
    """A sarga's highest number should sit just above the verses found in it.
    When the colophon of sarga 14 was read as a sarga-15 page, its closing gloss
    ॥ ७० ॥ landed as verse 15.70 in a sarga whose real highest is 62."""
    for s in _real_book()["sargas"]:
        assert s["highest"] - s["found"] <= 14, s


# --- the pratika rule -----------------------------------------------------
# The commentary opens by quoting the verse's first word with इति attached,
# and the इति is SANDHI'd into that word: नेमुस्ताम् + इति prints नेमुस्तामिति,
# with no literal इति anywhere in the string, and काचित् + इति prints
# काचिदिति, voicing the त्. So the quoted form cannot be reversed reliably --
# but it does not have to be. A three-character shared prefix is enough to
# tell two candidate blocks apart, which is what position alone could not do.

def test_the_sandhi_d_iti_is_stripped_to_a_usable_stem():
    assert rv.pratika_stem("नेमुस्तामिति") == "नेमुस्ताम"
    assert rv.pratika_stem("रोम्णामिति") == "रोम्णाम"
    assert rv.pratika_stem("काचिदिति") == "काचिद"


def test_there_is_no_literal_iti_to_split_on():
    """The reason a naive r'(.+?)इति' pattern finds nothing."""
    assert "इति" not in "नेमुस्तामिति"


def test_a_pratika_picks_the_right_block_of_two():
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "अ ॥ १ ॥"),
                     ("paragraph", "व्या : काचिदिति । gloss ॥ २ ॥"),
                     ("paragraph", "wrong candidate"),
                     ("paragraph", "काचिच्च दष्टमृदुलोष्ठपुटी"),
                     ("paragraph", "इ ॥ ३ ॥"))}
    r = rv.segment(pages)
    assert r["verses"][(1, 2)]["text"].startswith("काचिच्च")
    assert r["verses"][(1, 2)]["how"] == "pratika"


def test_it_declines_when_the_pratika_matches_both_candidates():
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "अ ॥ १ ॥"),
                     ("paragraph", "व्या : काचिदिति । gloss ॥ २ ॥"),
                     ("paragraph", "काचिच्च one"),
                     ("paragraph", "काचिच्च two"),
                     ("paragraph", "इ ॥ ३ ॥"))}
    assert rv.segment(pages)["verses_missing"] == 1


def test_a_commentary_with_no_quoted_first_word_yields_nothing():
    pages = {1: page(("header", "प्रथमः सर्गः"), ("paragraph", "व्या : उक्तोऽर्थः"))}
    stream, _ = rv.read_blocks(pages)
    assert rv.pratika_for(stream, 1, 2) is None


def test_there_is_no_verse_zero():
    """Sarga 10 carries a ॥ ० ॥ the OCR invented. It counted as a verse while
    every consumer iterating 1..highest skipped it, so the segmenter said 1212
    and the writer emitted 1211. An off-by-one between two counts of the same
    text is how Manimanjari lost a verse."""
    pages = {1: page(("header", "प्रथमः सर्गः"),
                     ("paragraph", "spurious mark ॥ ० ॥"),
                     ("paragraph", "अ ॥ १ ॥"))}
    r = rv.segment(pages)
    assert [v["verse"] for v in r["verses"].values()] == [1]
