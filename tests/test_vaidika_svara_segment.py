"""The Vaidika Svara Prakaraṇam segmenter.

ವೈದಿಕ ಸ್ವರ ಪ್ರಕರಣಮ್ { ಶೌನಕೀಯಂ, ಪಾಣಿನೀಯಂ ಚ } — a KANNADA treatise on Vedic
accent, 108 pages, expounding Sanskrit sūtras printed in Kannada script.

The traps this encodes, each found by counting across the book rather than
reading one page:

  * A NUMBER IN PARENTHESES BELONGS TO ANOTHER TEXT. `(ಫಿಟ್ ಸೂತ್ರ-೮೫)` cites
    the Phiṭ Sūtras. Counting those as this book's own made the Pāṇinīya part
    read as "1..87 with 58 gaps". But the guard must be the PARENTHESES, not
    the word ಫಿಟ್: p98 reads `( ಫಿಟ್ ಸೂತ್ರ ) ಸೂತ್ರ - ೪೧,` — a citation with no
    number, then this book's own sūtra 41 outside it.
  * THE SECTION IS WHERE THE NUMBERING RESTARTS, not where a heading falls.
    The Śaunakīya part restarts at 1 three times; the Pāṇinīya part runs 1..46
    straight through its own ಅಧ್ಯಾಯ headings.
  * THE CONTENTS PAGE OMITS A SECTION. Paired by position, every title from
    that point on lands on the wrong sūtra.
  * ಸೂತ್ರ + ಅರ್ಥ IS WRITTEN ಸೂತ್ರಾರ್ಥ — the ಅ absorbed into the vowel sign, with
    no literal ಅ left to match. The same sandhi trap as the pratīka in
    Rukmiṇīśa Vijaya.
"""
import importlib.util
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "vaidika_svara" / "segment.py"
_spec = importlib.util.spec_from_file_location("vsp_segment", TOOL)
vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vs)

STAGED = (Path(__file__).resolve().parents[1]
          / "data/ocr_staging/vaidika_svara_prakaranam_prabhakara_adiga_kadri")


def page(*blocks):
    return "".join(f'<p data-layout="{k}">{v}</p>' for k, v in blocks)


# --- citations of another text --------------------------------------------

def test_a_sutra_number_in_parentheses_is_a_citation():
    assert vs.sutra_marks("ಶೇಷಂ ಸರ್ವಮನುದಾತ್ತಮ್ । (ಫಿಟ್ ಸೂತ್ರ-ಪಾದ-೪-ಸೂತ್ರ-೮೭)") == []
    assert [n for _, _, n in vs.sutra_marks("ಪದಾಂತೇ (ಫಿಟ್ ಸೂತ್ರ-೮೫)")] == []


def test_the_guard_is_the_parentheses_and_not_the_word():
    """p98: a citation with no number, then this book's own sūtra 41 OUTSIDE
    it. Excluding on the word ಫಿಟ್ alone lost that sūtra, and a single missing
    unit is the Maṇimañjarī signature."""
    got = vs.sutra_marks("ಅನುದಾತ್ತಶಬ್ದಸೂಚಕಸೂತ್ರಗಳು ( ಫಿಟ್ ಸೂತ್ರ ) ಸೂತ್ರ - ೪೧,")
    assert [n for _, _, n in got] == [41]


def test_kannada_digits_are_read():
    assert [n for _, _, n in vs.sutra_marks("ಸೂತ್ರ-೨೪,")] == [24]
    assert [n for _, _, n in vs.sutra_marks("ಸೂತ್ರ - 24,")] == [24]


# --- the gloss opener ------------------------------------------------------

def test_sutrartha_is_the_gloss_opener_too():
    """ಸೂತ್ರ + ಅರ್ಥ is written ಸೂತ್ರಾರ್ಥ: the ಅ is absorbed into the vowel sign
    on ರ, so (?:ಸೂತ್ರ)?ಅರ್ಥ matches nothing. It is used once, on sūtra 1 —
    the first unit a reader sees — whose exposition sat in the sūtra slot."""
    assert vs.ARTHA.search("ಸೂತ್ರಾರ್ಥ :-ಸೂತ್ರಕಾರ ಶೌನಕರು")
    assert vs.ARTHA.search("ಅರ್ಥ :- ಸ್ವರಗಳನ್ನು")
    m = vs.ARTHA.search("ಸೂತ್ರಾರ್ಥ :- ಇದು")
    assert m.start() == 0, "the longer name must not match as the shorter"


# --- the numbering ---------------------------------------------------------

