"""The Veṅkaṭeśa Māhātmya segmenter.

श्रीवेङ्कटेशमाहात्म्यम् from the Bhaviṣyottara Purāṇa, 854 pages, printed with
TWO commentaries — कल्याणकाण्डदीपः and गूढकर्तृकव्याख्यानम्.

The traps this encodes, each found by counting across the book rather than
reading one page:

  * THE VERSE NUMBER IS PRINTED IN TWO FORMS. 1,280 blocks close with ॥ N ॥
    (U+0965 DOUBLE DANDA) and 584 with ।। N ।। (two U+0964 single dandas).
    Matching only the first loses 31% of the markers, and loses them SILENTLY:
    adhyāya 9 read as 44 verses instead of 215 and simply looked like a part of
    the book with little commentary.
  * THE RUNNING HEADER LAGS THE ADHYĀYA. Adhyāya 9 opens on p455 with a
    ॥ अथ नवमोऽध्यायः ॥ section-title; the header does not say so until p457.
  * A MŪLA BLOCK OFTEN HOLDS MANY VERSES, and p459 holds verses 20-26 WITH
    their gloss interleaved between them, all in one 862-character block.
"""
import importlib.util
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "venkatesha" / "segment.py"
_spec = importlib.util.spec_from_file_location("vs_segment", TOOL)
vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vs)

STAGED = (Path(__file__).resolve().parents[1]
          / "data/ocr_staging/venkatesha__venkatesha_mahatmya_vyakyana_sahita")


def page(*blocks):
    return "".join(f'<p data-layout="{k}">{v}</p>' for k, v in blocks)


# --- the two danda forms ---------------------------------------------------

def test_the_double_danda_marker_is_read():
    pages = {1: page(("section-title", "॥ अथ प्रथमोऽध्यायः ॥"),
                     ("paragraph", "मूलपाठोऽयमत्र वर्तते सुदीर्घतरः ॥ १ ॥"))}
    assert vs.segment(pages)["verses_found"] == 1


def test_two_single_dandas_are_the_same_marker():
    """।। N ।। -- 584 blocks in the book close this way, 31% of the markers."""
    pages = {1: page(("section-title", "॥ अथ प्रथमोऽध्यायः ॥"),
                     ("paragraph", "मूलपाठोऽयमत्र वर्तते सुदीर्घतरः ।। १ ।।"))}
    r = vs.segment(pages)
    assert r["verses_found"] == 1 and (1, 1) in r["verses"]


# --- the adhyāya -----------------------------------------------------------

def test_the_adhyaya_opening_beats_the_lagging_header():
    """The opening section-title is on p455 and the header not until p457."""
    assert vs.adhyaya_of("॥ अथ नवमोऽध्यायः ॥") == 9
    assert vs.adhyaya_of("नवमोऽध्यायः") == 9


def test_a_colophon_names_the_adhyaya_it_closes():
    col = ("।। इति अत्र श्रीमद्भविष्योत्तरपुराणे वेङ्कटगिरिमाहात्म्ये\n"
           "कल्याणकाण्डे वर्णनं नाम अष्टमोऽध्यायः ।।")
    assert vs.adhyaya_closed_by(col) == 8
    # It carries newlines: an earlier [^\n] pattern matched none of the 28.
    assert "\n" in col


def test_the_appendices_are_not_an_adhyaya():
    """परिशिष्टम् carried adhyāya 11 into it, and adhyāya 11's last gloss then
    never closed -- it ran to 109,687 characters, the rest of the book."""
    assert vs.NOT_AN_ADHYAYA.match("परिशिष्टम् - १")
    pages = {1: page(("section-title", "॥ अथ प्रथमोऽध्यायः ॥"),
                     ("paragraph", "मूलपाठोऽयमत्र वर्तते सुदीर्घतरः ॥ १ ॥")),
             2: page(("header", "परिशिष्टम् - १"),
                     ("paragraph", "परिशिष्टपाठोऽयमत्र वर्तते दीर्घः ॥ ९९ ॥"))}
    r = vs.segment(pages)
    assert [k for k in r["verses"]] == [(1, 1)]


# --- the two commentaries --------------------------------------------------

