"""Ṛksaṃhitā with nine vyākhyānas — what went wrong, and now cannot again.

Every test here is a measurement that came back wrong, not a rule that
sounded right.
"""
import json
import sys

import pytest

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _load(name, rel):
    """Under a name of its own: every segmenter here is ``segment.py``, so a
    plain import resolves to whichever one reached sys.modules first. The
    two files landed the same week, and the second one's import silently
    handed the first one's tests the wrong module -- 21 failures in a file
    nothing had touched."""
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

sys.path.insert(0, str(REPO / "tools" / "ocr_common"))
seg = _load("rs_segment", "tools/ruksamhita/segment.py")
wl = _load("rs_write_layers", "tools/ruksamhita/write_layers.py")

STAGED = REPO / "data/ocr_staging/ruksamhita__ruksamhita_9_vyakhyanagalu_bhaga_1"
MANDALA = REPO / "data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json"


@pytest.fixture(scope="module")
def units():
    if not STAGED.is_dir():
        pytest.skip("staged OCR not checked out")
    return seg.segment()


# ------------------------------------------------------- what not to write

def test_sayana_is_captured_but_never_written():
    """The corpus already has Sāyaṇa on 1,337 of these mantras.

    He is still read, so his block is consumed and does not drift into the
    commentary above it -- but a second copy is a duplicate, not a layer.
    """
    assert "sayana" in seg.ALREADY_LANDED
    assert "sayana" not in wl.LABELS


def test_the_samhita_and_padapatha_are_not_written_either():
    """Both are already on the shelf, with accents this OCR does not carry."""
    assert not {"samhita_patha", "pada_patha"} & set(wl.LABELS)


def test_every_written_key_has_a_label():
    for key in wl.LABELS:
        assert wl.LABELS[key].strip()


# ------------------------------------------------------------- the anchor

def test_a_quoted_rk_is_not_an_anchor(units):
    """The Nītimañjarī quotes ṛks to illustrate its maxims --
    ``अत्रार्थे ऋक् (ऋ.१.१.६)-`` and then the whole mantra with its
    padapāṭha. Anchoring on the mantra text landed on those quotations and
    skipped 1.1.7 and 1.1.8, because 1.1.9's quotation was met first, inside
    the commentary on 1.1.6. The book's own label is what is anchored on.
    """
    ids = [u["id"] for u in units if u.get("id")]
    assert ids == sorted(ids, key=lambda i: [int(x) for x in i.split(".")])
    assert len(ids) == len(set(ids)), "an id was given to two units"


def test_the_first_mantra_of_a_sukta_still_matches(units):
    """It is preceded by the sūkta's own header -- count, ṛṣi, devatā,
    metre -- so a comparison from the front of the block fails. 144 of the
    145 unaddressed on the first run were exactly this."""
    first_of_sukta = [u for u in units
                      if u.get("id") and u["id"].split(".")[2] == "1"]
    assert len(first_of_sukta) > 80
    assert all(u.get("match", 0) >= 0.78 for u in first_of_sukta)


def test_candidate_probes_steps_past_a_header():
    head = "१० पराशरः । शाक्त्यः । अग्निः । द्विपदा विराट् । पश्वा न तायुं गुहा"
    probes = seg.candidate_probes(head)
    assert len(probes) > 1
    assert any(p.startswith("पश्वा") for p in probes), probes


# --------------------------------------------------------- duplicate pages

def test_a_repeated_page_number_alone_is_not_a_duplicate(units):
    """The front matter is numbered separately and restarts, so volume 1
    prints a page 3 in the prologue and another in the body. Dropping by
    printed number alone threw away 110 mantras; the content has to agree
    too."""
    ids = {u["id"] for u in units if u.get("id")}
    assert len(ids) > 1150, f"only {len(ids)} mantras survived de-duplication"


def test_the_duplicate_scans_are_still_removed(units):
    """Two scans of one page open two units for one mantra, and the second
    goes unaddressed with its commentary lost."""
    assert sum(1 for u in units if not u.get("id")) < 25


# ---------------------------------------------------- introductions vs body

def test_a_commentarys_own_introduction_is_not_a_mantra(units):
    """Volume 1 gives pages 33-105 to the nine introductions, one after
    another, under a single mantra label. Read as a mantra, that filed
    131,513 characters as Madhva's gloss on 1.1.1 -- against a median of 134
    for that layer."""
    biggest = max((len(t) for u in units for t in u["layers"].values()),
                  default=0)
    assert biggest < 40000, f"a layer of {biggest} chars is not one gloss"


