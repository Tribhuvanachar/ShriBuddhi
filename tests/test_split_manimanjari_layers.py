"""split_manimanjari_layers.py: the three printed layers must come apart
cleanly, and the things that actually went wrong on this scan -- repeated
leaves, the colophon, merged scripts -- must stay fixed."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import split_manimanjari_layers as split  # noqa: E402

TIKA = ("भगवानिति ॥ भगवान् नारायणः, आदौ सृष्टेः प्रारम्भे, प्रकृतेः परः "
        "पूरकः, त्रीन् गुणान् ससर्ज । ततः महत्तत्त्वं विष्णुविग्रहम् ॥ %d ॥")
MULA = ("ससर्ज भगवानादौ त्रीन् गुणान् प्रकृतेः परः ।\n"
        "महत्तत्त्वं ततो विष्णोर्विग्रहं समजीजनत्")
KANNADA = ("ಭಗವಾನ್ = ಷಡ್ಗುಣಸಂಪನ್ನನಾದ ನಾರಾಯಣದೇವರು; ಆದೌ = ಸೃಷ್ಟಿಯ "
           "ಪ್ರಾರಂಭದಲ್ಲಿ; ತ್ರೀನ್ ಗುಣಾನ್ = ಮೂರು ಗುಣಗಳನ್ನು; ಸಸರ್ಜ = "
           "ಸೃಷ್ಟಿಮಾಡಿದರು || %d ||")


def verse_html(number):
    """One turn of the edition's cycle: tika, verse, number, Kannada gloss."""
    return ("<p data-layout=\"paragraph\">%s</p>\n"
            "<p data-layout=\"section-title\">%s</p>\n"
            "<p data-layout=\"paragraph\">॥ %s ॥</p>\n"
            "<p data-layout=\"paragraph\">%s</p>\n"
            % (TIKA % number, MULA, deva(number), KANNADA % number))


def deva(number):
    return "".join(chr(0x0966 + int(d)) for d in str(number))


def staged(pages):
    return {"engine": "sarvam-docai", "source": "test",
            "pages": [{"page": n, "ok": True, "html": html}
                      for n, html in pages]}


def split_pages(pages, **kwargs):
    doc = staged(pages)
    duplicates = split.duplicate_pages(doc)
    blocks = split.read_blocks(doc, duplicates)
    split.classify(blocks)
    return blocks, duplicates


class Cycle(unittest.TestCase):
    def test_each_printed_layer_comes_out_on_its_own(self):
        blocks, _ = split_pages([(1, verse_html(1) + verse_html(2))])
        for layer in ("mula", "tika_sanskrit", "tika_kannada"):
            units = split.assemble(blocks, layer)
            self.assertEqual([u["verse"] for u in units], [1, 2], layer)
        mula = split.assemble(blocks, "mula")
        self.assertIn("ससर्ज भगवानादौ", mula[0]["text"])
        self.assertNotIn("ಭಗವಾನ್", mula[0]["text"])
        kannada = split.assemble(blocks, "tika_kannada")
        self.assertNotIn("ससर्ज", kannada[0]["text"])

    def test_verse_numbers_are_positions_not_the_scans_digits(self):
        # The scan reads the second verse's numeral as 30. The position is
        # what counts; the misread numeral must not move the verse.
        html = verse_html(1) + verse_html(2).replace("॥ २ ॥", "॥ ३० ॥")
        blocks, _ = split_pages([(1, html)])
        self.assertEqual([u["verse"] for u in split.assemble(blocks, "mula")],
                         [1, 2])

    def test_a_verse_split_across_a_page_break_is_one_unit(self):
        head = ("<p data-layout=\"paragraph\">%s</p>\n"
                "<p data-layout=\"section-title\">%s</p>\n" % (TIKA % 1, MULA))
        tail = "<p data-layout=\"paragraph\">%s</p>" % (KANNADA % 1)
        blocks, _ = split_pages([(1, head), (2, tail)])
        kannada = split.assemble(blocks, "tika_kannada")
        self.assertEqual(len(kannada), 1)
        self.assertEqual(kannada[0]["pages"], [2])


class ScanDamage(unittest.TestCase):
    def test_a_leaf_photographed_twice_does_not_invent_verses(self):
        page = verse_html(1) + verse_html(2)
        blocks, duplicates = split_pages([(1, page), (2, page),
                                          (3, verse_html(3))])
        self.assertEqual(sorted(duplicates), [2])
        self.assertEqual([u["verse"] for u in split.assemble(blocks, "mula")],
                         [1, 2, 3])

    def test_a_verse_merged_with_its_kannada_gloss_is_pulled_apart(self):
        merged = ("<p data-layout=\"paragraph\">%s</p>\n"
                  "<p data-layout=\"paragraph\">%s\n%s</p>\n"
                  % (TIKA % 1, MULA, KANNADA % 1))
        blocks, _ = split_pages([(1, merged)])
        mula = split.assemble(blocks, "mula")
        self.assertEqual(len(mula), 1)
        self.assertNotIn("ಭಗವಾನ್", mula[0]["text"])
        self.assertIn("ಭಗವಾನ್", split.assemble(blocks, "tika_kannada")[0]["text"])

    def test_the_running_head_does_not_open_a_verse(self):
        # Left in, the running head is a Devanagari block after the Kannada
        # gloss -- the shape of a new verse -- and shifts everything after it.
        html = (verse_html(1)
                + "<p data-layout=\"paragraph\">मणिमञ्जरी</p>\n"
                + verse_html(2))
        blocks, _ = split_pages([(1, html)])
        self.assertEqual([u["verse"] for u in split.assemble(blocks, "mula")],
                         [1, 2])

    def test_a_bare_numeral_is_a_page_number_whatever_the_ocr_called_it(self):
        html = (verse_html(1)
                + "<p data-layout=\"dateline\">२९</p>\n"
                + verse_html(2))
        blocks, _ = split_pages([(1, html)])
        self.assertEqual([u["verse"] for u in split.assemble(blocks, "mula")],
                         [1, 2])
        self.assertNotIn("२९", "".join(b["text"] for b in blocks if b["layer"]))


