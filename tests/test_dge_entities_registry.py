"""dge_entities.json registry + cross-reference test data.

Validates the canonical entity registry's shape against the real corpus on
disk (data/), and separately pins down the exact test cases the second-
stage review asked for: कान्ताय, ब्रह्मसूत्रे १.१.२, अष्टाध्याय्याम् १.१.१,
ऋग्वेद १.१.१, भागवते १०.१४.८ -- including the "कान्ताय -> Sumadhvavijaya 1.1"
scenario from the original screenshots. The detection/resolution LOGIC for
those same cases is unit-tested under Node (js/entity-linker.test.js,
run with `node --test js/entity-linker.test.js`) since entity-linker.js
is a browser module; this file instead verifies the DATA those tests
assume is actually true of the real corpus -- so a future corpus edit that
breaks either test suite's assumptions is caught wherever it actually broke.
"""
import json
import os
import unittest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
DGE_DATA = os.path.join(REPO_ROOT, "data")
REGISTRY_PATH = os.path.join(DGE_DATA, "dge_entities.json")


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestRegistryShape(unittest.TestCase):
    def setUp(self):
        self.registry = _load_json(REGISTRY_PATH)
        self.entities = self.registry["entities"]

    def test_every_entity_has_the_required_fields(self):
        required = {"id", "display_name", "sanskrit_name", "aliases", "category",
                    "corpus_id", "canonical_route", "route_type", "reference_scheme",
                    "reference_components", "jump_target_kind"}
        for eid, e in self.entities.items():
            missing = required - set(e.keys())
            self.assertFalse(missing, f"{eid} is missing fields: {missing}")

    def test_every_alias_and_abbreviation_is_unique_to_one_entity(self):
        # A shared alias would make detection ambiguous -- the whole point of
        # a canonical registry is that one surface form means one entity.
        seen = {}
        for eid, e in self.entities.items():
            for alias in e.get("aliases", []) + e.get("abbreviations", []):
                key = alias.lower()
                self.assertNotIn(key, seen,
                    f"alias '{alias}' claimed by both {seen.get(key)} and {eid}")
                seen[key] = eid

    def test_canonical_route_exists_on_disk_for_reader_routes(self):
        # 'reader' route_type entities must open a real, already-digitized
        # leaf grantha -- this is what buildOpenUrl() actually navigates to,
        # so it's canonical_route (the specific leaf) that must exist, not
        # necessarily corpus_id (which for a multi-part work like Mahabharata
        # names the WORK's folder, several parvas deep from any one leaf).
        for eid, e in self.entities.items():
            if e["route_type"] != "reader":
                continue
            leaf = os.path.join(DGE_DATA, *e["canonical_route"].split("/"), "data.json")
            self.assertTrue(os.path.isfile(leaf),
                f"{eid}: canonical_route '{e['canonical_route']}' has no data.json on disk")

    def test_templated_route_part_1_exists_on_disk(self):
        # 'reader_templated' entities (Rigveda mandala_NN, Bhagavata skandha_NN,
        # Vishnu Purana amsha_NN) -- check part 1 specifically, since that is
        # also the Level-2 fallback entity-linker.js's buildOpenUrl() opens.
        for eid, e in self.entities.items():
            if e["route_type"] != "reader_templated":
                continue
            vars_ = {c: 1 for c in e["reference_components"]}
            route = e["canonical_route"]
            import re
            filled = re.sub(r"\{(\w+)(?::(\d+)d)?\}", lambda m: str(vars_.get(m.group(1), "")).zfill(int(m.group(2) or 1)), route)
            leaf = os.path.join(DGE_DATA, *filled.split("/"), "data.json")
            self.assertTrue(os.path.isfile(leaf),
                f"{eid}: templated route part 1 '{filled}' has no data.json on disk")


