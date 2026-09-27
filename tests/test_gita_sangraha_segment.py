"""Gītā Vyākhyāna Saṅgraha — the five of fifteen that were not already here.

Each test is a measurement that came back wrong, not a rule that sounded
right.
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
seg = _load("gs_segment", "tools/gita_sangraha/segment.py")
wl = _load("gs_write_layers", "tools/gita_sangraha/write_layers.py")

STAGED = REPO / "data/ocr_staging/giia_vyakhyana_sangr__ntaries_on_bhagavad_gita_v1"


@pytest.fixture(scope="module")
def units():
    if not STAGED.is_dir():
        pytest.skip("staged OCR not checked out")
    return seg.segment()


# ------------------------------------------------------- what not to write

def test_only_the_five_on_the_mula_gita_are_written():
    """Ten of the fifteen are already in the library, matched by author:
    the Gītābhāṣya division under DvaitaVedantaIn/gita_prasthana/gita_bhashya
    and the Gītātātparya division under gita_tatparya_nirnaya."""
    assert set(wl.COMMENTATORS) == seg.WRITTEN
    assert len(wl.COMMENTATORS) == 5
    already = {name for _, name in seg.ALREADY_LANDED}
    assert not (already & set(wl.COMMENTATORS))


def test_the_ten_are_still_read_so_they_cannot_drift(units):
    """Read, so their blocks are consumed, then dropped. Unread, a
    Bhāvadīpa block would be swallowed by whichever of the five preceded
    it."""
    seen = {k for u in units for k in u["layers"]}
    assert seen & {name for _, name in seg.ALREADY_LANDED}


def test_the_bhavaratnakosha_marker_is_read_both_ways():
    """``भा०र०`` comes through as ``भा०२०`` -- र as २ -- on 93 blocks of
    volume 1 alone. One spelling loses a tenth of it into its neighbour."""
    pat = dict((n, p) for p, n in seg.ALREADY_LANDED)["bhavaratnakosha"]
    assert pat.match("भा०र०— अथ")
    assert pat.match("भा०२०— अथ")


# ------------------------------------------------------------- the markers

def test_a_marker_set_down_twice_is_stripped_twice():
    """``अ०प्र०— अ०प्र०— पूर्वाध्याये…`` -- 12 blocks do this, and
    stripping once leaves the second sitting in the commentary as text."""
    hit, rest = seg.strip_marker("अ०प्र०— अ०प्र०— पूर्वाध्याये संसार")
    assert hit == "anvayaprakashika"
    assert rest.startswith("पूर्वाध्याये")


def test_each_of_the_five_is_recognised():
    for text, want in (("वि०वि०— कथम्", "gitavivrti"),
                       ("वा०ल०— 'मा ते", "gitalakshalankara"),
                       ("सा०सं०— ननु", "gitasarasangraha"),
                       ("अ०प्र०— तर्हि", "anvayaprakashika"),
                       ("त्रि०वि०— अत्र", "trividharthavivrti")):
        assert seg.strip_marker(text)[0] == want, text


# ------------------------------------------------------------ the address

def test_the_running_header_is_not_what_addresses(units):
    """It does carry the verse, but only a third of pages have one and they
    reach 453 of 700, with two impossible adhyāyas (57, 58) in the noise --
    and it is spelt both ``अध्याय`` and ``अध्यायः``, so matching one found
    volume 1 alone and called volumes 2-4 headerless."""
    assert seg.ADDRESS.search("अध्यायः ३ - श्लोकः १५")
    assert seg.ADDRESS.search("अध्याय २ - श्लोकः २४")


def test_the_ids_run_forward_and_land_on_real_verses(units):
    ids = [u["id"] for u in units if u.get("id")]
    order = [tuple(int(x) for x in i.split(".")) for i in ids]
    assert order == sorted(order)
    assert ids[0].startswith("1.")
    assert ids[-1] == "18.78"


def test_both_halves_of_a_split_verse_address_it(units):
    """A long verse is set as two half-verses under two ``गीता`` titles.
    The first half advanced the scan past the verse, so the second matched
    nothing and its commentary was dropped -- 46 units."""
    cont = [u for u in units if u.get("continues")]
    assert len(cont) > 20
    assert all(u.get("id") for u in cont)


def test_a_short_block_cannot_claim_a_verse():
    """Containment scoring is generous; the length floor is what stops it
    matching anything at all."""
    assert seg.score("रामः", "अ" * 60, 0.78) == 0.0


# ------------------------------------------------------------- the content

def test_the_addressed_units_are_actually_VERSE_shaped(units):
    for u in units:
        if not u.get("id"):
            continue
        for key, text in u["layers"].items():
            assert text.strip(), (u["id"], key)


def test_no_stored_commentary_still_carries_its_marker(units):
    found = wl.collect(units)
    for vid, layers in found.items():
        for key, text in layers.items():
            assert not any(p.match(text) for p, _ in seg.ALL_MARKERS), (vid, key)


def test_coverage_is_the_whole_gita(units):
    import collections
    per = collections.Counter(k for u in units if u.get("id")
                              for k in u["layers"] if k in seg.WRITTEN)
    assert per["gitasarasangraha"] > 600
    assert per["gitavivrti"] > 600
    assert per["anvayaprakashika"] > 600
    adhyayas = {int(u["id"].split(".")[0]) for u in units if u.get("id")}
    assert adhyayas == set(range(1, 19))


# -------------------------------------------------------------- the merge

def test_merge_appends_and_never_duplicates_a_commentator():
    payload = {"items": [{"shlokas": [
        {"number": 1, "bhashya": [{"commentator": "Swami Sivananda",
                                   "text": "T", "language": "english",
                                   "kind": "translation"}]}]}]}
    found = {1: {"gitavivrti": "A" * 40, "gitasarasangraha": "B" * 40}}
    wl.merge(payload, found)
    arr = payload["items"][0]["shlokas"][0]["bhashya"]
    assert arr[0]["commentator"] == "Swami Sivananda"   # untouched, and first
    assert len(arr) == 3
    stats = wl.merge(payload, found)                    # again: a no-op
    assert stats["added"] == 0 and stats["kept"] == 2
    assert len(arr) == 3


def test_a_written_entry_is_shaped_like_the_ones_already_there():
    payload = {"items": [{"shlokas": [{"number": 1, "bhashya": []}]}]}
    wl.merge(payload, {1: {"gitavivrti": "x" * 40}})
    e = payload["items"][0]["shlokas"][0]["bhashya"][0]
    assert set(e) == {"commentator", "text", "language", "kind"}
    assert e["language"] == "sanskrit" and e["kind"] == "commentary"


def test_a_two_character_fragment_is_not_a_commentary():
    assert wl.MIN_CHARS >= 10


# ------------------------------------------------- the files it writes into

def test_canonical_round_trips_every_adhyaya_byte_for_byte():
    for a in seg.ADHYAYAS:
        p = REPO / wl.TARGET.format(a)
        original = p.read_text(encoding="utf-8")
        assert wl.canonical(json.loads(original)) == original, a


def test_the_gita_still_has_all_its_verses_and_its_older_commentators():
    import collections
    total, who = 0, collections.Counter()
    for a in seg.ADHYAYAS:
        d = json.loads((REPO / wl.TARGET.format(a)).read_text(encoding="utf-8"))
        for s in d["items"][0]["shlokas"]:
            total += 1
            assert s.get("sanskrit_text")
            who.update(e["commentator"] for e in s.get("bhashya") or [])
    assert total == 701
    assert who["Swami Ramsukhdas"] == 1402
    assert who["Sri Madhavacharya"] == 700
    assert who["Sri Jayatritha"] == 700


def test_the_five_actually_landed_in_the_files():
    import collections
    who = collections.Counter()
    for a in seg.ADHYAYAS:
        d = json.loads((REPO / wl.TARGET.format(a)).read_text(encoding="utf-8"))
        for s in d["items"][0]["shlokas"]:
            who.update(e["commentator"] for e in s.get("bhashya") or [])
    for name in wl.COMMENTATORS.values():
        assert who[name] > 40, (name, who[name])


def test_no_provenance_reached_the_files():
    for a in seg.ADHYAYAS:
        d = json.loads((REPO / wl.TARGET.format(a)).read_text(encoding="utf-8"))
        for s in d["items"][0]["shlokas"]:
            for e in s.get("bhashya") or []:
                if e["commentator"] in wl.COMMENTATORS.values():
                    assert "http://" not in e["text"]
                    assert "https://" not in e["text"]
