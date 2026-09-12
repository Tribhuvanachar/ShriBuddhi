"""gemini_ocr_commentary.py tests -- Stage 1 CLI: staging behavior and the
optional immediate --merge. No network/poppler (--dry-run)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import gemini_ocr_commentary as goc
from link_english_commentary import save_json


class TestDefaultStagedPath(unittest.TestCase):
    def test_builds_expected_path(self):
        path = goc.default_staged_path("raghavendra_vijaya", "tika_x", 1, 12, 54)
        self.assertEqual(path, Path("dge/data/ocr_staging/raghavendra_vijaya/tika_x_canto1_pages12-54.json"))


class TestRunDryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="goc-run-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stages_without_merging_by_default(self):
        out_path = self.tmp / "staged.json"
        rc = goc.run(
            pdf=Path("fake.pdf"), pdf_url=None, part_urls=[], start_page=1, end_page=3, exclude_pages=[],
            work_slug="testwork", canto=1, commentary_key="tika_x", display_label="Tika X",
            context_anchor="test anchor", content_field="commentary", model="m", pages_per_gemini_batch=2,
            out_path=out_path, dry_run=True, do_merge=False, sarga_dir=None,
            include_review=False, include_unresolved=False, force=False,
        )
        self.assertEqual(rc, 0)
        staged = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(staged["canto"], 1)
        self.assertEqual(staged["commentary_key"], "tika_x")
        self.assertTrue(len(staged["shlokas"]) > 0)
        self.assertEqual(staged["source"]["exclude_pages"], [])

    def test_exclude_pages_removes_them_before_processing(self):
        out_path = self.tmp / "staged.json"
        rc = goc.run(
            pdf=Path("fake.pdf"), pdf_url=None, part_urls=[], start_page=1, end_page=3, exclude_pages=[2],
            work_slug="testwork", canto=1, commentary_key="tika_x", display_label="Tika X",
            context_anchor="", content_field="commentary", model="m", pages_per_gemini_batch=10,
            out_path=out_path, dry_run=True, do_merge=False, sarga_dir=None,
            include_review=False, include_unresolved=False, force=False,
        )
        self.assertEqual(rc, 0)

    def test_all_pages_excluded_is_a_clean_error(self):
        rc = goc.run(
            pdf=Path("fake.pdf"), pdf_url=None, part_urls=[], start_page=1, end_page=2, exclude_pages=[1, 2],
            work_slug="testwork", canto=1, commentary_key="tika_x", display_label="Tika X",
            context_anchor="", content_field="commentary", model="m", pages_per_gemini_batch=10,
            out_path=self.tmp / "staged.json", dry_run=True, do_merge=False, sarga_dir=None,
            include_review=False, include_unresolved=False, force=False,
        )
        self.assertEqual(rc, 1)

    def test_merge_true_also_writes_into_the_sarga(self):
        sarga_dir = self.tmp / "work"
        (sarga_dir / "sarga_1").mkdir(parents=True)
        save_json(sarga_dir / "sarga_1" / "data.json", {
            "metadata": {"totalShlokas": 1, "availableCommentaries": {}},
            "shlokas": {"1": {"sa": "v", "commentaries": {}}},
        })
        out_path = self.tmp / "staged.json"
        rc = goc.run(
            pdf=Path("fake.pdf"), pdf_url=None, part_urls=[], start_page=1, end_page=1, exclude_pages=[],
            work_slug="testwork", canto=1, commentary_key="tika_x", display_label="Tika X",
            context_anchor="", content_field="commentary", model="m", pages_per_gemini_batch=10,
            out_path=out_path, dry_run=True, do_merge=True, sarga_dir=sarga_dir,
            include_review=False, include_unresolved=False, force=False,
        )
        self.assertEqual(rc, 0)
        from link_english_commentary import load_json
        data = load_json(sarga_dir / "sarga_1" / "data.json")
        self.assertIn("tika_x", data["shlokas"]["1"]["commentaries"])

    def test_merge_without_sarga_dir_is_a_clean_error(self):
        rc = goc.run(
            pdf=Path("fake.pdf"), pdf_url=None, part_urls=[], start_page=1, end_page=1, exclude_pages=[],
            work_slug="testwork", canto=1, commentary_key="tika_x", display_label="Tika X",
            context_anchor="", content_field="commentary", model="m", pages_per_gemini_batch=10,
            out_path=self.tmp / "staged.json", dry_run=True, do_merge=True, sarga_dir=None,
            include_review=False, include_unresolved=False, force=False,
        )
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
