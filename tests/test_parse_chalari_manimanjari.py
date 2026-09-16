"""parse_chalari_manimanjari.py: the edition's rhythm, and the three ways it
does not hold.

The Manimanjari does not alternate verse/commentary one for one, and two
things in it look exactly like a verse without being one. Each of those cost
a wrong parse before it was understood, so each has a test here.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import parse_chalari_manimanjari as chalari  # noqa: E402

VERSE_1 = ["वन्दे गोविन्दम् आनन्द-ज्ञान-देहं पतिं श्रियः ।",
           "श्रीमद्-आनन्दतीर्थार्य-वल्लभं परम् अक्षरम् ॥१॥"]
VERSE_2 = ["ससर्ज भगवान् आदौ त्रीन् गुणान् प्रकृतेः परः ।",
           "महत्-तत्त्वं ततो विष्णुः सृष्टवान् ब्रह्मणस्तनुम् ॥२॥"]
VERSE_3 = ["महत्-तत्त्वाद् अहङ्कारं ससर्ज शिव-विग्रहं ।",
           "दैवान् देहान् मनः-खानि खं च स त्रि-विधात् ततः ॥३॥"]
COLOPHON = "इति श्री-मणिमञ्जर्यां प्रथमः सर्गः ॥ १ ॥"


class TheOrdinaryRhythm(unittest.TestCase):
    def test_verse_then_its_commentary(self):
        got = chalari.parse(VERSE_1 + ['"वन्दे गोविन्द" इति । अयम् अर्थः ॥ १ ॥'] + VERSE_2
                            + ['"ससर्ज" इति । भगवान् वासुदेवः ॥ २ ॥'])
        self.assertEqual([(u["sarga"], u["verse"]) for u in got], [(1, 1), (1, 2)])
        self.assertIn("वन्दे गोविन्द", got[0]["commentary"])
        self.assertIn("ससर्ज", got[1]["commentary"])
        self.assertIn("वन्दे गोविन्दम्", got[0]["mula"])


class ThingsThatLookLikeAVerse(unittest.TestCase):
    def test_a_commentarys_closing_words_are_not_a_verse(self):
        # "इत्यमरः । इत्युभयत्र ज्ञेयं ॥ ३ ॥" is 33 characters and closes with
        # a verse number. What it lacks is a verse line in front of it.
        paras = VERSE_3 + ['"महत्-तत्त्व" इति । शिव-शरीरं तमः-प्रधानम् ।',
                           "> नभो ऽन्तरिक्षं गगनम् अनन्तं सुर-वर्त्म खम्",
                           "इत्यमरः । इत्युभयत्र ज्ञेयं ॥ ३ ॥"]
        got = chalari.parse(paras)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["verse"], 3)
        self.assertIn("इत्यमरः", got[0]["commentary"])

    def test_a_quoted_verse_does_not_open_one(self):
        self.assertFalse(chalari.is_verse_open("> यत्रानवसरो ऽन्यत्र पदं तत्र प्रतिष्ठितम् ।"))

    def test_a_gloss_opener_does_not_open_one(self):
        self.assertFalse(chalari.is_verse_open('"वन्दे गोविन्द" इति ।'))

    def test_a_paragraph_of_prose_does_not_open_one(self):
        self.assertFalse(chalari.is_verse_open("क" * 400))


class RunsOfVerses(unittest.TestCase):
    """The edition prints three verses and then glosses all three."""

    def test_each_verse_in_a_run_gets_its_own_gloss(self):
        paras = (VERSE_1 + VERSE_2 + VERSE_3
                 + ['"वन्दे गोविन्द" इति । प्रथमः ॥ १ ॥',
                    '"ससर्ज" इति । द्वितीयः ॥ २ ॥',
                    '"महत्-तत्त्व" इति । तृतीयः ॥ ३ ॥'])
        got = chalari.parse(paras)
        self.assertEqual([u["verse"] for u in got], [1, 2, 3])
        self.assertIn("प्रथमः", got[0]["commentary"])
        self.assertIn("द्वितीयः", got[1]["commentary"])
        self.assertIn("तृतीयः", got[2]["commentary"])

    def test_three_glosses_packed_into_one_paragraph_still_separate(self):
        paras = (VERSE_1 + VERSE_2 + VERSE_3
                 + ['"वन्दे गोविन्द" इति । प्रथमः ॥ १ ॥ "ससर्ज" इति । द्वितीयः ॥ २ ॥ '
                    '"महत्-तत्त्व" इति । तृतीयः ॥ ३ ॥'])
        got = chalari.parse(paras)
        self.assertIn("प्रथमः", got[0]["commentary"])
        self.assertIn("द्वितीयः", got[1]["commentary"])
        self.assertNotIn("द्वितीयः", got[0]["commentary"])
        self.assertIn("तृतीयः", got[2]["commentary"])


class SargaBoundary(unittest.TestCase):
    def test_the_colophon_turns_the_sarga(self):
        paras = (VERSE_1 + ['"वन्दे गोविन्द" इति । अयम् ॥ १ ॥', COLOPHON]
                 + VERSE_2 + ['"ससर्ज" इति । भगवान् ॥ २ ॥'])
        got = chalari.parse(paras)
        self.assertEqual([(u["sarga"], u["verse"]) for u in got], [(1, 1), (2, 2)])

    def test_the_colophon_is_not_read_as_a_verse(self):
        self.assertFalse(chalari.is_verse_open(COLOPHON))


class Numerals(unittest.TestCase):
    def test_devanagari_and_ascii_digits_both_read(self):
        self.assertEqual(chalari.to_int("१२"), 12)
        self.assertEqual(chalari.to_int("12"), 12)

    def test_the_text_is_never_edited(self):
        paras = VERSE_1 + ['"वन्दे गोविन्द" इति । अयम् अर्थः ॥ १ ॥']
        got = chalari.parse(paras)
        self.assertEqual(got[0]["mula"], "\n".join(VERSE_1))
        self.assertIn('"वन्दे गोविन्द" इति ।', got[0]["commentary"])


if __name__ == "__main__":
    unittest.main()
