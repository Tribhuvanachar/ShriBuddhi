"""tools/build_sandhi_split_index.py — the validation and ranking that turn
sanskrit_parser's ~20 raw splits per word into the one or two a reader wants.

The splitter itself is not exercised here (it is a third-party library and a
slow one); what is tested is this repo's own logic around it.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import build_sandhi_split_index as b  # noqa: E402


class Ranking(unittest.TestCase):
    def rank(self, splits, counts):
        return [(s["a"], s["b"]) for s in b.rank_splits(splits, counts)]

    def test_a_split_naming_a_verb_comes_first(self):
        # The verb half is the whole reason a reader splits a compound: it is
        # the only piece that leads anywhere (to a root and its paradigm).
        splits = [
            {"a": "क", "b": "ख", "sa": b.SRC_NOMINAL, "sb": b.SRC_NOMINAL},
            {"a": "ग", "b": "घ", "sa": b.SRC_NOMINAL, "sb": b.SRC_VERB},
        ]
        self.assertEqual(self.rank(splits, {})[0], ("ग", "घ"))

    def test_corpus_frequency_breaks_a_tie_that_balance_would_get_wrong(self):
        # The real case: फलितमाह. Both halves of both candidates are in the
        # word lists and both name a verb, and on balance alone फलित + माह
        # wins by one letter -- but the corpus uses फलितम् and आह constantly
        # and माह almost never.
        splits = [
            {"a": "फलित", "b": "माह", "sa": b.SRC_NOMINAL, "sb": b.SRC_VERB},
            {"a": "फलितम्", "b": "आह", "sa": b.SRC_NOMINAL, "sb": b.SRC_VERB},
        ]
        counts = {"फलित": 900, "माह": 2, "फलितम्": 800, "आह": 4000}
        self.assertEqual(self.rank(splits, counts)[0], ("फलितम्", "आह"))

    def test_balance_still_decides_when_frequency_cannot(self):
        splits = [
            {"a": "अब", "b": "सदेफग", "sa": b.SRC_NOMINAL, "sb": b.SRC_NOMINAL},
            {"a": "अबस", "b": "देफग", "sa": b.SRC_NOMINAL, "sb": b.SRC_NOMINAL},
        ]
        counts = {"अब": 5, "सदेफग": 5, "अबस": 5, "देफग": 5}
        self.assertEqual(self.rank(splits, counts)[0], ("अबस", "देफग"))

    def test_ranking_is_total_so_a_build_is_reproducible(self):
        splits = [
            {"a": "ख", "b": "ग", "sa": b.SRC_NOMINAL, "sb": b.SRC_NOMINAL},
            {"a": "क", "b": "घ", "sa": b.SRC_NOMINAL, "sb": b.SRC_NOMINAL},
        ]
        self.assertEqual(self.rank(splits, {}), self.rank(list(reversed(splits)), {}))


class Buckets(unittest.TestCase):
    def test_bucket_matches_the_clients_own_convention(self):
        # ai.js's dgeSandhiBucketOf: first two SLP1 characters, an uppercase
        # one written with a trailing underscore. The two must agree or every
        # lookup misses.
        b.init_worker(set(), set(), set(), 2)
        # भवति is "Bavati" in SLP1 — B is aspirated bh, an uppercase letter,
        # so it is written B_ ; कृत्वा is "kftvA", both letters lowercase.
        self.assertEqual(b.bucket_of("भवति"), "B_a")
        self.assertEqual(b.bucket_of("आह"), "A_h")
        self.assertEqual(b.bucket_of("कृत्वा"), "kf")

    def test_every_bucket_name_is_filesystem_safe(self):
        b.init_worker(set(), set(), set(), 2)
        for word in ("भवति", "आह", "ॐकार", "कृत्वा"):
            name = b.bucket_of(word)
            self.assertTrue(name, word)
            self.assertRegex(name, r"^[A-Za-z0-9_x]+$", word)


class Sources(unittest.TestCase):
    def setUp(self):
        b.init_worker({"रामस्य"}, {"आह"}, {"प्र"}, 2)

    def test_a_verb_form_outranks_a_nominal_reading_of_the_same_half(self):
        b.init_worker({"आह"}, {"आह"}, set(), 2)
        self.assertEqual(b._source_of("आह", False), b.SRC_VERB)

    def test_an_upasarga_counts_only_as_a_first_half(self):
        # प्र is a prefix, not a word that can end a compound.
        self.assertEqual(b._source_of("प्र", True), b.SRC_UPASARGA)
        self.assertIsNone(b._source_of("प्र", False))

    def test_an_unrecognised_half_is_refused(self):
        self.assertIsNone(b._source_of("झझझ", True))


if __name__ == "__main__":
    unittest.main()
