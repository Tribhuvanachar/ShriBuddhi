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
    return next(iter(SHELF))


def test_shelf_addresses_are_read_not_guessed():
    assert len(SHELF) >= 30, "the reference layer stopped yielding addresses"
    for addr, unit in SHELF.items():
        assert len(addr) == 3 and all(addr)
        assert unit["unit_title"], f"{addr} has no unit_title to borrow"


def test_block_keeps_the_shelf_s_own_unit_title():
    addr = a_real_address()
    blocks = [{"layer": "tika_bhashyartha_ratnamala", "page": 1,
               "text": "परीक्षार्थः पाठः",
               "aranyaka_name": addr[0], "adhyaya_name": addr[1], "khanda_name": addr[2]}]
    files, stats = wl.build("ratnamala", blocks, SHELF)
    assert stats["placed"] == 1
    item = files["tika_bhashyartha_ratnamala"]["items"][0]
    assert item["unit_title"] == SHELF[addr]["unit_title"]
    assert item["reference"].endswith(item["unit_title"])
    assert item["section"] == addr[2]
    assert item["breadcrumb"][-1] == item["unit_title"]


def test_address_the_shelf_lacks_is_skipped_not_invented():
    blocks = [{"layer": "tika_khandartha", "page": 1, "text": "पाठः",
               "aranyaka_name": "चतुर्थारण्यके",
               "adhyaya_name": "नवमोऽध्यायः", "khanda_name": "नवम: खण्ड:"}]
    files, stats = wl.build("ratnamala", blocks, SHELF)
    assert stats["address_not_on_shelf"] == 1
    assert stats["placed"] == 0
    assert files == {}


def test_numeric_coordinates_map_onto_shelf_names():
    """bhagavantaraya carries the numbers its running head prints. That
    mapping is the whole reason the coordinate is usable, so pin it."""
    addr = wl.address_of({"aranyaka": 2, "adhyaya": 1, "khanda": 1})
    assert addr == ("द्वितीयारण्यके", "प्रथमोऽध्यायः", "प्रथम: खण्ड:")
    assert wl.address_of({"aranyaka": 2, "adhyaya": 99, "khanda": 1}) is None
    assert wl.address_of({"page": 5}) is None


def test_blocks_for_one_khanda_join_in_page_order():
    addr = a_real_address()
    mk = lambda pg, t: {"layer": "tika_khandartha", "page": pg, "text": t,
                        "aranyaka_name": addr[0], "adhyaya_name": addr[1],
                        "khanda_name": addr[2]}
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
                    "aranyaka_name": addr[0], "adhyaya_name": addr[1],
                    "khanda_name": addr[2]}]}, ensure_ascii=False))
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
                    "aranyaka_name": addr[0], "adhyaya_name": addr[1],
                    "khanda_name": addr[2]}]}, ensure_ascii=False))
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
