"""ocr_conflicts.py: only the pages two engines disagree on are sent onward."""

import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import ocr_conflicts as C  # noqa: E402


def stage(d, name, pages, key="text"):
    p = os.path.join(d, name)
    with io.open(p, "w", encoding="utf-8") as fh:
        json.dump({"pages": [{"page": n, key: t} for n, t in pages]}, fh)
    return p


class Normalising(unittest.TestCase):
    def test_layout_markup_is_not_a_disagreement(self):
        """Sarvam returns HTML to keep layout; Vision returns flat text.

        Comparing those raw reports a conflict on every page, which is the
        same as reporting none.
        """
        self.assertEqual(C.normalise("<p>धर्मक्षेत्रे</p>"), C.normalise("धर्मक्षेत्रे"))

    def test_a_verse_number_written_two_ways_is_not_a_disagreement(self):
        self.assertEqual(C.normalise("गीता ॥२॥"), C.normalise("गीता || 2 ||"))


class WhatGetsSentOn(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_agreeing_pages_cost_nothing(self):
        stage(self.d, "sarvam_pages1-3.json",
              [(1, "<p>धर्मक्षेत्रे कुरुक्षेत्रे</p>"), (2, "समवेता युयुत्सवः"), (3, "मामकाः पाण्डवाश्चैव")])
        stage(self.d, "vision_pages_1-3.json",
              [(1, "धर्मक्षेत्रे कुरुक्षेत्रे"), (2, "समवेता युयुत्सवः"), (3, "मामकाः पाण्डवाश्चैव")])
        s, v = C.find(self.d)
        conflicts, agreed, _ = C.compare(C.load_pages(s), C.load_pages(v), 0.92)
        self.assertEqual(3, agreed)
        self.assertEqual([], conflicts)

    def test_only_the_differing_page_is_carried_with_both_readings(self):
        stage(self.d, "sarvam_pages1-2.json",
              [(1, "धर्मक्षेत्रे कुरुक्षेत्रे"), (2, "सञ्जय उवाच")])
        stage(self.d, "vision_pages_1-2.json",
              [(1, "धर्मक्षेत्रे कुरुक्षेत्रे"), (2, "तञ्चय उगच ॐ ॐ ॐ अपूर्णम्")])
        s, v = C.find(self.d)
        conflicts, agreed, _ = C.compare(C.load_pages(s), C.load_pages(v), 0.92)
        self.assertEqual(1, agreed)
        self.assertEqual(1, len(conflicts))
        self.assertEqual(2, conflicts[0]["page"])
        # both readings travel, because the prompt resolves by comparing them
        self.assertIn("सञ्जय", conflicts[0]["sarvam"])
        self.assertIn("तञ्चय", conflicts[0]["vision"])

    def test_an_engine_returning_nothing_is_flagged_as_that_not_as_a_difference(self):
        """A blank page is a failure, not a disagreement about content.

        It still needs looking at -- the other engine's reading is unchecked --
        so it travels, labelled for what it actually is.
        """
        stage(self.d, "sarvam_pages1-1.json", [(1, "")])
        stage(self.d, "vision_pages_1-1.json", [(1, "अथातो ब्रह्मजिज्ञासा")])
        s, v = C.find(self.d)
        conflicts, agreed, only_one = C.compare(C.load_pages(s), C.load_pages(v), 0.92)
        self.assertEqual(0, agreed)
        self.assertEqual(1, only_one)
        self.assertEqual("one engine returned nothing", conflicts[0]["reason"])

    def test_a_page_both_engines_left_blank_is_not_reported(self):
        stage(self.d, "sarvam_pages1-1.json", [(1, "   ")])
        stage(self.d, "vision_pages_1-1.json", [(1, "")])
        s, v = C.find(self.d)
        conflicts, agreed, _ = C.compare(C.load_pages(s), C.load_pages(v), 0.92)
        self.assertEqual([], conflicts)
        self.assertEqual(0, agreed)

    def test_it_refuses_when_only_one_engine_has_run(self):
        stage(self.d, "sarvam_pages1-1.json", [(1, "अथ")])
        self.assertEqual(2, C.main(["--work", self.d]))


if __name__ == "__main__":
    unittest.main()
