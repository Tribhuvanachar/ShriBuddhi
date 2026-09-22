"""site_parity.py's repopulate_library must not advertise a dead link.

The first version tested `is_file()`. Every one of the Anandamakaranda
shelf's ten upanisad books carries an empty tika_jayatirtha and an empty
tippani beside it -- files that exist and hold "items": [] -- so that test
marked 328 entries populated in each downstream repo which open to
nothing. That is precisely the failure the function exists to prevent, and
the commit that introduced it claimed to be preventing it.

So: a file must carry units, in whichever of the corpus's three shapes it
uses, or it is not populated.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("site_parity", ROOT / "tools/site_parity.py")
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)


def w(tmp_path, name, payload):
    p = tmp_path / name
    p.write_text(json.dumps(payload, ensure_ascii=False))
    return p


def test_empty_shapes_are_not_units(tmp_path):
    assert sp.has_units(w(tmp_path, "a.json", {"items": []})) is False
    assert sp.has_units(w(tmp_path, "b.json", {"shlokas": {}})) is False
    assert sp.has_units(w(tmp_path, "c.json", [])) is False
    assert sp.has_units(w(tmp_path, "d.json", {"schema": "x"})) is False
    assert sp.has_units(tmp_path / "nope.json") is False


def test_populated_shapes_are_units(tmp_path):
    assert sp.has_units(w(tmp_path, "e.json", {"items": [{"id": 1}]})) is True
    assert sp.has_units(w(tmp_path, "f.json", {"shlokas": {"1": {"sa": "x"}}})) is True
    assert sp.has_units(w(tmp_path, "g.json", [{"id": 1}])) is True


def test_unreadable_file_is_not_populated(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json")
    assert sp.has_units(p) is False


def test_the_real_library_advertises_nothing_empty():
    """The live check, against this repo's own library.json: every grantha
    marked populated must actually open to something."""
    lib = json.loads((ROOT / "data/library.json").read_text())
    dead = [g["path"] for g in lib["granthas"]
            if g.get("populated") and not sp.has_units(ROOT / g["path"])]
    assert not dead, f"{len(dead)} granthas marked populated open to nothing: {dead[:5]}"


def test_repopulate_library_itself_rejects_an_empty_layer(tmp_path):
    """Testing has_units alone is not enough: repopulate_library has to
    actually call it. Reverting that one line to is_file() left every test
    above passing, which is how the 328 dead links got shipped in the first
    place. This drives the real function over a real library.json.
    """
    (tmp_path / "data").mkdir()
    full = tmp_path / "data/full"
    empty = tmp_path / "data/empty"
    for d in (full, empty):
        d.mkdir()
    (full / "data.json").write_text(json.dumps({"items": [{"id": "x"}]}))
    (empty / "data.json").write_text(json.dumps({"items": []}))
    (tmp_path / "data/library.json").write_text(json.dumps({"granthas": [
        {"path": "data/full/data.json", "populated": False, "title": "has text"},
        {"path": "data/empty/data.json", "populated": True, "title": "exists, empty"},
        {"path": "data/gone/data.json", "populated": True, "title": "no file"},
    ]}))

    on, off = sp.repopulate_library(tmp_path)
    assert (on, off) == (1, 2), f"expected 1 populated, got {on} populated / {off} not"

    got = {g["path"]: g["populated"]
           for g in json.loads((tmp_path / "data/library.json").read_text())["granthas"]}
    assert got["data/full/data.json"] is True
    assert got["data/empty/data.json"] is False, "an empty layer was advertised as populated"
    assert got["data/gone/data.json"] is False
