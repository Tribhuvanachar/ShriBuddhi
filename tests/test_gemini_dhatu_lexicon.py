"""gemini_dhatu_lexicon.py tests. Generic client mechanics are covered in
tests/test_gemini_client.py; this file covers only this script's own logic
(prompt anchoring, id-selector parsing, checkpoint round-trip, dry-run
mock). No network -- matches this project's other gemini_* test files,
which this script shipped without one of at first."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import gemini_dhatu_lexicon as gdl


SAMPLE_ENTRY = {
    "id": "01.0001", "dhatu": "भू", "dhatu_slp": "BU", "artha": "सत्तायाम्",
    "gana": 1, "pada": "परस्मैपदम्", "pada_iast": "Parasmaipada",
}


class TestBuildPrompt(unittest.TestCase):
    def test_includes_verified_fields_as_context(self):
        prompt = gdl.build_prompt(SAMPLE_ENTRY)
        self.assertIn("01.0001", prompt)
        self.assertIn("भू", prompt)
        self.assertIn("BU", prompt)
        self.assertIn("सत्तायाम्", prompt)
        self.assertIn("Parasmaipada", prompt)

    def test_prefers_pada_iast_over_pada(self):
        prompt = gdl.build_prompt(SAMPLE_ENTRY)
        self.assertIn("Parasmaipada", prompt)

    def test_falls_back_to_pada_when_no_iast(self):
        entry = dict(SAMPLE_ENTRY)
        del entry["pada_iast"]
        prompt = gdl.build_prompt(entry)
        self.assertIn("परस्मैपदम्", prompt)


class TestSelectDhatus(unittest.TestCase):
    ALL = [{"id": "01.0001"}, {"id": "01.0002"}, {"id": "01.0003"}, {"id": "02.0001"}]

    def test_all_returns_everything(self):
        self.assertEqual(gdl.select_dhatus(self.ALL, "all"), self.ALL)

    def test_comma_list(self):
        got = gdl.select_dhatus(self.ALL, "01.0001,02.0001")
        self.assertEqual([e["id"] for e in got], ["01.0001", "02.0001"])

    def test_range(self):
        got = gdl.select_dhatus(self.ALL, "01.0001-01.0002")
        self.assertEqual([e["id"] for e in got], ["01.0001", "01.0002"])

    def test_unknown_id_yields_nothing_extra(self):
        got = gdl.select_dhatus(self.ALL, "09.9999")
        self.assertEqual(got, [])


class TestMockResult(unittest.TestCase):
    def test_shape_matches_response_schema(self):
        result = gdl.mock_result(SAMPLE_ENTRY)
        self.assertEqual(set(result.keys()), {"meanings", "pedagogy"})
        self.assertEqual(set(result["meanings"].keys()), set(gdl.LANGUAGES))
        self.assertIn("concept", result["pedagogy"])
        self.assertIn("scenarios", result["pedagogy"])


class TestProcessOneDryRun(unittest.TestCase):
    def test_dry_run_needs_no_api_key(self):
        out = gdl.process_one(SAMPLE_ENTRY, api_key=None, model="x", dry_run=True, usage_totals=None)
        self.assertEqual(out["id"], "01.0001")
        self.assertIn("meanings", out)
        self.assertIn("pedagogy", out)


class TestCheckpointRoundTrip(unittest.TestCase):
    def setUp(self):
        self._orig_output = gdl.OUTPUT_PATH
        self._tmp = Path(self.id() + "_dhatu_lexicon.json")
        gdl.OUTPUT_PATH = self._tmp

    def tearDown(self):
        gdl.OUTPUT_PATH = self._orig_output
        if self._tmp.exists():
            self._tmp.unlink()

    def test_save_then_load_existing_round_trips(self):
        existing = {"01.0001": {"id": "01.0001", "meanings": {}, "pedagogy": {}, "model": "x"}}
        gdl.save(existing, model="x", of_total=2229)
        loaded = gdl.load_existing()
        self.assertEqual(set(loaded.keys()), {"01.0001"})
        data = json.loads(self._tmp.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "dhatu_lexicon")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["of_total"], 2229)

    def test_load_existing_missing_file_returns_empty(self):
        self.assertEqual(gdl.load_existing(), {})

    def test_load_existing_corrupt_json_returns_empty(self):
        self._tmp.write_text("{not json", encoding="utf-8")
        self.assertEqual(gdl.load_existing(), {})


if __name__ == "__main__":
    unittest.main()