def test_both_commentaries_are_recognised_by_name():
    assert vs.commentary_named("कल्याणकाण्डदीपः") == "kalyanakandadipa"
    assert vs.commentary_named("गूढकर्तृकव्याख्यानम्") == "gudhakartrikavyakhyana"


def test_the_ocr_spellings_of_each_name_are_recognised():
    """An unrecognised opener does not fail loudly -- its gloss is read as mūla
    instead, which is how 14 verses came to have a ṭīkā's name inside them."""
    for t in ("काण्डदीपः", "कल्याणाकाण्डदीपः", "काल्याणकाण्डदीपः",
              "नृपञ्चाननप्रणीतकल्याणकाण्डदीपः", "कल्याणकाण्डदीपः ।"):
        assert vs.commentary_named(t) == "kalyanakandadipa", t
    for t in ("गूढकर्तृकन्याख्यानम्", "गूढकर्तृव्याख्यानम्",
              "गूढकर्तृकब्याख्यानम्", "गूढकर्तृकव्याख्यानम"):
        assert vs.commentary_named(t) == "gudhakartrikavyakhyana", t


def test_a_verse_that_merely_mentions_a_commentary_is_not_an_opener():
    """Four blocks are VERSES naming a ṭīkā -- काशतां काण्डदीपोऽयं
    यावदाचन्द्रतारकम् ।। is the closing benediction, not a heading -- and two
    are section headings referring to one. All six carry text beyond the name."""
    for t in ("काशतां काण्डदीपोऽयं यावदाचन्द्रतारकम् ।।",
              "किरातादि दशः पद्मा लोकोऽयं काण्डदीपकः ।।",
              "कल्याणकाण्डदीपेड्भूत् प्रथमाध्यायलेखनम् ।।",
              "(अथ गूढकर्तृकव्याख्यानानुसारेण एकादशोऽध्यायः)"):
        assert vs.commentary_named(t) is None, t
        assert vs.commentary_prefixed(t) is None, t


def test_a_heading_run_together_with_its_gloss_still_opens():
    """p522 reads 'कल्याणकाण्डदीपः शुकवत्तिकाया वादनतूलतन्तुरुपादानम् ।' -- the
    OCR ran the heading and the first line of its gloss together. 30 blocks."""
    got = vs.commentary_prefixed("कल्याणकाण्डदीपः शुकवत्तिकाया वादनम् ।")
    assert got is not None
    assert got[0] == "kalyanakandadipa"
    assert got[1].startswith("शुकवत्तिकाया")


def test_the_gloss_attaches_to_the_verse_above_it():
    pages = {1: page(("section-title", "॥ अथ प्रथमोऽध्यायः ॥"),
                     ("paragraph", "मूलपाठोऽयमत्र वर्तते सुदीर्घतरः ॥ १ ॥"),
                     ("section-title", "कल्याणकाण्डदीपः"),
                     ("paragraph", "प्रथमटीकायाः पाठोऽयं भवति सुदीर्घः ।"),
                     ("section-title", "गूढकर्तृकव्याख्यानम्"),
                     ("paragraph", "द्वितीयटीकायाः पाठोऽयं भवति सुदीर्घः ।"))}
    v = vs.segment(pages)["verses"][(1, 1)]
    assert set(v["commentaries"]) == {"kalyanakandadipa", "gudhakartrikavyakhyana"}
    assert v["commentaries"]["kalyanakandadipa"].startswith("प्रथमटीकायाः")


def test_a_gloss_continuation_block_is_not_a_verse():
    """The gloss runs over many blocks and only the first names the ṭīkā."""
    pages = {1: page(("section-title", "॥ अथ प्रथमोऽध्यायः ॥"),
                     ("paragraph", "मूलपाठोऽयमत्र वर्तते सुदीर्घतरः ॥ १ ॥"),
                     ("section-title", "कल्याणकाण्डदीपः"),
                     ("paragraph", "टीकायाः प्रथमो भागोऽयं वर्तते सुदीर्घः ।"),
                     ("paragraph", "टीकायाः द्वितीयो भागोऽयं वर्तते सुदीर्घतरः ।"),
                     ("paragraph", "मूलपाठो द्वितीयोऽत्र वर्तते सुदीर्घः ॥ २ ॥"))}
    r = vs.segment(pages)
    assert r["verses_found"] == 2
    assert r["verses"][(1, 2)]["text"] == "मूलपाठो द्वितीयोऽत्र वर्तते सुदीर्घः ॥ २ ॥"


