"""find_text_start.py: a conservative lower bound on where a book's text begins."""

import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import find_text_start as F  # noqa: E402

LONG_SA = ("धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः । मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ " * 12)
LONG_KN = ("ಈ ಬ್ರಹ್ಮವು ಯಾವ ಸ್ವರೂಪವನ್ನು ಹೊಂದಿದೆ ಎಂಬುದನ್ನು ತಿಳಿಯಬೇಕು ಎಂದು ಹೇಳಲಾಗಿದೆ ಅದರ ವಿವರಣೆ ಇಲ್ಲಿದೆ । " * 14)
TITLE = "श्रीवादिराजतीर्थश्रीचरणविरचितम् पाषण्डखण्डनम् प्रकाशनम् बेङ्गळूरु २०११"


class LengthNotPunctuation(unittest.TestCase):
    def test_a_kannada_commentary_page_counts_as_body(self):
        """The first version keyed on danda density and this page failed it.

        Kannada prose carries far fewer dandas per character than Sanskrit
        verse, so page 58 of the 108 Upanishad scan -- 1,487 characters of real
        commentary -- scored as front matter, and the detector proposed
        starting sixty pages later. Length survives the script change.
        """
        pages = {1: TITLE, 2: TITLE, 3: LONG_KN, 4: LONG_KN, 5: LONG_KN}
        start, _ = F.find_start(pages)
        self.assertEqual(3, start)

    def test_a_sanskrit_verse_page_still_counts(self):
        pages = {1: TITLE, 2: TITLE, 3: TITLE, 4: LONG_SA, 5: LONG_SA}
        self.assertEqual(4, F.find_start(pages)[0])

    def test_a_roman_script_introduction_is_not_body(self):
        """What the old danda requirement was for, done by script instead."""
        pages = {1: "Introduction " * 200, 2: "Introduction " * 200,
                 3: LONG_SA, 4: LONG_SA}
        self.assertEqual(3, F.find_start(pages)[0])

    def test_kannada_prose_with_no_dandas_at_all_is_body(self):
        """The Harikathamrtasara volumes barely punctuate.

        Page 20 of hks__32 is 1,206 Kannada characters with ZERO dandas and
        page 200 is 863 with zero. Requiring one danda -- which was only ever
        meant to exclude roman-script prefaces -- threw away three hundred
        pages and put the start of that book on page 310 of 315.
        """
        no_danda = LONG_KN.replace("।", "")
        pages = {1: TITLE, 2: TITLE, 3: no_danda, 4: no_danda, 5: no_danda}
        self.assertEqual(3, F.find_start(pages)[0])

    def test_one_stray_full_page_does_not_start_the_book(self):
        pages = {1: TITLE, 2: LONG_SA, 3: TITLE, 4: TITLE, 5: LONG_SA, 6: LONG_SA}
        self.assertEqual(5, F.find_start(pages)[0])

    def test_it_errs_early_rather_than_late(self):
        """The two available errors are not equal.

        Starting a page early costs one page of OCR. Starting a page late
        loses text, and the loss surfaces months later in review. So a run of
        two qualifying pages is enough.
        """
        pages = {1: TITLE, 2: LONG_SA, 3: LONG_SA, 4: LONG_SA}
        self.assertEqual(2, F.find_start(pages)[0])

    def test_a_book_with_no_qualifying_page_reports_nothing_rather_than_guessing(self):
        self.assertIsNone(F.find_start({1: TITLE, 2: TITLE})[0])


if __name__ == "__main__":
    unittest.main()