def test_the_marker_numbers_what_follows_it():
    """The opposite of the bare ॥ N ॥ in the Kāvya works, which numbers what
    precedes."""
    pages = {13: page(("headline", "ಅಥ ಶೌನಕೋಕ್ತಮ್-ಋಗ್ವೇದೀಯ-ಸ್ವರಪ್ರಕರಣಮ್"),
                      ("paragraph", "ಸೂತ್ರ-೧, ಪ್ರಥಮಸೂತ್ರಸ್ಯ ಪಾಠಃ ಅತ್ರ ವರ್ತತೇ"),
                      ("paragraph", "ಸೂತ್ರ-೨, ದ್ವಿತೀಯಸೂತ್ರಸ್ಯ ಪಾಠಃ ಅತ್ರ ವರ್ತತೇ"))}
    r = vs.segment(pages)
    assert r["sutras_found"] == 2 and r["sutras_missing"] == 0
    assert r["units"][(0, 1)]["text"].startswith("ಪ್ರಥಮ")
    assert r["units"][(0, 2)]["text"].startswith("ದ್ವಿತೀಯ")


def test_a_section_is_where_the_numbering_restarts():
    """Not where a heading falls. An earlier pass reset on every ಅಧ್ಯಾಯ heading
    and reported one section as '3 sūtras, 4..6, gaps 1,2,3'."""
    pages = {13: page(("headline", "ಅಥ ಶೌನಕೋಕ್ತಮ್-ಋಗ್ವೇದೀಯ-ಸ್ವರಪ್ರಕರಣಮ್"),
                      ("paragraph", "ಸೂತ್ರ-೧, ಪಾಠಃ ಅತ್ರ ವರ್ತತೇ ಸುದೀರ್ಘಃ"),
                      ("paragraph", "ಸೂತ್ರ-೨, ಪಾಠಃ ಅತ್ರ ವರ್ತತೇ ಸುದೀರ್ಘಃ"),
                      ("paragraph", "ಸೂತ್ರ-೧, ಅನ್ಯಃ ಪಾಠಃ ಅತ್ರ ವರ್ತತೇ ಸುದೀರ್ಘಃ"))}
    r = vs.segment(pages)
    assert [s["found"] for s in r["sections"]] == [2, 1]
    assert (1, 1) in r["units"]


def test_an_adhyaya_heading_inside_a_run_does_not_restart_it():
    pages = {13: page(("headline", "ಅಥ ಪಾಣಿನೀಯ ಸಾಧಾರಣಸ್ವರ-ಪ್ರಕ್ರಿಯಾ"),
                      ("paragraph", "ಸೂತ್ರ-೧, ಪಾಠಃ ಅತ್ರ ವರ್ತತೇ ಸುದೀರ್ಘಃ"),
                      ("headline", "ಅಧ್ಯಾಯ-೨"),
                      ("paragraph", "ಸೂತ್ರ-೨, ಪಾಠಃ ಅತ್ರ ವರ್ತತೇ ಸುದೀರ್ಘಃ"))}
    r = vs.segment(pages)
    assert len(r["sections"]) == 1 and r["sections"][0]["found"] == 2


# --- the prose between the sūtras -----------------------------------------

def test_a_division_heading_ends_the_sutra_and_opens_a_passage():
    """Without this the LAST sūtra of a section ran on to the next marker: 0.34
    swallowed the six pages of ಉಪಕ್ರಮ- after it and 3.46 swallowed ಭಾಗ-೩ and
    the back matter. That prose is the book's own — a fifth of its Kannada —
    so it is kept as its own section rather than discarded."""
    body = "ಗದ್ಯಪಾಠಃ ಅತ್ರ ವರ್ತತೇ ಸುದೀರ್ಘಃ । " * 12
    pages = {13: page(("headline", "ಅಥ ಶೌನಕೋಕ್ತಮ್-ಋಗ್ವೇದೀಯ-ಸ್ವರಪ್ರಕರಣಮ್"),
                      ("paragraph", "ಸೂತ್ರ-೧, ಪಾಠಃ ಅತ್ರ ವರ್ತತೇ ಸುದೀರ್ಘಃ"),
                      ("headline", "ಉಪಕ್ರಮ-"),
                      ("paragraph", body))}
    r = vs.segment(pages)
    assert "ಗದ್ಯಪಾಠಃ" not in r["units"][(0, 1)]["text"], "the sūtra ran on"
    assert len(r["passages"]) == 1
    assert r["passages"][0]["heading"] == "ಉಪಕ್ರಮ-"
    assert "ಗದ್ಯಪಾಠಃ" in r["passages"][0]["text"]


