"""
Unit tests for the four parsers. Fixtures reproduce the exact heading strings
and markup conventions observed on the live sources on 17 Aug 2026 — including
the stray ')' in wisdomlib's Vīramitrodaya heading, which is real.

    python -m pytest tests -q          (or: python tests/test_parsers.py)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers import gdocs, gretil, sacredtexts          # noqa: E402
from wisdomlib import (classify_heading, parse_page,     # noqa: E402
                       parse_reference, split_sanskrit_block, toc_links)

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fx(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


class TestWisdomlibRigveda(unittest.TestCase):
    def setUp(self):
        self.p = parse_page(fx("wl_rigveda.html"))

    def test_reference(self):
        self.assertEqual(parse_reference(self.p["title"]), ("rv", 1, 164, 1))

    def test_sayana_extracted(self):
        s = self.p["sections"]["sayana"]
        self.assertIn("seven sons", s)
        self.assertNotIn("English translation", s)

    def test_translation_separate_from_sayana(self):
        self.assertIn("I have beheld", self.p["sections"]["translation"])
        self.assertNotIn("I have beheld", self.p["sections"]["sayana"])

    def test_sanskrit_split(self):
        acc, plain, iast = split_sanskrit_block(self.p["sections"]["sanskrit"])
        self.assertIn("॑", acc)                      # accented line kept
        self.assertNotIn("॑", plain)                 # plain line kept
        self.assertTrue(iast.startswith("apaśyaṃ"))

    def test_headings_classify(self):
        self.assertEqual(classify_heading("Commentary by Sāyaṇa: Ṛgveda-bhāṣya"), "sayana")
        self.assertEqual(classify_heading("Commentary by Sayana: Rgveda-bhasya"), "sayana")
        self.assertEqual(classify_heading("English translation:"), "translation")
        self.assertEqual(classify_heading("Padapatha [Accents, Plain, Transliterated]:"), "padapatha")
        self.assertEqual(classify_heading("Something we do not know"), "")


class TestWisdomlibSmriti(unittest.TestCase):
    def test_medhatithi(self):
        p = parse_page(fx("wl_manu.html"))
        self.assertEqual(parse_reference(p["title"]), ("verse", 1, 1))
        self.assertIn("Salutation to the Supreme Brahman", p["sections"]["medhatithi"])
        self.assertIn("Kullūka", p["sections"]["notes_jha"])

    def test_yajnavalkya_stray_paren_heading(self):
        p = parse_page(fx("wl_yajnavalkya.html"))
        self.assertIn("mitakshara", p["sections"])
        self.assertIn("viramitrodaya", p["sections"])
        self.assertIn("Mitramiśra says", p["sections"]["viramitrodaya"])

    def test_toc_links(self):
        links = toc_links(fx("wl_manu.html"))
        self.assertTrue(any(l["doc_id"] == 145372 for l in links))
        self.assertTrue(all(l["url"].startswith("https://") for l in links))


class TestSacredTexts(unittest.TestCase):
    def test_chapter_and_verses(self):
        page = sacredtexts.parse_chapter(fx("st_vishnu.html"))
        self.assertEqual(page["chapter"], 3)
        nums = [v["number"] for v in page["verses"]]
        self.assertEqual(nums, [1, 2, 3])
        # *n* asterisk-diacritics unwrapped, footnote block dropped entirely
        text = sacredtexts.page_text(fx("st_vishnu.html"))
        self.assertIn("Brâhmanas", text)
        self.assertNotIn("Br&acirc;hma*n*as", text)
        self.assertNotIn("See Manu VIII", text)
        self.assertIn("king", page["verses"][0]["text"])

    def test_roman(self):
        self.assertEqual(sacredtexts.roman_to_int("XIV"), 14)
        self.assertEqual(sacredtexts.roman_to_int("XC"), 90)


class TestGretil(unittest.TestCase):
    def test_manu_slashes(self):
        rows = gretil.parse(fx("gretil_manu.txt"))
        self.assertEqual(len(rows), 6)
        self.assertEqual((rows[0]["chapter"], rows[0]["verse"]), (1, 1))
        self.assertIn("manum ekāgram", rows[0]["text"])
        # header must be gone
        self.assertFalse(any("REFERENCE PURPOSES" in r["text"] for r in rows))

    def test_narada_parens(self):
        rows = gretil.parse(fx("gretil_narada.txt"))
        self.assertEqual(len(rows), 6)
        self.assertEqual((rows[-1]["chapter"], rows[-1]["verse"]), (1, 6))

    def test_page_refs_stripped(self):
        rows = gretil.parse(fx("gretil_parashara.txt"))
        self.assertTrue(rows)
        self.assertFalse(any("p. 37" in r["text"] for r in rows))


class TestGdocs(unittest.TestCase):
    def test_export_url(self):
        self.assertEqual(gdocs.export_url("ABC123"),
                         "https://docs.google.com/document/d/ABC123/export?format=txt")

    def test_parse_and_split(self):
        rows = gdocs.parse(fx("gdoc_medhatithi.txt"))
        self.assertEqual(len(rows), 2)
        mula, comm = gdocs.split_mula_and_commentary(rows[0]["text"])
        self.assertIn("manum ekāgram", mula)
        self.assertIn("Salutation", comm)


if __name__ == "__main__":
    unittest.main(verbosity=2)