def test_mantra_one_has_no_per_mantra_apparatus(units):
    """Not a gap: the edition treats it through the introductions, and the
    per-mantra body starts at the second mantra."""
    ids = [u["id"] for u in units if u.get("id")]
    assert ids[0] == "1.1.2"


# ------------------------------------------------------------- the content

def test_the_addressed_units_are_actually_MANTRA_shaped(units):
    for u in units:
        if not u.get("id"):
            continue
        assert len(u["mantra"]) >= 20, (u["id"], u["mantra"])
        for key, text in u["layers"].items():
            assert text.strip(), (u["id"], key)


def test_the_layers_are_the_ones_the_edition_prints(units):
    seen = {k for u in units for k in u["layers"]}
    assert seen <= set(wl.LABELS) | seg.ALREADY_LANDED, seen


def test_coverage_is_what_the_edition_covers(units):
    """Maṇḍala 1 only, and the three Dvaita layers stop when Madhva's
    Ṛgbhāṣya does, which is why their counts are the smaller ones."""
    import collections
    per = collections.Counter(k for u in units if u.get("id")
                              for k in u["layers"])
    assert per["siddhanjana"] > 1100
    assert per["mudgala"] > 1100
    assert per["venkatamadhava"] > 1100
    assert 300 < per["rgbhashya"] < per["siddhanjana"]
    assert all(u["id"].startswith("1.") for u in units if u.get("id"))


# -------------------------------------------------------------- the merge

def test_merge_never_overwrites_a_commentary_already_there():
    """The repository has been bitten the other way round: a --fix that
    replaced instead of merging deleted source_url from 214 entries and
    reported it as a success."""
    payload = {"items": [{"id": "1.1.1",
                          "commentaries": {"sayana": "ALREADY", "griffith": "G"}}]}
    stats = wl.merge(payload, {"1.1.1": {"sayana": "NEW", "mudgala": "M"}})
    com = payload["items"][0]["commentaries"]
    assert com["sayana"] == "ALREADY"
    assert com["griffith"] == "G"
    assert com["mudgala"] == "M"
    assert stats["kept"] == 1 and stats["added"] == 1


def test_merge_reports_an_id_the_file_does_not_have():
    payload = {"items": [{"id": "1.1.1", "commentaries": {}}]}
    stats = wl.merge(payload, {"9.9.9": {"mudgala": "x"}})
    assert stats["unknown"] == 1


def test_a_two_character_fragment_is_not_a_commentary():
    assert wl.MIN_CHARS >= 10


# ------------------------------------------------- the file it writes into

def test_canonical_round_trips_the_mandala_byte_for_byte():
    """This is what lets the merge touch one line per mantra instead of
    reflowing the file. Two earlier attempts elsewhere in this repository
    produced a 26,611-line diff and a 3.7-million-insertion diff."""
    original = MANDALA.read_text(encoding="utf-8")
    payload = json.loads(original)
    assert wl.canonical(payload) == original


def test_the_mandala_still_has_every_mantra_and_its_padapatha():
    d = json.loads(MANDALA.read_text(encoding="utf-8"))
    items = d["items"]
    assert len(items) == 2006
    assert all(i.get("samhita_patha") for i in items)
    assert sum(1 for i in items if i.get("pada_patha")) == 2006


def test_the_new_layers_actually_landed_in_the_file():
    d = json.loads(MANDALA.read_text(encoding="utf-8"))
    import collections
    keys = collections.Counter()
    for i in d["items"]:
        keys.update((i.get("commentaries") or {}).keys())
    for key in wl.LABELS:
        assert keys[key] > 20, (key, keys[key])


def test_the_layers_already_there_were_left_exactly_as_they_were():
    """The counts maṇḍala 1 carried before this import, unchanged. Sāyaṇa is
    the one that matters: he is one of the edition's nine, and a second copy
    of him would have been a duplicate rather than a layer."""
    d = json.loads(MANDALA.read_text(encoding="utf-8"))
    import collections
    keys = collections.Counter()
    for i in d["items"]:
        keys.update((i.get("commentaries") or {}).keys())
    assert keys["sayana"] == 1971
    assert keys["sayana_sukta"] == 190
    assert keys["griffith"] == 1963
    assert keys["elizarenkova"] == 2006
    assert keys["grassmann"] == 2006
    assert keys["geldner"] == 2005
    assert keys["oldenberg"] == 436
    assert keys["macdonell"] == 105


def test_no_provenance_reached_the_file():
    d = json.loads(MANDALA.read_text(encoding="utf-8"))
    for i in d["items"]:
        for key in wl.LABELS:
            text = (i.get("commentaries") or {}).get(key)
            if text:
                assert "http://" not in text and "https://" not in text
