"""Saṅgraha Rāmāyaṇam — six things that were measurably wrong first.

सङ्ग्रहरामायणम् of Nārāyaṇa Paṇḍitācārya, the same hand as the Sumadhva
Vijaya and the Maṇimañjarī, with Viśvapati Tīrtha's Bhāvārthadīpikā and
Bannañje Govindācārya's Saṅgrahacandrikā. Two volumes, 1,525 pages.

Unlike the other works landed this week this one is a grantha of its own:
neither the mūla nor either commentary was anywhere in the library.
"""
import json
import sys

import pytest

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _load(name, rel):
    """Under a name of its own: every segmenter here is ``segment.py``."""
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sys.path.insert(0, str(REPO / "tools" / "ocr_common"))
seg = _load("sr_segment", "tools/sangraha_ramayana/segment.py")
ws = _load("sr_write_shelf", "tools/sangraha_ramayana/write_shelf.py")

STAGED = REPO / "data/ocr_staging/sangraha_ramayanam_n__mentaries_bhavartha_dipi_v1"
SHELF = REPO / "data/Tattvavada/Itara/Kavya/sangraha_ramayana"


@pytest.fixture(scope="module")
def units():
    if not STAGED.is_dir():
        pytest.skip("staged OCR not checked out")
    return seg.segment()


# ------------------------------------------------------------- the address

def test_the_sarga_comes_from_the_colophon_not_the_running_head(units):
    """The head does carry it -- ``बालकां.स.५`` -- but only alternate pages
    have one, so an address held over from the last page that had one lands
    a whole page of verses in the sarga before theirs: 174 duplicate numbers
    and 960 gaps, and a verse from the middle of the work as verse 1."""
    sargas = {(u["kanda"], u["sarga"]) for u in units}
    assert len(sargas) == 64, sorted(sargas)


def test_the_kanda_is_read_from_the_name_in_front_of_kanda():
    """The colophons misspell it: Ayodhyā is set ``अयोद्धयाकाण्डे`` and
    ``अयोद्ध्याकाण्डे``, never ``अयोध्या``. Matching the correct spelling
    dropped the whole kāṇḍa -- 582 verses -- and silently renumbered the
    sargas of every kāṇḍa after it."""
    stems = {slug: stem for stem, slug, _ in seg.KANDAS}
    assert stems["ayodhya_kanda"] in "अयोद्ध्या"
    assert stems["aranya_kanda"] in "अरण्य"       # printed with the short अ


def test_every_kanda_is_present(units):
    got = {u["kanda"] for u in units}
    assert got == {slug for _, slug, _ in seg.KANDAS}


# -------------------------------------------------------------- the verses

def test_a_verse_labelled_paragraph_is_still_a_verse():
    """758 verses -- a third of the work -- come through as ``paragraph``
    rather than as a title. What marks one either way is what sits under
    it: its number alone on a line, or the first commentary."""
    assert seg.is_verse_block("paragraph", "क" * 40, "॥ २६ ॥")
    assert seg.is_verse_block("paragraph", "क" * 40, "(भा.दी.) अथ")
    assert not seg.is_verse_block("paragraph", "क" * 40, "ordinary prose")
    assert seg.is_verse_block("section-title", "क" * 40, "anything")


def test_a_footnote_is_never_a_verse():
    """The footnotes are variant readings -- 263 of them sit directly above
    a bare number, which is exactly the shape of a verse."""
    assert not seg.is_verse_block("footnote", "क" * 40, "॥ २६ ॥")


def test_the_furniture_around_a_sarga_break_is_not_a_verse():
    """The contents line for the sarga coming up, the Saṅgrahacandrikā's
    closing line, the editor's prose. One of those became verse 1 of 22 of
    the 64 sargas."""
    assert not seg.is_really_a_verse({"number": None, "layers": {}})
    assert seg.is_really_a_verse({"number": 3, "layers": {}})
    assert seg.is_really_a_verse({"number": None, "layers": {"bhavarthadipika": "x"}})


def test_the_pithika_is_not_part_of_the_first_sarga(units):
    """Volume 1 gives 72 pages to it before the mūla begins, and because
    the first colophon does not come until the end of sarga 1 all of it
    fell inside that sarga -- a line from a bibliography as verse 1."""
    first = [u for u in units
             if u["kanda"] == "bala_kanda" and u["sarga"] == "1"
             and u["number"] == 1][0]
    assert first["verse"].startswith("भूषारत्नं")


