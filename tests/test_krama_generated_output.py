"""dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_generated_output.json

Structural checks only -- this is generated, unvalidated output (see the
file's own "note" field and tools/pratishakhya/KRAMA_VERIFICATION_PACKET.md),
so these tests guard internal consistency (every pada word appears, pairs
are correctly overlapping, low-confidence units stay flagged), not
linguistic correctness -- that's exactly what external verification is for.
"""

import json
import os
import unittest

REPO = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(
    REPO, "dge", "data", "vedanga", "shiksha", "pratishakhya",
    "rigveda_pratishakhya", "krama_generated_output.json",
)


class KramaGeneratedOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA_PATH, encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_nine_verses_present(self):
        ids = [v["id"] for v in self.data["items"]]
        self.assertEqual(ids, [f"1.1.{n}" for n in range(1, 10)])

    def test_every_ardharca_has_one_fewer_pair_than_words(self):
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                n_words = len(ardharca["pada_words"])
                n_pairs = sum(1 for u in ardharca["units"] if u["type"] == "pair")
                with self.subTest(verse=verse["id"]):
                    self.assertEqual(n_pairs, n_words - 1)

    def test_last_word_of_every_ardharca_gets_parigraha(self):
        # sutra 10.9: ardharca-final words always route to Parigraha
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                units = ardharca["units"]
                self.assertEqual(units[-1]["type"], "parigraha", verse["id"])
                self.assertIn("10.9", units[-1]["rule"])

    def test_low_confidence_units_are_flagged_and_explained(self):
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                for unit in ardharca["units"]:
                    if unit.get("confidence") == "low":
                        with self.subTest(verse=verse["id"], text=unit["text"]):
                            self.assertIn("note", unit)
                            self.assertIn("10.3", unit["note"])

    def test_provenance_fields_present(self):
        for key in ("rule_source", "pada_samhita_source", "verification_packet", "note"):
            self.assertIn(key, self.data)
        self.assertIn("NOT validated", self.data["note"])


if __name__ == "__main__":
    unittest.main()
