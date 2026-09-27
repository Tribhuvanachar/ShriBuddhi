"""tools/aitareya/write_layers.py must not put OCR on the shelf unchecked.

Two things make this tool dangerous in a way segment.py is not: it writes
into the corpus, and three of the layers it would write already exist, so
a careless run replaces text a reader can see today.

So the tests here are mostly about refusal:

  * it will not write staged content that records no proofread pass,
    because the pipeline is OCR -> Gemini proofread -> place -> test ->
    merge, and Maṇimañjarī showed what raw OCR hides -- a Devanāgarī line
    read as Kannada, a 306-verse work landing as 305, and nothing
    downstream noticing;
  * it will not invent a unit_title. A block addressed to a khaṇḍa the
    shelf does not have is skipped and counted, not given a plausible
    heading -- a skipped block is visible, a mislabelled one reads as
    correct.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "tools/aitareya/write_layers.py"


def load():
    spec = importlib.util.spec_from_file_location("write_layers", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


wl = load()
SHELF = wl.shelf_units()


def a_real_address():
    """A shelf address, as the NUMERIC triple addresses now are."""
    return next(iter(SHELF))


def names_of(addr):
    """The shelf's own spelling of that address, for building a test block."""
    return SHELF[addr]["names"]


def test_shelf_addresses_are_read_not_guessed():
    assert len(SHELF) >= 30, "the reference layer stopped yielding addresses"
    for addr, unit in SHELF.items():
        assert len(addr) == 3 and all(isinstance(x, int) for x in addr)
        assert unit["unit_title"], f"{addr} has no unit_title to borrow"
        assert len(unit["names"]) == 3


def test_block_keeps_the_shelf_s_own_unit_title():
    addr = a_real_address()
    nm = names_of(addr)
    blocks = [{"layer": "tika_bhashyartha_ratnamala", "page": 1,
               "text": "परीक्षार्थः पाठः",
               "aranyaka_name": nm[0], "adhyaya_name": nm[1], "khanda_name": nm[2]}]
    files, stats = wl.build("ratnamala", blocks, SHELF)
    assert stats["placed"] == 1
    item = files["tika_bhashyartha_ratnamala"]["items"][0]
    assert item["unit_title"] == SHELF[addr]["unit_title"]
    assert item["reference"].endswith(item["unit_title"])
    assert item["section"] == names_of(addr)[2]
    assert item["breadcrumb"][-1] == item["unit_title"]


def test_address_the_shelf_lacks_is_skipped_not_invented():
    # An address that PARSES but that the shelf does not carry. (A block with
    # no parseable address at all is a different case -- it goes to the
    # anchoring pass, which the tests below cover.)
    absent = next((2, ad, kh) for ad in range(1, 9) for kh in range(1, 9)
                  if (2, ad, kh) not in SHELF)
    names = ([k for k, v in wl.ARANYAKA_NUM.items() if v == 2][0],
             [k for k, v in wl.ADHYAYA_NUM.items() if v == absent[1]][0],
             [k for k, v in wl.KHANDA_NUM.items() if v == absent[2]][0])
    blocks = [{"layer": "tika_khandartha", "page": 1, "text": "पाठः",
               "aranyaka_name": names[0], "adhyaya_name": names[1],
               "khanda_name": names[2]}]
    assert wl.address_of(blocks[0]) == absent and absent not in SHELF
    files, stats = wl.build("ratnamala", blocks, SHELF)
    assert stats["address_not_on_shelf"] == 1
    assert stats["placed"] == 0
    assert files == {}


def test_addresses_are_numbers_not_names():
    """Compared as numbers, never as spellings.

    The shelf writes the seventh khaṇḍa सप्त: खण्ड: and the ṭippaṇī's running
    head writes it सप्तम: खण्ड:. They are the same khaṇḍa. While addresses were
    strings, 23 blocks that had a home all along were counted "not on shelf"
    and dropped -- silently, because a dropped block looks exactly like a
    khaṇḍa the volume does not cover."""
    assert wl.address_of({"aranyaka": 2, "adhyaya": 1, "khanda": 1}) == (2, 1, 1)
    assert wl.address_of({"aranyaka": 2, "adhyaya": 99, "khanda": 1}) is None
    assert wl.address_of({"page": 5}) is None
    a = wl.address_of({"aranyaka_name": "द्वितीयारण्यके",
                       "adhyaya_name": "प्रथमोऽध्यायः", "khanda_name": "सप्त: खण्ड:"})
    b = wl.address_of({"aranyaka_name": "द्वितीयारण्यके",
                       "adhyaya_name": "प्रथमोऽध्यायः", "khanda_name": "सप्तम: खण्ड:"})
    assert a == b == (2, 1, 7), (a, b)


