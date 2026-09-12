"""tools/dvaitavedanta/import_sumadhva_vijaya.py — the repeating verse/commentary
shape this grantha's pages actually have, and the text guard that stops a
verse's commentary being bound to the wrong verse."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "dvaitavedanta"))

import import_sumadhva_vijaya as smv  # noqa: E402


PAGE = """
<p class="MsoPlainText"><strong>श्रीमत्कविकुलतिलक…</strong></p>
<h1>कान्ताय कल्याणगुणैकधाम्ने ।</h1>
<h1>नारायणायाखिलकारणाय ।। १ ।।</h1>
<p><strong>श्रीनारायणपण्डिताचार्यविरचिता</strong></p>
<h3>भावप्रकाशिका</h3>
<p>नमो जयात्मने ।</p>
<h3>मन्दोपाकारिणी</h3>
<p>लक्ष्मीनारायणं देवम् ।</p>
<h1>अनाकुलं गोकुलम् ।</h1>
<h1>तस्मै नमो नीरदनीलभासे ।। २ ।।</h1>
<h3>मन्दोपाकारिणी</h3>
<p>इदानीं वेदव्यासः ।</p>
"""


class ParseSarga(unittest.TestCase):
    def setUp(self):
        self.preamble, self.verses, self.order, self.leftover = smv.parse_sarga(PAGE)

    def test_each_numbered_h1_run_closes_one_verse(self):
        self.assertEqual(self.order, [1, 2])
        self.assertIn("कान्ताय", self.verses[1]["mula"])
        self.assertIn("नारायणाया", self.verses[1]["mula"])
        self.assertEqual(self.leftover, [])

    def test_a_commentary_attaches_to_the_verse_above_it_not_below(self):
        # The whole reason the general extractor lost this text: the second
        # verse's commentary sits after the first verse's, and only document
        # order says which verse each belongs to.
        self.assertIn("भावप्रकाशिका", self.verses[1]["commentaries"])
        self.assertNotIn("भावप्रकाशिका", self.verses[2]["commentaries"])
        self.assertIn("इदानीं", self.verses[2]["commentaries"]["मन्दोपाकारिणी"])

    def test_the_header_before_the_first_verse_is_not_commentary(self):
        self.assertTrue(self.preamble)
        for verse in self.verses.values():
            for text in verse["commentaries"].values():
                self.assertNotIn("कविकुलतिलक", text)

    def test_an_attribution_line_between_verse_and_h3_is_dropped(self):
        self.assertNotIn("विरचिता", self.verses[1]["commentaries"]["भावप्रकाशिका"])


class CommentaryNames(unittest.TestCase):
    def test_a_bare_name_maps_to_its_slug(self):
        self.assertEqual(smv.commentary_slug("मन्दोपाकारिणी")[1], "mandopakarini")

    def test_an_attributed_heading_still_maps(self):
        # sarga 9 opens "श्रीछलारिशेषाचार्यविरचिता मन्दोपाकारिणी"; dropping it
        # would lose that sarga's whole मन्दोपाकारिणी run.
        name, slug = smv.commentary_slug("श्रीछलारिशेषाचार्यविरचिता मन्दोपाकारिणी")
        self.assertEqual(slug, "mandopakarini")
        self.assertEqual(name, "मन्दोपाकारिणी")

    def test_a_heading_naming_none_of_the_three_is_refused(self):
        self.assertEqual(smv.commentary_slug("प्रश्न-उत्तर"), (None, None))


class TextGuard(unittest.TestCase):
    SITE = {
        38: {"mula": "अथ प्रथमपादः कथ्यते ।। ३८ ।।", "commentaries": {}},
        39: {"mula": "द्वितीयोऽयमधिकारः ।। ३९ ।।", "commentaries": {}},
        40: {"mula": "तृतीयमिदमुच्यते ।। ४० ।।", "commentaries": {}},
    }

    def test_hyphenation_and_numbering_do_not_defeat_a_match(self):
        # Our mula keeps the compounds hyphenated; the site does not.
        n, ratio = smv.best_match("अथ प्रथम-पादः कथ्यते ॥ ३८ ॥", self.SITE, 38)
        self.assertEqual(n, 38)
        self.assertGreater(ratio, 0.9)

    def test_a_renumbered_verse_is_found_at_its_real_number(self):
        # Sarga 11: the site runs ahead of us, so our 38 is their 40.
        n, ratio = smv.best_match("तृतीयमिदमुच्यते ॥ ३८ ॥", self.SITE, 38)
        self.assertEqual(n, 40)
        self.assertGreater(ratio, 0.9)

    def test_a_verse_the_site_does_not_have_scores_below_the_floor(self):
        _, ratio = smv.best_match("सर्वथा भिन्नमिदं वचनम् ॥ ३८ ॥", self.SITE, 38)
        self.assertLess(ratio, smv.MATCH_FLOOR)

    def test_squash_ignores_dandas_numerals_and_joiners(self):
        self.assertEqual(smv.squash("क-ख ।। १२ ।।"), smv.squash("कख"))


class PathaThresholds(unittest.TestCase):
    """The two floors that decide what counts as the same verse, and what
    counts as the two recensions genuinely disagreeing."""

    def ratio(self, a, b):
        import difflib
        return difflib.SequenceMatcher(None, smv.squash(a), smv.squash(b)).ratio()

    def test_hyphenation_alone_is_not_a_variant(self):
        # Our copy hyphenates compounds; the site does not. 987 shared verses
        # differ this way and none of them should be marked.
        r = self.ratio("कान्ताय कल्याण-गुणैक-धाम्ने नव-द्युनाथ-प्रतिम-प्रभाय ।",
                       "कान्ताय कल्याणगुणैकधाम्ने नवद्युनाथप्रतिमप्रभाय ।")
        self.assertGreaterEqual(r, smv.PATHA_SAME)

    def test_gemination_alone_is_not_a_variant(self):
        # कीर्तिः / कीर्त्तिः and वाग्मी / वाग्ग्मी are printing conventions.
        self.assertGreaterEqual(self.ratio("मध्वस्य कीर्तिर्दिननाथदीप्तिम्",
                                           "मध्वस्य कीर्त्तिर्द्दिन-नाथ-दीप्तिम्"),
                                smv.PATHA_SAME)

    def test_a_reordering_is_a_variant(self):
        # sarga 1 verse 41, measured at 0.88.
        r = self.ratio("स कृष्णवर्त्मा विजयेन युक्तो मुहुर्महाहेतिधरोऽप्रधृष्यः ।",
                       "विजयेन युक्तो स कृष्ण-वर्मा मुहुर्महा-हेति-धरोऽप्रधृष्यः ।")
        self.assertLess(r, smv.PATHA_SAME)
        self.assertGreater(r, smv.PATHA_FLOOR)

    def test_a_different_verse_falls_below_the_recognition_floor(self):
        # Bannanje's sarga 1 verse 55 has no counterpart at all.
        r = self.ratio("विश्वं मिथ्या विभुरगुणवानात्मनां नास्ति भेदो",
                       "आनन्दाद्यैर्गुरुगुणगणैः पूरितो वासुदेवो")
        self.assertLess(r, smv.PATHA_FLOOR)

    def test_the_floors_are_ordered(self):
        self.assertLess(smv.PATHA_FLOOR, smv.PATHA_SAME)


class RebuiltData(unittest.TestCase):
    """What the committed sargas must look like after the rebuild."""

    import json as _json
    import os as _os
    BASE = _os.path.join(_os.path.dirname(__file__), "..",
                         "dge", "data", "DvaitaVedanta", "Itara", "Kavya", "sumadhva_vijaya")

    def sarga(self, n):
        with open(self._os.path.join(self.BASE, f"sarga_{n}", "data.json"),
                  encoding="utf-8") as fh:
            return self._json.load(fh)

    def test_every_sarga_declares_both_pathas(self):
        for n in range(1, 17):
            versions = self.sarga(n)["metadata"]["pathaVersions"]
            self.assertEqual(versions["primary"]["key"], "dvaitavedanta")
            self.assertEqual(versions["variant"]["key"], "bannanje")

    def test_the_variance_flags_match_the_declared_count(self):
        # A stale flag once outlived the threshold that set it; this is what
        # would have caught it.
        for n in range(1, 17):
            doc = self.sarga(n)
            flagged = [k for k, v in doc["shlokas"].items() if v.get("bannanjeVaries")]
            self.assertEqual(len(flagged), doc["metadata"]["bannanjeCoverage"]["differing"],
                             f"sarga {n}")

    def test_a_variance_flag_never_appears_without_a_reading(self):
        for n in range(1, 17):
            for key, verse in self.sarga(n)["shlokas"].items():
                if verse.get("bannanjeVaries") or verse.get("bannanjeVerse"):
                    self.assertIn("bannanje", verse, f"sarga {n} verse {key}")

    def test_sarga_9_regained_the_verses_our_copy_was_missing(self):
        # It held 41 verses numbered 15..55; the recension (and the recitation
        # audio, at 55 tracks) both start at 1.
        keys = sorted(int(k) for k in self.sarga(9)["shlokas"])
        self.assertEqual(keys[0], 1)
        self.assertEqual(len(keys), 54)

    def test_verse_numbering_is_gapless_in_every_sarga(self):
        for n in range(1, 17):
            keys = sorted(int(k) for k in self.sarga(n)["shlokas"])
            self.assertEqual(keys, list(range(1, len(keys) + 1)), f"sarga {n}")


if __name__ == "__main__":
    unittest.main()