# --- multi-verse blocks ----------------------------------------------------

def test_a_block_of_many_verses_is_split_at_its_markers():
    """p456 carries verses 5 through 11 in one 622-character block; only the
    last marker closes it, so six of the seven are otherwise unreachable."""
    body = " ".join(f"मूलपाठोऽयमत्र वर्तते सुदीर्घतरः ॥ {n} ॥" for n in
                    ("१", "२", "३", "४"))
    pages = {1: page(("section-title", "॥ अथ प्रथमोऽध्यायः ॥"),
                     ("paragraph", body))}
    r = vs.segment(pages)
    assert sorted(n for _, n in r["verses"]) == [1, 2, 3, 4]


def test_a_long_mula_block_is_told_from_a_long_gloss_by_its_rhythm():
    """A flat length cap left p459's verses 20-26 -- 862 characters -- inside
    the gloss before them. What separates the two is that the mūla's markers
    come a verse apart, while a gloss quotes a number now and then."""
    mula = {"text": " ".join(f"पाठोऽयमत्र वर्तते दीर्घतरः सुन्दरः ॥ {n} ॥"
                             for n in ("२०", "२१", "२२", "२३", "२४", "२५", "२६")),
            "speaker": False}
    assert vs.looks_like_mula(mula)
    gloss = {"text": "टीका " + ("क" * 500) + " ॥ ५ ॥ " + ("ख" * 400) + " ॥ ६ ॥",
             "speaker": False}
    assert not vs.looks_like_mula(gloss)


# --- the real book ---------------------------------------------------------

def _real():
    if not STAGED.is_dir():
        import pytest
        pytest.skip("Venkatesa Mahatmya staging not present")
    return vs.segment(vs.load_pages(str(STAGED)))


def test_the_real_staged_book_is_complete_in_pages():
    r = _real()
    assert r["pages"] == 854
    assert r["page_range"] == [3, 856] and r["page_gaps"] == []
    assert len(r["adhyayas"]) == 11
    assert r["header_stats"]["adhyaya_openings"] == 11
    assert r["verses_found"] == 1523
    assert r["verses_missing"] == 64
    assert r["with_kalyana"] == 718
    assert r["with_gudha"] == 490


def test_the_addressed_verses_are_actually_verse_SHAPED():
    """A count of addresses says nothing about what stands under them.
    Rukmiṇīśa Vijaya was landed on its counts and was 71% plausible: 287 of its
    verses were nothing but a verse number. Only the screenshot showed it."""
    r = _real()
    V = r["verses"]
    lengths = [len(v["text"]) for v in V.values()]
    assert min(lengths) >= 25, "an empty or near-empty verse"
    assert sum(1 for n in lengths if n < 30) <= 1
    assert sum(1 for n in lengths if n > 600) <= 2, "prose in the mūla slot"
    assert sum(1 for n in lengths if 30 <= n <= 600) / len(V) >= 0.99

    # Nothing recognisably commentary may stand as mūla, and no verse's text
    # may stand under a second address.
    assert not [v for v in V.values()
                if "काण्डदीप" in v["text"] or "गूढकर्तृ" in v["text"]]
    assert len({v["text"] for v in V.values()}) == len(V)

    glosses = [c for v in V.values()
               for c in (v.get("commentaries") or {}).values()]
    assert len(glosses) == 1208
    assert max(len(c) for c in glosses) <= 20000, "a gloss that never closed"
    assert len(set(glosses)) == len(glosses), "one gloss under two verses"


def test_both_engines_ran_the_whole_book():
    """The only work in the backlog where Sarvam and Vision both cover every
    page, so a doubtful reading can be checked rather than guessed."""
    if not STAGED.is_dir():
        import pytest
        pytest.skip("Venkatesa Mahatmya staging not present")
    v = vs.vision_pages(str(STAGED))
    assert len(v) == 856 and min(v) == 1 and max(v) == 856
