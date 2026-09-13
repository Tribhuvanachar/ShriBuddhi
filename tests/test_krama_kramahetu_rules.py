"""dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_kramahetu_rules.json

Checks the committed output of tools/pratishakhya/build_krama_rules.py: the
interpretation layer built on top of the raw sutra text (data.json) and the
VedaVishtaram cross-check. Guards that the file stays complete (one entry
per patala-10/11 sutra, no silent gaps), that fully-worked-out entries carry
the fields a rule engine would need, and that the file is honest about what
is NOT yet done (patala 11's undetailed sutras stay marked as such, and
nothing claims to be validated against an attested Krama text it hasn't
actually been checked against).
"""

import json
import os
import unittest

REPO = os.path.join(os.path.dirname(__file__), "..")
RULES_PATH = os.path.join(
    REPO, "dge", "data", "vedanga", "shiksha", "pratishakhya",
    "rigveda_pratishakhya", "krama_kramahetu_rules.json",
)


class KramaKramahetuRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(RULES_PATH, encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.by_id = {item["id"]: item for item in cls.data["items"]}

    def test_complete_coverage_patala_10_and_11(self):
        # Every patala-10 (1-22) and patala-11 (1-71) sutra must have an
        # entry -- detailed or stub -- nothing silently skipped.
        for sutra in range(1, 23):
            self.assertIn(f"10.{sutra}", self.by_id)
        for sutra in range(1, 72):
            self.assertIn(f"11.{sutra}", self.by_id)
        self.assertEqual(len(self.data["items"]), 93)

    def test_fully_worked_out_entries_have_required_fields(self):
        required = {"summary", "conditions", "action", "exceptions", "examples",
                    "confidence", "basis", "sutra_text_devanagari"}
        for item in self.data["items"]:
            if item["rule_type"] in ("operative", "definitional", "optional"):
                with self.subTest(sutra=item["id"]):
                    self.assertTrue(required.issubset(item.keys()))
                    self.assertNotEqual(item["confidence"], "unclassified")
                    # 10.3 and 11.8 are the two patala-10/11 sutras deliberately
                    # left has_uncertain_reading=true by the VedaVishtaram
                    # cross-check (RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.4c)
                    # -- they have no text_devanagari to check yet.
                    self.assertTrue(item["sutra_text_devanagari"] or item["id"] in ("10.3", "11.8"),
                                     "missing sutra text for " + item["id"])

    def test_nothing_claims_validation_it_has_not_had(self):
        # This rule-logic layer is explicitly not yet validated against an
        # attested Krama-patha text (RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md
        # sec.7/sec.10) -- no entry should claim otherwise.
        for item in self.data["items"]:
            self.assertFalse(item.get("validated_against_attested_krama", False),
                              item["id"])

    def test_key_rules_present_and_operative(self):
        # The specific rules the original Gemini-derived review flagged as
        # missing or wrong in the naive prompt.
        expected_operative = {
            "10.2": "structural_pairing",   # base pairing algorithm
            "10.7": "parigraha_scope",      # Parigraha scope, not word+iti formula
            "10.14": "sthita_upasthita_definition",  # sthitopasthita, the real mechanism
            "10.18": "ardharca_boundary",   # no sandhi across ardharca
            "10.20": "pragrhya_in_parigraha",  # Pragrhya-in-Parigraha behaviour
            "10.22": "rephita",             # rephita predicate
            "11.19": "catuhkrama",          # the Sakala four-krama practice
        }
        for sutra_id, domain in expected_operative.items():
            with self.subTest(sutra=sutra_id):
                item = self.by_id[sutra_id]
                self.assertEqual(item["domain"], domain)
                self.assertIn(item["rule_type"], ("operative", "definitional"))
                self.assertTrue(item["action"] or item["rule_type"] == "definitional")

    def test_patala_10_fully_detailed(self):
        for sutra in range(1, 23):
            item = self.by_id[f"10.{sutra}"]
            with self.subTest(sutra=item["id"]):
                self.assertNotEqual(item["rule_type"], "operative-undetailed")


if __name__ == "__main__":
    unittest.main()
