"""The Dvaita Gita layers joined onto DvaitaVedantaIn by verse address.

Guards three things that are easy to break silently:
  * the spine's verse addressing still covers adhyayas 2-18 completely, and
    still covers adhyaya 1 not at all (the edition treats it as one summary
    unit -- a number that CHANGES here is a finding, either way);
  * every generated layer joins 100% -- a layer that quietly stops matching
    would render as an empty commentary tab, not as an error;
  * the layers still equal what the verse tree says, so the two copies of
    these commentaries cannot drift apart unnoticed.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / ("data/darshana/vedanta/dvaita/DvaitaVedantaIn/gita_prasthana"
                 "/gita_bhashya")
TOOL = ROOT / "tools/gita_verse_addressing/build_dvaita_gita_layers.py"

# Canonical verse counts, adhyayas 2-18 (adhyaya 1 is deliberately absent).
EXPECTED_REFS = 72 + 43 + 42 + 29 + 47 + 30 + 28 + 34 + 42 + 55 + 20 + 35 + 27 + 20 + 24 + 28 + 78


def _roster():
    # Every segmenter/builder in tools/ is named for its job, but several
    # share a module name across folders -- load by path under a unique name.
    spec = importlib.util.spec_from_file_location("dvaita_gita_layers", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ROSTER


@pytest.fixture(scope="module")
def spine_refs():
    data = json.loads((TARGET / "mula/data.json").read_text(encoding="utf-8"))
    return {r for it in data["items"] for r in (it.get("verse_refs") or [])}


def test_spine_covers_adhyayas_two_to_eighteen(spine_refs):
    assert len(spine_refs) == EXPECTED_REFS
    missing = [f"{a}.{v}" for a, n in (
        (2, 72), (3, 43), (4, 42), (5, 29), (6, 47), (7, 30), (8, 28), (9, 34),
        (10, 42), (11, 55), (12, 20), (13, 35), (14, 27), (15, 20), (16, 24),
        (17, 28), (18, 78)) for v in range(1, n + 1) if f"{a}.{v}" not in spine_refs]
    assert missing == []


def test_adhyaya_one_has_no_verse_units(spine_refs):
    """Not a gap to fix: DvaitaVedanta.in carries Madhva's first-adhyaya
    bhashya as one summary unit, so 1.1-1.47 have no spine unit to land on.
    If this ever starts passing verses, the edition changed shape."""
    assert [r for r in spine_refs if r.startswith("1.")] == []


@pytest.mark.parametrize("folder", [r[1] for r in _roster()])
def test_every_layer_unit_joins_the_spine(folder, spine_refs):
    items = json.loads((TARGET / folder / "data.json").read_text(encoding="utf-8"))["items"]
    assert items, f"{folder} is empty"
    orphans = [it["ref"] for it in items if it.get("ref") not in spine_refs]
    assert orphans == [], f"{folder}: {len(orphans)} units join nothing"


def test_manifest_reports_every_layer_fully_matched():
    manifest = json.loads((ROOT / "data/layer_manifest.json").read_text(encoding="utf-8"))
    rel = TARGET.relative_to(ROOT / "data").as_posix()
    layers = {l["folder"]: l for l in manifest["granthas"][rel]["layers"]}
    for _, folder, label, _, _ in _roster():
        assert folder in layers, f"{folder} missing from the layer manifest"
        assert layers[folder]["matched"] == layers[folder]["items"], folder
        assert layers[folder]["label"] == label


def test_layers_still_equal_the_verse_tree():
    """The layers are derived data. Regenerate and diff, so an edit to either
    copy of these commentaries surfaces here instead of drifting."""
    proc = subprocess.run([sys.executable, str(TOOL), "--check"],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
