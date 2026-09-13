"""Unit tests for the real Krama engine (tools/pratishakhya/{sanskrit_phonology,
pratishakhya_classify,krama_engine}.py). These exercise the ENGINE CODE
directly, complementing tests/test_krama_regenerated_output.py (which checks
the generated JSON) and tools/pratishakhya/validate_krama_rv1_1.py (which
runs the spec's own Test A-H suite with full PASS/FAIL/UNRESOLVED reporting).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pratishakhya"))

from sanskrit_phonology import (  # noqa: E402
    samhita_join, resolve_compound, reconstruct_chain, strip_zwnj_markers,
    deva_to_slp1, slp1_to_deva, ZWNJ,
)
from pratishakhya_classify import (  # noqa: E402
    is_pragrhya, is_monosyllable_avasana, parse_compound, requires_parigraha,
    get_sthita, get_upasthita, get_sthitopasthita, detect_bahumadhyagata, is_rephi,
)
from krama_engine import generate_ardharca, generate_verse, split_into_ardharcas  # noqa: E402


class SamhitaJoin(unittest.TestCase):
    def test_ordinary_no_sandhi_needed(self):
        result = samhita_join("अग्निम्", "ईळे")
        self.assertEqual(result["surface"], "अग्निमीळे")

    def test_resolve_w1_compound_false_does_not_misread_a_chain_avagraha(self):
        # Regression test for a real bug found 11 Sep 2026 while building
        # chain-reconstruction validation: "सूनवेऽग्ने" here is NOT a
        # Pada-patha compound -- it's running chained text that already
        # picked up an avagraha from an earlier elision join (ordinary
        # Sanskrit orthography). With resolve_w1_compound defaulting True,
        # samhita_join used to call resolve_compound() on it, which
        # collapsed every space built up so far. resolve_w1_compound=False
        # must prevent that.
        result = samhita_join("स नः पितेव सूनवेऽग्ने", "सूपायनः", resolve_w1_compound=False)
        self.assertEqual(result["surface"], "स नः पितेव सूनवेऽग्ने सूपायनः")

    def test_resolve_w1_compound_true_still_resolves_a_real_pada_compound(self):
        # The default (True) must still work for krama_engine.py's ordinary
        # per-pair use, where w1 legitimately IS a single Pada-patha
        # compound word.
        result = samhita_join("पुरःऽहितम्", "यज्ञस्य")
        self.assertEqual(result["surface"], "पुरोहितं यज्ञस्य")

    def test_diphthong_before_other_vowel_replaces_not_appends(self):
        # Regression test for a real bug found via external review (11 Sep
        # 2026), confirmed against standard Paninian grammar (6.1.78,
        # eco'yavAyAvaH) independent of either reviewer's say-so: e/o/ai/au
        # before a vowel OTHER than "a" must be REPLACED by a/a/A/A + the
        # glide, not kept unchanged with a glide merely appended after it
        # (the old code gave "वनेयिन्द्रः", an extra vowel that shouldn't
        # be there, instead of the correct "वनयिन्द्रः").
        self.assertEqual(samhita_join("वने", "इन्द्रः")["surface"], "वनयिन्द्रः")
        self.assertEqual(samhita_join("तस्मै", "इति")["surface"], "तस्मायिति")

    def test_diphthong_before_a_still_elides(self):
        # The +a branch (Panini 6.1.109) is unaffected by the above fix.
        result = samhita_join("सूनवे", "अग्ने")
        self.assertEqual(result["surface"], "सूनवेऽग्ने")

    def test_bare_consonant_before_independent_vowel_survives_two_joins(self):
        # Regression test for a real bug found while building
        # chain-reconstruction validation (11 Sep 2026): the correct
        # Devanagari output of one join, when fed back into a SECOND
        # samhita_join call, used to lose the distinction between a bare
        # consonant before an independent vowel ("र्ऋ") and that same
        # consonant with a dependent vowel-matra ("रृ") -- both collapse to
        # the identical SLP1 string in the indic_transliteration library.
        # Fixed with a ZWNJ marker (external review) that survives being
        # fed through samhita_join an arbitrary number of times; it must be
        # stripped via strip_zwnj_markers() at the point nothing re-joins
        # the string further (what reconstruct_chain()'s own return does).
        first = samhita_join("अग्निः", "पूर्वेभिः")
        second = samhita_join(first["surface"], "ऋषिभिः", resolve_w1_compound=False)
        third = samhita_join(second["surface"], "ईड्यः", resolve_w1_compound=False)
        self.assertEqual(strip_zwnj_markers(third["surface"]), "अग्निः पूर्वेभिर्ऋषिभिरीड्यः")

    def test_zwnj_marker_present_after_every_one_of_10_consecutive_joins(self):
        # Stronger version of the "survives 4/10 joins" claim (11 Sep 2026,
        # a second external review round): asserts the invariant holds
        # after EVERY individual join, not just by comparing the final
        # result. One ZWNJ is added per join that hits the f/F branch, so
        # the running count must equal the join index throughout, not just
        # "at least one present".
        words = ["पूर्वेभिः"] + ["ऋषिभिः"] * 10
        combined = words[0]
        for i, w in enumerate(words[1:], start=1):
            r = samhita_join(combined, w, resolve_w1_compound=False)
            combined = r["surface"]
            self.assertEqual(combined.count(ZWNJ), i, f"wrong ZWNJ count after join {i}: {combined!r}")
        final = strip_zwnj_markers(combined)
        self.assertEqual(final, "पूर्वेभिर्ऋषिभिर्ऋषिभिर्ऋषिभिर्ऋषिभिर्ऋषिभिर्ऋषिभिर्ऋषिभिर्ऋषिभिर्ऋषिभिर्ऋषिभिः")

    def test_visarga_a_class_before_voiced(self):
        result = samhita_join("देवः", "देवेभिः")
        self.assertEqual(result["surface"], "देवो देवेभिः")

    def test_visarga_before_short_a_elides(self):
        result = samhita_join("रामः", "अत्र")
        self.assertTrue(result["surface"].startswith("रामो"))


class NatvaBoundaryAndShuddhaksharaAgama(unittest.TestCase):
    """Round 3 (11 Sep 2026): two narrow, closed, source-cited additions from
    Uvata's own bhashya on 11.23 and 11.43, checked against an external
    review's proposed patches before installing -- both proposals had the
    same real bug, caught by actually running the code rather than trusting
    "I tested this" claims: "DUfzadam" uses SLP1 "f" (vocalic r, an
    independent VOWEL) instead of "r" (the consonant repha) for
    dhuuHsadam's Samhita form, which slp1_to_deva turns into the wrong word
    (dhuu-R-SADAM, not dhuurSadam) -- verified directly below."""

    def test_natva_boundary_pra_naH_exact_citation(self):
        result = samhita_join("प्र", "नः")
        self.assertEqual(result["surface"], "प्र णः")
        self.assertEqual(result["rule"], "natva_boundary_11_23")

    def test_natva_does_not_fire_without_the_upasarga_adjacent(self):
        # 11.23's whole point: apetahetuSu -- once "pra" is no longer
        # adjacent, plain sandhi applies, no retroflexion.
        result = samhita_join("नः", "इन्द्रः")
        self.assertNotIn("ण", result["surface"])
        self.assertNotEqual(result["rule"], "natva_boundary_11_23")

    def test_parigraha_restoration_is_automatic_no_leaked_retroflexion(self):
        # get_sthitopasthita builds the Parigraha citation for "naH" as
        # retaken on its own (not adjacent to "pra") -- the retroflexed
        # "NaH" form must never leak into it.
        result = get_sthitopasthita("नः")
        self.assertNotIn("ण", result)

    def test_shuddhakshara_agama_exact_citations(self):
        cases = [
            ("सु", "चन्द्र", "सुश्चन्द्र"),
            ("परि", "कृण्वन्", "परिष्कृण्वन्"),
            ("धूः", "सदम्", "धूर्षदम्"),
            ("वन", "सदम्", "वनर्षदम्"),
        ]
        for w1, w2, expected in cases:
            with self.subTest(w1=w1, w2=w2):
                result = samhita_join(w1, w2)
                self.assertEqual(result["surface"], expected)
                self.assertEqual(result["rule"], "shauddhakshara_agama_11_43")

    def test_shuddhakshara_agama_restoration_is_automatic(self):
        # Parigraha for "सुचन्द्र" is computed from the bare Pada word
        # directly (never from the augmented "सुश्चन्द्र" Samhita form), so
        # the augment must never appear in its Parigraha citation.
        result = get_sthitopasthita("सुचन्द्र")
        self.assertNotIn("श", result)

    def test_dhuuHsadam_rephi_cache_encoding_fix(self):
        # Regression test for a real, separate encoding bug found while
        # verifying the agama table above: REPHI_CACHE_SLP1 had "dh"
        # (lowercase d + h, not valid SLP1 for dha) where it needed the
        # single capital letter "D" -- is_rephi() on the actual Devanagari
        # word silently always returned False. Two entries were affected.
        self.assertTrue(is_rephi("धूःसदम्"))
        self.assertTrue(is_rephi("दुर्ध्यः"))


class Predicates(unittest.TestCase):
    def test_is_pragrhya_lexical_class(self):
        ok, _ = is_pragrhya("अस्मे")
        self.assertTrue(ok)

    def test_is_pragrhya_false_for_ordinary_word(self):
        ok, _ = is_pragrhya("अग्निम्")
        self.assertFalse(ok)

    def test_is_pragrhya_vocative_o(self):
        # Regression test for a real gap found 11 Sep 2026 while
        # fact-checking an external citation for sutra 1.68 ("okAra
        # AmantritajaH pragfhyaH" -- vocative 'o' is pragrhya): this
        # function had a context-gated check for vocative words ending in
        # -e, but none at all for -o, even though vibhaavaso (this
        # project's own cited 10.14 example) is exactly this case.
        ok, reason = is_pragrhya("विभावसो", context={"is_amantrita": True})
        self.assertTrue(ok)
        self.assertIn("1.68", reason)
        # Without is_amantrita context, an "o"-ending word must NOT be
        # assumed pragrhya -- plenty of non-vocative words end in "o" via
        # ordinary a-class visarga sandhi and are not pragrhya for that.
        ok2, _ = is_pragrhya("देवो")
        self.assertFalse(ok2)

    def test_is_monosyllable_avasana(self):
        self.assertTrue(is_monosyllable_avasana("आ"))
        self.assertFalse(is_monosyllable_avasana("अग्निम्"))

    def test_parse_compound(self):
        self.assertEqual(parse_compound("पुरःऽहितम्"),
                          {"is_compound": True, "segments": ["पुरः", "हितम्"]})
        self.assertEqual(parse_compound("अग्निम्"),
                          {"is_compound": False, "segments": ["अग्निम्"]})

    def test_requires_parigraha_compound(self):
        needs, reasons = requires_parigraha("पुरःऽहितम्", 2, 6)
        self.assertTrue(needs)
        self.assertIn("10.7", reasons)

    def test_requires_parigraha_ardharca_final(self):
        needs, reasons = requires_parigraha("ऋत्विजम्", 5, 6)
        self.assertTrue(needs)
        self.assertIn("10.9", reasons)

    def test_requires_parigraha_false_for_ordinary_mid_word(self):
        needs, _ = requires_parigraha("यज्ञस्य", 3, 6)
        self.assertFalse(needs)

    def test_sthitopasthita_uses_combined_form(self):
        # पुरोहितम् ends in a consonant (म्), so its real sandhi with इति
        # is a plain pass-through with no visible change other than the
        # two words fusing into one written run -- see
        # test_sthitopasthita_applies_real_sandhi_not_a_fixed_template
        # below for why this must be real samhita_join output, not a
        # hand-picked space-separated template.
        result = get_sthitopasthita("पुरःऽहितम्", "पुरोहितम्")
        self.assertEqual(result, "पुरोहितमिति पुरःऽहितम्")

    def test_sthitopasthita_applies_real_sandhi_not_a_fixed_template(self):
        # Found 11 Sep 2026 by contrasting two of Uvata's own worked
        # examples: 10.8's "ca iti ca" -> "cEti ca" (ordinary a+i->e guNa
        # sandhi) and 10.16's "purojitI iti" -> "purojitIti" (I+i->I) both
        # show REAL sandhi at the word+iti junction for non-pragrhya words
        # -- the previous "word + literal space + iti" template was wrong
        # for anything but the two pragrhya examples it happened to be
        # checked against (vibhAvaso, bAhU -- see the pragrhya-bypass test
        # below). This must go through samhita_join for real, not a
        # hand-written guNa-sandhi special case.
        self.assertEqual(get_sthitopasthita("च"), "चेति च")
        self.assertEqual(get_sthitopasthita("वा"), "वेति वा")
        self.assertEqual(get_sthitopasthita("चित्"), "चिदिति चित्")
        self.assertEqual(get_upasthita("च"), "चेति")

    def test_sthitopasthita_bypasses_sandhi_for_pragrhya_words(self):
        # The other half of the same finding: sandhi must NOT apply when
        # the word is pragrhya, since pragrhya vowels are defined to
        # resist external sandhi -- Uvata's own counter-examples, both
        # independently pragrhya for a documented reason (vibhAvaso:
        # vocative -o, sutra 1.68; bAhU: dual -U, Paatala 1's
        # morphological class), show NO change at all before iti.
        self.assertEqual(
            get_sthitopasthita("विभावसो", apply_sandhi=False), "विभावसो इति विभावसो"
        )
        self.assertEqual(get_upasthita("बाहू", apply_sandhi=False), "बाहू इति")
        # Sanity check: WITHOUT the bypass, this engine's ordinary sandhi
        # rules do NOT know about pragrhya and would wrongly apply the
        # eco'yavAyAvaH diphthong-substitution rule to word-final "o" --
        # confirming apply_sandhi=False is doing real work here, not a
        # no-op.
        self.assertNotEqual(
            get_sthitopasthita("विभावसो", apply_sandhi=True), "विभावसो इति विभावसो"
        )


class Bahumadhyagata(unittest.TestCase):
    """sutra 10.8's own worked examples: "narA ca zaMsam" (-> "cEti ca"),
    "zunaH cit zepam" (-> "ciditi cit"), "narA vA zaMsam" (-> "vEti vA") --
    a small, closed, source-cited particle class (ca/vA/cit), NOT a general
    parser for arbitrary multi-word compound-phrase membership. See
    detect_bahumadhyagata()'s own docstring for the "mo Su NaH" sub-case
    this does NOT cover."""

    def test_detects_middle_particle_with_neighbours_on_both_sides(self):
        self.assertEqual(detect_bahumadhyagata(["नरा", "च", "शंसम्"]), {1})
        self.assertEqual(detect_bahumadhyagata(["शुनः", "चित्", "शेपम्"]), {1})
        self.assertEqual(detect_bahumadhyagata(["नरा", "वा", "शंसम्"]), {1})

    def test_does_not_fire_at_either_end_of_the_word_list(self):
        # "in the middle of many words" requires a neighbour on both
        # sides -- a particle at position 0 or the last position has no
        # "middle" to occupy under this sutra.
        self.assertEqual(detect_bahumadhyagata(["च", "शंसम्"]), set())
        self.assertEqual(detect_bahumadhyagata(["शंसम्", "च"]), set())

    def test_does_not_fire_for_ordinary_words(self):
        self.assertEqual(detect_bahumadhyagata(["अग्निम्", "ईळे", "यज्ञस्य"]), set())

    def test_generate_ardharca_auto_detects_without_a_manual_flag(self):
        # Regression test for Test G in validate_krama_rv1_1.py: previously
        # requires_parigraha() only accepted a caller-supplied
        # is_bahumadhyagata bool with no derivation function at all.
        units = generate_ardharca(["नरा", "च", "शंसम्", "दैव्यम्"])
        parigraha_units = [u for u in units if u["type"] == "parigraha"]
        ca_unit = next(u for u in parigraha_units if u["for_word"] == "च")
        self.assertEqual(ca_unit["text"], "चेति च")
        self.assertIn("10.8", ca_unit["rule"])

    def test_explicit_empty_override_suppresses_auto_detection(self):
        units = generate_ardharca(["नरा", "च", "शंसम्", "दैव्यम्"], bahumadhyagata_positions=set())
        for_words = [u.get("for_word") for u in units if u["type"] == "parigraha"]
        self.assertNotIn("च", for_words)


class GenerateArdharca(unittest.TestCase):
    def test_ordinary_ardharca_has_n_minus_1_pairs_plus_final_parigraha(self):
        units = generate_ardharca(["अग्निम्", "ईळे", "यज्ञस्य"])
        self.assertEqual(units[0]["type"], "pair")
        self.assertEqual(units[1]["type"], "pair")
        self.assertEqual(units[-1]["type"], "parigraha")
        self.assertIn("10.9", units[-1]["rule"])

    def test_compound_word_gets_parigraha_immediately_after_its_pair(self):
        # यज्ञस्य is also this ardharca's last word, so it independently
        # triggers 10.9's own Parigraha at the end -- both a compound and an
        # ardharca-final Parigraha unit are expected here.
        units = generate_ardharca(["देवम्", "पुरःऽहितम्", "यज्ञस्य"])
        types = [u["type"] for u in units]
        self.assertEqual(types, ["pair", "parigraha", "pair", "parigraha"])
        self.assertEqual(units[1]["for_word"], "पुरःऽहितम्")
        self.assertIn("10.7", units[1]["rule"])
        self.assertIn("10.9", units[3]["rule"])

    def test_sutra_10_3_monosyllable_exception_reproduces_uvata_example(self):
        units = generate_ardharca(["आ", "मन्द्रम्", "वरेण्यम्"])
        texts = [u["text"] for u in units]
        self.assertEqual(texts[0], "आ मन्द्रम्")
        self.assertEqual(texts[1], "मन्द्रमा वरेण्यम्")
        self.assertEqual(texts[2], "आ वरेण्यम्")
        self.assertEqual(units[1]["type"], "monosyllable_retake_tri_unit")
        self.assertEqual(units[2]["type"], "monosyllable_confirm_pair")

    def test_sutra_10_3_branch_still_applies_ardharca_final_parigraha(self):
        # Regression test for a real bug found and fixed in this session: the
        # 10.3 special-case branch originally `continue`d without checking
        # 10.9, silently dropping Parigraha whenever an ardharca's last word
        # was preceded by the monosyllable aa.
        units = generate_ardharca(["आ", "मन्द्रम्", "वरेण्यम्"])
        self.assertEqual(units[-1]["type"], "parigraha")
        self.assertIn("10.9", units[-1]["rule"])
        self.assertEqual(units[-1]["text"], "वरेण्यमिति वरेण्यम्")


class GenerateVerse(unittest.TestCase):
    def test_no_sandhi_crosses_ardharca_boundary(self):
        ardharca1 = ["देवम्", "ऋत्विजम्"]
        ardharca2 = ["होतारम्", "रत्नऽधातमम्"]
        units_per_ardharca = generate_verse([ardharca1, ardharca2])
        self.assertEqual(len(units_per_ardharca), 2)
        # ऋत्विजम् (ardharca1's last word) never appears joined with होतारम्
        # (ardharca2's first word) in any unit's text.
        for unit in units_per_ardharca[0] + units_per_ardharca[1]:
            self.assertNotIn("ऋत्विजंहोतारम्", unit["text"])


class SplitIntoArdharcas(unittest.TestCase):
    def test_manual_override_used_when_present(self):
        ardharcas, method = split_into_ardharcas(
            "1.1.7", ["उप", "त्वा", "अग्ने", "दिवेऽदिवे", "दोषाऽवस्तः", "धिया", "वयम्", "नमः", "भरन्तः", "आ", "इमसि"],
            "उपत्वाग्ने दिवेदिवे दोषावस्तर्धिया वयम् । नमो भरन्त एमसि ॥",
        )
        self.assertEqual(method, "manual_override")
        self.assertEqual(len(ardharcas[0]), 7)
        self.assertEqual(len(ardharcas[1]), 4)

    def test_automatic_alignment_used_without_override(self):
        ardharcas, method = split_into_ardharcas(
            "1.1.1",
            ["अग्निम्", "ईळे", "पुरःऽहितम्", "यज्ञस्य", "देवम्", "ऋत्विजम्", "होतारम्", "रत्नऽधातमम्"],
            "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम् । होतारं रत्नधातमम् ॥",
        )
        self.assertEqual(method, "automatic_length_alignment")
        self.assertEqual(sum(len(a) for a in ardharcas), 8)


class ReconstructChain(unittest.TestCase):
    """reconstruct_chain() is the VALIDATE-mode helper (used by
    regenerate_krama_rv_1_1.py's attest_ardharcas(), not by the Krama
    generator itself) that folds samhita_join across a whole word sequence
    to simulate how continuous samhita_patha text is actually built."""

    def test_reproduces_rv_1_1_1_ardharca_1_exactly(self):
        computed, _rules = reconstruct_chain(
            ["अग्निम्", "ईळे", "पुरःऽहितम्", "यज्ञस्य", "देवम्", "ऋत्विजम्"]
        )
        self.assertEqual(computed, "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम्")

    def test_does_not_misread_its_own_elision_avagraha_as_a_compound(self):
        # Regression test for the same bug as
        # SamhitaJoin.test_resolve_w1_compound_false_does_not_misread_a_chain_avagraha,
        # exercised through the actual chain-building function rather than
        # a single hand-constructed call.
        computed, _rules = reconstruct_chain(
            ["सः", "नः", "पिताऽइव", "सूनवे", "अग्ने", "सुऽउपायनः", "भव"]
        )
        self.assertEqual(computed, "स नः पितेव सूनवेऽग्ने सूपायनो भव")

    def test_empty_input(self):
        self.assertEqual(reconstruct_chain([]), ("", []))

    def test_reproduces_rv_1_1_2_ardharca_1_exactly(self):
        # Regression test for the r/f ZWNJ fix, through the real function
        # (reconstruct_chain() strips the marker at its own return, so the
        # caller never needs to know it was involved).
        computed, _rules = reconstruct_chain(
            ["अग्निः", "पूर्वेभिः", "ऋषिऽभिः", "ईड्यः", "नूतनैः", "उत"]
        )
        self.assertEqual(computed, "अग्निः पूर्वेभिर्ऋषिभिरीड्यो नूतनैरुत")


class SLP1BareConsonantVowelCollision(unittest.TestCase):
    """A second external review round (11 Sep 2026) correctly rejected a
    prior claim that the r/f (vocalic-r) collision is "a unique artifact"
    -- it is NOT: EVERY vowel collides the same way at the pure SLP1
    transliteration level (a bare consonant + independent vowel letter is
    indistinguishable from that consonant + a dependent vowel-matra, for
    every vowel, not just f/F). That correction is verified below.

    But a transliteration-level collision existing is not automatically an
    ENGINE bug: samhita_join only special-cases f/F in
    _finish_consonant_then_vowel(), and the question that actually matters
    is whether letting every OTHER vowel fall through to the ordinary
    (dependent-matra) rendering ever produces a WRONG result. Checked
    against every real attested example available in this project's own
    data for the visarga-derived-consonant-before-vowel environment (not
    invented cases): DGE's own attested RV 1.1.2 Samhita-patha shows
    "र्+ई" -> "री" (dependent matra) and "र्+उ" -> "रु" (dependent matra)
    -- both confirmed correct by character-by-character inspection of the
    real Unicode codepoints, not assumed. "र्+ऋ" is the only one of the
    three actually-attested cases needing the independent-letter form.
    This is real (if limited) evidence the current scope is correct, not
    merely untested luck -- but it is NOT proof for every vowel/context
    this engine hasn't yet exercised, and should be revisited if/when
    scaling finds a counterexample."""

    def test_collision_exists_for_every_vowel_class_not_only_vocalic_r(self):
        # Pure transliteration-level fact, independent of this engine's
        # own behaviour: a bare consonant immediately followed by an
        # INDEPENDENT vowel letter is indistinguishable, in SLP1, from
        # that same consonant with a DEPENDENT vowel-matra, for every
        # vowel class -- not a property unique to f/F.
        pairs = [
            ("क्अ", "क"), ("क्इ", "कि"), ("क्ई", "की"), ("क्उ", "कु"),
            ("क्ऊ", "कू"), ("क्ए", "के"), ("क्ऐ", "कै"), ("क्ओ", "को"),
            ("क्औ", "कौ"), ("क्ऋ", "कृ"), ("क्ॠ", "कॄ"),
        ]
        for independent_form, dependent_form in pairs:
            with self.subTest(independent=independent_form, dependent=dependent_form):
                self.assertNotEqual(independent_form, dependent_form)
                self.assertEqual(
                    deva_to_slp1(independent_form), deva_to_slp1(dependent_form),
                    f"expected a collision between {independent_form!r} and {dependent_form!r}",
                )

    def test_other_vowel_classes_default_to_the_attested_dependent_matra_form(self):
        # Engine-reachability check: does the "not f/F" default path in
        # _finish_consonant_then_vowel() actually match DGE's own attested
        # text for the other vowel classes it's exercised against? These
        # are the two real (not synthetic) cases available -- see class
        # docstring for the exact codepoint verification.
        diphthong_visarga_before_u = samhita_join("नूतनैः", "उत")
        self.assertEqual(diphthong_visarga_before_u["surface"], "नूतनैरुत")  # attested RV 1.1.2

        iu_class_visarga_before_i = samhita_join("अग्निः", "इन्द्रः")
        self.assertEqual(iu_class_visarga_before_i["surface"], "अग्निरिन्द्रः")  # standard textbook form


if __name__ == "__main__":
    unittest.main()
