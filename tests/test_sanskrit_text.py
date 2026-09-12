"""tools/sanskrit_text.py — the one normalisation every detector shares.

Two things are being pinned. First that parasavarṇa applies the RIGHT nasal:
a blanket ं → म् is correct for one varga in five and wrong for the rest, and
that mistake is invisible until a lookup quietly stops matching. Second that
the offset map survives normalisation, because a reference found in the
canonical form has to be highlightable in the characters the reader can
actually see.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import sanskrit_text as st  # noqa: E402


class Parasavarna(unittest.TestCase):
    """8.4.58 अनुस्वारस्य ययि परसवर्णः — which nasal an anusvāra stands for
    depends on the consonant after it."""

    def test_each_varga_gets_its_own_nasal(self):
        for src, want in (("अंक", "अङ्क"), ("अंच", "अञ्च"), ("अंट", "अण्ट"),
                          ("अंत", "अन्त"), ("अंप", "अम्प"), ("अंब", "अम्ब")):
            self.assertEqual(st.parasavarna(src), want, src)

    def test_it_is_not_a_blanket_substitution(self):
        # The failure this exists to prevent: ं → म् everywhere is right for
        # प-varga alone and wrong for the other four.
        self.assertNotEqual(st.parasavarna("अंक"), "अम्क")
        self.assertNotEqual(st.parasavarna("अंत"), "अम्त")

    def test_every_letter_of_a_varga_maps_to_the_same_nasal(self):
        for letter in "कखगघङ":
            self.assertEqual(st.parasavarna("अं" + letter), "अङ्" + letter)
        for letter in "तथदधन":
            self.assertEqual(st.parasavarna("अं" + letter), "अन्" + letter)

    def test_an_anusvara_before_a_sibilant_is_left_alone(self):
        # The rule covers stops. Before श ष स ह the anusvāra stays written.
        for word in ("संशय", "संस्कार", "संहार", "वंश"):
            self.assertEqual(st.parasavarna(word), word, word)

    def test_a_word_final_anusvara_is_restored_as_m(self):
        # प्रसूनं IS प्रसूनम्; leaving it as an anusvāra is why the lexicon
        # did not recognise the word and the splitter offered प्र + सूनं.
        self.assertEqual(st.parasavarna("प्रसूनं"), "प्रसूनम्")
        self.assertEqual(st.parasavarna("वाक्यं"), "वाक्यम्")

    def test_text_with_no_anusvara_is_returned_untouched(self):
        self.assertEqual(st.parasavarna("कान्ताय"), "कान्ताय")


class Normalize(unittest.TestCase):
    def test_dandas_punctuation_and_quotes_are_dropped(self):
        self.assertEqual(st.normalize("।। कान्तायेति ।।"), "कान्तायेति")
        self.assertEqual(st.normalize("‘नमस्करोमि,’"), "नमस्करोमि")

    def test_avagraha_is_dropped_from_the_canonical_form(self):
        self.assertEqual(st.normalize("सोऽपि"), "सोपि")

    def test_vedic_accents_are_dropped(self):
        self.assertEqual(st.normalize("ग॒मॢँ"), st.normalize("गमॢँ"))

    def test_normalization_is_idempotent(self):
        once = st.normalize("।। अंब ।।")
        self.assertEqual(st.normalize(once), once)


class OffsetMap(unittest.TestCase):
    """A reference found in the canonical string has to land on the right
    characters of the source. Normalisation moves those offsets."""

    def test_every_normalized_character_points_back_at_a_source_character(self):
        src = "।। कान्तायेति ।।"
        norm, offsets = st.normalize_with_map(src)
        self.assertEqual(len(norm), len(offsets))
        for i, ch in enumerate(norm):
            self.assertEqual(src[offsets[i]], ch)

    def test_a_character_parasavarna_invents_still_points_somewhere_real(self):
        # ं becomes TWO characters (म and ्) and both point back at the one
        # ं they replaced, so a span over them maps to a real source range.
        norm, offsets = st.normalize_with_map("अंब")
        self.assertEqual(norm, "अम्ब")
        self.assertEqual(offsets, [0, 1, 1, 2])

    def test_dropped_characters_leave_no_hole_in_the_map(self):
        norm, offsets = st.normalize_with_map("क । ख")
        self.assertEqual(norm, "कख")
        self.assertEqual([("क । ख")[o] for o in offsets], ["क", "ख"])


class Protected(unittest.TestCase):
    """The Gold-Standard contract's fossilised clitics. They are the marks OF
    a citation, never the thing cited."""

    def test_the_contracts_denylist_is_recognised(self):
        for expr in ("इत्यर्थः", "इत्यादि", "इत्यादिना", "इत्यतः", "इत्युक्ते",
                     "तथाहि", "यद्वा", "किञ्च"):
            self.assertTrue(st.protected_spans(expr), expr)

    def test_a_fused_clitic_is_recognised_too(self):
        # मुख्याश्रयाय + इत्यर्थः is written मुख्याश्रयायेत्यर्थः. A matcher
        # looking only for the unfused spelling finds almost none of them,
        # because that is how commentaries actually write.
        spans = st.protected_spans("मुख्याश्रयायेत्यर्थः")
        self.assertEqual(len(spans), 1)
        self.assertTrue(st.is_protected("मुख्याश्रयायेत्यर्थः", 12, 20))

    def test_an_avagraha_elision_is_recognised(self):
        # The lead's own example: अरुर्द्विषदि'त्यादिना.
        self.assertTrue(st.protected_spans("अरुर्द्विषदि'त्यादिना"))

    def test_an_unrelated_word_is_not_protected(self):
        self.assertEqual(st.protected_spans("कान्ताय"), [])
        self.assertFalse(st.is_protected("कान्ताय", 0, 7))


if __name__ == "__main__":
    unittest.main()
