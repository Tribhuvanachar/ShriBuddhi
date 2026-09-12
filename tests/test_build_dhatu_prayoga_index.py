"""tools/build_dhatu_prayoga_index.py — how an occurrence is attributed when
the spelling does not name one root.

The defect these guard against is not a crash. कृत्वा is the ktvā of both
कृ॒ञ् हिंसायाम् (05.0007, "to injure") and डुकृ॒ञ् करणे (08.0010, "to do");
the form indexes answered with whichever came first in Dhātupāṭha order, so
every "having done" in the corpus was reported as an injuring — 29,938 of
them on a root attested 110 times. Nothing errored, and the page looked
authoritative.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import build_dhatu_prayoga_index as b  # noqa: E402


def write_index(root, name, payload):
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "0915.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return d


class LoadForms(unittest.TestCase):
    """The regression that silently emptied the index: build_prakriya_form_index
    started storing a LIST per form, and this still tested isinstance(rec, dict),
    so every tiṅanta form was skipped and a rebuild would have produced a
    kṛdanta-only index without a single warning."""

    def run_load(self, krt, tin):
        with tempfile.TemporaryDirectory() as tmp:
            kd = write_index(tmp, "krtindex", krt)
            fd = write_index(tmp, "formindex", tin)
            from pathlib import Path
            old_k, old_f = b.KRTINDEX, b.FORMINDEX
            b.KRTINDEX, b.FORMINDEX = Path(kd), Path(fd)
            try:
                return b.load_forms()
            finally:
                b.KRTINDEX, b.FORMINDEX = old_k, old_f

    def test_the_list_shape_is_read(self):
        forms = self.run_load({}, {"कृत्वा": [{"c": "05.0007", "k": "Lat.00"}]})
        self.assertEqual(forms["कृत्वा"], [("05.0007", "Lat.00")])

    def test_the_older_single_record_shape_still_works(self):
        forms = self.run_load({}, {"कृत्वा": {"c": "05.0007", "k": "Lat.00"}})
        self.assertEqual(forms["कृत्वा"], [("05.0007", "Lat.00")])

    def test_every_root_is_kept_not_the_first(self):
        forms = self.run_load(
            {"कृत्वा": [{"c": "05.0007", "k": "ktvA"}, {"c": "08.0010", "k": "ktvA"}]}, {})
        self.assertEqual({c for c, _ in forms["कृत्वा"]}, {"05.0007", "08.0010"})

    def test_krdanta_and_tinanta_readings_of_one_spelling_are_merged(self):
        forms = self.run_load({"कृतम्": [{"c": "08.0010", "k": "kta"}]},
                              {"कृतम्": [{"c": "05.0007", "k": "Lot.11"}]})
        self.assertEqual(forms["कृतम्"], [("08.0010", "krt:kta"), ("05.0007", "Lot.11")])

    def test_krdanta_keys_are_namespaced(self):
        # 'krt:' distinguishes a kṛt cell from a lakāra cell of the same name.
        forms = self.run_load({"कृतम्": [{"c": "08.0010", "k": "kta"}]}, {})
        self.assertEqual(forms["कृतम्"][0][1], "krt:kta")

    def test_the_manifest_is_not_read_as_forms(self):
        forms = self.run_load({}, {"_readme": "x", "कृत्वा": [{"c": "05.0007", "k": "Lat.00"}]})
        self.assertNotIn("_readme", forms)

    def test_stoplisted_and_too_short_forms_are_dropped(self):
        forms = self.run_load({}, {"च": [{"c": "01.0001", "k": "Lat.00"}],
                                   "ते": [{"c": "01.0001", "k": "Lat.00"}]})
        self.assertEqual(forms, {})


class Ranking(unittest.TestCase):
    KRTVA = [("05.0007", "krt:ktvA"), ("08.0010", "krt:ktvA")]

    def test_the_root_the_corpus_actually_attests_leads(self):
        # These are the real measured weights: forms only डुकृञ् can write
        # occur 17,049 times, forms only कृञ् can write 110 times.
        ranked = b.rank_readings(self.KRTVA, {"05.0007": 110, "08.0010": 17049})
        self.assertEqual(ranked[0][0], "08.0010")

    def test_dhatupatha_order_does_not_decide_it(self):
        # The old behaviour: lowest code wins. 05.0007 sorts first and is wrong.
        ranked = b.rank_readings(self.KRTVA, {"05.0007": 110, "08.0010": 17049})
        self.assertNotEqual(ranked[0][0], min(c for c, _ in self.KRTVA))

    def test_a_tie_is_broken_reproducibly(self):
        a = b.rank_readings(self.KRTVA, {})
        c = b.rank_readings(list(reversed(self.KRTVA)), {})
        self.assertEqual(a, c)

    def test_weights_come_only_from_unambiguous_evidence(self):
        # A root with no unambiguous attestation has weight 0 and must never
        # outrank one that has some, however many shared forms it appears in.
        ranked = b.rank_readings(self.KRTVA, {"08.0010": 1})
        self.assertEqual(ranked[0][0], "08.0010")


class Chips(unittest.TestCase):
    def test_an_unambiguous_word_keeps_the_three_element_shape(self):
        # render.js destructures [word, code, key, amb]; a certain chip has
        # always been three elements and readers rely on the fourth being
        # absent rather than 0.
        self.assertEqual(b.chip_for("गच्छति", [("01.1137", "Lat.00")], {}),
                         ["गच्छति", "01.1137", "Lat.00"])

    def test_an_ambiguous_word_reports_how_many_roots_and_which(self):
        chip = b.chip_for("कृत्वा", [("05.0007", "krt:ktvA"), ("08.0010", "krt:ktvA")],
                          {"05.0007": 110, "08.0010": 17049})
        word, code, key, amb, alts = chip
        self.assertEqual(code, "08.0010")
        self.assertEqual(amb, 2)
        self.assertEqual(alts, ["05.0007"])

    def test_the_alternatives_list_is_capped(self):
        readings = [("0%d.000%d" % (i, i), "Lat.00") for i in range(1, 10)]
        chip = b.chip_for("x", readings, {})
        self.assertLessEqual(len(chip[4]), 6)

    def test_two_cells_of_one_root_do_not_read_as_two_roots(self):
        # Ambiguity is about ROOTS. One root producing a form in two cells is
        # not a homograph and must not be flagged as one.
        chip = b.chip_for("भवति", [("01.0001", "Lat.00"), ("01.0001", "Lot.00")], {})
        self.assertEqual(len(chip), 3)


class ShippedIndex(unittest.TestCase):
    """The committed index — the numbers the lead actually reported on."""

    def setUp(self):
        path = b.OUT / "manifest.json"
        if not path.exists():
            self.skipTest("dhatu_prayoga index not built")
        self.manifest = json.loads(path.read_text(encoding="utf-8"))

    def load(self, code):
        return json.loads((b.OUT / "by_dhatu" / code[:2] / (code + ".json")).read_text(encoding="utf-8"))

    def test_the_injuring_root_no_longer_claims_the_doing(self):
        # 05.0007 कृ॒ञ् हिंसायाम् reported 29,938 occurrences, almost all of
        # them कृत्वा "having done". Its certain count is now two figures
        # lower, and डुकृ॒ञ् करणे carries the attested ones.
        himsa = self.load("05.0007")
        karana = self.load("08.0010")
        self.assertLess(himsa["total"], 1000)
        self.assertGreater(karana["total"], himsa["total"] * 10)

    def test_a_shared_occurrence_is_recorded_against_both_roots(self):
        himsa = self.load("05.0007")["forms"].get("krt:ktvA")
        karana = self.load("08.0010")["forms"].get("krt:ktvA")
        self.assertIsNotNone(himsa)
        self.assertIsNotNone(karana)
        self.assertEqual(himsa["sn"], karana["sn"])
        self.assertEqual(himsa["n"], 0)
        self.assertEqual(karana["n"], 0)

    def test_shared_counts_are_never_folded_into_the_certain_total(self):
        himsa = self.load("05.0007")
        certain = sum(f["n"] for f in himsa["forms"].values())
        self.assertEqual(himsa["total"], certain)

    def test_root_weights_are_the_certain_totals(self):
        weights = json.loads((b.OUT / "root_weights.json").read_text(encoding="utf-8"))["weights"]
        self.assertEqual(weights["08.0010"], self.load("08.0010")["total"])
        self.assertEqual(weights["05.0007"], self.load("05.0007")["total"])

    def test_the_manifest_says_how_it_counts(self):
        self.assertIn("counting", self.manifest)
        self.assertGreater(self.manifest["sharedOccurrences"], 0)
        self.assertLess(self.manifest["sharedOccurrences"], self.manifest["occurrences"])
        # byDhatu grew a column; a reader taking [1] as "cells" would now be
        # reading the shared count.
        self.assertEqual(len(self.manifest["byDhatu"]["08.0010"]), 3)


if __name__ == "__main__":
    unittest.main()
