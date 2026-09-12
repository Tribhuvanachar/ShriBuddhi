"""
Unit tests for the phase-2 parsers (Vedas outside the Ṛgveda) and for the
Sāmaveda rigveda_ref propagation.

    python tests/test_phase2.py
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers import sacredtexts_veda as stv     # noqa: E402
from parsers import wikisource as wk            # noqa: E402
from propagate_samaveda import normalise_ref, ref_agreement  # noqa: E402
from common import sniff_indent               # noqa: E402

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fx(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


class TestGriffithAtharvaveda(unittest.TestCase):
    def setUp(self):
        self.h = stv.parse_av_hymn(fx("st_av.html"))

    def test_book_and_hymn_from_roman(self):
        self.assertEqual((self.h["book"], self.h["hymn"]), (1, 1))

    def test_all_three_verses_split(self):
        self.assertEqual(sorted(self.h["verses"]), [1, 2, 3])

    def test_superscript_number_not_glued_to_text(self):
        self.assertTrue(self.h["verses"][1].startswith("Now may"))
        self.assertNotIn("1Now", self.h["verses"][1])

    def test_verses_do_not_bleed_into_each_other(self):
        self.assertNotIn("Come thou again", self.h["verses"][1])
        self.assertIn("Vasoshpati", self.h["verses"][2])

    def test_url(self):
        self.assertEqual(stv.av_url(1, 1),
                         "https://sacred-texts.com/hin/av/av01001.htm")
        self.assertEqual(stv.av_url(20, 143),
                         "https://sacred-texts.com/hin/av/av20143.htm")


class TestGriffithShuklaYajurveda(unittest.TestCase):
    def setUp(self):
        self.p = stv.parse_wyv_book(fx("st_wyv.html"))

    def test_book_from_spelled_out_ordinal(self):
        self.assertEqual(self.p["book"], 1)

    def test_verses(self):
        self.assertEqual(sorted(self.p["verses"]), [1, 2, 3])
        self.assertIn("Strainer of Vasu", self.p["verses"][2])

    def test_masthead_not_treated_as_content(self):
        joined = " ".join(self.p["verses"].values())
        self.assertNotIn("THE TEXTS OF THE WHITE YAJURVEDA", joined)

    def test_url(self):
        self.assertEqual(stv.wyv_url(3),
                         "https://sacred-texts.com/hin/wyv/wyvbk03.htm")

    def test_all_forty_ordinals_resolve(self):
        # The White Yajurveda runs to 40 adhyayas and Griffith spells each one
        # out ("BOOK THE FORTIETH."). A short ordinal list would not fail
        # loudly -- parse_wyv_book falls back to the caller's number, which
        # silently disarms the importer's misalignment guard.
        self.assertEqual(len(stv.BOOK_WORDS), 40)
        for label, expected in [("BOOK THE FIRST.", 1),
                                ("BOOK THE TWENTY-THIRD.", 23),
                                ("BOOK THE TWENTY THIRD.", 23),
                                ("BOOK THE FORTIETH.", 40)]:
            html = f"<html><body><h3>{label}</h3><p>1 A verse long enough to keep.</p></body></html>"
            self.assertEqual(stv.parse_wyv_book(html, fallback=0)["book"], expected, label)


class TestKeithTaittiriya(unittest.TestCase):
    def setUp(self):
        self.k = stv.parse_ts_kanda(fx("st_ts.html"))

    def test_keys_are_dge_ids(self):
        self.assertEqual(sorted(self.k), ["2.1.1", "2.1.2", "2.1.3"])

    def test_prapathaka_title_is_not_mistaken_for_a_reference(self):
        # "The Special Animal Sacrifices" is an <h3> exactly like "ii. 1. 1."
        self.assertNotIn("The Special Animal Sacrifices", " ".join(self.k.values()))
        self.assertEqual(len(self.k), 3)

    def test_clauses_kept_together(self):
        self.assertIn("For food thee", self.k["2.1.1"])
        self.assertIn("Savitr", self.k["2.1.1"])

    def test_footnote_markers_stripped(self):
        self.assertNotIn("[1]", self.k["2.1.1"])

    def test_footnote_block_not_appended_to_last_anuvaka(self):
        self.assertNotIn("Cf. Sayana", self.k["2.1.3"])


class TestWikisource(unittest.TestCase):
    def test_parse_response_unwrapped(self):
        html = wk.html_from_parse(fx("ws_whitney.json"))
        self.assertIsNotNone(html)
        self.assertIn("thrice seven", html)

    def test_missing_page_returns_none_not_exception(self):
        self.assertIsNone(wk.html_from_parse(fx("ws_missing.json")))

    def test_whitney_translation_and_notes_separated(self):
        rows = wk.parse_whitney_hymn(wk.html_from_parse(fx("ws_whitney.json")))
        self.assertEqual(sorted(rows), [1, 2])
        self.assertIn("thrice seven", rows[1]["translation"])
        # the apparatus — the part that reports Sayana — must not be merged in
        self.assertNotIn("Ppp. reads", rows[1]["translation"])
        self.assertIn("Ppp. reads", rows[1]["commentary"])
        self.assertIn("Sayana", rows[2]["commentary"])

    def test_av_title(self):
        self.assertEqual(wk.av_title(1, 1), "Atharva-Veda Samhita/Book_I/Hymn_1")
        self.assertEqual(wk.av_title(19, 72), "Atharva-Veda Samhita/Book_XIX/Hymn_72")

    def test_devanagari_verse_split(self):
        html = wk.html_from_parse(fx("ws_sa_smriti.json"))
        verses = wk.parse_devanagari_verses(wk.page_body_text(html))
        self.assertEqual([v["number"] for v in verses], [1, 2, 3])
        self.assertIn("धर्मं", verses[0]["text"])
        self.assertNotIn("॥", verses[0]["text"])

    def test_urls(self):
        self.assertIn("action=parse", wk.parse_url("Foo/Bar"))
        self.assertIn("sa.wikisource.org", wk.search_url("स्मृति", lang="sa"))


class TestSamavedaRefNormalisation(unittest.TestCase):
    def test_devanagari_numerals_and_zero_padding(self):
        self.assertEqual(normalise_ref("०६.०१६.१०"), "6.16.10")
        self.assertEqual(normalise_ref("०१.०१२.०१"), "1.12.1")
        self.assertEqual(normalise_ref("०९.०६४.२८"), "9.64.28")

    def test_already_ascii_passes_through(self):
        self.assertEqual(normalise_ref("10.191.4"), "10.191.4")

    def test_empty(self):
        self.assertEqual(normalise_ref(None), "")
        self.assertEqual(normalise_ref("  "), "")


class FakeFetcher:
    """Stands in for common.Fetcher: a dict of url -> body, and a record of
    what was asked for, so a test can assert the probe order (cheap first)."""

    def __init__(self, pages):
        self.pages = pages
        self.asked = []
        self.stats = {"hit": 0, "miss": 0, "fail": 0}

    def get(self, url, allow_missing=False):
        self.asked.append(url)
        return self.pages.get(url)


class TestSamavedaRefVerification(unittest.TestCase):
    """rigveda_ref is source data, and eight of the corpus's 1,760 are wrong."""

    RV_616_10 = "अग्न आ याहि वीतये गृणानो हव्यदातये । नि होता सत्सि बर्हिषि ॥"

    def test_the_same_verse_agrees(self):
        self.assertGreater(ref_agreement(self.RV_616_10, self.RV_616_10), 0.95)

    def test_a_samaveda_variant_reading_still_agrees(self):
        # SV keeps its own readings: 'भुवो' where the Ṛgveda has 'भवा'.
        sv = "अग्ने त्वं नो अन्तम उत त्राता शिवो भुवो वरूथ्यः ॥"
        rv = "अग्ने त्वं नो अन्तम उत त्राता शिवो भवा वरूथ्यः ॥"
        self.assertGreater(ref_agreement(sv, rv), 0.55)

    def test_reordering_for_the_chant_is_not_read_as_disagreement(self):
        # The word-overlap half of the measure exists for this: the Sāmaveda
        # rearranges words to fit the melody, which a sequence ratio alone
        # scores as a different verse.
        rv = "अभि प्रिया दिवस्पदा सोमो हिन्वानो अर्षति । विप्रस्य धारया कविः ॥"
        sv = "विप्रस्य धारया कविः अभि प्रिया दिवस्पदा सोमो हिन्वानो अर्षति ॥"
        self.assertGreater(ref_agreement(sv, rv), 0.8)

    def test_a_wrong_ref_is_caught(self):
        # SV 385's ref names RV 4.39.6, which shares no word with it. Following
        # it would hand the reader Sāyaṇa on an unrelated verse, and it would
        # read perfectly plausibly.
        sv = "एदु मधोर्मदिन्तरꣳ सिञ्चाध्वर्यो अन्धसः ॥"
        rv = "दधिक्राव्णो अकारिषं जिष्णोरश्वस्य वाजिनः । सुरभि नो मुखा करत् ॥"
        self.assertLess(ref_agreement(sv, rv), 0.55)

    def test_empty_text_never_looks_like_agreement(self):
        self.assertEqual(ref_agreement("", self.RV_616_10), 0.0)
        self.assertEqual(ref_agreement(self.RV_616_10, ""), 0.0)


