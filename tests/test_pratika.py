"""dge/js/pratika.js — which commentary words count as quotations of the verse.

Run under node against the real module, because the thing being asserted is
behavioural: given this verse and this commentary word, is it a pratīka?

The examples are verbatim from Sumadhva Vijaya sarga 1 with the
Padārthadīpikodbodhikā, which is exactly the shape the feature exists for:

    ।। कान्तायेति ।। कान्ताय रमणीयाय ।

कान्तायेति announces the citation (कान्ताय + इति fused), कान्ताय recurs as the
lemma, रमणीयाय is the gloss and is not in the verse at all.
"""

import json
import os
import shutil
import subprocess
import unittest

REPO = os.path.join(os.path.dirname(__file__), "..")
MODULE = os.path.join(REPO, "dge", "js", "pratika.js")

# The opening verse, tokenised as the reader shows it.
MULA = ["कान्ताय", "कल्याणगुणैकधाम्ने", "नवद्युनाथप्रतिमप्रभाय", "।",
        "नारायणायाखिलकारणाय", "श्रीप्राणनाथाय", "नमस्करोमि", "।।", "१", "।।"]


@unittest.skipUnless(shutil.which("node"), "node not available")
class Citation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = cls.run_node([
            "कान्तायेति", "कान्ताय", "रमणीयाय", "नमस्करोमीति", "नमस्करोमि",
            "मुख्याश्रयायेत्यर्थः", "इत्यर्थः", "इति", "च", "तु",
            "कल्याणगुणैकधाम्ने", "गुणैकदेहायेत्यपि", "ये", "तेन",
        ])

    @staticmethod
    def run_node(words):
        script = r"""
const fs=require('fs');
const win={activeScript:'devanagari'};
global.window=win;
global.document={addEventListener(){},querySelectorAll(){return{forEach(){}}}};
eval(fs.readFileSync(process.argv[1],'utf8'));
const mula=JSON.parse(process.argv[2]), words=JSON.parse(process.argv[3]);
const out={};
for(const w of words) out[w]=win.dgePratikaCitation(w, mula);
console.log(JSON.stringify(out));
"""
        res = subprocess.run(["node", "-e", script, MODULE, json.dumps(MULA), json.dumps(words)],
                             capture_output=True, text=True)
        if res.returncode != 0:
            raise AssertionError(res.stderr[-1000:])
        return json.loads(res.stdout)

    def test_a_fused_iti_citation_is_found_and_marked_as_announced(self):
        # कान्ताय + इति → कान्तायेति (य् + इ → ये). This is the citation form
        # a commentary actually uses; matching only bare repetitions misses it.
        got = self.results["कान्तायेति"]
        self.assertIsNotNone(got)
        self.assertEqual(got["index"], 0)
        self.assertTrue(got["fused"])

    def test_the_i_stem_fusion_is_found_too(self):
        # नमस्करोमि + इति → नमस्करोमीति (इ + इ → ई).
        got = self.results["नमस्करोमीति"]
        self.assertIsNotNone(got)
        self.assertEqual(got["index"], MULA.index("नमस्करोमि"))
        self.assertTrue(got["fused"])

    def test_a_bare_recurrence_is_a_citation_but_not_an_announced_one(self):
        got = self.results["कान्ताय"]
        self.assertIsNotNone(got)
        self.assertEqual(got["index"], 0)
        self.assertFalse(got["fused"])

    def test_the_commentators_own_gloss_is_never_a_pratika(self):
        # The rule that keeps this from being a bold-everything highlighter:
        # रमणीयाय glosses कान्ताय and appears nowhere in the verse.
        self.assertIsNone(self.results["रमणीयाय"])

    def test_a_gloss_carrying_ityarthah_is_still_not_a_pratika(self):
        # मुख्याश्रयायेत्यर्थः looks exactly like a citation — word + इति form —
        # but मुख्याश्रयाय is the commentator's word, not the verse's.
        self.assertIsNone(self.results["मुख्याश्रयायेत्यर्थः"])
        self.assertIsNone(self.results["गुणैकदेहायेत्यपि"])

    def test_the_fossilised_clitics_are_denied(self):
        # Gold-Standard contract Part 0.4: these are the marks OF a citation
        # and are never the thing cited.
        for word in ("इत्यर्थः", "इति", "च", "तु"):
            self.assertIsNone(self.results[word], word)

    def test_short_bare_matches_are_not_evidence(self):
        # ये and तेन coincide with verse words constantly without quoting them.
        # Measured: of 300 bare matches in one sarga, the 87 at four characters
        # or fewer were all of this kind.
        self.assertIsNone(self.results["ये"])
        self.assertIsNone(self.results["तेन"])

    def test_a_long_bare_lemma_survives_the_length_bar(self):
        self.assertIsNotNone(self.results["कल्याणगुणैकधाम्ने"])


@unittest.skipUnless(shutil.which("node"), "node not available")
class Contract(unittest.TestCase):
    """Rules the Gold-Standard contract states explicitly, pinned to the source
    so a later edit cannot quietly drop one."""

    def setUp(self):
        with open(MODULE, encoding="utf-8") as fh:
            self.js = fh.read()

    def test_every_denylisted_clitic_from_the_contract_is_present(self):
        for word in ("इत्यर्थः", "इत्याह", "तथाहि", "यद्वा", "किञ्च", "इत्येवमादि"):
            self.assertIn(word, self.js, word)

    def test_the_sync_is_scoped_to_one_card(self):
        # Verse 3's कान्ताय must never light up verse 1's.
        self.assertIn("closest('.shloka-card')", self.js)

    def test_a_tap_does_not_swallow_the_word_tools(self):
        # A pratīka is still a word; opening its analysis is right, so the tap
        # handler must not cancel the event the word tools listen for. Checks
        # for a CALL, not the word — the comment above that line says the same
        # thing in prose and would otherwise fail this.
        self.assertNotIn("preventDefault()", self.js)
        self.assertNotIn("preventDefault(", self.js.replace("does NOT preventDefault", ""))


if __name__ == "__main__":
    unittest.main()
