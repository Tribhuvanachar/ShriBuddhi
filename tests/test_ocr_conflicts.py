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
        conflicts, agreed, _ = C.compare(C.load_all(s), C.load_all(v), 0.92)
        self.assertEqual(3, agreed)
        self.assertEqual([], conflicts)

    def test_only_the_differing_page_is_carried_with_both_readings(self):
        stage(self.d, "sarvam_pages1-2.json",
              [(1, "धर्मक्षेत्रे कुरुक्षेत्रे"), (2, "सञ्जय उवाच")])
        stage(self.d, "vision_pages_1-2.json",
              [(1, "धर्मक्षेत्रे कुरुक्षेत्रे"), (2, "तञ्चय उगच ॐ ॐ ॐ अपूर्णम्")])
        s, v = C.find(self.d)
        conflicts, agreed, _ = C.compare(C.load_all(s), C.load_all(v), 0.92)
        self.assertEqual(1, agreed)
        self.assertEqual(1, len(conflicts))
        self.assertEqual(2, conflicts[0]["page"])
        # both readings travel, because the prompt resolves by comparing them
        self.assertIn("सञ्जय", conflicts[0]["sarvam"])
        self.assertIn("तञ्चय", conflicts[0]["vision"])

    def test_a_page_only_one_engine_covered_is_counted_but_not_billed(self):
        """A blank from one engine is missing coverage, not a disagreement.

        It must not travel to Gemini: paying a third model to choose between a
        reading and a blank buys nothing -- it has no second opinion to weigh,
        so it would simply retype the one reading at full price. It is counted
        so the gap is visible, and left out of the conflicts.
        """
        stage(self.d, "sarvam_pages1-1.json", [(1, "")])
        stage(self.d, "vision_pages_1-1.json", [(1, "अथातो ब्रह्मजिज्ञासा")])
        s, v = C.find(self.d)
        conflicts, agreed, only_one = C.compare(C.load_all(s), C.load_all(v), 0.92)
        self.assertEqual(0, agreed)
        self.assertEqual(1, only_one)
        self.assertEqual([], conflicts)

    def test_every_chunk_of_a_work_is_compared_not_just_the_first(self):
        """Sarvam caps a request at 200 pages, so a book arrives in chunks.

        Comparing only the first file made every page outside it look like a
        conflict -- a 6% disagreement reported as 50%, which is a costing error
        in the one direction that matters.
        """
        stage(self.d, "sarvam_pages1-2.json", [(1, "अथ प्रथमः"), (2, "द्वितीयः")])
        stage(self.d, "sarvam_pages3-4.json", [(3, "तृतीयः"), (4, "चतुर्थः")])
        stage(self.d, "vision_pages_1-4.json",
              [(1, "अथ प्रथमः"), (2, "द्वितीयः"), (3, "तृतीयः"), (4, "चतुर्थः")])
        s, v = C.find(self.d)
        self.assertEqual(2, len(s))
        conflicts, agreed, only_one = C.compare(C.load_all(s), C.load_all(v), 0.92)
        self.assertEqual(4, agreed)
        self.assertEqual([], conflicts)
        self.assertEqual(0, only_one)

    def test_a_page_both_engines_left_blank_is_not_reported(self):
        stage(self.d, "sarvam_pages1-1.json", [(1, "   ")])
        stage(self.d, "vision_pages_1-1.json", [(1, "")])
        s, v = C.find(self.d)
        conflicts, agreed, _ = C.compare(C.load_all(s), C.load_all(v), 0.92)
        self.assertEqual([], conflicts)
        self.assertEqual(0, agreed)

    def test_it_refuses_when_only_one_engine_has_run(self):
        stage(self.d, "sarvam_pages1-1.json", [(1, "अथ")])
        self.assertEqual(2, C.main(["--work", self.d]))


if __name__ == "__main__":
    unittest.main()


class LongPagesCompareCorrectly(unittest.TestCase):
    """The comparison must not fall apart at real page length.

    difflib's autojunk heuristic only engages above 200 elements, so a short
    fixture proves nothing about a 1,600-character page of commentary -- which
    is what every page in this corpus actually is.
    """

    def test_two_readings_differing_in_one_digit_agree(self):
        base = "श्रीरामस्य वनवासनिमित्तमुक्त्वा दशरथमरणकारणमाह आत्मेति राजा दशरथः " * 12
        self.assertGreater(len(base), 200)
        a, b = "490 " + base, "410 " + base
        conflicts, agreed, _ = C.compare({1: a}, {1: b}, 0.92)
        self.assertEqual(1, agreed, "a one-digit difference is not a conflict")
        self.assertEqual([], conflicts)

    def test_genuinely_different_long_pages_still_conflict(self):
        a = "श्रीरामस्य वनवासनिमित्तमुक्त्वा दशरथमरणकारणमाह " * 12
        b = "अथातो ब्रह्मजिज्ञासा जन्माद्यस्य यतः शास्त्रयोनित्वात् " * 12
        self.assertGreater(len(a), 200)
        conflicts, agreed, _ = C.compare({1: a}, {1: b}, 0.92)
        self.assertEqual(0, agreed)
        self.assertEqual(1, len(conflicts))