class TestIndentSniffing(unittest.TestCase):
    """The corpus is not written at one indent width, and reformatting a
    10,000-item file to add one key per item buries the real change."""

    def test_reads_two(self):
        self.assertEqual(sniff_indent('{\n  "schema": "vedic_text",\n  "items": []\n}'), 2)

    def test_reads_one(self):
        self.assertEqual(sniff_indent('{\n "schema": "smriti",\n "items": []\n}'), 1)

    def test_falls_back_when_there_is_nothing_to_read(self):
        self.assertEqual(sniff_indent("{}"), 1)
        self.assertEqual(sniff_indent(""), 1)

    def test_ignores_the_opening_brace_line(self):
        # The first line carries no indent and must not be measured.
        self.assertEqual(sniff_indent('{\n    "a": 1\n}'), 4)


class TestMinorSmritis(unittest.TestCase):
    def setUp(self):
        import import_minor_smritis as ims
        from parsers import wikisource as w
        self.ims, self.w = ims, w
        verses = ('<div class="mw-parser-output">'
                  '<p>अथातः सम्प्रवक्ष्यामि धर्मं वै लोकसंग्रहम् ॥ १ ॥</p>'
                  '<p>ब्राह्मणः क्षत्रियो वैश्यः शूद्रश्चेति चतुर्विधः ॥ २ ॥</p></div>')
        self.pages = {
            w.category_url(ims.CATEGORY, lang="sa"): json.dumps(
                {"query": {"categorymembers": [
                    {"title": "यमस्मृतिः", "ns": 0},
                    {"title": "वर्गः:उपस्मृतयः", "ns": 14}]}}, ensure_ascii=False),
            w.category_url("वर्गः:उपस्मृतयः", lang="sa"): json.dumps(
                {"query": {"categorymembers": [{"title": "शङ्खस्मृतिः", "ns": 0}]}},
                ensure_ascii=False),
            w.parse_url("यमस्मृतिः", lang="sa"): json.dumps(
                {"parse": {"title": "यमस्मृतिः", "text": verses}}, ensure_ascii=False),
            w.prefix_url("यमस्मृतिः/", lang="sa"): json.dumps({"query": {"allpages": []}}),
        }

    def test_category_walk_follows_subcategories(self):
        f = FakeFetcher(self.pages)
        titles = self.ims.enumerate_category(f)
        self.assertIn("यमस्मृतिः", titles)
        self.assertIn("शङ्खस्मृतिः", titles)          # came from the subcategory
        self.assertNotIn("वर्गः:उपस्मृतयः", titles)   # the subcategory itself is not a work

    def test_category_hit_costs_no_extra_request(self):
        f = FakeFetcher(self.pages)
        titles = self.ims.enumerate_category(f)
        before = len(f.asked)
        title, how = self.ims.find_title(f, ["यमस्मृतिः"], titles, "Yama")
        self.assertEqual((title, how), ("यमस्मृतिः", "category"))
        self.assertEqual(len(f.asked), before, "a category hit must not re-fetch")

    def test_missing_work_reports_not_found_rather_than_guessing(self):
        f = FakeFetcher(self.pages)
        title, how = self.ims.find_title(f, ["दक्षस्मृतिः"], [], "Daksa")
        self.assertIsNone(title)
        self.assertEqual(how, "not found")

    def test_search_fallback_rejects_a_shared_prefix_false_match(self):
        # Regression: Caturvargacintāmaṇi's search fallback used to accept
        # any hit sharing its first 4 codepoints ("चतुर", "four-"), which
        # matched an unrelated Vācaspatyam dictionary entry.
        variant = "चतुर्वर्गचिन्तामणिः"
        stem = variant.rstrip("ः").rstrip("्")
        pages = dict(self.pages)
        pages[self.w.parse_url(variant, lang="sa")] = None
        pages[self.w.search_url(stem, lang="sa")] = json.dumps(
            {"query": {"search": [{"title": "वाचस्पत्यम्/चतुर्भाव", "size": 100}]}},
            ensure_ascii=False)
        f = FakeFetcher(pages)
        title, how = self.ims.find_title(f, [variant], [], "Caturvargacintāmaṇi")
        self.assertIsNone(title)
        self.assertEqual(how, "not found")

    def test_search_fallback_accepts_a_genuine_close_match(self):
        variant = "वीरमित्रोदयः - श्राद्धप्रकाशः"
        stem = variant.rstrip("ः").rstrip("्")
        pages = dict(self.pages)
        pages[self.w.parse_url(variant, lang="sa")] = None
        pages[self.w.search_url(stem, lang="sa")] = json.dumps(
            {"query": {"search": [{"title": variant, "size": 5000}]}},
            ensure_ascii=False)
        f = FakeFetcher(pages)
        title, how = self.ims.find_title(f, [variant], [], "Vīramitrodaya")
        self.assertEqual((title, how), (variant, "search"))

    def test_search_fallback_rejects_a_same_name_subsection_of_another_work(self):
        # Regression: "दायभागः" is both Jīmūtavāhana's independent nibandha
        # and a traditional vyavahāra-pada topic name, so it also surfaces as
        # a Nārada Smṛti chapter with the identical leaf title. A leaf-only
        # comparison would score this a perfect match; comparing full titles
        # correctly keeps the unrelated "नारदस्मृतिः/..." prefix in the score.
        variant = "दायभागः"
        stem = variant.rstrip("ः").rstrip("्")
        wrong_work = "नारदस्मृतिः/व्यवहारपदानि/दायभागः"
        pages = dict(self.pages)
        pages[self.w.parse_url(variant, lang="sa")] = None
        pages[self.w.search_url(stem, lang="sa")] = json.dumps(
            {"query": {"search": [{"title": wrong_work, "size": 14899}]}},
            ensure_ascii=False)
        f = FakeFetcher(pages)
        title, how = self.ims.find_title(f, [variant], [], "Dāyabhāga")
        self.assertIsNone(title)
        self.assertEqual(how, "not found")

    def test_build_grantha_shape_matches_dge_schema(self):
        f = FakeFetcher(self.pages)
        data, stats = self.ims.build_grantha(
            f, "यमस्मृतिः", "Yama Smṛti", "Yama", "smriti_dharmashastra_text")
        self.assertEqual(data["schema"], "smriti_dharmashastra_text")
        self.assertEqual(len(data["items"]), 1)
        shlokas = data["items"][0]["shlokas"]
        self.assertEqual([s["number"] for s in shlokas], [1, 2])
        self.assertNotIn("॥", shlokas[0]["sanskrit_text"])
        self.assertEqual(stats["verses"], 2)

    def test_licence_is_recorded_not_assumed(self):
        f = FakeFetcher(self.pages)
        data, _ = self.ims.build_grantha(
            f, "यमस्मृतिः", "Yama Smṛti", "Yama", "smriti_dharmashastra_text")
        lic = data["commentary_sources"]["sa_wikisource"]["licence"]
        self.assertIn("CC BY-SA", lic)
        self.assertIn("share-alike", lic)

    def test_every_target_has_at_least_one_title_variant(self):
        for slug, (_label, _author, variants) in self.ims.TARGETS.items():
            self.assertTrue(variants, slug)
            for v in variants:
                self.assertTrue(any("\u0900" <= ch <= "\u097f" for ch in v),
                                f"{slug}: {v} is not Devanagari")


