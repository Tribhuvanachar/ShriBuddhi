"""The catalogue stamp must match the files it stamps.

js/core.js and js/layer-stitch.js now fetch library.json and
layer_manifest.json at `?v=<hash from data/catalog-version.json>` so the
browser can cache them. That is only safe while the stamp is current: a
content push that forgets to re-run the stamper would leave every reader
holding the previous catalogue, and a newly added grantha would be invisible
to them with nothing in the logs to say why. This turns that into a failing
test instead.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAMP = ROOT / "data/catalog-version.json"
TOOL = ROOT / "tools/stamp_catalog_version.py"


def _digest(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()[:12]


def test_stamp_matches_the_catalogue_files():
    stamp = json.loads(STAMP.read_text(encoding="utf-8"))
    assert stamp["library"] == _digest("data/library.json"), (
        "library.json changed without re-running tools/stamp_catalog_version.py")
    assert stamp["manifest"] == _digest("data/layer_manifest.json"), (
        "layer_manifest.json changed without re-running "
        "tools/stamp_catalog_version.py")


def test_stamper_is_idempotent():
    proc = subprocess.run([sys.executable, str(TOOL), "--check"],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_reader_asks_for_the_stamp_uncached_and_the_rest_by_hash():
    """The whole point is one small uncached file and big cacheable ones.
    If someone reinstates cache:'no-store' on library.json the 521 KB per
    page view comes straight back, silently."""
    core = (ROOT / "js/core.js").read_text(encoding="utf-8")
    stitch = (ROOT / "js/layer-stitch.js").read_text(encoding="utf-8")
    assert "'data/catalog-version.json?t=' + Date.now()" in core
    assert "'data/library.json?v=' + v.library" in core
    assert "'data/layer_manifest.json?v=' + v.manifest" in stitch
    # The no-store fallbacks are deliberate (a deployment that has not stamped
    # yet must still be correct), but they must stay FALLBACKS, reached only
    # when the stamp is missing -- never the primary path.
    for src, name in ((core, "library.json"), (stitch, "layer_manifest.json")):
        assert f"fetch('data/{name}?t=' + Date.now(), {{ cache: 'no-store' }})" in src
        assert src.count(f"data/{name}?t=") == 1
