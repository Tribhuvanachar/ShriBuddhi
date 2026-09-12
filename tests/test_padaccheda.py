"""tools/padaccheda.py — undoing the sandhi that welded two words into one.

The examples are real joins from the corpus, and each one is here because it
exercises a different rule. The failure that matters is not a crash: it is a
confident wrong cut, so the gating tests are as load-bearing as the matching
ones.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import padaccheda as p  # noqa: E402

# A small closed vocabulary keeps these tests about the ALGORITHM. The real
# builder loads 374,961 words; here the words are named so a failure says
# which rule broke rather than which shard changed.
VOCAB = {
    "कान्ताय", "इति", "नारायणाय", "अखिलकारणाय", "रामस्य", "एव", "तत्", "तद्",
    "श्रुत्वा", "सः", "अपि", "मुहुः", "महान्तः", "जगत्", "प्रसिद्धा", "गृहे",
    "अभूत्", "सखी", "इव", "तथा", "तावत्", "आशु", "उक्तम्", "यत्", "प्रति",
    "उवाच", "विकटा", "इन", "अंश", "वो", "धर्मक्षेत्रे", "कुरुक्षेत्रे",
}
FREQ = {w: 50 for w in VOCAB}


def seg(freq=None):
    return p.Segmenter(VOCAB, freq if freq is not None else FREQ)


def pieces(result):
    return [w for w, _rule in result] if result else None


class Junctions(unittest.TestCase):
    def test_plain_abutment(self):
        # जगत् + प्रसिद्धा, nothing changed at the seam.
        self.assertEqual(pieces(seg().split("जगत्प्रसिद्धा")), ["जगत्", "प्रसिद्धा"])

    def test_savarnadirgha_absorbs_the_second_word_entirely(self):
        # नारायणाय + अखिलकारणाय → नारायणायाखिलकारणाय. The अ of the second word
        # is not in the written form at all; a substring search can never find
        # it, which is why the split has to UNDO the junction.
        self.assertEqual(pieces(seg().split("नारायणायाखिलकारणाय")),
                         ["नारायणाय", "अखिलकारणाय"])

    def test_guna_recovers_the_citation_form(self):
        # कान्ताय + इति → कान्तायेति (a + i → e), the commonest way a
        # commentary names the word it is about to explain.
        self.assertEqual(pieces(seg().split("कान्तायेति")), ["कान्ताय", "इति"])

    def test_vrddhi(self):
        # रामस्य + एव → रामस्यैव (a + e → ai).
        self.assertEqual(pieces(seg().split("रामस्यैव")), ["रामस्य", "एव"])

    def test_savarnadirgha_on_long_i(self):
        # सखी + इव → सखीव.
        self.assertEqual(pieces(seg().split("सखीव")), ["सखी", "इव"])

    def test_jashtva_where_the_virama_has_vanished(self):
        # तत् + इति → तदिति. Nothing in the writing marks this join: the
        # virāma is gone and the त is voiced to द. Without the rule the
        # commonest citation form in the grammatical literature has no
        # analysis at all.
        self.assertEqual(pieces(seg().split("तदिति"))[1], "इति")

    def test_the_devoiced_reading_wins_a_tie(self):
        # तत् and तद् are both real; तत् is what a padaccheda prints.
        self.assertEqual(pieces(seg().split("तदिति"))[0], "तत्")

    def test_shchutva_plus_chatva(self):
        # तत् + श्रुत्वा → तच्छ्रुत्वा.
        self.assertEqual(pieces(seg().split("तच्छ्रुत्वा")), ["तत्", "श्रुत्वा"])

    def test_visarga_before_a_voiced_sound(self):
        # मुहुः + महान्तः → मुहुर्महान्तः.
        self.assertEqual(pieces(seg().split("मुहुर्महान्तः")), ["मुहुः", "महान्तः"])

    def test_avagraha_is_a_boundary_not_punctuation(self):
        # गृहे + अभूत् → गृहेऽभूत्. The ऽ is the text telling us an अ was
        # elided exactly here — the one place the writing marks the join. The
        # word-mark normaliser strips it because it only needs a lookup key;
        # doing that here would throw away the evidence.
        self.assertEqual(pieces(seg().split("गृहेऽभूत्")), ["गृहे", "अभूत्"])

    def test_expand_avagraha_is_the_mechanism(self):
        self.assertEqual(p.expand_avagraha("सोऽपि"), "सोअपि")
        self.assertEqual(p.expand_avagraha("रामः"), "रामः")


class NoSplit(unittest.TestCase):
    """What it must NOT do. A wrong split shown confidently is worse than none."""

    def test_a_word_that_is_itself_in_the_lexicon_is_left_alone(self):
        # धर्मक्षेत्रे is one word; a one-piece path is always cheaper than
        # any two-piece path, so the cost model protects it without a rule.
        self.assertIsNone(seg().split("धर्मक्षेत्रे"))

    def test_a_token_with_no_analysis_returns_none_not_a_guess(self):
        self.assertIsNone(seg().split("क्ष्वेडितम्"))

    def test_non_devanagari_is_not_touched(self):
        self.assertIsNone(seg().split("Ramasya"))

    def test_an_overlong_token_is_declined_rather_than_searched(self):
        long_token = "क" * (p.Segmenter.MAX_LEN + 4)
        self.assertIsNone(seg().split(long_token))


class Confidence(unittest.TestCase):
    """The gate between "the search found something" and "show this to a reader"."""

    def test_a_case_ending_mistaken_for_a_word_is_refused(self):
        # विकटेन is one declined form. It parses as विकटा + इन — both in the
        # lexicon, and wrong. The short piece is what gives it away.
        s = seg()
        self.assertEqual(pieces(s.split("विकटेन")), ["विकटा", "इन"])
        self.assertIsNone(s.confident_split("विकटेन"))

    def test_a_genuinely_short_word_still_passes(self):
        # इव is two characters and correct in सखीव, so the short-piece rule
        # is a closed list of real particles rather than a length cutoff.
        self.assertIsNotNone(seg().confident_split("सखीव"))
        self.assertIn("इव", p.Segmenter.SHORT_WORDS)

    def test_a_piece_the_corpus_never_uses_is_refused(self):
        # Everything in the lexicon is a "real word"; only frequency
        # distinguishes one a reader will recognise.
        s = p.Segmenter(VOCAB, {"नारायणाय": 50, "अखिलकारणाय": 1})
        self.assertIsNotNone(s.split("नारायणायाखिलकारणाय"))
        self.assertIsNone(s.confident_split("नारायणायाखिलकारणाय"))

    def test_too_many_pieces_is_refused_however_cheap(self):
        self.assertLessEqual(p.Segmenter.CONFIDENT_MAX_PIECES, 3)

    def test_with_no_frequency_data_the_gate_does_not_block_everything(self):
        # A caller with no corpus (a unit test, a one-off word) should still
        # get answers rather than silence.
        self.assertIsNotNone(seg(freq={}).confident_split("कान्तायेति"))


class SamasaVigraha(unittest.TestCase):
    """Breaking a compound is not the same operation as undoing sandhi, and the
    mark between the pieces has to say which one happened."""

    VOCAB = VOCAB | {"पूर्व", "शैल", "शिखरे", "श्री", "प्राण", "नाथाय",
                     "कल्याण", "गुण", "गुणा", "धाम्ने", "मेखला", "कान्त",
                     "कान्ता", "अय", "सभा", "जि", "तानि",
                     "धर्म", "क्षेत्रे", "एक", "कल्याणगुणैकधाम्ने"}
    STEMS = {"पूर्व", "शैल", "धर्म", "श्री", "कल्याण", "गुण", "गुणा", "जगत्",
             "एक", "मेखला", "कान्त", "कान्ता", "सभा", "विकटा"}
    AVYAYA = {"इव"}
    INFLECTED = {"शिखरे", "क्षेत्रे", "नाथाय", "धाम्ने", "कान्ताय", "तानि",
                 "प्रसिद्धा", "महान्तः", "गृहे"}
    VERBS = {"अभूत्"}

    def seg(self):
        freq = {w: 50 for w in self.VOCAB | self.STEMS}
        return p.Segmenter(self.VOCAB, freq, self.STEMS, self.AVYAYA,
                           self.INFLECTED, self.VERBS)

    def rendered(self, token):
        got = self.seg().analyse(token)
        if not got:
            return None
        out = got["pieces"][0]
        for i, seam in enumerate(got["seams"]):
            out += seam + got["pieces"][i + 1]
        return out

    def test_a_compound_is_marked_with_hyphens(self):
        self.assertEqual(self.rendered("पूर्वशैलशिखरे"), "पूर्व-शैल-शिखरे")

    def test_a_compound_already_in_the_lexicon_is_still_broken_out(self):
        # धर्मक्षेत्रे is one word and the sandhi search rightly refuses to cut
        # it; the compound search has to override that, because the question
        # "what is this made of" is a different question.
        self.assertIsNone(self.seg().split("धर्मक्षेत्रे"))
        self.assertEqual(self.rendered("धर्मक्षेत्रे"), "धर्म-क्षेत्रे")

    def test_a_compound_carrying_sandhi_inside_it(self):
        # कल्याण + गुण + एक + धाम्ने is written कल्याणगुणैकधाम्ने, गुण + एक
        # fused to गुणै by वृद्धिः. A concatenation-only splitter misses every
        # long compound, since most of them do this.
        self.assertEqual(self.rendered("कल्याणगुणैकधाम्ने"), "कल्याण-गुण-एक-धाम्ने")

    def test_the_bare_stem_wins_over_the_commoner_word(self):
        # गुणा is also a word, and the corpus writes it MORE often than गुण.
        # A compound member is the bare stem; frequency is the wrong judge of
        # a question grammar has already settled.
        self.assertIn("गुण-एक", self.rendered("कल्याणगुणैकधाम्ने"))

    def test_sandhi_and_compound_in_one_token(self):
        # नारायणाय + अखिलकारणाय, whose second half is itself अखिल-कारणाय.
        seg = p.Segmenter(
            self.VOCAB | {"नारायणाय", "अखिल", "कारणाय", "अखिलकारणाय"},
            {w: 50 for w in ("नारायणाय", "अखिल", "कारणाय", "अखिलकारणाय")},
            self.STEMS | {"अखिल"}, self.AVYAYA,
            self.INFLECTED | {"नारायणाय", "कारणाय"}, self.VERBS)
        got = seg.analyse("नारायणायाखिलकारणाय")
        self.assertEqual(got["pieces"], ["नारायणाय", "अखिल", "कारणाय"])
        self.assertEqual(got["seams"], ["+", "-"])

    def test_an_indeclinable_on_either_side_is_a_word_boundary(self):
        # मेखला is a stem, so looking only leftward marks मेखलेव as मेखला-इव.
        # इव is a whole word and the join is sandhi.
        self.assertEqual(self.rendered("मेखलेव"), "मेखला+इव")

    def test_iti_is_a_word_boundary_though_the_morphology_calls_it_a_lemma(self):
        seg = p.Segmenter(self.VOCAB | {"कान्ताय", "इति"},
                          {"कान्ताय": 50, "इति": 900},
                          self.STEMS, self.AVYAYA, self.INFLECTED, self.VERBS)
        got = seg.analyse("कान्तायेति")
        self.assertEqual(got["seams"], ["+"])

    def test_plain_abutment_inside_one_token_is_a_compound_seam(self):
        # प्राण is used 2,664 times in the corpus and is in no subanta record
        # as a lemma, so the lemma lookup gets श्री-प्राण-नाथाय wrong at the
        # second seam. The rule that produced the seam does not.
        seg = p.Segmenter(self.VOCAB, {w: 50 for w in self.VOCAB},
                          self.STEMS, self.AVYAYA, self.INFLECTED, self.VERBS)
        got = seg.analyse("श्रीप्राणनाथाय")
        self.assertEqual(got["pieces"], ["श्री", "प्राण", "नाथाय"])
        self.assertEqual(got["seams"], ["-", "-"])

    def test_a_short_word_is_not_pulled_apart_into_two_lexicon_entries(self):
        # कान्ताय is a dative, not कान्ता + अय; नैच्छत् is one verb form.
        self.assertIsNone(self.seg().vigraha("कान्ताय"))

    def test_a_two_character_member_is_refused_but_the_numerals_are_not(self):
        # सभा-जि-तानि was the damage: जि is a real root, तानि a real form,
        # the whole thing nonsense. एक has to survive the same rule.
        self.assertIn("एक", p.Segmenter.VIGRAHA_SHORT_MEMBERS)
        self.assertGreaterEqual(p.Segmenter.VIGRAHA_MIN_MEMBER, 3)


class Rules(unittest.TestCase):
    def test_the_junction_table_keeps_both_readings_of_a_shared_form(self):
        # गुणः ओ = अ + उ and the visarga ओ = अः + अ are both true. A dict keyed
        # on the written form could only hold one, which is why this is a list.
        fused = [row[0] for row in p.JUNCTIONS]
        self.assertGreater(fused.count('ो'), 1)

    def test_every_junction_row_is_well_formed(self):
        for fuse, lefts, rights, rule, sutra in p.JUNCTIONS:
            self.assertIsInstance(fuse, str)
            self.assertTrue(lefts, rule)
            self.assertTrue(rule)

    def test_a_split_reports_which_rule_it_used(self):
        got = seg().split("कान्तायेति")
        self.assertTrue(all(rule for _w, rule in got))


if __name__ == "__main__":
    unittest.main()
