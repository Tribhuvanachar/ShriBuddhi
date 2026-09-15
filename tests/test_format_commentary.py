"""tests for tools/format_commentary.py.

Three kinds of case: the specification's own examples (written with ASCII
pipes), the shape the real corpus actually uses (dash-introduced, danda-closed),
and the things that must NOT be tagged -- which is where the specification
contradicts itself and where the damage would be.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

from format_commentary import Formatter, format_commentary  # noqa: E402

F = Formatter()


def tps(text):
    """-> the list of pratikas tagged, each including its closing delimiter."""
    import re
    return re.findall(r"<TP>(.*?)</TP>", F.format(text), re.S)


class Pattern1Spec(unittest.TestCase):
    """Section 6: all four delimiter combinations, closing delimiter INSIDE."""

    def test_all_four_combinations(self):
        for op, cl in (("|", "|"), ("|", "||"), ("||", "|"), ("||", "||")):
            src = f"इत्याह {op} मुक्तस्त्विति {cl}"
            self.assertEqual(tps(src), [f"मुक्तस्त्विति {cl}"], src)

    def test_the_opening_delimiter_stays_outside(self):
        out = F.format("इत्याह | मुक्तस्त्विति |")
        self.assertIn("इत्याह | <TP>", out)
        self.assertNotIn("<TP>| ", out)

    def test_representative_introducers(self):
        for intro in ("इत्याह", "अत आह", "तदाह", "भावेनाह", "योजयति",
                      "विशदयति", "व्याचष्टे", "व्यनक्ति"):
            src = f"{intro} || मुक्तस्त्विति ||"
            self.assertEqual(tps(src), ["मुक्तस्त्विति ||"], intro)

    def test_spacing_variations(self):
        for src in ("इत्याह | मुक्तस्त्विति |",
                    "इत्याह  |  मुक्तस्त्विति  |",
                    "इत्याह- | मुक्तस्त्विति ||",
                    "इत्याह - || मुक्तस्त्विति |"):
            self.assertEqual(len(tps(src)), 1, src)


class Pattern1RealCorpus(unittest.TestCase):
    """The shape the supplied sample actually has: introducer, dash, pratika,
    danda. No opening delimiter anywhere -- implementing the spec literally
    would have found nothing at all in the text it was written for."""

    def test_dash_introduced(self):
        self.assertEqual(tps("कथमित्यत आह– विषयाणामिति ।। मात्रा"), ["विषयाणामिति ।।"])

    def test_sandhi_joined_introducer(self):
        # कोषोक्तेः + आह -> कोषोक्तेराह: the letters आ and ह never occur
        # together, so a literal word-list match misses it entirely.
        self.assertEqual(tps("इति कोषोक्तेराह– ननु गन्धरसेति ।। भिन्नेति ।।"),
                         ["ननु गन्धरसेति ।।"])

    def test_a_plain_space_between_introducer_and_pratika(self):
        # P1C. The Bhavacandrika writes "इत्यत आह उद्देशेनैवेति ।" with no
        # delimiter and no dash, so requiring one missed the real pratika.
        self.assertEqual(tps("इत्याह विषयाणामिति ।। मात्रा"), ["विषयाणामिति ।।"])

    def test_what_stops_that_form_running_into_prose(self):
        # Not a dash any more -- the citation particle. This is the SM6:2
        # false positive: an introducer followed by 77 characters of prose
        # ending in वा, which is not how any citation ends.
        self.assertEqual(
            tps("इत्याह साक्षात्परम्परासाधारणसकलगुरुसङ्ग्रहार्थं गुरोः इति "
                "सामान्येन निर्देश इति वा ।"), [])

    def test_a_bare_particle_is_not_a_pratika(self):
        # इति and इत्यर्थः are commentary joinery with no lemma quoted.
        self.assertEqual(tps("इत्याह इति ।"), [])
        self.assertEqual(tps("इत्याह इत्यर्थः ।"), [])


class Pattern2(unittest.TestCase):
    def test_one_and_two_word_forms(self):
        self.assertEqual(tps("... इति । | भवतीति |"), ["भवतीति |"])
        self.assertEqual(tps("... इति । | भवतीति ||"), ["भवतीति ||"])
        self.assertEqual(tps("... इति । | निरूपयतीति |"), ["निरूपयतीति |"])
        self.assertEqual(tps("... इति । | तद् निरूपयतीति ||"), ["तद् निरूपयतीति ||"])

    def test_three_words_is_not_a_pratika(self):
        self.assertEqual(tps("... इति । | तद् एव निरूपयतीति ||"), [])

    def test_unapproved_ending_is_not_a_pratika(self):
        self.assertEqual(tps("... इति । | गच्छति |"), [])

    def test_no_closing_delimiter_is_not_a_pratika(self):
        self.assertEqual(tps("... इति । | भवतीति और"), [])


class MustNotFire(unittest.TestCase):
    """Section 29: not every ।। is a pratika. These three are named in the
    specification itself, and section 11's own rule would tag all of them --
    in danda-punctuated prose '। x ।।' and '| x |' are the same shape. Pattern
    2 is therefore restricted to the pipe forms, which every one of the
    specification's own Pattern-2 examples uses."""

    def test_segmentation_markers_are_left_alone(self):
        for src in ("इत्यर्थः । भिन्नेति ।। मात्रा इति",
                    "इत्यर्थः । द्वन्द्वत्वेति ।। स्पर्शानां",
                    "इत्यनेन । विषयाणामिति ।। मात्रा विषया"):
            self.assertEqual(tps(src), [], src)


