#!/usr/bin/env python3
"""Tests for archive_sayana.py — the alignment of the archive.org scan.

The fixture reproduces the edition's real layout, including its real defects:
OCR damage inside the mantra text, a sukta-end marker that is not a mantra, and
a mantra the scan drops entirely. Those are the cases that decide whether the
aligner is safe, and none of them can be exercised against a clean fixture.

    python tools/sayana_smriti/tests/test_archive_sayana.py
"""
import io
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import archive_sayana  # noqa: E402
from archive_sayana import (Block, align, fetch, looks_like_apparatus,  # noqa: E402
                            parse_blocks, similarity, skeleton, to_int)

# RV 1.1.1-1.1.3, laid out as the edition prints them. Mantra 2's samhita line
# carries deliberate OCR damage (अग्नि: -> अग्नि;, ऋषिभि -> रुषिभि) of the kind
# seen in the real scan; mantra 3 is missing from the scan altogether.
FIXTURE = """
अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम्‌ । होतारं रत्नधातमम्‌ ॥ १ ॥
अग्निम्‌ । ईळे । पुरःऽहितम्‌ । यज्ञस्य । देवम्‌ । ऋत्विजम्‌ ॥ १ ॥
अग्निमीळे इति । ईळे स्तौमि । पुरोहितं पुरतो हितम्‌ । अयमर्थः ॥
अग्नि; पूर्वेभि रुषिभिरीड्यो नूतनैरुत । स देवाँ एह वक्षति ॥ २ ॥
अग्निः । पूर्वेभिः । ऋषिऽभिः । ईड्यः । नूतनैः । उत ॥ २ ॥
अग्निः पूर्वेभिरिति । पूर्वेभिः पुरातनैः ऋषिभिः स्तुत्यः । एष द्वितीयस्य भाष्यम्‌ ॥
इति प्रथमं सूक्तम्‌ ॥ ९ ॥
"""

ITEMS = [
    {"id": "1.1.1",
     "samhita_patha_plain": "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम् । होतारं रत्नधातमम् ॥",
     "pada_patha_plain": "अग्निम् । ईळे । पुरःऽहितम् । यज्ञस्य । देवम् । ऋत्विजम् ॥"},
    {"id": "1.1.2",
     "samhita_patha_plain": "अग्निः पूर्वेभिरृषिभिरीड्यो नूतनैरुत । स देवाँ एह वक्षति ॥",
     "pada_patha_plain": "अग्निः । पूर्वेभिः । ऋषिऽभिः । ईड्यः । नूतनैः । उत ॥"},
    {"id": "1.1.3",
     "samhita_patha_plain": "अग्निना रयिमश्नवत्पोषमेव दिवेदिवे । यशसं वीरवत्तमम् ॥",
     "pada_patha_plain": "अग्निना । रयिम् । अश्नवत् । पोषम् । एव । दिवेऽदिवे ॥"},
]


class TestSkeleton(unittest.TestCase):
    def test_accents_and_punctuation_removed(self):
        self.assertEqual(skeleton("अ॒ग्नि॑म् ।"), skeleton("अग्निम्"))

    def test_la_variants_folded(self):
        # The scan prints both ळ and ल for the same sound; DGE uses ळ.
        self.assertEqual(skeleton("अग्निमीळे"), skeleton("अग्निमीले"))

    def test_latin_and_digits_dropped(self):
        self.assertEqual(skeleton("अग्नि 42 abc"), skeleton("अग्नि"))

    def test_empty(self):
        self.assertEqual(skeleton(""), "")
        self.assertEqual(skeleton(None or ""), "")


class TestNumbering(unittest.TestCase):
    def test_devanagari_digits(self):
        self.assertEqual(to_int("११"), 11)
        self.assertEqual(to_int("९"), 9)

    def test_ascii_digits(self):
        self.assertEqual(to_int("7"), 7)

    def test_garbage_is_none(self):
        self.assertIsNone(to_int("॥"))


class TestParseBlocks(unittest.TestCase):
    def setUp(self):
        self.blocks = parse_blocks(FIXTURE)

    def test_every_marker_becomes_a_block(self):
        # two per mantra for 1.1.1 and 1.1.2, plus the sukta-end marker
        self.assertEqual([b.num for b in self.blocks], [1, 1, 2, 2, 9])

    def test_block_text_is_what_precedes_its_marker(self):
        self.assertIn("अग्निमीळे", self.blocks[0].text)
        self.assertIn("ईळे", self.blocks[1].text)

    def test_sukta_end_marker_is_not_filtered_here(self):
        # Deliberate: the caller decides what a block is by matching it against
        # a mantra it holds, which beats guessing from the number alone.
        self.assertEqual(self.blocks[-1].num, 9)


