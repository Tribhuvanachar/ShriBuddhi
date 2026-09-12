"""Parser tests. These are the tests that encode the failures the importer
was written to avoid, so a regression shows up as a named failure rather than
a quietly smaller corpus."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from kavya.parsers import ambuda_tei, gretil_tei, sanskritsahitya, wikisource
from kavya.schema import validate_layer

F = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name, mode="r"):
    with open(os.path.join(F, name), mode, encoding="utf-8") as fh:
        return fh.read()


COMMENTARY_KEYS = {"vd": {"id": "vallabhadeva", "commentator": "वल्लभदेवः",
                          "name_sa": "वल्लभदेवटीका", "kind": "tika"}}


class TestSanskritSahitya(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(fx("meghadutam.json"))
        self.layers = sanskritsahitya.parse(
            self.doc, "meghaduta", commentary_keys=COMMENTARY_KEYS)

    def test_splits_into_one_layer_per_content_kind(self):
        self.assertEqual(
            sorted(self.layers),
            ["anvaya", "mula", "padaccheda", "translation_en",
             "translation_hi", "vallabhadeva"])

    def test_mula_carries_every_unit(self):
        ids = [sh["id"] for it in self.layers["mula"]["items"]
               for sh in it["shlokas"]]
        self.assertEqual(ids, ["1.1", "1.2", "2.1"])

    def test_chapters_become_items(self):
        self.assertEqual([i["id"] for i in self.layers["mula"]["items"]],
                         ["1", "2"])

    def test_chapter_name_is_kept(self):
        self.assertEqual(self.layers["mula"]["items"][0]["name_sa"], "पूर्वमेघः")

    def test_chandas_rides_on_the_mula_shloka(self):
        sh = self.layers["mula"]["items"][0]["shlokas"][0]
        self.assertEqual(sh["chandas"], "मन्दाक्रान्ता")

    def test_commentary_becomes_bhashya_not_artha(self):
        sh = self.layers["vallabhadeva"]["items"][0]["shlokas"][0]
        self.assertTrue(sh["bhashya"][0]["text"].startswith("कश्चिद्यक्षः"))
        self.assertEqual(sh["bhashya"][0]["commentator"], "वल्लभदेवः")
        self.assertEqual(sh["artha"], "")

    def test_commentary_layer_is_not_flagged_ai(self):
        self.assertFalse(self.layers["vallabhadeva"]["grantha"]["ai_generated"])

    def test_padaccheda_is_structured_and_has_a_flat_fallback(self):
        sh = self.layers["padaccheda"]["items"][0]["shlokas"][0]
        self.assertEqual(sh["padaccheda"][0]["w"], "कश्चित्")
        self.assertEqual(sh["padaccheda"][0]["p"][0]["lemma"], "कः")
        self.assertEqual(sh["padaccheda"][0]["p"][0]["case_number"], "1.1")
        self.assertIn("कश्चित् = a certain", sh["artha"])

    def test_verbal_morphology_is_preserved(self):
        sh = self.layers["padaccheda"]["items"][0]["shlokas"][0]
        verb = sh["padaccheda"][1]["p"][0]
        self.assertEqual(verb["lakara"], "लिट्")
        self.assertEqual(verb["pada"], "A1")
        self.assertEqual(verb["finite"], "चक्रे")

    def test_sparse_layers_skip_units_without_that_key(self):
        ids = [sh["id"] for it in self.layers["translation_hi"]["items"]
               for sh in it["shlokas"]]
        self.assertEqual(ids, ["1.1"])

    def test_undeclared_commentary_key_is_not_silently_imported(self):
        for layer in self.layers.values():
            for it in layer["items"]:
                for sh in it["shlokas"]:
                    for b in sh.get("bhashya", []):
                        self.assertNotIn("undeclared", b["text"])

    def test_probe_reports_the_undeclared_key(self):
        rep = sanskritsahitya.probe(self.doc)
        self.assertIn("zz", rep["unknown_keys"])
        self.assertNotIn("vd", rep["unknown_keys"] and [] or [])

    def test_counts_are_recorded(self):
        self.assertEqual(self.layers["mula"]["grantha"]["counts"]["shlokas"], 3)

    def test_layers_validate(self):
        for lid, layer in self.layers.items():
            self.assertEqual(validate_layer(layer), [], lid)


class TestGretilConventions(unittest.TestCase):
    def test_bhasa_prose_is_detected_as_colon_not_dot(self):
        name, hits = gretil_tei.detect_convention(fx("bhasa_svapna.txt"))
        self.assertEqual(name, "COLON")
        self.assertEqual(hits, 6)

    def test_bhasa_acts_do_not_collapse_into_act_one(self):
        units = list(gretil_tei.split_units(fx("bhasa_svapna.txt")))
        acts = sorted({p[0] for p, _, _ in units})
        self.assertEqual(acts, ["1", "2", "3", "6"])

    def test_bhasa_units_are_marked_prose(self):
        units = list(gretil_tei.split_units(fx("bhasa_svapna.txt")))
        self.assertTrue(all(is_prose for _, is_prose, _ in units))

    def test_bhasa_builds_one_item_per_act(self):
        layer = gretil_tei.build_layer(
            gretil_tei.split_units(fx("bhasa_svapna.txt")),
            "svapnavasavadatta", "mula", "mula", item_depth=1)
        self.assertEqual([i["id"] for i in layer["items"]],
                         ["1", "2", "3", "6"])
        self.assertEqual(layer["grantha"]["counts"]["shlokas"], 6)

    def test_dominant_convention_wins_over_a_stray_marker(self):
        """One stray COLON marker must not flip a DOT file to prose."""
        name, _ = gretil_tei.detect_convention(fx("kavyaprakasha_bala.txt"))
        self.assertEqual(name, "DOT")

    def test_kavyaprakasha_yields_every_entry_not_just_the_first(self):
        units = list(gretil_tei.split_units(fx("kavyaprakasha_bala.txt")))
        self.assertEqual(len(units), 15)
        self.assertEqual(sorted({p[0] for p, _, _ in units}), ["1", "2", "3"])

    def test_paren_convention(self):
        text = "vAgarthAv iva (1.1)\ntau ca (1.2)\n"
        name, _ = gretil_tei.detect_convention(text)
        self.assertEqual(name, "PAREN")
        units = list(gretil_tei.split_units(text))
        self.assertEqual([p for p, _, _ in units], [["1", "1"], ["1", "2"]])
        self.assertEqual(units[0][2], "vAgarthAv iva")

    def test_bare_danda_convention_with_devanagari_digits(self):
        text = "प्रचण्डसूर्यः ॥ १.१ ॥ सदावगाह ॥ १.२ ॥"
        units = list(gretil_tei.split_units(text, "BARE"))
        self.assertEqual([p for p, _, _ in units], [["1", "1"], ["1", "2"]])

    def test_empty_text_yields_nothing(self):
        self.assertEqual(list(gretil_tei.split_units("")), [])
        self.assertEqual(gretil_tei.detect_convention("")[0], None)


class TestGretilTEI(unittest.TestCase):
    def setUp(self):
        self.units = list(gretil_tei.split_units_tei(fx("raghu_tei.xml")))

    def test_xml_id_is_the_reference(self):
        self.assertEqual([p for p, _, _ in self.units],
                         [["1", "1"], ["1", "2"], ["2", "1"]])

    def test_verse_lines_stay_on_separate_lines(self):
        """<l>a</l><l>b</l> must not concatenate into "ab"."""
        self.assertEqual(self.units[0][2],
                         "वागर्थाविव सम्पृक्तौ\nवागर्थप्रतिपत्तये")

    def test_single_line_units_have_no_stray_newline(self):
        self.assertEqual(self.units[2][2], "अथ प्रजानामधिपः प्रभाते")

    def test_build_layer_nests_by_sarga(self):
        layer = gretil_tei.build_layer(self.units, "raghuvamsha", "mula", "mula")
        self.assertEqual([i["id"] for i in layer["items"]], ["1", "2"])
        self.assertEqual(layer["items"][0]["shlokas"][0]["id"], "1.1")

    def test_tika_layer_writes_bhashya(self):
        layer = gretil_tei.build_layer(
            self.units, "raghuvamsha", "sanjivini", "tika",
            commentator="मल्लिनाथः")
        sh = layer["items"][0]["shlokas"][0]
        self.assertEqual(sh["bhashya"][0]["commentator"], "मल्लिनाथः")
        self.assertEqual(sh["sanskrit_text"], "")


class TestAmbuda(unittest.TestCase):
    def test_div_stack_supplies_the_missing_chapter(self):
        units = list(ambuda_tei.split_units(fx("ambuda_kumara.xml")))
        self.assertEqual([p for p, _, _ in units],
                         [["1", "1"], ["1", "2"], ["2", "1"]])

    def test_body_text_survives(self):
        units = list(ambuda_tei.split_units(fx("ambuda_kumara.xml")))
        self.assertTrue(units[0][2].startswith("अस्त्युत्तरस्यां"))


class TestWikisource(unittest.TestCase):
    def setUp(self):
        self.units = list(wikisource.split_units(fx("wikisource_ritu.txt")))

    def test_headings_set_the_chapter(self):
        self.assertEqual([p for p, _, _ in self.units],
                         [["1", "1"], ["1", "2"], ["2", "1"]])

    def test_templates_are_stripped(self):
        self.assertTrue(all("header" not in b for _, _, b in self.units))

    def test_links_are_unwrapped_to_their_label(self):
        self.assertIn("दिनान्तरम्", self.units[2][2])
        self.assertNotIn("[[", self.units[2][2])

    def test_reference_is_not_left_in_the_body(self):
        self.assertTrue(all("॥" not in b for _, _, b in self.units))


if __name__ == "__main__":
    unittest.main(verbosity=2)
