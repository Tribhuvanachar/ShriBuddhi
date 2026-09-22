"""proofread.py spends money from several threads at once. Prove it cannot
overspend, cannot charge for a call that failed, and cannot lose work.

The first version called Gemini one block at a time and took over two
hours for 1,406 blocks, with the implied rate worsening as it went --
gemini_client's HTTP timeout is 60 s with no retry, so one slow call
stalls the whole queue behind it. Concurrency fixes the clock and
introduces three ways to lose money instead:

  * N workers each deciding there is room for the same last rupee;
  * a failed call still counted against the budget, so a run stops early
    having bought nothing with the difference;
  * a block whose result is dropped because two threads wrote the file at
    once, which means paying for it again on the next run.

Each has a test. None of these calls Gemini -- call_gemini is substituted.
"""
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "tools/aitareya/proofread.py"


def load():
    spec = importlib.util.spec_from_file_location("aitareya_proofread", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def staged(tmp_path, n_blocks, chars=1127):
    """A staged volume of n identical blocks, each costing exactly one page."""
    d = tmp_path / "staged"
    d.mkdir(exist_ok=True)
    (d / "vol_segmented.json").write_text(json.dumps({
        "blocks": [{"page": i, "layer": "x", "text": "क" * chars}
                   for i in range(n_blocks)]}, ensure_ascii=False))
    return d


def run(mod, tmp_path, argv, fake):
    mod.call_gemini = fake
    mod.GeminiError = RuntimeError
    monkey_argv = ["proofread.py"] + argv
    old = sys.argv
    sys.argv = monkey_argv
    try:
        mod.main()
    finally:
        sys.argv = old


def test_budget_stops_the_run_under_concurrency(tmp_path, monkeypatch):
    """A budget of 1.5 pages buys 1 page, with 16 workers running.

    HONEST LIMIT: this does NOT prove the lock around the check-and-debit.
    Removing that lock leaves this passing, because in CPython the
    read-check-write window is a few bytecodes and nothing a test can inject
    from outside lands inside it. The lock is correct by construction --
    check and debit must be one step or N workers each find room for the
    same last rupee -- and this test covers the ordinary case only: that the
    budget is enforced at all when more than one thread is spending.
    """
    mod = load()
    d = staged(tmp_path, 16)
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    calls = []
    lock = threading.Lock()

    def fake(*a, **k):
        with lock:
            calls.append(1)
        return {"text": "ठीक", "classification": "accept"}

    run(mod, tmp_path, ["--volumes", "vol", "--staged-dir", str(d),
                        "--budget", str(mod.RATE_PER_PAGE * 1.5), "--real",
                        "--concurrency", "16"], fake)
    assert len(calls) == 1, f"bought {len(calls)} pages on a 1.5-page budget"


def test_a_failed_call_is_not_charged(tmp_path, monkeypatch):
    mod = load()
    d = staged(tmp_path, 20)
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    n = {"i": 0}
    lock = threading.Lock()

    def fake(*a, **k):
        with lock:
            n["i"] += 1
            mine = n["i"]
        if mine <= 10:
            raise RuntimeError("simulated timeout")
        return {"text": "ठीक", "classification": "accept"}

    budget = mod.RATE_PER_PAGE * 15
    run(mod, tmp_path, ["--volumes", "vol", "--staged-dir", str(d),
                        "--budget", str(budget), "--real", "--concurrency", "4"], fake)
    doc = json.loads((d / "vol_segmented.json").read_text())
    ok = [b for b in doc["blocks"] if b.get("text_proofread")]
    # 10 failed and must not have eaten budget, so the 10 that worked all land
    assert len(ok) == 10, f"{len(ok)} blocks proofread; failures were charged"
    assert doc.get("proofread") is not True, "marked proofread with blocks still undone"


def test_every_bought_block_is_written(tmp_path, monkeypatch):
    """What is paid for must reach the file. A dropped result is paid twice."""
    mod = load()
    d = staged(tmp_path, 120)
    monkeypatch.setenv("GEMINI_API_KEY", "test")

    def fake(*a, **k):
        return {"text": "ठीक", "classification": "accept"}

    run(mod, tmp_path, ["--volumes", "vol", "--staged-dir", str(d),
                        "--budget", "999", "--real", "--concurrency", "12"], fake)
    doc = json.loads((d / "vol_segmented.json").read_text())
    done = [b for b in doc["blocks"] if b.get("text_proofread")]
    assert len(done) == 120, f"only {len(done)} of 120 survived the write"
    assert doc["proofread"] is True


def test_rerunning_a_finished_file_spends_nothing(tmp_path, monkeypatch):
    mod = load()
    d = staged(tmp_path, 30)
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    calls = []

    def fake(*a, **k):
        calls.append(1)
        return {"text": "ठीक", "classification": "accept"}

    args = ["--volumes", "vol", "--staged-dir", str(d), "--budget", "999",
            "--real", "--concurrency", "8"]
    run(mod, tmp_path, args, fake)
    first = len(calls)
    run(mod, tmp_path, args, fake)
    assert first == 30 and len(calls) == 30, (
        f"resume re-sent blocks: {len(calls) - first} extra calls")
