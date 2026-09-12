"""Replay every engine-verified example verse in tests/fixtures/chandas_examples.json.

The fixture grows as tools/chandas/apply_gemini_chandas.py accepts examples (from our own corpus,
the Chandojñānam sample file, or Gemini's answers to GEMINI_CHANDAS_TASK.md); each entry must keep
being identified as its vṛtta by js/chandas.js.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "chandas_examples.json"
RUNNER = ROOT / "tools" / "kamadhenu" / "chandas_runner.js"
EXAMPLES = json.loads(FIXTURE.read_text(encoding="utf-8"))["examples"] if FIXTURE.exists() else []

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


@pytest.fixture(scope="module")
def results():
    r = subprocess.run(["node", str(RUNNER)], input=json.dumps([e["text"] for e in EXAMPLES], ensure_ascii=False),
                       capture_output=True, text=True, cwd=str(ROOT), check=True)
    return dict(zip((e["vrutta"] for e in EXAMPLES), json.loads(r.stdout)))


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["vrutta"] for e in EXAMPLES])
def test_example_is_identified(example, results):
    res = results[example["vrutta"]]
    raw = (res.get("match") or {}).get("names") or []
    names = set(raw) | {x.strip() for n in raw for x in n.split(",")}
    wanted = {example["vrutta"]} | {x.strip() for x in example["vrutta"].split(",")}
    assert names & wanted, f"{example['source']}: engine said {raw}"
    scan = ["".join("G" if c == "ग" else "L" for c in p["pattern"]) for p in res["padas"]]
    assert scan == example["scan"]
