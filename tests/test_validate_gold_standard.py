"""tools/validate_gold_standard.py tests.

The end-to-end case runs against tests/fixtures/gold_standard_sample.json --
3 REAL units (BG_2.1/2.12/2.37) lifted verbatim from the project lead's own
Gold-Standard reference sample, the same real data test-gold-render.js is
checked against. The exact finding counts pinned below are not synthetic
expectations -- they are genuine gaps in the reference sample itself,
confirmed by direct inspection (see each check's docstring in
validate_gold_standard.py): BG_2.37 writes "जित्वा वा भोक्ष्यसे महीम्" as one
combined pratika span while word_mappings splits it into two entries plus an
unused "कौन्तेय" entry (3 real V3-forward failures); BG_2.1's "कुतः" and part
of BG_2.37's combined span have no word_mappings match (V3-reverse warnings);
BG_2.12/BG_2.37 leave "देहतोऽपि"/"पक्षद्वयेऽपि" avagrahas in gloss (V4
warnings). A validator that reported zero findings against this file would be
the one that's wrong.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import validate_gold_standard as vgs

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "gold_standard_sample.json")


class TestRealSample(unittest.TestCase):
    def setUp(self):
        vgs.findings.clear()

    def test_end_to_end_against_real_reference_sample(self):
        units = list(vgs.iter_units(FIXTURE))
        self.assertEqual(len(units), 3)
        all_units = []
        for source_label, uid, unit, mula_text in units:
            self.assertTrue(vgs.check_schema(uid, unit))
            vgs.check_v1_source_immutability(uid, source_label, mula_text, {}, update=False)
            vgs.check_v2_v3_pratika(uid, unit)
            vgs.check_v4_gloss_tokens(uid, unit)
            vgs.check_v5_dialectic_pairing(uid, unit)
            vgs.check_v7_closed_world_citations(uid, unit)
            all_units.append((uid, unit))
        vgs.check_v6_danda_integrity(all_units)

        fails = [f for f in vgs.findings if f["severity"] == "FAIL"]
        by_check = {}
        for f in fails:
            by_check.setdefault(f["check"], []).append(f)

        self.assertEqual(len(by_check.get("V3-forward", [])), 3,
                          "BG_2.37's split word_mappings vs combined pratika span is a real parity gap")
        self.assertEqual(len(fails), 3, f"unexpected additional FAIL findings: {fails}")

        warn_checks = {f["check"] for f in vgs.findings if f["severity"] == "WARN"}
        self.assertIn("V3-reverse", warn_checks)
        self.assertIn("V4", warn_checks)
        # No checksum baseline was passed in, so V1 warns rather than fails.
        self.assertTrue(all(f["severity"] == "WARN" for f in vgs.findings if f["check"] == "V1"))


class TestSchema(unittest.TestCase):
    def setUp(self):
        vgs.findings.clear()

    def test_missing_commentary_markdown_fails(self):
        self.assertFalse(vgs.check_schema("u1", {"word_mappings": []}))
        self.assertEqual(vgs.findings[0]["check"], "SCHEMA")

    def test_word_mapping_missing_keys_fails(self):
        unit = {"commentary_markdown": "text", "word_mappings": [{"mula_word": "x"}]}
        self.assertFalse(vgs.check_schema("u1", unit))

    def test_well_formed_unit_passes(self):
        unit = {"commentary_markdown": "text", "word_mappings": [
            {"mula_word": "x", "pratika": "x", "gloss": "y"}]}
        self.assertTrue(vgs.check_schema("u1", unit))


class TestV2MalformedQuoteStyle(unittest.TestCase):
    def setUp(self):
        vgs.findings.clear()

    def test_curly_quote_pratika_flagged_when_it_matches_a_real_mapping(self):
        unit = {
            "commentary_markdown": '“राजा” इत्यादि — no wait',
            "word_mappings": [{"mula_word": "राजा", "pratika": "राजा", "gloss": "g"}],
        }
        # Build the curly-quote bold form directly to avoid escaping confusion.
        unit["commentary_markdown"] = "**“राजा”** इति ।"
        vgs.check_v2_v3_pratika("u1", unit)
        v2 = [f for f in vgs.findings if f["check"] == "V2"]
        self.assertEqual(len(v2), 1)

    def test_curly_single_quote_emphasis_not_matching_any_mapping_is_not_flagged(self):
        # Matches the real BG_2.37 case: legitimate emphasis, not a mistyped pratika.
        unit = {
            "commentary_markdown": "**‘न चैतद्विद्मः’** इति ।",
            "word_mappings": [{"mula_word": "x", "pratika": "हतो वा", "gloss": "g"}],
        }
        vgs.check_v2_v3_pratika("u1", unit)
        self.assertEqual([f for f in vgs.findings if f["check"] == "V2"], [])


class TestV5DialecticPairing(unittest.TestCase):
    def setUp(self):
        vgs.findings.clear()

    def test_unresolved_objection_warns(self):
        unit = {"commentary_markdown": "पूर्वपक्षः इति चेत् — इति ।"}
        vgs.check_v5_dialectic_pairing("u1", unit)
        self.assertEqual(len(vgs.findings), 1)
        self.assertEqual(vgs.findings[0]["check"], "V5")

    def test_resolved_objection_is_silent(self):
        unit = {"commentary_markdown": "पूर्वपक्षः इति चेत् — न, तस्मात् नाद्यः इति सिद्धान्तः ।"}
        vgs.check_v5_dialectic_pairing("u1", unit)
        self.assertEqual(vgs.findings, [])

    def test_explicit_unanswered_flag_is_silent(self):
        unit = {"commentary_markdown": "इति चेत् — इति ।", "flags": {"unanswered": "deferred"}}
        vgs.check_v5_dialectic_pairing("u1", unit)
        self.assertEqual(vgs.findings, [])


class TestV6DandaIntegrity(unittest.TestCase):
    def setUp(self):
        vgs.findings.clear()

    def test_bound_danda_passes(self):
        unit = {"id": "u1", "commentary_markdown": "श्लोकः अत्र समाप्तः ।", "word_mappings": []}
        vgs.check_v6_danda_integrity([("u1", unit)])
        self.assertEqual([f for f in vgs.findings if f["severity"] == "FAIL"], [])

    def test_block_leading_danda_fails(self):
        # A paragraph that itself begins with a danda has nothing before it
        # for bindDandas() to bind to -- a real "line-initial danda" case.
        unit = {"id": "u1", "commentary_markdown": "। अनाथ दण्डः इति ।", "word_mappings": []}
        vgs.check_v6_danda_integrity([("u1", unit)])
        v6 = [f for f in vgs.findings if f["check"] == "V6"]
        self.assertEqual(len(v6), 1)
        self.assertEqual(v6[0]["severity"], "FAIL")


class TestChecksumRoundTrip(unittest.TestCase):
    def setUp(self):
        vgs.findings.clear()

    def test_update_then_match_is_silent_then_mismatch_fails(self):
        manifest = {}
        vgs.check_v1_source_immutability("u1", "f.json", "मूलम्", manifest, update=True)
        self.assertIn("f.json::u1", manifest)

        vgs.findings.clear()
        vgs.check_v1_source_immutability("u1", "f.json", "मूलम्", manifest, update=False)
        self.assertEqual(vgs.findings, [])

        vgs.findings.clear()
        vgs.check_v1_source_immutability("u1", "f.json", "मूलम् बदला हुआ", manifest, update=False)
        self.assertEqual(len(vgs.findings), 1)
        self.assertEqual(vgs.findings[0]["severity"], "FAIL")


if __name__ == "__main__":
    unittest.main()
