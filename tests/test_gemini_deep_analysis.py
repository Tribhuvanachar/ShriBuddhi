"""gemini_deep_analysis.py tests. No network: covers the prerequisite-gate
(skip a verse with no padaccheda/anvaya yet rather than regenerating them),
the index-matched batch merge, and the metadata.availableCommentaries
non-registration (this data isn't stored under commentaries, so it must
NOT create a phantom entry there)."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import gemini_deep_analysis as gda
from link_english_commentary import load_json, save_json


class TestAnalyzeShloka(unittest.TestCase):
    def test_skips_a_verse_with_no_padaccheda_yet(self):
        shloka = {"sa": "text", "commentaries": {}}
        outcome = gda.analyze_shloka(shloka, None, "m", dry_run=True, force=False)
        self.assertEqual(outcome, "skipped_no_prereqs")
        self.assertNotIn(gda.FIELD_KEY, shloka)

    def test_skips_a_verse_with_padaccheda_but_no_anvaya(self):
        shloka = {"sa": "text", "commentaries": {"gemini_padaccheda": "a-b"}}
        outcome = gda.analyze_shloka(shloka, None, "m", dry_run=True, force=False)
        self.assertEqual(outcome, "skipped_no_prereqs")

    def test_dry_run_analyzes_a_verse_with_both_prereqs(self):
        shloka = {"sa": "text", "commentaries": {"gemini_padaccheda": "a-b", "gemini_anvaya": "b a"}}
        outcome = gda.analyze_shloka(shloka, None, "m", dry_run=True, force=False)
        self.assertEqual(outcome, "analyzed")
        self.assertIn(gda.FIELD_KEY, shloka)
        self.assertIn("chandas", shloka[gda.FIELD_KEY])

    def test_rerun_without_force_does_not_overwrite(self):
        shloka = {"sa": "text", "commentaries": {"gemini_padaccheda": "a-b", "gemini_anvaya": "b a"},
                  gda.FIELD_KEY: {"bhavartha": "ORIGINAL"}}
        outcome = gda.analyze_shloka(shloka, None, "m", dry_run=True, force=False)
        self.assertEqual(outcome, "skipped_existing")
        self.assertEqual(shloka[gda.FIELD_KEY]["bhavartha"], "ORIGINAL")

    def test_force_overwrites(self):
        shloka = {"sa": "text", "commentaries": {"gemini_padaccheda": "a-b", "gemini_anvaya": "b a"},
                  gda.FIELD_KEY: {"bhavartha": "ORIGINAL"}}
        outcome = gda.analyze_shloka(shloka, None, "m", dry_run=True, force=True)
        self.assertEqual(outcome, "analyzed")
        self.assertNotEqual(shloka[gda.FIELD_KEY]["bhavartha"], "ORIGINAL")

    def test_blank_sanskrit_text_is_skipped(self):
        shloka = {"sa": "  ", "commentaries": {"gemini_padaccheda": "a", "gemini_anvaya": "a"}}
        outcome = gda.analyze_shloka(shloka, None, "m", dry_run=True, force=False)
        self.assertEqual(outcome, "skipped_no_prereqs")


class TestAnalyzeBatch(unittest.TestCase):
    def test_dry_run_batch_analyzes_verses_with_prereqs_only(self):
        chunk = [
            ("1", {"sa": "v1", "commentaries": {"gemini_padaccheda": "a", "gemini_anvaya": "a"}}),
            ("2", {"sa": "v2", "commentaries": {}}),  # no prereqs
        ]
        counts = gda.analyze_batch(chunk, None, "m", dry_run=True, force=False)
        self.assertEqual(counts["analyzed"], 1)
        self.assertEqual(counts["skipped_no_prereqs"], 1)
        self.assertIn(gda.FIELD_KEY, chunk[0][1])
        self.assertNotIn(gda.FIELD_KEY, chunk[1][1])

    def test_results_matched_by_index_not_response_order(self):
        chunk = [
            ("1", {"sa": "v1", "commentaries": {"gemini_padaccheda": "a", "gemini_anvaya": "a"}}),
            ("2", {"sa": "v2", "commentaries": {"gemini_padaccheda": "b", "gemini_anvaya": "b"}}),
        ]
        real_call = gda.call_gemini_for_batch

        def fake_call(verses, api_key, model, usage_totals=None):
            return {"results": [
                {"index": "2", "chandas": {"name": "C2"}, "alankara": [], "samasa_vishesha": [],
                 "pratipadartha": [], "bhavartha": "B2"},
                {"index": "1", "chandas": {"name": "C1"}, "alankara": [], "samasa_vishesha": [],
                 "pratipadartha": [], "bhavartha": "B1"},
            ]}
        gda.call_gemini_for_batch = fake_call
        try:
            counts = gda.analyze_batch(chunk, "key", "m", dry_run=False, force=False)
        finally:
            gda.call_gemini_for_batch = real_call
        self.assertEqual(counts["analyzed"], 2)
        self.assertEqual(chunk[0][1][gda.FIELD_KEY]["bhavartha"], "B1")
        self.assertEqual(chunk[1][1][gda.FIELD_KEY]["bhavartha"], "B2")

    def test_verse_missing_from_response_is_left_alone(self):
        chunk = [
            ("1", {"sa": "v1", "commentaries": {"gemini_padaccheda": "a", "gemini_anvaya": "a"}}),
        ]
        real_call = gda.call_gemini_for_batch

        def fake_call(verses, api_key, model, usage_totals=None):
            return {"results": []}
        gda.call_gemini_for_batch = fake_call
        try:
            counts = gda.analyze_batch(chunk, "key", "m", dry_run=False, force=False)
        finally:
            gda.call_gemini_for_batch = real_call
        self.assertEqual(counts["analyzed"], 0)
        self.assertNotIn(gda.FIELD_KEY, chunk[0][1])


class TestRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gda-run-test-"))
        self.sarga_dir = self.tmp / "sargas"
        (self.sarga_dir / "sarga_1").mkdir(parents=True)
        save_json(self.sarga_dir / "sarga_1" / "data.json", {
            "metadata": {"totalShlokas": 2, "availableCommentaries": {}},
            "shlokas": {
                "1": {"sa": "verse one", "commentaries": {"gemini_padaccheda": "a-b", "gemini_anvaya": "b a"}},
                "2": {"sa": "verse two", "commentaries": {}},  # no prereqs
            },
        })

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_analyzes_only_verses_with_prereqs_and_does_not_register_a_commentary(self):
        rc = gda.run(self.sarga_dir, [1], "m", dry_run=True, force=False, limit=None)
        self.assertEqual(rc, 0)
        data = load_json(self.sarga_dir / "sarga_1" / "data.json")
        self.assertIn(gda.FIELD_KEY, data["shlokas"]["1"])
        self.assertNotIn(gda.FIELD_KEY, data["shlokas"]["2"])
        # must NOT create a phantom commentary entry -- this data isn't
        # stored under commentaries, so it must never appear in the
        # catalog that drives the reader's commentary toggle buttons
        self.assertNotIn(gda.FIELD_KEY, data["metadata"]["availableCommentaries"])

    def test_missing_api_key_without_dry_run_is_a_clean_error(self):
        os.environ.pop("GEMINI_API_KEY", None)
        rc = gda.run(self.sarga_dir, [1], "m", dry_run=False, force=False, limit=None)
        self.assertEqual(rc, 1)

    def test_batch_size_greater_than_one_still_works(self):
        rc = gda.run(self.sarga_dir, [1], "m", dry_run=True, force=False, limit=None, batch_size=10)
        self.assertEqual(rc, 0)
        data = load_json(self.sarga_dir / "sarga_1" / "data.json")
        self.assertIn(gda.FIELD_KEY, data["shlokas"]["1"])


class TestSchemaFieldsForReaderUi(unittest.TestCase):
    """23 Aug 2026: vigraha (per-word etymology) and vyakarana_vishesha
    (verse-level grammar notes) were added so dge/js/render.js's
    Shloka Fields toggles (Pratipadartha/Vyakarana) have something real to
    show beyond the case/tense-mood-person column that was already there."""

    def test_pratipadartha_item_schema_has_vigraha(self):
        item_props = gda.RESPONSE_SCHEMA["properties"]["pratipadartha"]["items"]["properties"]
        self.assertIn("vigraha", item_props)

    def test_top_level_schema_has_vyakarana_vishesha(self):
        self.assertIn("vyakarana_vishesha", gda.RESPONSE_SCHEMA["properties"])
        # optional, like confidence_note -- not every verse has a note
        # beyond what pratipadartha/samasa_vishesha already say
        self.assertNotIn("vyakarana_vishesha", gda.RESPONSE_SCHEMA["required"])

    def test_batch_schema_inherits_the_same_fields(self):
        item_props = gda.RESPONSE_SCHEMA_BATCH["properties"]["results"]["items"]["properties"]
        self.assertIn("vyakarana_vishesha", item_props)
        self.assertIn("vigraha", item_props["pratipadartha"]["items"]["properties"])

    def test_mock_analyze_verse_carries_the_new_fields(self):
        mock = gda.mock_analyze_verse()
        self.assertIn("vyakarana_vishesha", mock)


if __name__ == "__main__":
    unittest.main()
