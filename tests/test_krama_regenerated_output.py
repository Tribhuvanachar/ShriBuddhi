"""dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_regenerated_output.json

This is the OUTPUT of tools/pratishakhya/regenerate_krama_rv_1_1.py, the real
computational Krama engine (sanskrit_phonology.py + pratishakhya_classify.py +
krama_engine.py) run directly against DGE's own Pada-patha/Samhita-patha --
not the earlier hand-aligned tools/pratishakhya/generate_krama_rv_1_1.py.
Structural checks only, mirroring tests/test_krama_generated_output.py's
convention -- linguistic correctness is what validate_krama_rv1_1.py's Test
A-H suite and external verification (KRAMA_VERIFICATION_PACKET.md) are for.
"""

import json
import os
import unittest

REPO = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(
    REPO, "dge", "data", "vedanga", "shiksha", "pratishakhya",
    "rigveda_pratishakhya", "krama_regenerated_output.json",
)

PARIGRAHA_LIKE = {"parigraha", "monosyllable_confirm_pair"}
PAIR_LIKE = {"pair", "monosyllable_retake_tri_unit"}


class KramaRegeneratedOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA_PATH, encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_nine_verses_present(self):
        ids = [v["id"] for v in self.data["items"]]
        self.assertEqual(ids, [f"1.1.{n}" for n in range(1, 10)])

    def test_no_verse_has_a_hardcoded_pada_word_list(self):
        # every verse's pada_words must come from DGE's own data.json, not a
        # value typed into this repo's scripts -- checked indirectly here by
        # confirming the source script itself carries no per-verse literal
        # (see tools/pratishakhya/regenerate_krama_rv_1_1.py's own docstring
        # and the absence of any VERSES/PARIGRAHA_FORMS-shaped constant there).
        script_path = os.path.join(REPO, "tools", "pratishakhya", "regenerate_krama_rv_1_1.py")
        with open(script_path, encoding="utf-8") as f:
            src = f.read()
        for verse_word in ("अग्निमीळे", "पुरःऽहितम्", "रत्नधातमम्"):
            self.assertNotIn(verse_word, src)

    def test_every_ardharca_ends_in_ardharca_final_parigraha(self):
        # sutra 10.9: ardharca-final words always route to Parigraha, even
        # when the preceding unit was the 10.3 monosyllable-exception path
        # (a real bug this session found and fixed in krama_engine.py: the
        # 10.3 branch originally `continue`d without checking 10.9 at all).
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                units = ardharca["units"]
                with self.subTest(verse=verse["id"]):
                    self.assertIn(units[-1]["type"], PARIGRAHA_LIKE)
                    self.assertIn("10.9", units[-1]["rule"])

    def test_pair_and_special_units_cover_every_word_boundary(self):
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                n_words = len(ardharca["pada_words"])
                n_pair_like = sum(1 for u in ardharca["units"] if u["type"] in PAIR_LIKE)
                with self.subTest(verse=verse["id"]):
                    self.assertEqual(n_pair_like, n_words - 1)

    def test_low_confidence_units_are_flagged(self):
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                for unit in ardharca["units"]:
                    if unit.get("confidence") == "low":
                        with self.subTest(verse=verse["id"], text=unit["text"]):
                            self.assertIn("note", unit)

    def test_counts_are_internally_consistent(self):
        counts = self.data["counts"]
        recomputed = {"pada_count": 0, "pair_count": 0, "parigraha_count": 0,
                      "ardharca_count": 0, "special_exception_count": 0, "unresolved_count": 0,
                      "candidate_reconstruction_count": 0, "chain_reconstruction_mismatch_count": 0}
        tri_unit_count = 0
        total_word_boundaries = 0
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                recomputed["ardharca_count"] += 1
                recomputed["pada_count"] += len(ardharca["pada_words"])
                total_word_boundaries += max(len(ardharca["pada_words"]) - 1, 0)
                if ardharca["chain_reconstruction"]["status"] == "DIFFERS":
                    recomputed["chain_reconstruction_mismatch_count"] += 1
                for u in ardharca["units"]:
                    if u["type"] == "pair":
                        recomputed["pair_count"] += 1
                    elif u["type"] == "parigraha":
                        recomputed["parigraha_count"] += 1
                    elif u["type"] in ("monosyllable_retake_tri_unit", "monosyllable_confirm_pair"):
                        recomputed["special_exception_count"] += 1
                        if u["type"] == "monosyllable_retake_tri_unit":
                            tri_unit_count += 1
                    if u.get("confidence") == "low":
                        recomputed["unresolved_count"] += 1
                    if u.get("status") == "candidate_reconstruction":
                        recomputed["candidate_reconstruction_count"] += 1
        # invariant_check is a derived/reported sub-object, not an independent
        # count -- compared separately so this test still pins its own formula.
        invariant_check = counts["invariant_check"]
        counts_without_invariant = {k: v for k, v in counts.items() if k != "invariant_check"}
        self.assertEqual(counts_without_invariant, recomputed)
        self.assertTrue(invariant_check["holds"])
        self.assertEqual(invariant_check["pair_count"] + invariant_check["monosyllable_retake_tri_unit_count"],
                          invariant_check["total_word_boundaries"])
        self.assertEqual(invariant_check["total_word_boundaries"], total_word_boundaries)

    def test_status_field_present_on_every_unit(self):
        # every unit must declare canonical vs candidate_reconstruction --
        # a consumer must never have to infer this from "type" or "confidence"
        # (11 Sep 2026 review point 5).
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                for u in ardharca["units"]:
                    with self.subTest(verse=verse["id"], text=u["text"]):
                        self.assertIn(u.get("status"), ("canonical", "candidate_reconstruction"))

    def test_parigraha_units_declare_retake_state(self):
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                for u in ardharca["units"]:
                    if u["type"] == "parigraha":
                        with self.subTest(verse=verse["id"], text=u["text"]):
                            self.assertEqual(u["retake_state"], "STHITOPASTHITA")
                            self.assertTrue(u["trigger_reasons"])

    def test_every_ardharca_has_chain_reconstruction(self):
        for verse in self.data["items"]:
            for ardharca in verse["ardharcas"]:
                cr = ardharca["chain_reconstruction"]
                with self.subTest(verse=verse["id"]):
                    self.assertIn(cr["status"], ("EXACT_MATCH", "DIFFERS"))
                    self.assertIsInstance(cr["computed"], str)

    def test_chain_reconstruction_matches_at_least_17_of_18(self):
        # Known, documented baseline (see sec.6.7/6.8 of the architecture
        # doc): after the r/f ZWNJ fix and the diphthong-glide fix (11 Sep
        # 2026, from external review), 17 of 18 ardharcas match exactly.
        # The one known remaining mismatch is RV 1.1.7 ardharca 1's
        # visarga-before-aa gap, still genuinely unresolved (no sutra
        # citation found yet) -- not something this test should silently
        # let regress further.
        mismatches = [
            (v["id"], a_idx)
            for v in self.data["items"]
            for a_idx, a in enumerate(v["ardharcas"])
            if a["chain_reconstruction"]["status"] == "DIFFERS"
        ]
        self.assertLessEqual(len(mismatches), 1, f"unexpected new mismatches: {mismatches}")

    def test_comparison_against_hand_aligned_output_present(self):
        comparison = self.data["comparison_against_hand_aligned_output"]
        self.assertIsNotNone(comparison)
        ids = [r["id"] for r in comparison]
        self.assertEqual(ids, [f"1.1.{n}" for n in range(1, 10)])

    def test_pair_level_diffs_against_hand_aligned_output_are_the_two_known_ones(self):
        # 11 Sep 2026: get_sthitopasthita() was fixed to apply real sandhi
        # at the word+iti junction (previously a fixed "word SPACE iti"
        # template, which only matched Uvata's two PRAGRHYA examples -- see
        # pratishakhya_classify.py's own docstring and
        # RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md). That makes EVERY
        # parigraha-type unit differ from the old hand-aligned file, which
        # used the wrong template throughout -- so the previous "7 of 9
        # verses match exactly" baseline no longer means anything (0 of 9
        # verses can match exactly now, by construction, regardless of
        # whether anything is actually wrong). What this test checks
        # instead: no NEW divergence was introduced in the actual pairing/
        # phonology (non-Parigraha) logic -- every pair-type diff must
        # still be one of the two already-documented cases from sec.6.6
        # (1.1.2's 10.3 firing on a second, previously-unflagged position;
        # 1.1.7's still-open visarga-before-aa gap, whose index shift
        # cascades into the two neighbouring units of the same ardharca).
        comparison = self.data["comparison_against_hand_aligned_output"]
        known_pair_level_verses = {"1.1.2", "1.1.7"}
        for verse in comparison:
            for ardharca in verse["ardharcas"]:
                for diff in ardharca["diffs"]:
                    unit_type = diff.get("new_type") or diff.get("old_type")
                    if unit_type in PARIGRAHA_LIKE:
                        continue  # expected everywhere, from the sandhi fix
                    with self.subTest(id=verse["id"], diff=diff):
                        self.assertIn(verse["id"], known_pair_level_verses)

    def test_provenance_fields_present(self):
        for key in ("engine_source", "pada_samhita_source", "note"):
            self.assertIn(key, self.data)


if __name__ == "__main__":
    unittest.main()
