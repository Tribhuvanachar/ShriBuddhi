#!/usr/bin/env python3
"""Tests for wikisource_sayana.py — Sāyaṇa's Ṛgveda-bhāṣya from sa.wikisource.

The fixture reproduces the page layout as the wiki really writes it, including
the parts that decide whether the importer is safe rather than merely working:

  * three printed forms per mantra (accented saṃhitā, accented pada, plain
    pada), each closed by ``॥N`` with the trailing danda dropped;
  * a sūkta-level preamble that glosses no single mantra;
  * a mantra whose ``॥N`` marker is missing altogether, as RV 10.90 has for
    four of its sixteen;
  * a gloss that opens on the tail of its own printed mantra;
  * a cut that would hand the reader the *next* mantra's commentary.

None of those can be exercised against a tidy fixture, and each of them was
found in the real corpus rather than imagined.

    python tools/sayana_smriti/tests/test_wikisource_sayana.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wikisource_sayana import (ATTRIBUTION, SUKTA_COUNTS, check_offbyone,  # noqa: E402
                               clean_span, clean_wikitext, find_template,
                               fold_with_map, head_window, is_mantra_fragment,
                               mantra_words, markers, opening_overlap,
                               parse_title, split_sukta, sukta_titles)

PAGE = """{{header
 | title      = [[ऋग्वेदः]] - [[ऋग्वेदः मण्डल १|मण्डल १]]
 | section    = सूक्तं १.१
}}
[[File:Agni.jpg|thumb|[[नारदपुराणम्|अग्निः]]]]
<poem><span style="font-size: 14pt">
अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम् ।
होतारं रत्नधातमम् ॥१॥
अग्निः पूर्वेभिरृषिभिरीड्यो नूतनैरुत ।
स देवाँ एह वक्षति ॥२॥
अग्निना रयिमश्नवत् पोषमेव दिवेदिवे ॥३॥
</span></poem>