# ------------------------------------------------------------ the numbering

def test_verses_are_keyed_by_position_and_the_key_is_sound(units):
    """The printed numbers give 144 duplicates and 1,587 gaps read straight
    off the page, because the book sets a verse's number on the line below
    it and the scan drops and repeats those lines."""
    import collections
    by = collections.defaultdict(list)
    for u in units:
        by[(u["kanda"], u["sarga"])].append(u["number"])
    for key, numbers in by.items():
        assert sorted(numbers) == list(range(1, len(numbers) + 1)), key


def test_the_printed_number_is_kept_beside_it(units):
    """Nothing is thrown away: a reader sees what the page says."""
    kept = sum(1 for u in units if u.get("printed"))
    assert kept > 3000


# -------------------------------------------------------------- the content

def test_the_verses_are_actually_VERSE_shaped(units):
    for u in units:
        assert seg.MIN_VERSE <= len(u["verse"]) <= seg.MAX_VERSE, u["verse"][:60]
        for key, text in u["layers"].items():
            assert text.strip(), (u["kanda"], u["sarga"], u["number"], key)


def test_both_commentaries_reach_most_of_the_work(units):
    import collections
    per = collections.Counter(k for u in units for k in u["layers"])
    assert per["bhavarthadipika"] > 3000
    assert per["sangrahacandrika"] > 2000


# ---------------------------------------------------------------- the shelf

def test_the_modern_commentary_is_gated_not_published():
    """Bannañje Govindācārya's own, first published in this 2015 edition.
    Holding it back is reversible; publishing it is not."""
    assert "sangrahacandrika" in ws.GATED
    core = (REPO / "js/core.js").read_text(encoding="utf-8")
    assert "sangrahacandrika: true" in core


def test_the_gate_actually_runs_on_the_shape_this_work_uses():
    """It did not. DGE_COPYRIGHT_GATED_COMMENTARY_KEYS was applied in the
    flat-items branch and defensively in the nested-shlokas branch, but
    dgeNormalizeGranthaData returned the plain {metadata, shlokas} shape --
    the one every kāvya on the shelf uses -- untouched, so a gated key
    rendered to a reader, pill and all. Found by gating the Saṅgrahacandrikā
    and then watching it render."""
    core = (REPO / "js/core.js").read_text(encoding="utf-8")
    head = core[core.index("function dgeNormalizeGranthaData"):]
    head = head[:head.index("// Display labels")]
    assert "dgeVisibleCommentaries" in head, \
        "the kavya branch returns before the gate is applied"
    assert "availableCommentaries" in head, \
        "a gated key would still be listed in the picker"


def test_the_traditional_commentary_is_not_gated():
    assert "bhavarthadipika" not in ws.GATED


def test_every_sarga_becomes_a_file_the_reader_can_read():
    if not SHELF.is_dir():
        pytest.skip("not landed")
    dirs = sorted(d.name for d in SHELF.iterdir() if d.is_dir())
    assert len(dirs) == 64
    for d in dirs:
        payload = json.loads((SHELF / d / "data.json").read_text(encoding="utf-8"))
        shlokas = payload["shlokas"]
        assert shlokas, d
        assert sorted(int(k) for k in shlokas) == list(range(1, len(shlokas) + 1))
        assert payload["metadata"]["totalShlokas"] == len(shlokas)
        assert payload["metadata"]["author"] == "Narayana Panditacharya"


def test_it_is_on_the_go_live_shelf():
    overrides = json.loads(
        (REPO / "admin/config/library-overrides.json").read_text(encoding="utf-8"))
    allow = (overrides.get("shelf") or {}).get("allow") or []
    assert any(a.endswith("Kavya/sangraha_ramayana") for a in allow), allow


def test_no_provenance_reaches_the_shelf():
    if not SHELF.is_dir():
        pytest.skip("not landed")
    for d in SHELF.iterdir():
        if not d.is_dir():
            continue
        blob = (d / "data.json").read_text(encoding="utf-8")
        assert "source_url" not in blob
        assert "http://" not in blob and "https://" not in blob