class SargaBoundary(unittest.TestCase):
    COLOPHON = ("इति श्रीमत्कविकुलतिलक श्रीमन्नारायणपण्डिताचार्यविरचितायां "
                "मणिमञ्जर्यां प्रथमस्सर्गः ॥")
    SIGNATURE = ("श्रीमन्नृसिंहवर्यानुग्रहजप्रज्ञराघवेन्द्रेण ।\n"
                 "मणिमञ्जरीप्रकाशे रचिते पूर्णोऽयमादिमस्सर्गः")

    def sarga_one_then_two(self, last_verse_html):
        return [(1, verse_html(1) + last_verse_html
                 + "<p data-layout=\"paragraph\">%s</p>\n" % self.COLOPHON
                 + "<p data-layout=\"paragraph\">%s</p>\n" % self.SIGNATURE
                 + "<p data-layout=\"headline\">द्वितीयसर्ग प्रारम्भः</p>\n"
                 + verse_html(1))]

    def test_the_colophon_does_not_become_a_verse_of_its_own(self):
        blocks, _ = split_pages(self.sarga_one_then_two(verse_html(2)))
        mula = split.assemble(blocks, "mula")
        self.assertEqual([(u["sarga"], u["verse"]) for u in mula],
                         [(1, 1), (1, 2), (2, 1)])

    def test_a_verse_printed_into_the_colophon_is_still_a_verse(self):
        # Sarga 6's last verse came back in one paragraph with the colophon
        # under it. Read as colophon it was lost; read as verse it swallowed
        # the colophon.
        run_together = ("<p data-layout=\"paragraph\">%s</p>\n"
                        "<p data-layout=\"section-title\">%s\n॥ २ ॥\n%s</p>\n"
                        % (TIKA % 2, MULA, self.COLOPHON))
        pages = [(1, verse_html(1) + run_together
                  + "<p data-layout=\"headline\">द्वितीयसर्ग प्रारम्भः</p>\n"
                  + verse_html(1))]
        blocks, _ = split_pages(pages)
        mula = split.assemble(blocks, "mula")
        self.assertEqual([(u["sarga"], u["verse"]) for u in mula],
                         [(1, 1), (1, 2), (2, 1)])
        self.assertNotIn("प्रथमस्सर्गः", mula[1]["text"])


class Report(unittest.TestCase):
    def test_the_second_engine_confirms_the_numbering(self):
        blocks, _ = split_pages([(1, verse_html(1) + verse_html(2))])
        text = split.report(blocks, {1: {1, 2}})
        self.assertIn("2 of 2 verses confirmed", text)
        self.assertIn("both engines", text)

    def test_a_count_the_page_contradicts_is_reported_not_corrected(self):
        blocks, _ = split_pages([(1, verse_html(1) + verse_html(2))])
        text = split.report(blocks, {1: {1, 2, 3}})
        self.assertIn("higher than the verse count", text)
        # and the verses themselves are untouched
        self.assertEqual([u["verse"] for u in split.assemble(blocks, "mula")],
                         [1, 2])


if __name__ == "__main__":
    unittest.main()


class MissingMula(unittest.TestCase):
    """One verse came back with its mula misread into Kannada glyphs. The
    verse is still there and still numbered; it must not be dropped."""

    def pages_with_unreadable_verse(self):
        garbled = ("<p data-layout=\"paragraph\">%s</p>\n"
                   "<p data-layout=\"paragraph\">ನೀಲಾಂ ನಗ್ನಜಿತಃಪುತ್ರೀ "
                   "ಮಿತ್ರವಿन्दाಂ पितृष्वसुः ।</p>\n"
                   "<p data-layout=\"paragraph\">%s</p>\n"
                   % (TIKA % 2, KANNADA % 2))
        return [(1, verse_html(1) + garbled + verse_html(3))]

    def test_a_verse_the_scan_lost_still_counts_as_a_verse(self):
        blocks, _ = split_pages(self.pages_with_unreadable_verse())
        kannada = split.assemble(blocks, "tika_kannada")
        self.assertEqual([u["verse"] for u in kannada], [1, 2, 3])
        self.assertEqual([u["verse"] for u in split.assemble(blocks, "mula")],
                         [1, 3])

    def test_and_the_report_names_it(self):
        blocks, _ = split_pages(self.pages_with_unreadable_verse())
        self.assertIn("s1v2", split.report(blocks))

    def test_the_gloss_formula_is_not_mistaken_for_a_verse(self):
        # "नीलामिति ॥ ..." is a gloss: the इ sandhis into the pratika's vowel,
        # and the line carries on past the danda. A verse's line ends at it.
        blocks, _ = split_pages(self.pages_with_unreadable_verse())
        mula = split.assemble(blocks, "mula")
        self.assertFalse([u for u in mula if "नीलामिति" in u["text"]])
