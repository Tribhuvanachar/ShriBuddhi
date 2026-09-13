"""tools/sarvam_docai.unpack — turning Sarvam's zip into one entry per page.

This is the paid path. A mistake here is not caught by a failing build: the
pages come back, the money is spent, and the output is quietly the wrong shape.
That is what happened on 13 Sep 2026 — a ten-page slice came back as twelve zip
members (a status manifest, ten per-page JSON files, and the rendered HTML for
the whole slice), the old code concatenated all twelve into one string, filed it
under the first page, and threw away the per-page structure Sarvam had already
worked out.
"""
import json
import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import sarvam_docai as S  # noqa: E402


def page_json(page_num, blocks):
    return json.dumps({"page_num": page_num, "image_width": 1588, "image_height": 2369,
                       "blocks": blocks}, ensure_ascii=False)


def block(text, layout_tag="paragraph", order=0, conf=0.5):
    return {"block_id": f"p-b{order}", "layout_tag": layout_tag, "reading_order": order,
            "confidence": conf, "text": text}


def zipped(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i, m in enumerate(members):
            z.writestr(f"doc_{i:03d}", m)
    return buf.getvalue()


MANIFEST = json.dumps({"status": "completed", "page_count": 2, "pages_succeeded": 2})


class RealResponseShape(unittest.TestCase):
    """The shape Sarvam actually returned for pages 44-53."""

    def setUp(self):
        self.payload = zipped([
            MANIFEST,
            page_json(1, [block("श्रीलक्ष्मीनृसिंहनखप्रार्थनम्", "headline", 0, 0.64),
                          block("श्रियं दिशतु मे नखः", "paragraph", 1, 0.38)]),
            page_json(2, [block("राघवेन्द्रविजयः", "header", 0, 0.9),
                          block("१०", "page-number", 1, 0.99)]),
            "<html><body><p>the whole slice, rendered</p></body></html>",
        ])
        self.out = S.unpack(self.payload, "html", [44, 45])

    def test_one_entry_per_requested_page(self):
        self.assertEqual([e["page"] for e in self.out], [44, 45])

    def test_the_status_manifest_is_not_filed_as_a_page(self):
        for e in self.out:
            self.assertNotIn("page_count", e.get("html", ""))
            self.assertNotIn('"status"', e.get("html", ""))

    def test_page_num_is_mapped_onto_the_real_pdf_page(self):
        # page_num is 1-based within the slice; the book's page 44 is slice page 1.
        self.assertIn("नखप्रार्थनम्", self.out[0]["html"])
        self.assertIn("राघवेन्द्रविजयः", self.out[1]["html"])

    def test_each_layout_tag_keeps_its_own_block_tag(self):
        # "all N" in the studio selects every block the OCR tagged alike, so a
        # headline and a paragraph must not both arrive as <p>.
        self.assertIn("<h1", self.out[0]["html"])
        self.assertIn("<p", self.out[0]["html"])
        self.assertIn("<h4", self.out[1]["html"])     # running header
        self.assertIn("<div", self.out[1]["html"])    # page number

    def test_what_sarvam_decided_is_carried_through(self):
        self.assertIn('data-layout="headline"', self.out[0]["html"])
        self.assertIn('data-confidence="0.64"', self.out[0]["html"])

    def test_block_counts_are_reported(self):
        self.assertEqual([e["blocks_count"] for e in self.out], [2, 2])


class Ordering(unittest.TestCase):
    def test_blocks_come_out_in_reading_order_not_zip_order(self):
        out = S.unpack(zipped([page_json(1, [block("second", "paragraph", 2),
                                             block("first", "paragraph", 1)])]),
                       "html", [7])
        self.assertLess(out[0]["html"].index("first"), out[0]["html"].index("second"))

    def test_an_empty_block_is_dropped_rather_than_emitted_hollow(self):
        out = S.unpack(zipped([page_json(1, [block("  ", "paragraph", 0),
                                             block("real", "paragraph", 1)])]),
                       "html", [7])
        self.assertEqual(out[0]["html"].count("<p"), 1)

    def test_markup_in_the_text_is_escaped(self):
        out = S.unpack(zipped([page_json(1, [block("a < b & c", "paragraph", 0)])]), "html", [7])
        self.assertIn("a &lt; b &amp; c", out[0]["html"])

    def test_a_line_break_inside_a_block_survives_as_br(self):
        out = S.unpack(zipped([page_json(1, [block("line one\nline two", "paragraph", 0)])]),
                       "html", [7])
        self.assertIn("line one<br>line two", out[0]["html"])


class Gaps(unittest.TestCase):
    def test_a_page_missing_from_the_response_is_marked_not_invented(self):
        out = S.unpack(zipped([page_json(1, [block("only page one")])]), "html", [44, 45])
        self.assertTrue(out[0]["ok"])
        self.assertFalse(out[1]["ok"])
        self.assertIn("no page 2", out[1]["error"])


class Fallback(unittest.TestCase):
    """A response with no per-page JSON still has to produce something."""

    def test_one_document_per_page_is_still_matched_up(self):
        out = S.unpack(zipped(["<p>a</p>", "<p>b</p>"]), "html", [3, 4])
        self.assertEqual([e["page"] for e in out], [3, 4])
        self.assertEqual(out[0]["html"], "<p>a</p>")

    def test_a_single_document_is_kept_whole_and_says_so(self):
        out = S.unpack(b"<p>the lot</p>", "html", [3, 4])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["page"], 3)
        self.assertEqual(out[0]["page_end"], 4)
        self.assertIn("not split per page", out[0]["note"])


class JsonFormat(unittest.TestCase):
    def test_asking_for_json_keeps_the_raw_blocks_as_well(self):
        out = S.unpack(zipped([page_json(1, [block("x", "headline", 0)])]), "json", [44])
        self.assertEqual(out[0]["blocks"][0]["layout_tag"], "headline")
        self.assertIn("<h1", out[0]["html"])


if __name__ == "__main__":
    unittest.main()