def test_the_reference_layer_is_the_mula():
    """It was tika_bhashya, which is a COMMENTARY and carries 31 of the mūla's
    38 khaṇḍas. Seven khaṇḍas that exist in the text therefore had no address,
    and every block addressed to one was dropped -- 153 blocks, among them the
    whole of Viśveśvara Tīrtha's ṭīkā, 298 blocks and 453,151 characters. That
    read as a deliberate hold rather than as a bug. The mūla defines where a
    commentary can attach; a commentary does not."""
    assert wl.REF_LAYER.name == "data.json"
    assert wl.REF_LAYER.parent.name == "mula"
    assert len(SHELF) == 38


# --- the blocks that open a volume, before its running head prints one -----

def _anchor_blocks():
    """Two shelf units, and a run of blocks: front matter, then a block that
    quotes the first unit, a continuation, then one that quotes the second."""
    first, second = sorted(SHELF)[0], sorted(SHELF)[1]
    t1 = SHELF[first]["unit_title"]
    t2 = SHELF[second]["unit_title"]
    mk = lambda pg, txt: {"layer": "tika_upanishat", "page": pg, "text": txt}
    return first, second, [
        mk(1, "(मङ्गलाचरणम्) नारायणं निखिलपूर्णगुणैकदेहम्"),
        mk(2, t1 + " इति व्याख्यायते"),
        mk(3, "तस्यैव विवरणं क्रियते"),
        mk(4, t2 + " इति व्याख्यायते"),
    ]


def test_unaddressed_blocks_anchor_on_the_mula_the_edition_quotes():
    first, second, blocks = _anchor_blocks()
    got = wl.anchor_unaddressed(blocks, SHELF)
    assert got[0] == wl.FRONT_MATTER, "front matter must not take a khaṇḍa"
    assert got[1] == first
    assert got[2] == first, "a continuation stays with the anchor above it"
    assert got[3] == second


def test_anchoring_is_abandoned_when_the_anchors_are_out_of_order():
    """A wrong address is worse than none: a hole is visible and a wrong
    address is not. So the whole pass is dropped rather than part-trusted."""
    first, second, blocks = _anchor_blocks()
    blocks[1]["text"], blocks[3]["text"] = blocks[3]["text"], blocks[1]["text"]
    assert wl.anchor_unaddressed(blocks, SHELF) == {}


def test_anchoring_is_abandoned_when_a_run_is_broken():
    first, second, blocks = _anchor_blocks()
    blocks.append({"layer": "tika_upanishat", "page": 5,
                   "text": SHELF[first]["unit_title"] + " पुनरुक्तम्"})
    assert wl.anchor_unaddressed(blocks, SHELF) == {}


def test_front_matter_gets_a_unit_of_its_own():
    """The maṅgalācaraṇam and the history of the Upaniṣad belong to the work,
    not to any khaṇḍa, and sort before khaṇḍa 1."""
    unit = wl.FRONT_MATTER_UNIT(SHELF)
    assert unit["unit_title"]
    assert wl.FRONT_MATTER < min(SHELF)
    blocks = [{"layer": "tika_upanishat", "page": 1,
               "text": "(मङ्गलाचरणम्) नारायणं निखिलपूर्णगुणैकदेहम्"}]
    files, stats = wl.build("ratnamala", blocks, SHELF)
    assert stats["front_matter"] == 1 and stats["no_address"] == 0
    item = files["tika_upanishat"]["items"][0]
    assert item["unit_title"] == unit["unit_title"]
    assert "" not in item["breadcrumb"], "an empty breadcrumb segment"


def test_blocks_for_one_khanda_join_in_page_order():
    addr = a_real_address()
    nm = names_of(addr)
    mk = lambda pg, t: {"layer": "tika_khandartha", "page": pg, "text": t,
                        "aranyaka_name": nm[0], "adhyaya_name": nm[1],
                        "khanda_name": nm[2]}
    files, _ = wl.build("ratnamala", [mk(9, "तृतीयम्"), mk(3, "प्रथमम्"), mk(6, "द्वितीयम्")], SHELF)
    body = files["tika_khandartha"]["items"][0]["sanskrit_text"]
    assert body.split("\n") == ["प्रथमम्", "द्वितीयम्", "तृतीयम्"]