class TestRequiredCrossReferenceCases(unittest.TestCase):
    """The exact five cases named in the review brief."""

    def test_brahmasutra_1_1_2_target_unit_exists_in_the_real_corpus(self):
        # ब्रह्मसूत्रे १.१.२ -> darshana/vedanta/dvaita/Anandamakaranda/sutra_prasthana/
        #   brahma_sutra_bhashya/mula, unit id "BS_C01_S01_V02" (Chapter/
        #   Section/Verse -- the real id shape, not a plain dotted number).
        data = _load_json(os.path.join(
            DGE_DATA, "darshana", "vedanta", "dvaita", "Anandamakaranda",
            "sutra_prasthana", "brahma_sutra_bhashya", "mula", "data.json"))
        ids = {item.get("id") for item in data.get("items", [])}
        self.assertIn("BS_C01_S01_V02", ids)
        sutra = next(item for item in data["items"] if item["id"] == "BS_C01_S01_V02")
        self.assertIn("जन्माद्यस्य यतः", sutra["sanskrit_text"])

    def test_ashtadhyayi_1_1_1_target_unit_exists_in_the_real_corpus(self):
        # अष्टाध्याय्याम् १.१.१ -> vedanga/vyakarana/ashtadhyayi/sutrapatha, "1.1.1"
        data = _load_json(os.path.join(
            DGE_DATA, "vedanga", "vyakarana", "ashtadhyayi", "sutrapatha", "data.json"))
        ids = {item.get("id") for item in data.get("items", [])}
        self.assertIn("1.1.1", ids)
        rule = next(item for item in data["items"] if item["id"] == "1.1.1")
        self.assertEqual(rule["sanskrit_text"], "वृद्धिरादैच्")

    def test_rigveda_1_1_1_target_unit_exists_in_the_real_corpus(self):
        # ऋग्वेद १.१.१ -> vedas/rigveda/shakala_shakha/samhita/mandala_01, "1.1.1"
        data = _load_json(os.path.join(
            DGE_DATA, "vedas", "rigveda", "shakala_shakha", "samhita",
            "mandala_01", "data.json"))
        ids = {item.get("id") for item in data.get("items", [])}
        self.assertIn("1.1.1", ids)
        rik = next(item for item in data["items"] if item["id"] == "1.1.1")
        # Vedic accent marks (svara) are interleaved between characters in
        # samhita_patha, so a plain substring check must strip them first
        # rather than assume a run of consonants/vowels stays contiguous.
        unaccented = "".join(ch for ch in rik["samhita_patha"] if ch not in "॒॑")
        self.assertIn("अग्निमीळे", unaccented)

    def test_bhagavata_10_14_8_target_chapter_and_shloka_exist_in_the_real_corpus(self):
        # भागवते १०.१४.८ -> purana/maha_purana/bhagavata_purana/skandha_10,
        # chapter "Skandha 10, Adhyaya 14", shloka number 8.
        data = _load_json(os.path.join(
            DGE_DATA, "purana", "maha_purana", "bhagavata_purana", "skandha_10", "data.json"))
        chapter = next((it for it in data["items"] if it.get("id") == "adhyaya_14"), None)
        self.assertIsNotNone(chapter, "adhyaya_14 not found in skandha_10")
        self.assertEqual(chapter["reference"], "Skandha 10, Adhyaya 14")
        shloka_numbers = {sh["number"] for sh in chapter["shlokas"]}
        self.assertIn(8, shloka_numbers)

    def test_kantaya_is_the_opening_word_of_sumadhvavijaya_sarga_1_shloka_1(self):
        # The exact screenshot scenario: searching कान्ताय should surface
        # Sumadhvavijaya 1.1 as a (near-)exact match, because it verbatim
        # opens that shloka. This pins down the underlying corpus fact
        # dge-search.js's word-exact scoring path (js/dge-search.js's
        # _score(), 'word-exact' via) relies on; the search engine itself is
        # a browser/CDN-index module exercised via Playwright, not here.
        data = _load_json(os.path.join(
            DGE_DATA, "DvaitaVedanta", "Itara", "Kavya", "sumadhva_vijaya", "sarga_1", "data.json"))
        shlokas = data.get("shlokas") or data.get("items")
        first = shlokas["1"] if isinstance(shlokas, dict) else shlokas[0]
        # 9 Sep 2026: the primary text is now the DvaitaVedanta recension,
        # which opens straight on कान्ताय; the ॐ ॥ this once asserted was the
        # invocation our earlier copy (now carried as बन्नञ्जे-पाठः) printed
        # ahead of it. The fact the test exists to pin -- कान्ताय is the
        # opening WORD of 1.1 -- is unchanged, so the assertion follows it
        # rather than the old string.
        opening = first["sa"].lstrip("ॐ ॥।\n ")
        self.assertTrue(opening.startswith("कान्ताय"), opening[:40])
        self.assertTrue(first.get("bannanje", "").lstrip("ॐ ॥।\n ").startswith("कान्ताय"))


if __name__ == "__main__":
    unittest.main()
