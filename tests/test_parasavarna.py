"""Parasavarṇa -> anusvāra: the Python tool and the JS mirror must agree."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import parasavarna  # noqa: E402

CASES = [
    ("इन्द्र", "इंद्र"),
    ("अङ्ग", "अंग"),
    ("कुण्ड", "कुंड"),
    ("सम्पूर्ण", "संपूर्ण"),
    ("पञ्च", "पंच"),
    ("श्रीसुमतीन्द्रतीर्थः", "श्रीसुमतींद्रतीर्थः"),
    # real conjuncts, not parasavarṇa: must be left alone
    ("अन्न", "अन्न"),
    ("धन्य", "धन्य"),
    ("ब्रह्म", "ब्रह्म"),
    ("सन्स्कार", "सन्स्कार"),
    ("rāma", "rāma"),
]


@pytest.mark.parametrize("src,want", CASES)
def test_python(src, want):
    assert parasavarna.to_anusvara(src) == want


def test_only_indic_targets():
    assert parasavarna.for_script("इन्द्र", "kannada") == "इंद्र"
    assert parasavarna.for_script("इन्द्र", "iast") == "इन्द्र"
    assert parasavarna.for_script("इन्द्र", "devanagari") == "इन्द्र"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_mirror_agrees():
    src = (ROOT / "js" / "transliteration.js").read_text(encoding="utf-8")
    m = re.search(r"const DGE_PARASAVARNA_CLASSES.*?\n}\n", src, re.S)
    assert m, "dgeParasavarna block not found in js/transliteration.js"
    block = src[m.start():src.index("\n}\n", src.index("function dgeParasavarna")) + 3]
    script = block + "\nconsole.log(JSON.stringify(" + json.dumps([c[0] for c in CASES], ensure_ascii=False) + ".map(dgeParasavarna)));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    assert json.loads(out) == [c[1] for c in CASES]