class TestAlign(unittest.TestCase):
    def setUp(self):
        self.res = align(ITEMS, parse_blocks(FIXTURE), threshold=0.5)

    def test_clean_mantra_aligns(self):
        self.assertIn("1.1.1", self.res["aligned"])

    def test_bhashya_is_the_commentary_not_the_pada_patha(self):
        got = self.res["aligned"]["1.1.1"]["text"]
        self.assertIn("स्तौमि", got)
        self.assertNotIn("पुरःऽहितम्", got)

    def test_ocr_damaged_mantra_still_aligns(self):
        # 1.1.2's samhita line is damaged in the fixture; the pada-patha is the
        # second key that rescues it, which is the whole reason for having two.
        self.assertIn("1.1.2", self.res["aligned"])
        self.assertIn("द्वितीयस्य", self.res["aligned"]["1.1.2"]["text"])

    def test_missing_mantra_is_reported_not_guessed(self):
        self.assertNotIn("1.1.3", self.res["aligned"])
        self.assertIn("1.1.3", self.res["misses"])

    def test_a_miss_does_not_derail_what_follows(self):
        # 1.1.3 is absent from the scan. The cursor must not stall or run away.
        items = ITEMS + [dict(ITEMS[0], id="1.1.4")]
        res = align(items, parse_blocks(FIXTURE), threshold=0.5)
        self.assertIn("1.1.1", res["aligned"])
        self.assertIn("1.1.2", res["aligned"])

    def test_mantras_far_into_a_shared_volume_still_anchor(self):
        # One OCR file covers maṇḍalas 2-5 and another 6-8, so a maṇḍala's
        # mantras can start thousands of blocks in. Simulated here by prefixing
        # a long run of unrelated blocks: a window measured from position zero
        # would never reach the real text, and every maṇḍala but the volume's
        # first would come back empty.
        filler = "पूर्वं किमपि वाक्यम्‌ ॥ १ ॥\n" * 300
        res = align(ITEMS, parse_blocks(filler + FIXTURE), threshold=0.5)
        self.assertIn("1.1.1", res["aligned"])
        self.assertIn("1.1.2", res["aligned"])

    def test_scores_are_recorded_for_every_mantra(self):
        self.assertEqual(len(self.res["scores"]), len(ITEMS))

    def test_threshold_is_enforced(self):
        # Pitched just above the best score actually achieved, rather than at a
        # guessed constant: both fixture mantras score 1.0 (the damaged samhita
        # line is rescued by the pada-patha key), so a hard-coded 0.999 would
        # have tested nothing.
        ceiling = max(self.res["scores"]) + 0.001
        strict = align(ITEMS, parse_blocks(FIXTURE), threshold=ceiling)
        self.assertEqual(strict["aligned"], {})

    def test_second_key_is_what_rescues_a_damaged_mantra(self):
        # Drop the pada-patha and 1.1.2 must degrade, since its samhita line is
        # the damaged one. This is the evidence that two keys are earning their
        # place rather than being redundant.
        one_key = [{k: v for k, v in it.items() if k != "pada_patha_plain"}
                   for it in ITEMS]
        res = align(one_key, parse_blocks(FIXTURE), threshold=0.5)
        both = self.res["scores"][1]
        single = res["scores"][1]
        self.assertLess(single, both)

    def test_unrelated_mantra_scores_far_below_threshold(self):
        # The safety property: a wrong attachment must not look like a right one.
        alien = [{"id": "1.1.1",
                  "samhita_patha_plain": "इषे त्वोर्जे त्वा वायव स्थोपायवः स्थ",
                  "pada_patha_plain": "इषे । त्वा । ऊर्जे । त्वा ॥"}]
        res = align(alien, parse_blocks(FIXTURE), threshold=0.55)
        self.assertEqual(res["aligned"], {})
        self.assertLess(max(res["scores"]), 0.55)


