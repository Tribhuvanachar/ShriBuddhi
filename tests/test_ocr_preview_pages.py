"""ocr_preview_pages.py tests -- the fast, Gemini/Vision-free preview path
(poppler calls mocked, no real PDF/network)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import ocr_preview_pages as opp


class TestRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="preview-test-"))
        self.out_dir = self.tmp / "out"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fake_render(self, requested_pages, out_dir):
        # simulates render_pages() producing a real PNG per requested page
        result = {}
        for n in requested_pages:
            p = out_dir / f"page-{n:02d}.png"
            p.write_bytes(b"fake-png")
            result[n] = p
        return result

    def test_writes_requested_pages_and_meta(self):
        with patch("ocr_preview_pages.get_page_count", return_value=100), \
             patch("ocr_preview_pages.render_pages", side_effect=lambda pdf, pages, tmp: self._fake_render(pages, tmp)):
            rc = opp.run(Path("fake.pdf"), None, [], [1, 12, 54], self.out_dir)
        self.assertEqual(rc, 0)
        self.assertTrue((self.out_dir / "page-1.png").exists())
        self.assertTrue((self.out_dir / "page-12.png").exists())
        self.assertTrue((self.out_dir / "page-54.png").exists())
        meta = json.loads((self.out_dir / "meta.json").read_text())
        self.assertEqual(meta["total_pages"], 100)
        self.assertEqual(meta["rendered_pages"], [1, 12, 54])
        self.assertEqual(meta["out_of_range_pages"], [])

    def test_out_of_range_pages_are_reported_not_rendered(self):
        with patch("ocr_preview_pages.get_page_count", return_value=20), \
             patch("ocr_preview_pages.render_pages", side_effect=lambda pdf, pages, tmp: self._fake_render(pages, tmp)):
            rc = opp.run(Path("fake.pdf"), None, [], [5, 999], self.out_dir)
        self.assertEqual(rc, 0)
        meta = json.loads((self.out_dir / "meta.json").read_text())
        self.assertEqual(meta["rendered_pages"], [5])
        self.assertEqual(meta["out_of_range_pages"], [999])
        self.assertFalse((self.out_dir / "page-999.png").exists())


if __name__ == "__main__":
    unittest.main()
