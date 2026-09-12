"""tools/reference_detect.py — a link is made because a commentator is CITING
something, never because a word exists in a database.

The false-positive tests here matter more than the positive ones. The system
this replaces linked on presence, and presence proves nothing: तन्त्राणि is an
ordinary noun that also sits in the dhātu data, भावः likewise. A wrong
scholarly link misleads a reader in a way a missing one never does, so every
case below that expects (none) is guarding a real regression, most of them
found by running the detectors over 1.4 million characters of real commentary
and reading what came back.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import reference_detect as rd  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), "..")
DHATUPATHA = os.path.join(REPO, "dge/data/vedanga/vyakarana/dhatupatha/data.json")
SUTRAPATHA = os.path.join(REPO, "dge/data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json")
REGISTRY = os.path.join(REPO, "dge/data/kosha/_citation_registry.json")


def _load(path, key="items"):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)[key]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(DHATUPATHA) and os.path.exists(SUTRAPATHA)):
            raise unittest.SkipTest("authoritative lists not present")
        cls.dhatu = rd.DhatuDetector(_load(DHATUPATHA))
        cls.sutra = rd.SutraDetector(_load(SUTRAPATHA))
        cls.kosha = rd.KoshaDetector(_load(REGISTRY, "names"))

    def refs(self, text):
        return rd.detect_all(text, self.dhatu, self.kosha, self.sutra)

    def kinds(self, text):
        return {r["type"] for r in self.refs(text)}

    def only(self, text):
        got = self.refs(text)
        self.assertEqual(len(got), 1, [(r["type"], r["surface"]) for r in got])
        return got[0]


class NoLinkWithoutContext(Base):
    """The class of error this whole rework exists to remove."""

    def test_an_ordinary_noun_that_is_also_in_the_dhatu_data(self):
        # तन्त्राणि and भावः are the project lead's own examples.
        for text in ("तन्त्राणि", "तन्त्राणि विविधानि सन्ति",
                     "भावः", "अयं भावः स्पष्टः"):
            self.assertEqual(self.refs(text), [], text)

    def test_a_root_inside_a_longer_word_is_not_a_root(self):
        # ज्वल is a root; ज्वलन्ति is a verb form that contains it.
        self.assertEqual(self.refs("गुणा ज्वलन्ति"), [])

    def test_iti_alone_is_not_a_citation(self):
        # Ordinary sentences close with इति constantly.
        self.assertEqual(self.refs("मम प्रयोजनम् इति भावः"), [])

    def test_a_lexicons_name_used_as_an_ordinary_word(self):
        # अमर means "deathless"; धनञ्जय is a name people have.
        self.assertEqual(self.refs("अमरो देवः"), [])

    def test_a_citation_frame_belonging_to_the_previous_sentence(self):
        # "…इत्यर्थः । विश्वं सकलम्" — the इत्यर्थः closed the sentence
        # before, and विश्व here is the ordinary word. Found in real
        # commentary; the danda is what gives it away.
        self.assertEqual(self.refs("गच्छति सति इत्यर्थः । विश्वं सकलं कार्यजातम्"), [])

    def test_a_two_letter_root_is_not_linked_on_terminology_alone(self):
        # तु is a root AND the commonest particle in the language. It turned
        # up inside an Amarakośa quotation on the strength of a nearby क्रिया.
        got = self.refs("तैः ‘भूषा तु स्यादलङ्क्रियां’ इत्यमरः आर्यैः")
        self.assertNotIn("dhatu", {r["type"] for r in got})

    def test_a_sutra_that_is_only_a_word_inside_someone_elses_quotation(self):
        # 4.1.3 स्त्रियाम् happens to be the first word of an Amarakośa line.
        # The quotation marks are real; they are not Pāṇini's.
        got = self.refs("तनुः मूर्तिः । ‘स्त्रियां मूर्तिस्तनुस्तनूः’ इत्यमरः ।")
        self.assertNotIn("sutra", {r["type"] for r in got})


class DhatuCitation(Base):
    """A root is cited when its own traditional artha stands beside it."""

    def test_root_with_its_artha_and_iti(self):
        # The lead's example. दीप्तौ is what the dhātupāṭha records for ज्वल,
        # and sandhi has fused इति onto it.
        ref = self.only("ज्वल दीप्ताविति")
        self.assertEqual(ref["type"], "dhatu")
        self.assertEqual(ref["surface"], "ज्वल")
        self.assertEqual(ref["confidence"], "high")

    def test_root_with_artha_and_grammatical_context(self):
        ref = self.only("जि जये लिट्")
        self.assertEqual(ref["ref_id"], "01.0642")
        self.assertEqual(ref["confidence"], "high")

    def test_root_with_artha_alone(self):
        for text, root in (("दिश अतिसर्जने", "दिश"), ("भू सत्तायाम्", "भू")):
            ref = self.only(text)
            self.assertEqual(ref["surface"], root)
            self.assertEqual(ref["confidence"], "high")

    def test_the_traditional_citation_format_from_real_commentary(self):
        for text, root in (
                ("अग्रहीत् स्वीचकार । ‘ग्रह उपादाने इत्यतो लुङ्", "ग्रह"),
                ("सस्नुः स्नातवन्तः ‘ष्णा शौचे’ इत्यतो लिट्", "ष्णा"),
                ("अन्वशेत । शीङ् स्वप्ने लङ् ।।", "शीङ्")):
            got = [r for r in self.refs(text) if r["type"] == "dhatu"]
            self.assertTrue(got, text)
            self.assertEqual(got[0]["surface"], root)

    def test_every_link_is_validated_against_the_dhatupatha(self):
        ids = {i["id"] for i in _load(DHATUPATHA)}
        for r in self.refs("‘दिश अतिसर्जने’ इति धातोः लोट्"):
            if r["type"] == "dhatu":
                self.assertIn(r["ref_id"], ids)


class KoshaCitation(Base):
    def test_a_lexicon_named_in_a_citation_frame(self):
        for text in ("इति अमरः", "इत्यामरः", "इति अमरकोशः", "अमरकोशे उक्तम्"):
            got = [r for r in self.refs(text) if r["type"] == "kosha"]
            self.assertTrue(got, text)
            self.assertEqual(got[0]["ref_id"], "amarakosha")

    def test_a_name_carrying_its_own_frame_needs_nothing_else(self):
        self.assertEqual(self.only("इत्यामरः")["confidence"], "high")

    def test_the_registry_is_data_not_code(self):
        with open(REGISTRY, encoding="utf-8") as fh:
            reg = json.load(fh)
        self.assertIn("names", reg)
        self.assertGreater(len(reg["names"]), 20)
        self.assertGreater(len(set(reg["names"].values())), 5)


class SutraCitation(Base):
    def test_a_whole_sutra_quoted_verbatim(self):
        ref = self.only("अतिशायने तमबिष्ठनौ")
        self.assertEqual(ref["type"], "sutra")
        self.assertEqual(ref["ref_id"], "5.3.55")

    def test_a_quotation_that_omits_the_middle_of_the_sutra(self):
        # 3.1.22 is धातोरेकाचो हलादेः क्रियासमभिहारे यङ्; the commentary
        # quotes across the omission. Prefix matching cannot reach this, which
        # is why fragments are indexed rather than openings.
        got = [r for r in self.refs("धातोरेकाचः क्रियासमभिहारे यङ्") if r["type"] == "sutra"]
        self.assertTrue(got)
        self.assertEqual(got[0]["ref_id"], "3.1.22")

    def test_real_citations_from_the_corpus(self):
        for text, sid in (
                ("ते अग्न्याहिताः ‘वाहिताग्न्यादिषु’ इति सूत्रात्", "2.2.37"),
                ("समीपे । ‘उपर्यध्यधसः सामीप्ये’ इति सूत्रेण", "8.1.7"),
                ("न ‘कर्तृकर्मणोः कृति’ इति षष्ठी", "2.3.65")):
            got = [r for r in self.refs(text) if r["type"] == "sutra"]
            self.assertTrue(got, text)
            self.assertEqual(got[0]["ref_id"], sid, text)

    def test_an_ambiguous_fragment_identifies_nothing(self):
        # संज्ञायाम् opens three sutras and IS 2.1.43 entire. A fragment that
        # could mean several things is not in the index at all.
        from sanskrit_text import fold
        self.assertNotIn(fold("संज्ञायाम्"), self.sutra.fragments)

    def test_every_link_is_validated_against_the_sutrapatha(self):
        ids = {i["id"] for i in _load(SUTRAPATHA)}
        for r in self.refs("‘वाहिताग्न्यादिषु’ इति सूत्रात्"):
            if r["type"] == "sutra":
                self.assertIn(r["ref_id"], ids)


class Overlap(Base):
    def test_a_citation_is_one_reference_not_three(self):
        # ज्वल दीप्ताविति is a dhātu citation. Its own words must not also be
        # linked separately.
        got = self.refs("ज्वल दीप्ताविति")
        self.assertEqual(len(got), 1)

    def test_the_higher_priority_reference_wins_a_contested_span(self):
        refs = [
            {"type": "dhatu", "start": 0, "end": 4, "surface": "x"},
            {"type": "sutra", "start": 0, "end": 4, "surface": "x"},
        ]
        kept = rd.resolve_overlaps(refs)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["type"], "sutra")

    def test_a_longer_span_wins_over_a_shorter_one_inside_it(self):
        refs = [
            {"type": "sutra", "start": 0, "end": 20, "surface": "long"},
            {"type": "dhatu", "start": 5, "end": 8, "surface": "in"},
        ]
        kept = rd.resolve_overlaps(refs)
        self.assertEqual([k["surface"] for k in kept], ["long"])

    def test_disjoint_references_all_survive(self):
        refs = [
            {"type": "dhatu", "start": 0, "end": 4, "surface": "a"},
            {"type": "kosha", "start": 10, "end": 14, "surface": "b"},
        ]
        self.assertEqual(len(rd.resolve_overlaps(refs)), 2)


class Metadata(Base):
    def test_every_reference_carries_what_the_renderer_needs(self):
        for r in self.refs("‘दिश अतिसर्जने’ इति धातोः लोट् ‘वाहिताग्न्यादिषु’ इति सूत्रात्"):
            for field in ("type", "start", "end", "surface", "ref_id",
                          "confidence", "reason"):
                self.assertIn(field, r)
            self.assertIn(r["confidence"], ("high", "medium"))

    def test_the_span_lands_on_the_original_characters(self):
        text = "अग्रहीत् । ‘ग्रह उपादाने इत्यतो लुङ्"
        for r in self.refs(text):
            self.assertEqual(text[r["start"]:r["end"]], r["surface"])

    def test_a_reason_is_recorded_for_every_link(self):
        # Item 17 of the directive: it must be possible to see WHY.
        for r in self.refs("ज्वल दीप्ताविति"):
            self.assertTrue(r["reason"])


if __name__ == "__main__":
    unittest.main()
