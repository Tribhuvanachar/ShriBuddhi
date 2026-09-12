"""link_english_commentary.py tests. Synthetic sarga/OCR fixtures, no
network, no real corpus touched."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import link_english_commentary as lec


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


class TestMergeCanto(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lec-test-"))
        self.sarga_path = self.tmp / "sarga_1" / "data.json"
        self.ocr_path = self.tmp / "canto_1.json"
        _write(self.sarga_path, {
            "metadata": {"title": "Demo", "totalShlokas": 3, "availableCommentaries": {}},
            "shlokas": {
                "1": {"sa": "one", "commentaries": {}},
                "2": {"sa": "two", "commentaries": {}},
                "3": {"sa": "three", "commentaries": {}},
            },
        })

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_links_every_non_null_verse(self):
        _write(self.ocr_path, {"canto": 1, "verse_count_found": 3,
                                "verses": {"1": "English one", "2": "English two", "3": "English three"},
                                "uncertain_boundaries": []})
        report = lec.merge_canto(self.sarga_path, self.ocr_path, "translator_english",
                                  "Translator (English)", force=False)
        self.assertEqual(report["linked"], 3)
        data = lec.load_json(self.sarga_path)
        self.assertEqual(data["shlokas"]["2"]["commentaries"]["translator_english"], "English two")
        self.assertEqual(data["metadata"]["availableCommentaries"]["translator_english"],
                          "Translator (English)")

    def test_a_null_verse_is_skipped_not_fabricated(self):
        _write(self.ocr_path, {"canto": 1, "verse_count_found": 3,
                                "verses": {"1": "English one", "2": None, "3": "English three"},
                                "uncertain_boundaries": []})
        report = lec.merge_canto(self.sarga_path, self.ocr_path, "translator_english",
                                  "Translator (English)", force=False)
        self.assertEqual(report["linked"], 2)
        self.assertEqual(report["skipped_null"], 1)
        data = lec.load_json(self.sarga_path)
        self.assertNotIn("translator_english", data["shlokas"]["2"]["commentaries"])

    def test_rerun_without_force_does_not_overwrite(self):
        _write(self.ocr_path, {"canto": 1, "verse_count_found": 3,
                                "verses": {"1": "English one", "2": "English two", "3": "English three"},
                                "uncertain_boundaries": []})
        lec.merge_canto(self.sarga_path, self.ocr_path, "translator_english", "Translator", force=False)
        # simulate a re-run with different (e.g. corrected) text
        _write(self.ocr_path, {"canto": 1, "verse_count_found": 3,
                                "verses": {"1": "CHANGED", "2": "English two", "3": "English three"},
                                "uncertain_boundaries": []})
        report = lec.merge_canto(self.sarga_path, self.ocr_path, "translator_english", "Translator", force=False)
        self.assertEqual(report["linked"], 0)
        self.assertEqual(report["skipped_existing"], 3)
        data = lec.load_json(self.sarga_path)
        self.assertEqual(data["shlokas"]["1"]["commentaries"]["translator_english"], "English one")

    def test_force_overwrites_existing(self):
        _write(self.ocr_path, {"canto": 1, "verse_count_found": 3,
                                "verses": {"1": "English one", "2": "English two", "3": "English three"},
                                "uncertain_boundaries": []})
        lec.merge_canto(self.sarga_path, self.ocr_path, "translator_english", "Translator", force=False)
        _write(self.ocr_path, {"canto": 1, "verse_count_found": 3,
                                "verses": {"1": "CHANGED", "2": "English two", "3": "English three"},
                                "uncertain_boundaries": []})
        report = lec.merge_canto(self.sarga_path, self.ocr_path, "translator_english", "Translator", force=True)
        self.assertEqual(report["linked"], 3)
        data = lec.load_json(self.sarga_path)
        self.assertEqual(data["shlokas"]["1"]["commentaries"]["translator_english"], "CHANGED")

    def test_verse_count_mismatch_refuses_to_merge(self):
        _write(self.ocr_path, {"canto": 1, "verse_count_found": 2,
                                "verses": {"1": "English one", "2": "English two"},
                                "uncertain_boundaries": []})
        with self.assertRaises(ValueError):
            lec.merge_canto(self.sarga_path, self.ocr_path, "translator_english", "Translator", force=False)
        # must not have written a partial merge
        data = lec.load_json(self.sarga_path)
        self.assertEqual(data["shlokas"]["1"]["commentaries"], {})

    def test_ocr_verse_number_not_present_in_sarga_raises(self):
        _write(self.ocr_path, {"canto": 1, "verse_count_found": 3,
                                "verses": {"1": "a", "2": "b", "99": "c"},
                                "uncertain_boundaries": []})
        with self.assertRaises(ValueError):
            lec.merge_canto(self.sarga_path, self.ocr_path, "translator_english", "Translator", force=False)


class TestRunMultipleCantos(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lec-run-test-"))
        self.sarga_dir = self.tmp / "sargas"
        self.ocr_dir = self.tmp / "ocr"
        for n, count in [(1, 2), (2, 2)]:
            _write(self.sarga_dir / f"sarga_{n}" / "data.json", {
                "metadata": {"totalShlokas": count, "availableCommentaries": {}},
                "shlokas": {str(i): {"sa": f"s{i}", "commentaries": {}} for i in range(1, count + 1)},
            })
            _write(self.ocr_dir / f"canto_{n}.json", {
                "canto": n, "verse_count_found": count,
                "verses": {str(i): f"canto{n} verse{i} english" for i in range(1, count + 1)},
                "uncertain_boundaries": [],
            })

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_merges_all_requested_cantos(self):
        rc = lec.run(self.sarga_dir, self.ocr_dir, "translator_english", "Translator",
                     [1, 2], force=False)
        self.assertEqual(rc, 0)
        d1 = lec.load_json(self.sarga_dir / "sarga_1" / "data.json")
        d2 = lec.load_json(self.sarga_dir / "sarga_2" / "data.json")
        self.assertEqual(d1["shlokas"]["1"]["commentaries"]["translator_english"], "canto1 verse1 english")
        self.assertEqual(d2["shlokas"]["2"]["commentaries"]["translator_english"], "canto2 verse2 english")

    def test_missing_sarga_file_is_a_clean_error(self):
        rc = lec.run(self.sarga_dir, self.ocr_dir, "translator_english", "Translator",
                     [1, 5], force=False)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