class TestApparatus(unittest.TestCase):
    """The edition's critical apparatus, verbatim from RV 5.1.2's alignment.

    This was caught by reading a pairing, not by any score: an apparatus block
    scores exactly as well as a real one, because the score measures the mantra
    printed ABOVE it and says nothing about what follows.
    """

    REAL = ("१. ख-च-फ-' आत्रेये ' नास्ति। २. ख-ग-च-ण-भ-ल-स-' प्रातरनुवाके ' नास्ति। "
            "३. ख- ग-च-ण-न-भ-ल-स-प्रवृद्धोऽभूत् ।")
    PROSE = ("अयं \"अग्निः \"जनानाम् अध्वर्य्वादीनां समिधा समिद्भिः अबोधि "
             "प्रबुद्धोऽभूत् ।")

    def test_apparatus_is_recognised(self):
        self.assertTrue(looks_like_apparatus(self.REAL))

    def test_commentary_prose_is_not(self):
        self.assertFalse(looks_like_apparatus(self.PROSE))

    def test_empty_is_not(self):
        self.assertFalse(looks_like_apparatus(""))

    def test_a_bare_number_alone_is_not_enough(self):
        # Sayana himself numbers things. Both marks must be present, or ordinary
        # commentary that opens with a numeral would be thrown away.
        self.assertFalse(looks_like_apparatus("१. अयं अग्निः जनानाम् समिधा अबोधि"))

    def test_apparatus_is_skipped_in_favour_of_the_commentary(self):
        doc = ("अग्निमीळे पुरोहितं यज्ञस्य ॥ १ ॥\n"
               "अग्निम् । ईळे । पुरःऽहितम् ॥ १ ॥\n"
               + self.REAL + " ॥ २ ॥\n"
               + self.PROSE + " ॥ ३ ॥\n")
        res = align([ITEMS[0]], parse_blocks(doc), threshold=0.5)
        got = res["aligned"]["1.1.1"]["text"]
        self.assertIn("जनानाम्", got)
        self.assertNotIn("नास्ति", got)


class TestSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(similarity("अग्नि", "अग्नि"), 1.0)

    def test_empty_is_zero_not_error(self):
        self.assertEqual(similarity("", "अग्नि"), 0.0)

    def test_unrelated_scores_low(self):
        self.assertLess(similarity(skeleton("अग्निमीळे पुरोहितं"),
                                   skeleton("इषे त्वोर्जे त्वा")), 0.4)


class TestFetch(unittest.TestCase):
    """A dropped connection should cost a few seconds, not the whole run.

    archive.org timed out once mid-probe and ended a job that had already done
    its work. What the retry must NOT do is hammer a server that has answered
    plainly: a 404 is an answer, and asking again cannot change it.
    """

    def setUp(self):
        self.slept = []
        self._sleep, archive_sayana.time.sleep = archive_sayana.time.sleep, self.slept.append
        self._urlopen = archive_sayana.urllib.request.urlopen
        self.addCleanup(self.restore)

    def restore(self):
        archive_sayana.time.sleep = self._sleep
        archive_sayana.urllib.request.urlopen = self._urlopen

    def serve(self, *outcomes):
        """Answer successive calls with the given exceptions or payloads."""
        self.calls = []

        def urlopen(req, timeout=None):
            self.calls.append(req.full_url)
            out = outcomes[len(self.calls) - 1]
            if isinstance(out, Exception):
                raise out
            return io.BytesIO(out)

        archive_sayana.urllib.request.urlopen = urlopen

    def test_transient_timeout_is_retried(self):
        self.serve(TimeoutError(110, "Connection timed out"), b"ok")
        self.assertEqual(fetch("https://archive.org/metadata/x"), b"ok")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.slept, [2])

    def test_gives_up_after_the_last_attempt(self):
        boom = urllib.error.URLError("timed out")
        self.serve(boom, boom, boom, boom)
        with self.assertRaises(urllib.error.URLError):
            fetch("https://archive.org/metadata/x", attempts=4)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(self.slept, [2, 4, 8])

    def test_404_is_an_answer_and_is_not_retried(self):
        gone = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        self.serve(gone, b"never reached")
        with self.assertRaises(urllib.error.HTTPError):
            fetch("https://archive.org/metadata/x")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.slept, [])

    def test_server_saying_not_now_is_retried(self):
        for code in (429, 503):
            with self.subTest(code=code):
                self.serve(urllib.error.HTTPError("u", code, "", {}, None), b"ok")
                self.assertEqual(fetch("https://archive.org/download/x"), b"ok")
                self.assertEqual(len(self.calls), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
