"""ocr_pipeline.py tests -- parsing, text-building, and the 7z/download
prep logic (subprocess/network calls mocked, no real 7z/poppler/network)."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import ocr_pipeline as op


class TestParsePageList(unittest.TestCase):
    def test_comma_list(self):
        self.assertEqual(op.parse_page_list("1,2,50"), [1, 2, 50])

    def test_ranges(self):
        self.assertEqual(op.parse_page_list("1-3,7,10-12"), [1, 2, 3, 7, 10, 11, 12])

    def test_dedupes_and_sorts(self):
        self.assertEqual(op.parse_page_list("5,1,5,2-3"), [1, 2, 3, 5])

    def test_blank_spec_is_empty(self):
        self.assertEqual(op.parse_page_list(""), [])

    def test_whitespace_tolerant(self):
        self.assertEqual(op.parse_page_list(" 1, 2 , 3-4 "), [1, 2, 3, 4])


class TestBuildOcrPagesText(unittest.TestCase):
    def test_labels_pages_by_their_real_number(self):
        text = op.build_ocr_pages_text({12: "first", 13: "second"})
        self.assertIn("--- Page 12 ---\nfirst", text)
        self.assertIn("--- Page 13 ---\nsecond", text)

    def test_sorted_regardless_of_dict_insertion_order(self):
        text = op.build_ocr_pages_text({13: "b", 12: "a"})
        self.assertLess(text.index("Page 12"), text.index("Page 13"))


class TestRenderPages(unittest.TestCase):
    def test_filters_to_only_requested_pages_within_range(self):
        # simulates pdftoppm producing pages 10-14 (lo=10,hi=14) for a
        # request of [10, 12, 14] -- 11 and 13 must be dropped even though
        # pdftoppm rendered them (a contiguous -f/-l range can't skip an
        # excluded page in the middle). Filenames use real page numbers,
        # zero-padded, matching pdftoppm's confirmed actual behavior.
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            for n in range(10, 15):
                (out_dir / f"page-{n:02d}.png").write_bytes(b"")
            with patch("ocr_pipeline.subprocess.run"):
                result = op.render_pages(Path("fake.pdf"), [10, 12, 14], out_dir)
        self.assertEqual(sorted(result.keys()), [10, 12, 14])
        self.assertEqual(result[10].name, "page-10.png")

    def test_parses_real_page_number_even_if_pdftoppm_skips_one(self):
        # a damaged/blank page pdftoppm silently drops shouldn't corrupt
        # the mapping for the pages it DID render
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            for n in (10, 12, 13, 14):  # 11 missing entirely
                (out_dir / f"page-{n:02d}.png").write_bytes(b"")
            with patch("ocr_pipeline.subprocess.run"):
                result = op.render_pages(Path("fake.pdf"), [10, 11, 12, 13, 14], out_dir)
        self.assertEqual(sorted(result.keys()), [10, 12, 13, 14])

    def test_empty_page_list_returns_empty_without_calling_pdftoppm(self):
        with patch("ocr_pipeline.subprocess.run") as mock_run:
            result = op.render_pages(Path("fake.pdf"), [], Path("/tmp"))
        self.assertEqual(result, {})
        mock_run.assert_not_called()


class TestPreparePdf(unittest.TestCase):
    def test_requires_exactly_one_source(self):
        with self.assertRaises(ValueError):
            op.prepare_pdf(None, [], Path("/tmp"))
        with self.assertRaises(ValueError):
            op.prepare_pdf("http://x/a.pdf", ["http://x/a.7z.001"], Path("/tmp"))

    def test_more_than_three_parts_rejected(self):
        with self.assertRaises(ValueError):
            op.prepare_pdf(None, ["u1", "u2", "u3", "u4"], Path("/tmp"))

    def test_pdf_url_downloads_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            with patch("ocr_pipeline.download_file", return_value=workdir / "input.pdf") as mock_dl:
                result = op.prepare_pdf("http://x/a.pdf", [], workdir)
            mock_dl.assert_called_once_with("http://x/a.pdf", workdir, "input.pdf")
            self.assertEqual(result, workdir / "input.pdf")

    def test_seven_zip_parts_downloaded_then_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            downloaded = []

            def fake_download(url, dest_dir, fallback_name):
                p = dest_dir / fallback_name
                p.write_bytes(b"")
                downloaded.append(p)
                return p

            # simulate 7z actually producing a PDF, since prepare_pdf globs for one
            def fake_7z_run(cmd, **kwargs):
                (workdir / "extracted.pdf").write_bytes(b"%PDF-1.4")
                return MagicMock(returncode=0)

            with patch("ocr_pipeline.download_file", side_effect=fake_download), \
                 patch("ocr_pipeline.subprocess.run", side_effect=fake_7z_run) as mock_run:
                result = op.prepare_pdf(None, ["http://x/a.7z.001", "http://x/a.7z.002", "http://x/a.7z.003"], workdir)
            self.assertEqual(len(downloaded), 3)
            self.assertEqual(result, workdir / "extracted.pdf")
            self.assertIn("7z", mock_run.call_args[0][0][0])

    def test_no_pdf_after_extraction_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)

            def fake_download(url, dest_dir, fallback_name):
                p = dest_dir / fallback_name
                p.write_bytes(b"")
                return p

            with patch("ocr_pipeline.download_file", side_effect=fake_download), \
                 patch("ocr_pipeline.subprocess.run"):
                with self.assertRaises(RuntimeError):
                    op.prepare_pdf(None, ["http://x/a.7z.001"], workdir)


class TestOcrAndProofread(unittest.TestCase):
    def test_dry_run_batches_and_concatenates_shlokas(self):
        page_texts = {1: "a", 2: "b", 3: "c"}
        result = op.ocr_and_proofread(page_texts, "m", "", pages_per_gemini_batch=2,
                                       api_key=None, dry_run=True)
        # 3 pages at batch size 2 -> 2 batches -> 2 mock shlokas
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