class Paragraphs(unittest.TestCase):
    def test_a_start_marker_begins_a_new_paragraph_and_belongs_to_it(self):
        out = F.format("... इति भावः । किञ्च अत्र विचारः ।")
        self.assertIn('<p class="rule">\nकिञ्च अत्र विचारः ।\n</p>', out)
        self.assertNotIn('<p class="rule">\nअत्र विचारः', out)

    def test_every_configured_marker_is_recognised(self):
        for marker in list(F.starters.values()):
            out = F.format(f"पूर्वं वाक्यम् । {marker} उत्तरं वाक्यम् ।")
            self.assertIn(f'<p class="rule">\n{marker}', out, marker)

    def test_an_existing_newline_does_not_double_the_paragraph(self):
        a = F.format("... इति भावः ।\nकिञ्च अत्र विचारः ।")
        b = F.format("... इति भावः । किञ्च अत्र विचारः ।")
        self.assertEqual(a.count('<p class="rule">'), b.count('<p class="rule">'))
        self.assertNotIn("<p class=\"rule\">\n\n", a)

    def test_paragraph_detection_never_splits_a_tp(self):
        # ननु is a paragraph starter AND sits inside this pratika.
        out = F.format("इति कोषोक्तेराह– ननु गन्धरसेति ।। शेषम् ।")
        self.assertIn("<TP>ननु गन्धरसेति ।।</TP>", out)
        self.assertNotIn('<p class="rule">\nननु गन्धरसेति', out)


class Contract(unittest.TestCase):
    def test_no_nesting_and_balanced_tags(self):
        out = F.format(FIXTURE)
        self.assertEqual(out.count("<TP>"), out.count("</TP>"))
        self.assertEqual(out.count('<p class="rule">'), out.count("</p>"))
        self.assertNotIn("<TP><TP>", out)
        self.assertEqual(F.validate(FIXTURE, out), [])

    def test_the_sanskrit_is_never_altered(self):
        import re
        keep = lambda s: "".join(re.findall(r"[ऀ-ॿ]", s))
        self.assertEqual(keep(FIXTURE), keep(F.format(FIXTURE)))

    def test_idempotence(self):
        once = F.format(FIXTURE)
        self.assertEqual(F.format(once), once)

    def test_determinism(self):
        self.assertEqual(F.format(FIXTURE), F.format(FIXTURE))
        self.assertEqual(format_commentary(FIXTURE), F.format(FIXTURE))

    def test_dandas_are_never_rewritten(self):
        out = F.format(FIXTURE)
        self.assertEqual(FIXTURE.count("।"), out.count("।"))
        self.assertEqual(out.count("|"), 0)

    def test_it_makes_no_network_call(self):
        import socket
        orig = socket.socket
        socket.socket = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("the formatter opened a socket"))
        try:
            F.format(FIXTURE)
        finally:
            socket.socket = orig


FIXTURE = (
    "रूपं शब्दो गन्धरसस्पर्शाश्च विषया अमी’ इति कोषोक्तेराह– ननु गन्धरसेति ।। भिन्नेति ।। "
    "मात्रा इति स्पर्शा इति च भिन्नपदत्व इत्यर्थः । द्वन्द्वत्वेति ।। स्पर्शानां "
    "त्वगिन्द्रियग्राह्यगुणविशेषाणाम् । स्त्रीलिङ्गमात्रापरामर्शस्तेषामित्यनेन कथमित्यत आह– "
    "विषयाणामिति ।। मात्रा विषया इति प्रकृतत्वात् पुंलिङ्गेन विषयपरामर्शो युक्त इति भावः ।\n\n"
    "ननु न शरीरविषयसन्निकर्षस्य विषयानुभवहेतुत्वं, सुप्त्यादौ व्यभिचारादित्यत आह– "
    "देहशब्देनेति ।। देहगतत्वं सम्बन्ध इति भावः । केचित्तु लक्षिता च सा लक्षणेति कर्मधारयः ।\n\n"
    "अनुवादप्रकारं दर्शयन् लक्षितार्थं विशदयति– तत्तदित्यादिना ।।"
)


class RealSampleRegression(unittest.TestCase):
    def test_the_pratikas_the_sample_contains(self):
        self.assertEqual(tps(FIXTURE), [
            "ननु गन्धरसेति ।।", "विषयाणामिति ।।", "देहशब्देनेति ।।", "तत्तदित्यादिना ।।"])

    def test_the_segmentation_markers_in_it_are_untouched(self):
        out = F.format(FIXTURE)
        for word in ("भिन्नेति", "द्वन्द्वत्वेति"):
            self.assertNotIn(f"<TP>{word}", out, word)


if __name__ == "__main__":
    unittest.main()
