"""tools/build_manimanjari.py must not land a Maṇimañjarī that is wrong.

The staged split arrived with two defects, and the reason they mattered is
that nothing downstream would have caught either one:

  * the Kannada ṭīkā had a block with no verse number, so sarga 3 held 30
    units and sarga 4 held 40 -- a total that still came to 306 and so still
    looked right in every aggregate;
  * mūla 4.30 was absent entirely, because Sarvam read that Devanāgarī line
    as Kannada. A 306-verse work landed with 305 and no check complained.

So the builder's job is not only to repair those two; it is to refuse when
the numbers do not add up. These tests exercise the refusal, because a
validator that never fires is indistinguishable from no validator.

The builder reads its input from a git ref, so the tests drive the pure
functions -- repair(), validate(), build() -- over fixtures built in memory,
and never run the --write path. Nothing here touches the working tree: an
earlier test in this repo rebuilt a tracked JSON file on every run and
dirtied the tree, which is what test_writes_nothing below exists to prevent.
"""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "tools/build_manimanjari.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_manimanjari", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bm = load_module()


def make_layers():
    """A clean staged corpus carrying exactly the two known defects."""
    layers = {}
    for name in bm.LAYERS:
        blocks = []
        for sarga, total in bm.CANONICAL.items():
            for v in range(1, total + 1):
                if name == "mula" and sarga == 4 and v == 30:
                    continue                      # defect 2: the dropped verse
                if name == "tika_kannada" and sarga == 3 and v == 31:
                    continue                      # defect 1: becomes the orphan
                blocks.append({"id": f"s{sarga}_v{v}", "type": name,
                               "sarga": sarga, "verse": v, "page": 100 + sarga,
                               "pages": [100 + sarga],
                               "text": f"{name} {sarga}.{v} पाठः ಪಾಠ",
                               "ocr_confidence": 0.9})
        layers[name] = blocks
    layers["tika_kannada"].append({
        "id": "s4_vNone", "type": "tika_kannada", "sarga": 4, "verse": None,
        "page": 173, "pages": [173], "text": "ಆದಿ, ದೇವಃ = ...", "ocr_confidence": 0.5})
    return layers


def test_repairs_both_defects_and_validates():
    layers = make_layers()
    log = bm.repair(layers)
    assert len(log) == 2
    bm.validate(layers)          # must not raise
    kan = [b for b in layers["tika_kannada"] if b["sarga"] == 3 and b["verse"] == 31]
    assert len(kan) == 1 and kan[0]["provenance"]["relabelled"] is True
    mula = [b for b in layers["mula"] if b["sarga"] == 4 and b["verse"] == 30]
    assert len(mula) == 1 and mula[0]["provenance"]["recovered"] is True


def test_recovered_verse_is_the_text_the_page_prints():
    """The reading that separates the page from Vision's OCR is पुत्रीं.

    Vision read पुत्र. If this constant is ever "corrected" back to the OCR
    reading, the shelf would carry a verse that is both unmetrical and at
    odds with the ṭīkā's own gloss (पुत्री नीलां), so it is pinned here.
    """
    assert "नग्नजितःपुत्रीं" in bm.MULA_4_30
    assert bm.MULA_4_30.count("॥") == 2
    for name in ("नीलां", "मित्रविन्दां", "कैकयसुतां", "लक्षणां"):
        assert name in bm.MULA_4_30


def test_refuses_when_a_verse_is_missing():
    layers = make_layers()
    bm.repair(layers)
    layers["tika_sanskrit"] = [b for b in layers["tika_sanskrit"]
                               if not (b["sarga"] == 5 and b["verse"] == 20)]
    with pytest.raises(SystemExit, match="canonical counts"):
        bm.validate(layers)


def test_refuses_when_a_verse_is_duplicated():
    layers = make_layers()
    bm.repair(layers)
    dup = dict([b for b in layers["mula"] if b["sarga"] == 2 and b["verse"] == 5][0])
    layers["mula"].append(dup)
    with pytest.raises(SystemExit, match="canonical counts"):
        bm.validate(layers)


def test_refuses_to_patch_a_split_that_has_changed():
    """If the staged file no longer carries the defect, the repair is stale
    and must not be applied blind on top of whatever is there now."""
    layers = make_layers()
    layers["mula"].append({"id": "s4_v30", "type": "mula", "sarga": 4,
                           "verse": 30, "page": 190, "pages": [190],
                           "text": "somebody already fixed this"})
    with pytest.raises(SystemExit, match="staged split has changed"):
        bm.repair(layers)


def test_refuses_a_second_unnumbered_block():
    layers = make_layers()
    layers["tika_kannada"].append({"id": "s6_vNone", "type": "tika_kannada",
                                   "sarga": 6, "verse": None, "page": 250,
                                   "pages": [250], "text": "another orphan"})
    with pytest.raises(SystemExit, match="exactly 1 unnumbered"):
        bm.repair(layers)


def test_built_shape_matches_the_kavya_shelf():
    layers = make_layers()
    bm.repair(layers)
    built = bm.build(layers)
    assert sorted(built) == sorted(bm.CANONICAL)
    for sarga, data in built.items():
        md = data["metadata"]
        assert md["totalShlokas"] == bm.CANONICAL[sarga] == len(data["shlokas"])
        assert set(md["availableCommentaries"]) == {"sanskrit_tika", "kannada_tika"}
        for v, unit in data["shlokas"].items():
            assert unit["sa"], f"{sarga}.{v} has no mūla"
            # every verse carries both ṭīkās -- that is the claim in the docs
            assert set(unit["commentaries"]) == {"sanskrit_tika", "kannada_tika"}
        json.dumps(data, ensure_ascii=False)   # must be serialisable as written


def test_writes_nothing():
    """Driving repair/validate/build must not touch a single file on disk.

    An earlier test in this repo rebuilt a tracked JSON file on every run and
    dirtied the working tree, so this checks the thing itself: it snapshots
    the mtime and size of every file the builder could plausibly write --
    the eight sarga files and data/library.json -- runs the whole pipeline,
    and asserts nothing moved. Comparing `git status` instead would not
    work: it cannot tell a file this test wrote from one landed by hand
    before the test ran.
    """
    watched = [ROOT / "data/library.json"]
    watched += sorted((ROOT / "data/Tattvavada/Itara/Kavya/manimanjari").glob("*/data.json"))
    before = {f: (f.stat().st_mtime_ns, f.stat().st_size) for f in watched if f.exists()}
    assert before, "nothing to watch -- the shelf is not built, so this proves nothing"

    layers = make_layers()
    bm.repair(layers)
    bm.validate(layers)
    bm.build(layers)

    after = {f: (f.stat().st_mtime_ns, f.stat().st_size) for f in watched if f.exists()}
    assert after == before, (
        "the builder wrote to disk without --write: "
        f"{sorted(str(f.relative_to(ROOT)) for f in before if before.get(f) != after.get(f))}")
