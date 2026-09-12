"""merge_staged_commentary.py tests -- Stage 2 of the OCR pipeline. Same
classification-gating/verse-validation guarantees as the pipeline's Stage 1
used to enforce directly, now split out here since merging is its own step."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import merge_staged_commentary as msc
from link_english_commentary import load_json, save_json


class TestMergeShlokas(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="merge-staged-test-"))
        self.sarga_path = self.tmp / "sarga_1" / "data.json"
        self.sarga_path.parent.mkdir(parents=True)
        save_json(self.sarga_path, {
            "metadata": {"totalShlokas": 3, "availableCommentaries": {}},
            "shlokas": {
                "1": {"sa": "verse one", "commentaries": {}},
                "2": {"sa": "verse two", "commentaries": {}},
                "3": {"sa": "verse three", "commentaries": {}},
            },
        })

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _shlokas(self, overrides=None):
        base = [
            {"number": 1, "page": 1, "sa": "sa1", "commentary": "c1", "classification": "accept"},
            {"number": 2, "page": 1, "sa": "sa2", "commentary": "c2", "classification": "accept"},
        ]
        for i, o in (overrides or {}).items():
            base[i].update(o)
        return base

    def test_accept_classified_verses_merge_by_default(self):
        report = msc.merge_shlokas(self.sarga_path, self._shlokas(), "tika_x", "Tika X",
                                    include_review=False, include_unresolved=False, force=False)
        self.assertEqual(report["linked"], 2)
        data = load_json(self.sarga_path)
        self.assertEqual(data["shlokas"]["1"]["commentaries"]["tika_x"], "c1")
        self.assertEqual(data["metadata"]["availableCommentaries"]["tika_x"], "Tika X")

    def test_review_classified_is_held_back_by_default(self):
        shlokas = self._shlokas({0: {"classification": "review"}})
        report = msc.merge_shlokas(self.sarga_path, shlokas, "tika_x", "Tika X",
                                    include_review=False, include_unresolved=False, force=False)
        self.assertEqual(report["linked"], 1)
        self.assertEqual(report["held_review"], 1)
        data = load_json(self.sarga_path)
        self.assertNotIn("tika_x", data["shlokas"]["1"]["commentaries"])

    def test_include_review_flag_merges_held_back_verses(self):
        shlokas = self._shlokas({0: {"classification": "review"}})
        report = msc.merge_shlokas(self.sarga_path, shlokas, "tika_x", "Tika X",
                                    include_review=True, include_unresolved=False, force=False)
        self.assertEqual(report["linked"], 2)
        self.assertEqual(report["held_review"], 0)

    def test_unresolved_classified_is_held_back_by_default(self):
        shlokas = self._shlokas({1: {"classification": "unresolved"}})
        report = msc.merge_shlokas(self.sarga_path, shlokas, "tika_x", "Tika X",
                                    include_review=False, include_unresolved=False, force=False)
        self.assertEqual(report["held_unresolved"], 1)
        self.assertEqual(report["linked"], 1)

    def test_verse_number_outside_canto_range_raises(self):
        shlokas = self._shlokas({0: {"number": 99}})
        with self.assertRaises(ValueError):
            msc.merge_shlokas(self.sarga_path, shlokas, "tika_x", "Tika X",
                               include_review=False, include_unresolved=False, force=False)

    def test_nonexistent_shloka_number_raises(self):
        save_json(self.sarga_path, {
            "metadata": {"totalShlokas": 10, "availableCommentaries": {}},
            "shlokas": {"1": {"sa": "v", "commentaries": {}}},
        })
        shlokas = [{"number": 4, "page": 1, "sa": "sa", "commentary": "c", "classification": "accept"}]
        with self.assertRaises(ValueError):
            msc.merge_shlokas(self.sarga_path, shlokas, "tika_x", "Tika X",
                               include_review=False, include_unresolved=False, force=False)

    def test_blank_commentary_field_is_skipped_not_written(self):
        shlokas = self._shlokas({0: {"commentary": "   "}})
        report = msc.merge_shlokas(self.sarga_path, shlokas, "tika_x", "Tika X",
                                    include_review=False, include_unresolved=False, force=False)
        self.assertEqual(report["skipped_blank"], 1)
        self.assertEqual(report["linked"], 1)

    def test_rerun_without_force_does_not_overwrite(self):
        msc.merge_shlokas(self.sarga_path, self._shlokas(), "tika_x", "Tika X",
                           include_review=False, include_unresolved=False, force=False)
        report = msc.merge_shlokas(self.sarga_path, self._shlokas(), "tika_x", "Tika X",
                                    include_review=False, include_unresolved=False, force=False)
        self.assertEqual(report["linked"], 0)
        self.assertEqual(report["skipped_existing"], 2)

    def test_content_field_sa_uses_verse_text_instead_of_commentary(self):
        report = msc.merge_shlokas(self.sarga_path, self._shlokas(), "mula_x", "Mula X",
                                    include_review=False, include_unresolved=False, force=False,
                                    content_field="sa")
        data = load_json(self.sarga_path)
        self.assertEqual(data["shlokas"]["1"]["commentaries"]["mula_x"], "sa1")

    def test_no_top_level_shlokas_dict_raises(self):
        bad_path = self.tmp / "bad.json"
        save_json(bad_path, {"items": []})
        with self.assertRaises(ValueError):
            msc.merge_shlokas(bad_path, self._shlokas(), "tika_x", "Tika X",
                               include_review=False, include_unresolved=False, force=False)


class TestMergeStagedFile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="merge-staged-file-test-"))
        self.sarga_dir = self.tmp / "work"
        (self.sarga_dir / "sarga_1").mkdir(parents=True)
        save_json(self.sarga_dir / "sarga_1" / "data.json", {
            "metadata": {"totalShlokas": 2, "availableCommentaries": {}},
            "shlokas": {"1": {"sa": "v1", "commentaries": {}}, "2": {"sa": "v2", "commentaries": {}}},
        })
        self.staged_path = self.tmp / "staged.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_staged(self, **overrides):
        staged = {
            "canto": 1, "commentary_key": "tika_x", "display_label": "Tika X",
            "content_field": "commentary",
            "shlokas": [{"number": 1, "page": 1, "sa": "sa1", "commentary": "c1", "classification": "accept"}],
        }
        staged.update(overrides)
        with open(self.staged_path, "w", encoding="utf-8") as fh:
            json.dump(staged, fh)
        return self.staged_path

    def test_merges_from_a_real_staged_file(self):
        self._write_staged()
        report = msc.merge_staged_file(self.staged_path, self.sarga_dir, False, False, False)
        self.assertEqual(report["linked"], 1)
        data = load_json(self.sarga_dir / "sarga_1" / "data.json")
        self.assertEqual(data["shlokas"]["1"]["commentaries"]["tika_x"], "c1")

    def test_missing_canto_field_raises(self):
        self._write_staged(canto=None)
        with self.assertRaises(ValueError):
            msc.merge_staged_file(self.staged_path, self.sarga_dir, False, False, False)

    def test_missing_sarga_file_raises(self):
        self._write_staged(canto=99)
        with self.assertRaises(FileNotFoundError):
            msc.merge_staged_file(self.staged_path, self.sarga_dir, False, False, False)


if __name__ == "__main__":
    unittest.main()
