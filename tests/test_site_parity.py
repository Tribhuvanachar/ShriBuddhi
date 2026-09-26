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


def test_library_json_is_not_frozen_downstream():
    """PER_REPO must not hold data/library.json.

    Protecting it looked right -- its `populated` flags are repo-specific --
    and froze every downstream catalogue instead. A grantha added here
    never appeared there at all: BrahmaBuddhi sat at 1,696 entries against
    this repo's 1,716, so Manimanjari's eight sargas were invisible in the
    repo where review is supposed to happen.

    The right order is copy THEN repopulate. sync() copies, main() calls
    repopulate_library() straight after, and that is what makes the file
    repo-specific. Excluding it from the copy skipped the first half.
    """
    assert "data/library.json" not in sp.PER_REPO
    assert "sitemap.xml" in sp.PER_REPO, "sitemap.xml IS per-repo and must stay protected"


def test_sync_copies_the_catalogue_then_repopulates_it(tmp_path, monkeypatch):
    """Drives the real pair: a target whose catalogue is missing a grantha
    ends up with it listed, and flagged by what the target actually holds."""
    src, dst = tmp_path / "src", tmp_path / "dst"
    for r in (src, dst):
        (r / "data").mkdir(parents=True)
        (r / ".git").mkdir()
    (src / "data/library.json").write_text(json.dumps({"granthas": [
        {"path": "data/old/data.json", "populated": True, "title": "old"},
        {"path": "data/new/data.json", "populated": True, "title": "new upstream"},
    ]}))
    (dst / "data/library.json").write_text(json.dumps({"granthas": [
        {"path": "data/old/data.json", "populated": True, "title": "old"},
    ]}))
    # the target holds `old` but not `new`
    (dst / "data/old").mkdir()
    (dst / "data/old/data.json").write_text(json.dumps({"items": [{"id": 1}]}))

    monkeypatch.setattr(sp, "ROOT", src)
    rel = [Path("data/library.json")]
    report = sp.classify(dst, rel)
    sp.sync(dst, rel, report, overwrite=True)
    on, off = sp.repopulate_library(dst)

    got = json.loads((dst / "data/library.json").read_text())["granthas"]
    paths = {g["path"]: g["populated"] for g in got}
    assert len(got) == 2, "the upstream catalogue did not come down"
    assert paths["data/old/data.json"] is True
    assert paths["data/new/data.json"] is False, "flagged populated without the file"
    assert (on, off) == (1, 1)


# --- the split-layer shape ------------------------------------------------
# A layer too large for one file is an index -- {units_total, parts} -- with
# the text in sibling part-NNN.json files keyed `units`. Nyaya Sudha's 8
# layers hold 27,413 units that way and were every one marked populated:false,
# so the reader answered "This text hasn't been added to the library" for the
# whole grantha. has_units looked for items/shlokas/units and the index has
# none of them.

def idx(tmp_path, **kw):
    return w(tmp_path, "data.json", {"schema": "grantha_tika_text", "work": "w",
                                     "layer": "l", **kw})


def test_a_populated_split_layer_counts_as_populated(tmp_path):
    assert sp.has_units(idx(tmp_path, units_total=7826,
                            parts=["part-001.json", "part-002.json"])) is True


def test_a_split_layer_declaring_zero_units_does_not(tmp_path):
    assert sp.has_units(idx(tmp_path, units_total=0, parts=["part-001.json"])) is False


def test_an_index_with_no_parts_does_not(tmp_path):
    assert sp.has_units(idx(tmp_path, units_total=10, parts=[])) is False


def test_with_no_declared_total_it_reads_a_part(tmp_path):
    w(tmp_path, "part-001.json", {"units": [{"id": "1"}, {"id": "2"}]})
    assert sp.has_units(idx(tmp_path, parts=["part-001.json"])) is True


def test_with_no_declared_total_and_empty_parts_it_is_not_populated(tmp_path):
    w(tmp_path, "part-001.json", {"units": []})
    assert sp.has_units(idx(tmp_path, parts=["part-001.json"])) is False


def test_a_missing_part_file_is_not_treated_as_content(tmp_path):
    assert sp.has_units(idx(tmp_path, parts=["part-nope.json"])) is False


def test_the_real_nyaya_sudha_layers_are_populated():
    base = (ROOT / "data/darshana/vedanta/dvaita/DvaitaVedantaIn"
                   "/sutra_prasthana/anuvyakhyana_sudha")
    if not base.is_dir():
        import pytest
        pytest.skip("Nyaya Sudha not present")
    layers = [d for d in sorted(base.iterdir()) if d.is_dir()]
    assert layers
    for d in layers:
        assert sp.has_units(d / "data.json") is True, d.name