{{सायणभाष्यम्|
‘अग्निमीळे' इति सूक्तं प्रातरनुवाके आग्नेये क्रतौ विनियुक्तम् ।<ref>a note</ref> गतो विनियोगः ॥

अ॒ग्निमी॑ळे पु॒रोहि॑तं य॒ज्ञस्य॑ दे॒वमृ॒त्विज॑म् ॥१

अ॒ग्निम् । ई॒ळे॒ । पु॒रःऽहि॑तम् । य॒ज्ञस्य॑ । दे॒वम् । ऋ॒त्विज॑म् ॥१

अग्निम् । ईळे । पुरःऽहितम् । यज्ञस्य । देवम् । ऋत्विजम् ॥१

अग्निनामकं देवम् “ईळे स्तौमि । ‘ईड स्तुतौ' इति धातुः ॥

अ॒ग्निः पूर्वे॑भि॒र्ऋषि॑भि॒रीड्यो॒ नूत॑नैरु॒त ॥२

अग्निः । पूर्वेभिः । ऋषिऽभिः । ईड्यः । नूतनैः । उत ॥२

अयम् “अग्निः “पूर्वेभिः पुरातनैः “ऋषिभिः “ईड्यः स्तुत्यः ॥

अग्निना रयिमश्नवत् पोषमेव दिवेदिवे

अग्निना । रयिम् । अश्नवत् । पोषम् । एव । दिवेऽदिवे

तेन “अग्निना यजमानः “रयिं धनम् “अश्नवत् प्राप्नोति ॥
}}
"""

ITEMS = [
    {"id": "1.1.1",
     "samhita_patha_plain": "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम् ॥",
     "pada_patha_plain": "अग्निम् । ईळे । पुरःऽहितम् । यज्ञस्य । देवम् । ऋत्विजम् ॥"},
    {"id": "1.1.2",
     "samhita_patha_plain": "अग्निः पूर्वेभिर्ऋषिभिरीड्यो नूतनैरुत ॥",
     "pada_patha_plain": "अग्निः । पूर्वेभिः । ऋषिऽभिः । ईड्यः । नूतनैः । उत ॥"},
    {"id": "1.1.3",
     "samhita_patha_plain": "अग्निना रयिमश्नवत् पोषमेव दिवेदिवे ॥",
     "pada_patha_plain": "अग्निना । रयिम् । अश्नवत् । पोषम् । एव । दिवेऽदिवे ॥"},
]


def body_of(page=PAGE):
    return clean_wikitext(find_template(page))


class TestTitles(unittest.TestCase):
    def test_reads_devanagari_numerals(self):
        self.assertEqual(parse_title("ऋग्वेदः सूक्तं १.१७२"), (1, 172))
        self.assertEqual(parse_title("ऋग्वेदः सूक्तं १०.१९१"), (10, 191))

    def test_accepts_the_colon_spelling_the_wiki_also_uses(self):
        self.assertEqual(parse_title("ऋग्वेद: सूक्तं ९.११३"), (9, 113))

    def test_rejects_pages_that_are_not_suktas(self):
        self.assertIsNone(parse_title("ऐतरेय ब्राह्मणम्/पञ्चिका ३ (तृतीय पञ्चिका)"))
        self.assertIsNone(parse_title("ऋग्वेदः मण्डल १"))

    def test_rejects_out_of_range_numbers(self):
        # Maṇḍala 2 has 43 sūktas; 2.99 is not a typo to be tolerated.
        self.assertIsNone(parse_title("ऋग्वेदः सूक्तं २.९९"))
        self.assertIsNone(parse_title("ऋग्वेदः सूक्तं ११.१"))

    def test_both_title_spellings_are_probed(self):
        titles = sukta_titles(6, 75)
        self.assertEqual(len(titles), 2)
        self.assertIn("ऋग्वेदः सूक्तं ६.७५", titles)
        self.assertIn("ऋग्वेद: सूक्तं ६.७५", titles)

    def test_sukta_counts_sum_to_the_rigveda(self):
        self.assertEqual(sum(SUKTA_COUNTS.values()), 1028)


class TestTemplate(unittest.TestCase):
    def test_finds_the_named_boundary(self):
        tpl = find_template(PAGE)
        self.assertIsNotNone(tpl)
        self.assertIn("अग्निनामकं देवम्", tpl)
        # The mantras printed above the template are not part of it.
        self.assertNotIn("{{header", tpl)

    def test_missing_template_is_none_not_an_exception(self):
        self.assertIsNone(find_template("{{header}}\nno bhashya here"))

    def test_brace_matching_survives_a_nested_template(self):
        page = "{{सायणभाष्यम्|\nप्रथमम् {{ref|अन्तः}} अन्तिमम्\n}}\nafter"
        tpl = find_template(page)
        self.assertIn("अन्तिमम्", tpl)
        self.assertNotIn("after", tpl)

    def test_unclosed_template_keeps_the_tail_rather_than_dropping_it(self):
        tpl = find_template("{{सायणभाष्यम्|\nभाष्यम् अपूर्णम्")
        self.assertIn("भाष्यम् अपूर्णम्", tpl)


class TestCleanWikitext(unittest.TestCase):
    def test_strips_refs_comments_and_file_links(self):
        out = clean_wikitext("क<ref>note</ref>ख<!-- hide -->ग "
                             "[[File:X.jpg|thumb|[[क|caption]]]] घ")
        for gone in ("note", "hide", "File:", "caption"):
            self.assertNotIn(gone, out)
        for kept in ("क", "ख", "ग", "घ"):
            self.assertIn(kept, out)

    def test_keeps_the_display_side_of_a_piped_link(self):
        self.assertIn("मण्डल १", clean_wikitext("[[ऋग्वेदः मण्डल १|मण्डल १]]"))
        self.assertNotIn("ऋग्वेदः मण्डल", clean_wikitext("[[ऋग्वेदः मण्डल १|मण्डल १]]"))

    def test_keeps_the_pratika_quotation_marks(self):
        # They are how Sāyaṇa marks the mantra's own words, and the off-by-one
        # check reads them.
        self.assertIn("“अग्निः", clean_wikitext("अयम् “अग्निः पूर्वेभिः"))


class TestMarkers(unittest.TestCase):
    def test_reads_the_number_without_a_closing_danda(self):
        self.assertEqual([n for n, _s, _e in markers("पदम् ॥२ अन्यत्")], [2])

    def test_reads_the_number_with_one(self):
        self.assertEqual([n for n, _s, _e in markers("पदम् ॥ १२ ॥")], [12])

    def test_folding_maps_back_to_the_original_offsets(self):
        text = "अ॒ग्निः । ईळे ॥१"
        folded, fmap = fold_with_map(text)
        self.assertEqual(len(folded), len(fmap))
        self.assertNotIn("।", folded)
        self.assertNotIn("॥", folded)
        # Every folded character points at a real position, in order.
        self.assertTrue(all(0 <= i < len(text) for i in fmap))
        self.assertEqual(fmap, sorted(fmap))


class TestSplit(unittest.TestCase):
    def setUp(self):
        self.cuts, self.preamble, self.misses = split_sukta(body_of(), ITEMS)
        self.by = {c.mid: c for c in self.cuts}

    def test_every_mantra_is_placed(self):
        self.assertEqual(self.misses, [])
        self.assertEqual(sorted(self.by), ["1.1.1", "1.1.2", "1.1.3"])

    def test_each_gloss_is_the_one_printed_under_its_own_mantra(self):
        self.assertIn("ईळे स्तौमि", self.by["1.1.1"].text)
        self.assertIn("पुरातनैः", self.by["1.1.2"].text)
        self.assertIn("रयिं धनम्", self.by["1.1.3"].text)

    def test_a_gloss_does_not_carry_the_next_mantras_commentary(self):
        self.assertNotIn("पुरातनैः", self.by["1.1.1"].text)
        self.assertNotIn("रयिं धनम्", self.by["1.1.2"].text)

    def test_a_gloss_does_not_carry_the_next_mantras_printed_text(self):
        # The accented saṃhitā of mantra 2 must not trail mantra 1's gloss:
        # that is what made correct cuts look one-late before the block start
        # was taken from the earliest match rather than the best-scoring one.
        self.assertNotIn("पूर्वे॑भि", self.by["1.1.1"].text)

    def test_the_printed_mantra_is_not_served_as_commentary(self):
        for cut in self.cuts:
            self.assertNotIn("॥१", cut.text[:40])
            self.assertNotIn("पुरःऽहितम्", cut.text)

    def test_the_sukta_preamble_is_kept_apart_from_mantra_one(self):
        self.assertIn("विनियुक्तम्", self.preamble)
        self.assertNotIn("विनियुक्तम्", self.by["1.1.1"].text)

    def test_a_mantra_with_no_verse_number_is_still_placed(self):
        # Mantra 3 is printed without any ॥३ marker, as RV 10.90 prints four of
        # its sixteen. The mantra's own text is the anchor, so it still lands.
        self.assertIn("1.1.3", self.by)
        self.assertFalse(self.by["1.1.3"].numbered)

    def test_the_verse_number_is_recorded_where_it_does_agree(self):
        self.assertTrue(self.by["1.1.1"].numbered)
        self.assertTrue(self.by["1.1.2"].numbered)

    def test_scores_are_high_on_transcribed_text(self):
        for cut in self.cuts:
            self.assertGreater(cut.score, 0.75, cut.mid)


class TestCleanSpan(unittest.TestCase):
    def test_strips_a_leading_danda_and_verse_number(self):
        self.assertEqual(clean_span(" ॥१ हे अग्ने"), "हे अग्ने")

    def test_strips_a_stranded_vowel_sign(self):
        # The cut can fall inside the last akṣara of the printed mantra.
        self.assertEqual(clean_span("ः ॥११ पूर्वं व्याख्याता"), "पूर्वं व्याख्याता")
        self.assertEqual(clean_span("् ॥५ सिद्धैषा"), "सिद्धैषा")

    def test_strips_the_varga_tally_printed_at_the_end(self):
        self.assertEqual(clean_span("इति भाष्यम् ॥ ॥ २२ ॥"), "इति भाष्यम्")

    def test_trims_a_leftover_word_of_the_mantra_before_the_marker(self):
        item = {"samhita_patha_plain": "इन्द्रायेन्दो परि स्रव ॥",
                "pada_patha_plain": "इन्द्राय । इन्दो इति । परि । स्रव ॥"}
        out = clean_span("स्रव ॥७॥ हे पवमान यत्र", 7, item)
        self.assertEqual(out, "हे पवमान यत्र")

    def test_keeps_commentary_that_merely_quotes_a_numbered_verse(self):
        # Same shape, but the head is Sāyaṇa's prose rather than the mantra, so
        # trimming it would eat the commentary's first line.
        item = {"samhita_patha_plain": "अग्निमीळे पुरोहितम् ॥",
                "pada_patha_plain": "अग्निम् । ईळे । पुरःऽहितम् ॥"}
        text = "अत्र निगदव्याख्यातम् ॥१ इति यास्कः"
        self.assertEqual(clean_span(text, 1, item), text)


class TestMantraFragment(unittest.TestCase):
    def setUp(self):
        self.item = {"samhita_patha_plain": "सजोषसा उषसा सूर्येण च सोमं पिबतमश्विना ॥",
                     "pada_patha_plain": "सऽजोषसा । उषसा । सूर्येण । च । सोमम् । पिबतम् । अश्विना ॥"}

    def test_a_scrap_of_the_mantra_is_not_commentary(self):
        self.assertTrue(is_mantra_fragment("सोमं पिबतम् ॥", self.item))

    def test_a_bare_mark_is_not_commentary(self):
        for junk in ("ः", "्", "से", " ॥ "):
            self.assertTrue(is_mantra_fragment(junk, self.item), junk)

    def test_a_short_genuine_cross_reference_survives(self):
        # Sāyaṇa disposes of a repeated refrain in three words, and that IS his
        # commentary on it. Length alone must not decide.
        for real in ("पूर्वं व्याख्याता", "इयं व्याख्यातचरा", "एषा सिद्धा"):
            self.assertFalse(is_mantra_fragment(real, self.item), real)

    def test_ordinary_commentary_is_never_a_fragment(self):
        self.assertFalse(is_mantra_fragment(
            "हे अश्विनौ युवां सोमं पिबतम् इति स्तूयते । तत्र दृष्टान्तः ।"
            " अयमर्थः सर्वत्र समानः ॥", self.item))


class TestOffByOne(unittest.TestCase):
    def test_correct_cuts_read_as_their_own(self):
        cuts, _pre, _miss = split_sukta(body_of(), ITEMS)
        res = check_offbyone(cuts, ITEMS)
        self.assertEqual(res["late"], 0)
        self.assertEqual(res["late_ids"], [])
        self.assertGreaterEqual(res["own"], 2)

    def test_a_deliberate_one_step_slip_is_caught(self):
        # This is the defect no coverage figure and no similarity median can
        # see: every mantra still sits above *some* commentary.
        cuts, _pre, _miss = split_sukta(body_of(), ITEMS)
        by = {c.mid: c for c in cuts}
        texts = [by[f"1.1.{i}"].text for i in (1, 2, 3)]
        for i, cut_id in enumerate(("1.1.1", "1.1.2")):
            by[cut_id].text = texts[i + 1]
        res = check_offbyone(list(by.values()), ITEMS)
        self.assertGreaterEqual(res["late"], 2)
        self.assertIn("1.1.1", res["late_ids"])

    def test_the_window_grows_with_the_mantra(self):
        # A 20-word triṣṭubh is only a quarter quoted after 400 characters, so
        # a fixed window called correct pairings inconclusive.
        short = head_window(["क" * 5] * 4)
        long = head_window(["क" * 5] * 24)
        self.assertGreater(long, short)
        self.assertGreaterEqual(short, 400)

    def test_overlap_ignores_accents_and_punctuation(self):
        item = {"pada_patha_plain": "अ॒ग्निः । पूर्वे॑भिः । ऋषि॑ऽभिः ॥"}
        words = mantra_words(item)
        self.assertTrue(words)
        self.assertEqual(opening_overlap("अग्निः पूर्वेभिः ऋषिऽभिः", words), 1.0)

    def test_overlap_is_zero_against_an_unrelated_gloss(self):
        words = mantra_words({"pada_patha_plain": "सोमः । पवते । मधुऽमान् ॥"})
        self.assertEqual(opening_overlap("हे इन्द्र त्वं शचीपते", words), 0.0)


class TestAttribution(unittest.TestCase):
    def test_share_alike_is_recorded_not_assumed(self):
        lic = ATTRIBUTION["sayana"]["licence"]
        self.assertIn("CC BY-SA", lic)
        self.assertIn("Share-alike", lic)
        self.assertIn("attribute", lic)

    def test_the_source_and_attribution_are_named(self):
        block = ATTRIBUTION["sayana"]
        self.assertIn("wikisource", block["source"])
        self.assertIn("Wikisource", block["attribution"])
        self.assertTrue(block["licence_url"].startswith("https://"))

    def test_the_edition_is_not_passed_off_as_a_critical_one(self):
        self.assertIn("Wikisource", ATTRIBUTION["sayana"]["edition"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
