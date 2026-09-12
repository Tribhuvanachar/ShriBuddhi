#!/usr/bin/env python3
"""Tests for parsers/wikisource.py's parse_devanagari_verses().

The original pattern only matched a bare running-count "॥ N ॥" marker, so it
silently found ZERO verses on any page numbered by chapter.verse ("॥ १.१ ॥") —
which is how commentaries and nibandhas (Mitakshara, among others) are
numbered on sa.wikisource. Confirmed against the live site (25 Aug):
Mitakshara's Sadacaradhyaya page has 302 real "॥ chapter.verse ॥" markers and
297 real commentary units; the old pattern found 1.

    python tools/sayana_smriti/tests/test_wikisource.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.wikisource import parse_devanagari_verses  # noqa: E402


class TestCompoundNumbering(unittest.TestCase):
    def test_chapter_dot_verse_marker_is_found(self):
        # Real shape from Mitaksara/Sadacaradhyaya, trimmed.
        text = (
            "श्रीगणेशाय नमः\n"
            "योगीश्वरं याज्ञवल्क्यं संपूज्य मुनयोऽब्रुवन् ॥ १.१ ॥\n"
            "मिथिलास्थः स योगीन्द्रः क्षणं ध्यात्वाब्रवीन् मुनीन् ॥ १.२ ॥\n"
        )
        verses = parse_devanagari_verses(text)
        self.assertEqual([v["number"] for v in verses], ["1.1", "1.2"])
        self.assertIn("योगीश्वरं", verses[0]["text"])
        self.assertIn("मिथिलास्थः", verses[1]["text"])

    def test_plain_running_number_still_works(self):
        text = "प्रथमः श्लोकः इति ॥ १ ॥\nद्वितीयः श्लोकः इति ॥ २ ॥\n"
        verses = parse_devanagari_verses(text)
        self.assertEqual([v["number"] for v in verses], [1, 2])
        self.assertIsInstance(verses[0]["number"], int)

    def test_multi_dot_reference_number(self):
        text = "टीका किञ्चिद् वचनम् अत्र ॥ १२.४५.२ ॥\n"
        verses = parse_devanagari_verses(text)
        self.assertEqual(verses[0]["number"], "12.45.2")


class TestJunkDropped(unittest.TestCase):
    def test_footnote_citation_line_dropped(self):
        text = "२. दक्षस्मृ० अ० २ श्लो २९ ॥ १ ॥\nनिष्कलं निर्गुणं शान्तं निरवद्यं निरञ्जनम् ॥ २ ॥\n"
        verses = parse_devanagari_verses(text)
        self.assertEqual(len(verses), 1)
        self.assertIn("निष्कलं", verses[0]["text"])

    def test_variant_reading_note_dropped(self):
        text = "इत्यधिक पाठ. क. पु. ॥ १ ॥\nसत्यं ज्ञानम् अनन्तं ब्रह्म ॥ २ ॥\n"
        verses = parse_devanagari_verses(text)
        self.assertEqual(len(verses), 1)
        self.assertIn("सत्यं", verses[0]["text"])

    def test_scan_tool_credit_line_dropped(self):
        text = "देवनागरी कर्तुं प्रयुक्तः उपकरणः ॥ १ ॥\nधर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ॥ २ ॥\n"
        verses = parse_devanagari_verses(text)
        self.assertEqual(len(verses), 1)
        self.assertIn("धर्मक्षेत्रे", verses[0]["text"])

    def test_short_or_low_devanagari_chunk_dropped(self):
        # A stray English/publisher-boilerplate fragment: low Devanagari
        # ratio, would previously have been kept verbatim as a "verse".
        text = "Printed by Jai Krishna Das Gupta ॥ १ ॥\nवसुधैव कुटुम्बकम् इति वचनम् प्रसिद्धम् ॥ २ ॥\n"
        verses = parse_devanagari_verses(text)
        self.assertEqual(len(verses), 1)
        self.assertIn("वसुधैव", verses[0]["text"])

    def test_empty_chunk_is_skipped_not_a_bug(self):
        text = "॥ १ ॥\nप्रथमः श्लोकः इति ॥ २ ॥\n"
        verses = parse_devanagari_verses(text)
        self.assertEqual(len(verses), 1)


if __name__ == "__main__":
    unittest.main()