class TestUpanishads(unittest.TestCase):
    def setUp(self):
        from parsers import upanishad as up
        self.up = up

    def test_gretil_tags_become_ids(self):
        g = self.up.parse_gretil_upanishad(fx("gretil_chandogya.htm"))
        self.assertEqual([r for r, _ in g["mula"]], ["1.1.1", "1.1.2", "1.1.3"])
        self.assertEqual([r for r, _ in g["bhashya"]], ["1.1.1", "1.1.2"])

    def test_mula_and_bhashya_are_separated(self):
        g = self.up.parse_gretil_upanishad(fx("gretil_chandogya.htm"))
        mula = dict(g["mula"])
        bh = dict(g["bhashya"])
        self.assertIn("om ity etad", mula["1.1.1"])
        self.assertIn("avadhāraṇārthaḥ", bh["1.1.1"])
        self.assertNotIn("avadhāraṇārthaḥ", mula["1.1.1"])

    def test_gretil_header_is_not_swallowed_by_verse_one(self):
        g = self.up.parse_gretil_upanishad(fx("gretil_chandogya.htm"))
        first = dict(g["mula"])["1.1.1"]
        self.assertNotIn("GRETIL-Version", first)
        self.assertNotIn("title:", first)

    def test_squash_folds_diacritics_rather_than_dropping_them(self):
        # Dropping Â turns BRÂHMANA into BRHMANA, which matches no unit word,
        # and every Brihadaranyaka section heading goes unrecognised.
        self.assertEqual(self.up.squash("SECOND BRÂHMAN A."), "SECONDBRAHMANA")
        self.assertEqual(self.up.squash("FIRST KHAN D A."), "FIRSTKHANDA")

    def test_sbe_page_yields_one_section(self):
        g = self.up.parse_sbe_sections(fx("sbe_chandogya.htm"))
        self.assertEqual(len(g), 1)
        self.assertEqual((g[0]["ordinal"], g[0]["unit"]), (1, "KHANDA"))
        self.assertEqual(sorted(g[0]["verses"]), [1, 2, 3])

    def test_sbe_footnote_is_not_read_as_a_verse(self):
        g = self.up.parse_sbe_sections(fx("sbe_chandogya.htm"))
        self.assertNotIn("begins here", " ".join(g[0]["verses"].values()))

    def test_a_page_holding_two_sections_splits(self):
        # sbe15054 really does carry both the second and third brahmana of
        # Brihadaranyaka I. Counting files instead of sections shifts every
        # later id by one.
        html = ("<html><body><h1>BRIHADARANYAKA-UPANISHAD.</h1>"
                "<h3>SECOND BR&Acirc;HMAN A<sup><a href=\"#fn_255\">6</a></sup>.</h3>"
                "<p>1. Verily there was nothing here in the beginning.</p>"
                "<p>2. He desired, let a second body be born of me.</p>"
                "<h3>THIRD BR&Acirc;HMAN A.</h3>"
                "<p>1. There were two kinds of descendants of Pragapati.</p>"
                "<div class=\"footnotes\"><a name=\"fn_255\"></a><p>6. A footnote.</p></div>"
                "</body></html>")
        g = self.up.parse_sbe_sections(html)
        self.assertEqual([(x["ordinal"], x["unit"]) for x in g],
                         [(2, "BRAHMANA"), (3, "BRAHMANA")])
        self.assertEqual(sorted(g[0]["verses"]), [1, 2])
        self.assertEqual(sorted(g[1]["verses"]), [1])

    def test_every_sbe_range_matches_its_declared_structure(self):
        # The importer refuses to write on a mismatch, so this is the check
        # that the shipped config is actually right rather than merely safe.
        from import_upanishads import UPANISHADS, section_ids
        for slug, cfg in UPANISHADS.items():
            sbe = cfg.get("sbe")
            if not sbe:
                continue
            skip = set(sbe.get("skip", []))
            pages = len([p for p in range(sbe["first"], sbe["last"] + 1) if p not in skip])
            sections = len(section_ids(cfg["structure"], cfg["levels"]))
            # Brihadaranyaka is one page short because sbe15054 holds two sections.
            expected_pages = sections - (1 if slug == "brihadaranyaka" else 0)
            self.assertEqual(pages, expected_pages,
                             f"{slug}: {pages} pages vs {sections} sections")

    def test_section_ids_shape(self):
        from import_upanishads import section_ids
        self.assertEqual(section_ids([2, 3], 3), ["1.1", "1.2", "2.1", "2.2", "2.3"])
        self.assertEqual(section_ids([1, 1, 1], 2), ["1", "2", "3"])
        self.assertEqual(section_ids([1], 1), [""])

    def test_sbe_url(self):
        self.assertEqual(self.up.sbe_url(1, 22),
                         "https://sacred-texts.com/hin/sbe01/sbe01022.htm")
        self.assertEqual(self.up.sbe_url(15, 100),
                         "https://sacred-texts.com/hin/sbe15/sbe15100.htm")


if __name__ == "__main__":
    unittest.main(verbosity=2)
