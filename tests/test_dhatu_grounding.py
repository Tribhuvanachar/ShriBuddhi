"""dhatu_grounding.py tests. No network, no real kosha build required --
KoshaIndex degrades to empty when given no build root, and vritti lookup
uses a real temp fixture. Covers the marker-stripping/folding helpers and
the relevant-node text extraction, since those are the parts most likely
to silently mismatch a root against its dictionary headword."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import dhatu_grounding as dg


class TestStripMarkers(unittest.TestCase):
    def test_strips_tilde_backslash_caret_and_digits(self):
        self.assertEqual(dg.strip_markers("za\\da~"), "zada")
        self.assertEqual(dg.strip_markers("eDa~\\"), "eDa")
        self.assertEqual(dg.strip_markers("kzu\\di~^r"), "kzudir")

    def test_plain_root_is_unchanged(self):
        self.assertEqual(dg.strip_markers("BU"), "BU")

    def test_empty_input(self):
        self.assertEqual(dg.strip_markers(""), "")
        self.assertEqual(dg.strip_markers(None), "")


class TestFold(unittest.TestCase):
    def test_long_vowels_fold_to_short(self):
        self.assertEqual(dg._fold("BU"), "Bu")
        # K/B are distinct consonants (kh/bh), not vowel-fold targets -- only
        # A/I/U/F/X lower to a/i/u/f/x.
        self.assertEqual(dg._fold("BUKA"), "BuKa")

    def test_sibilants_merge(self):
        self.assertEqual(dg._fold("Sas"), "sas")

    def test_doubled_letters_collapse(self):
        # only CONSECUTIVE repeats collapse -- "tt" -> "t", "h" is untouched
        self.assertEqual(dg._fold("kattha"), "katha")


class TestLoadVrittiRelevant(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.vritti_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write(self, dhatu_id, vrittis):
        (self.vritti_dir / f"{dhatu_id}.json").write_text(
            json.dumps({"vrittis": vrittis}), encoding="utf-8")

    def test_missing_file_returns_empty(self):
        self.assertEqual(dg.load_vritti_relevant(self.vritti_dir, "99.9999"), {})

    def test_short_text_without_nodes_used_whole(self):
        self._write("01.0001", [{"source": "madhaviya", "text": "a short entry"}])
        got = dg.load_vritti_relevant(self.vritti_dir, "01.0001")
        self.assertEqual(got, {"madhaviya": "a short entry"})

    def test_nodes_filter_to_relevant_only(self):
        text = "AAAA relevant-part BBBB general-part CCCC"
        nodes = [[0, 19, "r"], [19, 43, "g"]]
        self._write("01.0002", [{"source": "madhaviya", "text": text, "nodes": nodes}])
        got = dg.load_vritti_relevant(self.vritti_dir, "01.0002")
        self.assertEqual(got["madhaviya"], "AAAA relevant-part")

    def test_no_relevant_nodes_falls_back_to_full_text(self):
        text = "only general discussion here"
        nodes = [[0, len(text), "g"]]
        self._write("01.0003", [{"source": "kshira", "text": text, "nodes": nodes}])
        got = dg.load_vritti_relevant(self.vritti_dir, "01.0003")
        self.assertEqual(got["kshira"], text)

    def test_long_text_is_capped(self):
        text = "x" * (dg.VRITTI_CAP + 500)
        self._write("01.0004", [{"source": "dhatupradipa", "text": text}])
        got = dg.load_vritti_relevant(self.vritti_dir, "01.0004")
        self.assertEqual(len(got["dhatupradipa"]), dg.VRITTI_CAP)


class TestKoshaIndexEmpty(unittest.TestCase):
    def test_no_build_root_gives_empty_index(self):
        idx = dg.KoshaIndex(None, ["macdonell"])
        self.assertEqual(idx.by_key, {})
        self.assertEqual(idx.lookup("BU"), [])


class TestBuildGrounding(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.vritti_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_no_sources_gives_empty_grounding(self):
        text, sources = dg.build_grounding({"id": "09.9999", "dhatu_slp": "xyz"},
                                            self.vritti_dir, None, None)
        self.assertEqual(text, "")
        self.assertEqual(sources, [])

    def test_own_vritti_is_included_and_labeled(self):
        (self.vritti_dir / "01.0001.json").write_text(
            json.dumps({"vrittis": [{"source": "madhaviya", "text": "सत्तायाम्"}]}),
            encoding="utf-8")
        text, sources = dg.build_grounding({"id": "01.0001", "dhatu_slp": "BU"},
                                            self.vritti_dir, None, None)
        self.assertIn("सत्तायाम्", text)
        self.assertIn("Mādhavīya Dhātuvṛtti (Sāyaṇa)", sources)


if __name__ == "__main__":
    unittest.main()
