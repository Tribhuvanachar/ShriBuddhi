"""gemini_bench.py tests -- only the network-free logic (sample loading,
chunking, cost math). The actual model/concurrency comparisons need a real
GEMINI_API_KEY and are run manually via .github/workflows/gemini-bench.yml,
not exercised here."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import gemini_bench as gb
from link_english_commentary import save_json


class TestLoadSampleVerses(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gemini-bench-test-"))
        self.sarga_path = self.tmp / "data.json"
        save_json(self.sarga_path, {
            "metadata": {"totalShlokas": 3},
            "shlokas": {
                "1": {"sa": "verse one", "commentaries": {"pavamanacharya_english": "trans one"}},
                "2": {"sa": "  ", "commentaries": {}},
                "3": {"sa": "verse three", "commentaries": {}},
            },
        })

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_skips_blank_verses_and_caps_at_n(self):
        verses = gb.load_sample_verses(self.sarga_path, 2)
        self.assertEqual([v["index"] for v in verses], ["1", "3"])

    def test_carries_the_english_translation_when_present(self):
        verses = gb.load_sample_verses(self.sarga_path, 1)
        self.assertEqual(verses[0]["en"], "trans one")

    def test_does_not_mutate_the_source_file(self):
        before = self.sarga_path.read_text(encoding="utf-8")
        gb.load_sample_verses(self.sarga_path, 10)
        after = self.sarga_path.read_text(encoding="utf-8")
        self.assertEqual(before, after)


class TestChunked(unittest.TestCase):
    def test_splits_into_even_groups(self):
        self.assertEqual(gb._chunked([1, 2, 3, 4], 2), [[1, 2], [3, 4]])

    def test_last_group_may_be_short(self):
        self.assertEqual(gb._chunked([1, 2, 3], 2), [[1, 2], [3]])


class TestCost(unittest.TestCase):
    def test_computes_input_and_output_cost_separately(self):
        usage = {"prompt_tokens": 1_000_000, "output_tokens": 500_000}
        cost = gb._cost(usage, price_in=0.75, price_out=3.75)
        self.assertAlmostEqual(cost, 0.75 + 1.875)

    def test_missing_usage_fields_default_to_zero(self):
        self.assertEqual(gb._cost({}, 1.0, 1.0), 0.0)

    def test_thinking_tokens_are_billed_at_the_output_rate(self):
        # real observed shape for gemini-flash-latest: thoughts_tokens can
        # exceed output_tokens and must not be left out of the cost
        usage = {"prompt_tokens": 1_000_000, "output_tokens": 200_000, "thoughts_tokens": 300_000}
        cost = gb._cost(usage, price_in=0.75, price_out=3.75)
        self.assertAlmostEqual(cost, 0.75 + (200_000 + 300_000) / 1_000_000 * 3.75)


if __name__ == "__main__":
    unittest.main()