def test_write_refuses_unproofread_staged_content(tmp_path, monkeypatch, capsys):
    """The refusal is the point. If this ever passes silently, raw OCR can
    reach the shelf."""
    staged = tmp_path / "staged"
    staged.mkdir()
    addr = a_real_address()
    (staged / "ratnamala_segmented.json").write_text(json.dumps({
        "blocks": [{"layer": "tika_khandartha", "page": 1, "text": "पाठः",
                    "aranyaka_name": names_of(addr)[0],
                    "adhyaya_name": names_of(addr)[1],
                    "khanda_name": names_of(addr)[2]}]}, ensure_ascii=False))
    out = tmp_path / "shelf"
    monkeypatch.setattr(wl, "STAGED", staged)
    monkeypatch.setattr(wl, "TARGET", out)
    monkeypatch.setattr("sys.argv", ["write_layers.py", "--write", "--volumes", "ratnamala"])
    wl.main()
    assert "refusing to write" in capsys.readouterr().out
    assert not out.exists(), "it wrote to the shelf despite refusing"


def test_allow_unproofread_is_what_actually_writes(tmp_path, monkeypatch):
    staged = tmp_path / "staged"
    staged.mkdir()
    addr = a_real_address()
    (staged / "ratnamala_segmented.json").write_text(json.dumps({
        "blocks": [{"layer": "tika_khandartha", "page": 1, "text": "पाठः",
                    "aranyaka_name": names_of(addr)[0],
                    "adhyaya_name": names_of(addr)[1],
                    "khanda_name": names_of(addr)[2]}]}, ensure_ascii=False))
    out = tmp_path / "shelf"
    monkeypatch.setattr(wl, "STAGED", staged)
    monkeypatch.setattr(wl, "TARGET", out)
    monkeypatch.setattr("sys.argv", ["write_layers.py", "--write", "--volumes",
                                     "ratnamala", "--allow-unproofread"])
    wl.main()
    written = out / "tika_khandartha/data.json"
    assert written.is_file()
    doc = json.loads(written.read_text())
    assert doc["schema"] == wl.SCHEMA
    assert doc["items"][0]["provenance"]["from"].endswith("ratnamala_segmented.json")


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    real = wl.TARGET
    before = {p: p.stat().st_mtime_ns for p in real.glob("*/data.json")}
    assert before, "nothing to watch -- the shelf is empty, so this proves nothing"
    monkeypatch.setattr("sys.argv", ["write_layers.py"])
    wl.main()
    after = {p: p.stat().st_mtime_ns for p in real.glob("*/data.json")}
    assert after == before, "a dry run touched the shelf"


def test_it_shelves_the_proofread_text_not_the_raw_ocr():
    """The whole point of the Gemini pass is that its output reaches the
    shelf. An earlier version read b["text"] unconditionally, so a paid
    pass over 1,406 blocks would have been written to disk and then
    ignored -- and nothing would have looked wrong, because the output is
    well-formed either way. Money spent, no trace.
    """
    addr = a_real_address()
    block = {"layer": "tika_khandartha", "page": 1,
             "text": "कच्चा पाठः",                    # what OCR read
             "text_proofread": "संस्कृतः पाठः",        # what Gemini returned
             "aranyaka_name": addr[0], "adhyaya_name": addr[1],
             "khanda_name": addr[2]}
    files, stats = wl.build("ratnamala", [block], SHELF)
    item = files["tika_khandartha"]["items"][0]
    assert item["sanskrit_text"] == "संस्कृतः पाठः", "shelved the raw OCR"
    assert stats["proofread_text"] == 1 and stats["raw_text"] == 0
    assert item["provenance"]["text"] == "Gemini-proofread"


def test_a_block_with_no_proofread_falls_back_and_says_so():
    """Falling back is right -- a block Gemini could not reach should still
    be placed -- but it must not claim to be proofread."""
    addr = a_real_address()
    block = {"layer": "tika_khandartha", "page": 1, "text": "कच्चा पाठः",
             "aranyaka_name": addr[0], "adhyaya_name": addr[1],
             "khanda_name": addr[2]}
    files, stats = wl.build("ratnamala", [block], SHELF)
    item = files["tika_khandartha"]["items"][0]
    assert item["sanskrit_text"] == "कच्चा पाठः"
    assert stats["raw_text"] == 1 and stats["proofread_text"] == 0
    assert "NOT proofread" in item["provenance"]["text"]


def test_an_empty_proofread_does_not_blank_the_text():
    """Gemini returning "" must not wipe a block. The raw reading is worse
    than the proofread one and better than nothing."""
    addr = a_real_address()
    block = {"layer": "tika_khandartha", "page": 1, "text": "कच्चा पाठः",
             "text_proofread": "   ",
             "aranyaka_name": addr[0], "adhyaya_name": addr[1],
             "khanda_name": addr[2]}
    files, _ = wl.build("ratnamala", [block], SHELF)
    assert files["tika_khandartha"]["items"][0]["sanskrit_text"] == "कच्चा पाठः"
