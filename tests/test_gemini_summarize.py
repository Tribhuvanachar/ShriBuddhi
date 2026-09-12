"""gemini_summarize.py tests. Generic client mechanics are covered in
tests/test_gemini_client.py; this file covers only this script's own
logic (which fields get filled, idempotency, dry-run mock). No network."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import gemini_summarize as gs
from link_english_commentary import load_json, save_json


class TestAnalyzeShloka(unittest.TestCase):
    def test_dry_run_fills_all_three_fields_by_default(self):
        shloka = {"sa": "रामो राजमणिः सदा विजयते", "commentaries": {}}
        changed = gs.analyze_shloka(shloka, None, "m", dry_run=True, force=False,
                                     fields=["padaccheda", "anvaya", "summary"])
        self.assertTrue(changed)
        self.assertIn("gemini_padaccheda", shloka["commentaries"])
        self.assertIn("gemini_anvaya", shloka["commentaries"])
        self.assertIn("gemini_summary", shloka["commentaries"])

    def test_blank_sanskrit_text_is_left_alone(self):
        shloka = {"sa": "   ", "commentaries": {}}
        changed = gs.analyze_shloka(shloka, None, "m", dry_run=True, force=False,
                                     fields=["summary"])
        self.assertFalse(changed)
        self.assertEqual(shloka["commentaries"], {})

    def test_rerun_without_force_does_not_overwrite(self):
        shloka = {"sa": "text", "commentaries": {"gemini_summary": "ORIGINAL"}}
        changed = gs.analyze_shloka(shloka, None, "m", dry_run=True, force=False,
                                     fields=["summary"])
        self.assertFalse(changed)
        self.assertEqual(shloka["commentaries"]["gemini_summary"], "ORIGINAL")

    def test_force_overwrites(self):
        shloka = {"sa": "text", "commentaries": {"gemini_summary": "ORIGINAL"}}
        changed = gs.analyze_shloka(shloka, None, "m", dry_run=True, force=True,
                                     fields=["summary"])
        self.assertTrue(changed)
        self.assertNotEqual(shloka["commentaries"]["gemini_summary"], "ORIGINAL")

    def test_only_requested_fields_are_filled(self):
        shloka = {"sa": "text", "commentaries": {}}
        gs.analyze_shloka(shloka, None, "m", dry_run=True, force=False, fields=["summary"])
        self.assertIn("gemini_summary", shloka["commentaries"])
        self.assertNotIn("gemini_padaccheda", shloka["commentaries"])
        self.assertNotIn("gemini_anvaya", shloka["commentaries"])

    def test_existing_english_translation_is_passed_as_context(self):
        # verify build_prompt actually includes the translation when present
        prompt = gs.build_prompt("सा", "an English translation")
        self.assertIn("an English translation", prompt)
        self.assertIn("सा", prompt)

    def test_no_translation_omits_that_section(self):
        prompt = gs.build_prompt("सा", None)
        self.assertNotIn("Existing published", prompt)


class TestAnalyzeBatch(unittest.TestCase):
    def test_dry_run_batch_fills_all_verses(self):
        chunk = [
            ("1", {"sa": "verse one", "commentaries": {}}),
            ("2", {"sa": "verse two", "commentaries": {}}),
        ]
        changed = gs.analyze_batch(chunk, None, "m", dry_run=True, force=False,
                                    fields=["padaccheda", "anvaya", "summary"])
        self.assertEqual(changed, 2)
        for n_str, shloka in chunk:
            self.assertIn("gemini_summary", shloka["commentaries"])

    def test_blank_and_already_done_verses_are_skipped(self):
        chunk = [
            ("1", {"sa": "  ", "commentaries": {}}),
            ("2", {"sa": "text", "commentaries": {"gemini_summary": "ORIGINAL"}}),
        ]
        changed = gs.analyze_batch(chunk, None, "m", dry_run=True, force=False, fields=["summary"])
        self.assertEqual(changed, 0)
        self.assertEqual(chunk[0][1]["commentaries"], {})
        self.assertEqual(chunk[1][1]["commentaries"]["gemini_summary"], "ORIGINAL")

    def test_results_are_matched_by_index_not_response_order(self):
        chunk = [
            ("1", {"sa": "verse one", "commentaries": {}}),
            ("2", {"sa": "verse two", "commentaries": {}}),
        ]
        real_call = gs.call_gemini_for_batch

        def fake_call(verses, api_key, model, usage_totals=None):
            # deliberately return results out of order, tagged distinctly
            return {"results": [
                {"index": "2", "padaccheda": "P2", "anvaya": "A2", "summary": "S2"},
                {"index": "1", "padaccheda": "P1", "anvaya": "A1", "summary": "S1"},
            ]}
        gs.call_gemini_for_batch = fake_call
        try:
            changed = gs.analyze_batch(chunk, "key", "m", dry_run=False, force=False,
                                        fields=["padaccheda", "anvaya", "summary"])
        finally:
            gs.call_gemini_for_batch = real_call
        self.assertEqual(changed, 2)
        self.assertEqual(chunk[0][1]["commentaries"]["gemini_summary"], "S1")
        self.assertEqual(chunk[1][1]["commentaries"]["gemini_summary"], "S2")

    def test_verse_missing_from_response_is_left_alone_not_fabricated(self):
        chunk = [
            ("1", {"sa": "verse one", "commentaries": {}}),
            ("2", {"sa": "verse two", "commentaries": {}}),
        ]
        real_call = gs.call_gemini_for_batch

        def fake_call(verses, api_key, model, usage_totals=None):
            return {"results": [{"index": "1", "padaccheda": "P1", "anvaya": "A1", "summary": "S1"}]}
        gs.call_gemini_for_batch = fake_call
        try:
            changed = gs.analyze_batch(chunk, "key", "m", dry_run=False, force=False, fields=["summary"])
        finally:
            gs.call_gemini_for_batch = real_call
        self.assertEqual(changed, 1)
        self.assertIn("gemini_summary", chunk[0][1]["commentaries"])
        self.assertNotIn("gemini_summary", chunk[1][1]["commentaries"])

    def test_empty_chunk_after_filtering_makes_no_call(self):
        chunk = [("1", {"sa": "text", "commentaries": {"gemini_summary": "X"}})]
        real_call = gs.call_gemini_for_batch

        def fake_call(*a, **k):
            raise AssertionError("should not call Gemini when nothing is missing")
        gs.call_gemini_for_batch = fake_call
        try:
            changed = gs.analyze_batch(chunk, "key", "m", dry_run=False, force=False, fields=["summary"])
        finally:
            gs.call_gemini_for_batch = real_call
        self.assertEqual(changed, 0)


class TestBuildBatchPrompt(unittest.TestCase):
    def test_includes_every_verse_index_and_text(self):
        prompt = gs.build_batch_prompt([
            {"index": "1", "sa": "सा", "en": "translation one"},
            {"index": "2", "sa": "सा२", "en": None},
        ])
        self.assertIn("index: 1", prompt)
        self.assertIn("index: 2", prompt)
        self.assertIn("सा", prompt)
        self.assertIn("translation one", prompt)


class TestRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gs-run-test-"))
        self.sarga_dir = self.tmp / "sargas"
        (self.sarga_dir / "sarga_1").mkdir(parents=True)
        save_json(self.sarga_dir / "sarga_1" / "data.json", {
            "metadata": {"totalShlokas": 2, "availableCommentaries": {}},
            "shlokas": {
                "1": {"sa": "verse one", "commentaries": {}},
                "2": {"sa": "verse two", "commentaries": {}},
            },
        })

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dry_run_analyzes_every_verse_and_labels_them(self):
        rc = gs.run(self.sarga_dir, [1], "m", dry_run=True, force=False, limit=None,
                    fields=["summary"])
        self.assertEqual(rc, 0)
        data = load_json(self.sarga_dir / "sarga_1" / "data.json")
        self.assertIn("gemini_summary", data["shlokas"]["1"]["commentaries"])
        self.assertIn("gemini_summary", data["shlokas"]["2"]["commentaries"])
        self.assertEqual(data["metadata"]["availableCommentaries"]["gemini_summary"],
                          "AI Summary (Gemini, unreviewed)")

    def test_limit_caps_total_verses_considered(self):
        rc = gs.run(self.sarga_dir, [1], "m", dry_run=True, force=False, limit=1,
                    fields=["summary"])
        self.assertEqual(rc, 0)
        data = load_json(self.sarga_dir / "sarga_1" / "data.json")
        self.assertIn("gemini_summary", data["shlokas"]["1"]["commentaries"])
        self.assertNotIn("gemini_summary", data["shlokas"]["2"]["commentaries"])

    def test_missing_api_key_without_dry_run_is_a_clean_error(self):
        os.environ.pop("GEMINI_API_KEY", None)
        rc = gs.run(self.sarga_dir, [1], "m", dry_run=False, force=False, limit=None,
                    fields=["summary"])
        self.assertEqual(rc, 1)

    def test_batch_size_greater_than_one_still_analyzes_every_verse(self):
        rc = gs.run(self.sarga_dir, [1], "m", dry_run=True, force=False, limit=None,
                    fields=["summary"], batch_size=10, concurrency=1)
        self.assertEqual(rc, 0)
        data = load_json(self.sarga_dir / "sarga_1" / "data.json")
        self.assertIn("gemini_summary", data["shlokas"]["1"]["commentaries"])
        self.assertIn("gemini_summary", data["shlokas"]["2"]["commentaries"])

    def test_concurrency_greater_than_one_still_analyzes_every_verse(self):
        rc = gs.run(self.sarga_dir, [1], "m", dry_run=True, force=False, limit=None,
                    fields=["summary"], batch_size=1, concurrency=4)
        self.assertEqual(rc, 0)
        data = load_json(self.sarga_dir / "sarga_1" / "data.json")
        self.assertIn("gemini_summary", data["shlokas"]["1"]["commentaries"])
        self.assertIn("gemini_summary", data["shlokas"]["2"]["commentaries"])

    def test_batched_and_concurrent_together_still_correct(self):
        rc = gs.run(self.sarga_dir, [1], "m", dry_run=True, force=False, limit=None,
                    fields=["summary"], batch_size=1, concurrency=4)
        self.assertEqual(rc, 0)
        data = load_json(self.sarga_dir / "sarga_1" / "data.json")
        self.assertEqual(data["metadata"]["availableCommentaries"]["gemini_summary"],
                          "AI Summary (Gemini, unreviewed)")


if __name__ == "__main__":
    unittest.main()