# --- the table of contents -------------------------------------------------

def test_the_contents_sections_are_matched_by_containment():
    """They cannot be paired by position: the contents page has three sections
    and the body four, because the book OMITS the six-sūtra ಅಥ ಸಮಾಸಸ್ವರ
    ವಿಷಯಃ section from it."""
    # Two contents sections, three body sections, and exactly one
    # order-preserving pairing: the middle body section is too short to hold
    # either, and only the last can hold 1..9.
    toc = {(0, n): "t" for n in range(1, 6)}
    toc.update({(1, n): "t" for n in range(1, 10)})
    body = {(0, n): {} for n in range(1, 6)}
    body.update({(1, n): {} for n in range(1, 3)})
    body.update({(2, n): {} for n in range(1, 10)})
    assert vs.align_toc(toc, body) == {0: 0, 1: 2}


def test_an_ambiguous_alignment_attaches_no_titles_at_all():
    """A wrong heading reads as correct, which is worse than none."""
    toc = {(0, 1): "a"}
    body = {(0, 1): {}, (1, 1): {}}
    assert vs.align_toc(toc, body) == {}


# --- the real book ---------------------------------------------------------

def _real():
    if not STAGED.is_dir():
        import pytest
        pytest.skip("Vaidika Svara staging not present")
    return vs.segment(vs.load_pages(str(STAGED)))


def test_the_real_staged_book_is_complete():
    r = _real()
    # 108 pages delivered, 107 with content: p111 is a blank leaf that Sarvam
    # read successfully and correctly returned empty.
    assert r["pages"] == 107
    assert r["page_range"] == [5, 112]
    assert len(r["sections"]) == 4
    assert [s["found"] for s in r["sections"]] == [34, 6, 13, 46]
    assert [s["part"] for s in r["sections"]] == [
        "saunakiya", "saunakiya", "saunakiya", "paniniya"]
    assert r["sutras_found"] == 99
    assert r["sutras_missing"] == 0
    assert r["toc_entries"] == 86
    assert r["with_title"] == 86, "the contents-page alignment slipped"
    assert r["with_artha"] == 77
    assert len(r["passages"]) == 7
    # The contents page and the body must pair uniquely; three sections there
    # against four here, because the book omits one from its own contents.
    assert r["toc_sections_matched"] == 3


def test_the_addressed_sutras_are_actually_unit_SHAPED():
    """A count of addresses says nothing about what stands under them.
    Rukmiṇīśa Vijaya was landed on its counts and was 71% plausible: 287 of its
    verses were nothing but a verse number. Only the screenshot showed it."""
    r = _real()
    U = r["units"]
    lengths = [len(u["text"]) for u in U.values()]
    assert min(lengths) >= 40, "an empty or near-empty unit"
    assert max(lengths) <= 6000, "a unit that ran on into the next section"
    assert sum(1 for n in lengths if 60 <= n <= 6000) / len(U) >= 0.95

    # No unit may still contain a marker of its own, stand under two
    # addresses, or hold another unit's text.
    assert not [u for u in U.values() if vs.sutra_marks(u["text"])]
    assert len({u["text"] for u in U.values()}) == len(U)
    assert len({u["title"] for u in U.values() if u["title"]}) == r["with_title"]


def test_almost_nothing_of_the_body_is_left_unplaced():
    """The check that would have caught the sūtras running on, and the one that
    says the prose passages are worth keeping: 98% of the body's Kannada ends
    up under an address."""
    import re
    r = _real()
    pages = vs.load_pages(str(STAGED))
    kn = lambda t: len(re.findall(r"[ಀ-೿]", t))
    placed = (sum(kn(u["text"]) for u in r["units"].values())
              + sum(kn(p["text"]) for p in r["passages"]))
    whole = 0
    for p in sorted(pages):
        if p < vs.FIRST_BODY_PAGE:
            continue
        for m in vs.BLOCK.finditer(pages[p]):
            if m.group(2) in vs.SKIP_LAYOUTS:
                continue
            whole += kn(vs.untag(m.group(3)))
    assert placed / whole >= 0.97, f"{placed} of {whole}"
    assert r["unattached_blocks"] <= 2


def test_both_engines_ran_the_whole_book():
    """Sarvam refused this book once with HTTP 402 -- an empty prepaid balance,
    not a refusal of the content -- and the re-dispatch took all 108 pages."""
    if not STAGED.is_dir():
        import pytest
        pytest.skip("Vaidika Svara staging not present")
    v = vs.vision_pages(str(STAGED))
    assert len(v) >= 108 and min(v) == 1 and max(v) == 112
