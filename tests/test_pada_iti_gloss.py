"""tools/pratishakhya/regenerate_krama_rv_1_1.py's pada_patha "iti"-gloss
handling.

Found 11-13 Sep 2026 while running the already-built reconstruct_chain()
checker against more of Mandala 1 as a diagnostic (not a scaling of the
committed Krama generator's output, which stays gated on the lead's own
"only after" decision -- see RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.6.6
and PENDING.md): DGE's own pada_patha uses "iti" as an editorial
disambiguation gloss on the word immediately before it (541+76+1 times in
Mandala 1 alone) -- a completely different thing from a real, independent
"iti" WORD (a quotative particle) that appears as its own pada elsewhere in
the very same corpus (12 times in Mandala 1). RV 1.1 itself has zero
instances of either, so this is pure net-new coverage, not a change to
already-shipped output -- confirmed by diffing the committed
krama_regenerated_output.json before and after (no diff).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "pratishakhya"))

from regenerate_krama_rv_1_1 import _strip_pada_iti_gloss, split_pada_words  # noqa: E402


class StripPadaItiGloss(unittest.TestCase):
    def test_plain_word_gloss_keeps_only_the_glossed_word(self):
        # RV 1.2.1's own pada_patha token, verbatim.
        self.assertEqual(_strip_pada_iti_gloss("वायो इति"), ["वायो"])

    def test_compound_gloss_keeps_the_avagraha_split_form(self):
        # RV 1.2.5's own pada_patha token, verbatim: gives the fused
        # citation form, "iti", then the true split compound -- the split
        # form is what this project's own compound convention needs
        # (matches "पुरःऽहितम्"-style tokens elsewhere in this corpus).
        self.assertEqual(
            _strip_pada_iti_gloss("वाजिनीवसू इति वाजिनीऽवसू"), ["वाजिनीऽवसू"]
        )

    def test_standalone_iti_token_is_a_real_word_not_a_gloss(self):
        # RV 1.109.3 etc.: "iti" as its OWN danda-delimited token is a
        # genuine quotative particle (a real Pada word), not a gloss on
        # anything -- must survive unchanged, not be dropped.
        self.assertEqual(_strip_pada_iti_gloss("इति"), ["इति"])

    def test_ordinary_word_with_no_iti_is_unaffected(self):
        self.assertEqual(_strip_pada_iti_gloss("अग्निम्"), ["अग्निम्"])

    def test_two_words_sharing_one_token_with_no_intervening_danda(self):
        # RV 1.162.12's own pada_patha, verbatim -- an isolated data quirk
        # (a missing danda between two otherwise-independent Pada words,
        # the second of which happens to carry its own gloss): must yield
        # BOTH real words, not merge or drop either.
        self.assertEqual(
            _strip_pada_iti_gloss("उपऽआसते उतो इति"), ["उपऽआसते", "उतो"]
        )

    def test_split_pada_words_applies_the_gloss_fix_across_a_whole_verse(self):
        # RV 1.2.1's actual pada_patha (accents already stripped, as
        # split_pada_words expects).
        pada = "वायो इति । आ । याहि । दर्शत । इमे । सोमाः । अरंऽकृताः । तेषाम् । पाहि । श्रुधि । हवम् ॥"
        self.assertEqual(
            split_pada_words(pada),
            ["वायो", "आ", "याहि", "दर्शत", "इमे", "सोमाः", "अरंऽकृताः", "तेषाम्",
             "पाहि", "श्रुधि", "हवम्"],
        )

    def test_split_pada_words_unaffected_for_rv_1_1_shape_input(self):
        # RV 1.1.1's own pada_patha (no iti anywhere) -- confirms this fix
        # is a strict no-op for input shapes like RV 1.1's own, which is
        # why the committed krama_regenerated_output.json doesn't change.
        pada = "अग्निम् । ईळे । पुरःऽहितम् । यज्ञस्य । देवम् । ऋत्विजम् । होतारम् । रत्नऽधातमम् ॥"
        self.assertEqual(
            split_pada_words(pada),
            ["अग्निम्", "ईळे", "पुरःऽहितम्", "यज्ञस्य", "देवम्", "ऋत्विजम्",
             "होतारम्", "रत्नऽधातमम्"],
        )


if __name__ == "__main__":
    unittest.main()
