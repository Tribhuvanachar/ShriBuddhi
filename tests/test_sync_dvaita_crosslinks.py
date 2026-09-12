"""tests for tools/sync_dvaita_crosslinks.py — how the catalogue's authors
are resolved to project person ids, what lands in the generated works index,
and the deliberate split between adding a spelling and adding a person."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import sync_dvaita_crosslinks as s  # noqa: E402


def catalogue(items=None, authors=None, cross=None):
    return {
        "items": items or [],
        "masters": {"authors": authors or [], "categories": [], "titles": []},
        "crossLinks": cross or {},
    }


def item(row, grantha, karta_id, parent=None, vishaya="", vibhaga=""):
    return {"id": f"r{row}", "row": row, "grantha": grantha, "kartaId": karta_id,
            "parentId": parent, "vishayaVibhaga": vishaya, "vibhaga": vibhaga}


def author(aid, canonical, iast="", count=1, variants=None):
    return {"id": aid, "canonical": canonical, "iast": iast, "count": count,
            "key": canonical, "variants": variants or [{"value": canonical, "count": count}]}


class ResolvePersonIds(unittest.TestCase):
    def test_alias_match_beats_parampara_node_match(self):
        cat = catalogue(cross={
            "parampara": [{"kind": "author", "authorId": "kar-1", "nodeId": "node_guess"}],
            "authorAliases": [{"authorId": "kar-1", "personId": "jayatirtha"}],
        })
        person_of, source = s.resolve_person_ids(cat, {})
        self.assertEqual(person_of["kar-1"], "jayatirtha")
        self.assertEqual(source["kar-1"], "author-aliases")

    def test_a_scholars_confirmation_beats_everything_derived(self):
        cat = catalogue(cross={
            "authorAliases": [{"authorId": "kar-1", "personId": "wrong_guess"}],
        })
        overrides = {"links": {"kar-1": "vyasatirtha"}}
        person_of, source = s.resolve_person_ids(cat, overrides)
        self.assertEqual(person_of["kar-1"], "vyasatirtha")
        self.assertEqual(source["kar-1"], "confirmed")

    def test_non_author_links_in_overrides_are_ignored(self):
        # overrides.links also holds row -> library path confirmations.
        cat = catalogue()
        person_of, _ = s.resolve_person_ids(cat, {"links": {"r12": "dge/data/x/data.json"}})
        self.assertEqual(person_of, {})


class WorksIndex(unittest.TestCase):
    def build(self):
        cat = catalogue(
            items=[item(1, "मूलम्-A", "kar-1"),
                   item(2, "टीका-B", "kar-1", parent="r1", vishaya="टीका"),
                   item(3, "other", "kar-2")],
            authors=[author("kar-1", "जयतीर्थः", "jayatīrthaḥ", 2), author("kar-2", "X")],
            cross={"authorAliases": [{"authorId": "kar-1", "personId": "jayatirtha"}],
                    "library": [{"id": "r1", "matches": []}]},
        )
        person_of, source = s.resolve_person_ids(cat, {})
        return s.build_works_index(cat, person_of, source)

    def test_only_matched_authors_appear(self):
        idx = self.build()
        self.assertEqual(list(idx), ["jayatirtha"])
        self.assertEqual(idx["jayatirtha"]["count"], 2)

    def test_a_commentary_carries_the_mula_it_was_written_on(self):
        # Without the parent, one जयतीर्थीय-टीका is indistinguishable from the
        # nine others he wrote for the other prakaranas.
        works = self.build()["jayatirtha"]["works"]
        self.assertEqual(works[1]["title"], "टीका-B")
        self.assertEqual(works[1]["parent"], "मूलम्-A")
        self.assertIsNone(works[0]["parent"])

    def test_digitised_works_are_flagged_from_the_library_cross_link(self):
        works = self.build()["jayatirtha"]["works"]
        self.assertTrue(works[0]["digitised"])
        self.assertFalse(works[1]["digitised"])

    def test_representative_spelling_is_the_commonest_not_the_first(self):
        cat = catalogue(
            items=[item(1, "A", "kar-aaa"), item(2, "B", "kar-zzz"), item(3, "C", "kar-zzz")],
            authors=[author("kar-aaa", "rare", count=1), author("kar-zzz", "common", count=2)],
            cross={"authorAliases": [{"authorId": "kar-aaa", "personId": "p"},
                                      {"authorId": "kar-zzz", "personId": "p"}]},
        )
        person_of, source = s.resolve_person_ids(cat, {})
        idx = s.build_works_index(cat, person_of, source)
        self.assertEqual(idx["p"]["canonical"], "common")


class AliasProposals(unittest.TestCase):
    def setUp(self):
        self.cat = catalogue(
            authors=[author("kar-1", "जयतीर्थः", "jayatīrthaḥ", 3,
                            variants=[{"value": "जयतीर्थः", "count": 2}, {"value": "जयतीर्थ", "count": 1}])],
            cross={"authorAliases": [{"authorId": "kar-1", "personId": "jayatirtha"}]},
        )
        self.person_of, self.source = s.resolve_person_ids(self.cat, {})

    def test_unknown_spellings_are_proposed_known_ones_are_not(self):
        aliases = {"persons": {"jayatirtha": {}}, "aliases": {"जयतीर्थः": "jayatirtha"}}
        add_aliases, add_persons = s.propose_alias_changes(
            self.cat, aliases, {}, self.person_of, self.source)
        self.assertEqual(add_aliases, {"जयतीर्थ": "jayatirtha"})
        self.assertEqual(add_persons, {})

    def test_a_person_the_file_does_not_declare_is_proposed_separately(self):
        # Adding a spelling to a known person is mechanical; declaring a new
        # person is an identity claim, so the two are never mixed.
        add_aliases, add_persons = s.propose_alias_changes(
            self.cat, {"persons": {}, "aliases": {}}, {}, self.person_of, self.source)
        self.assertIn("jayatirtha", add_persons)
        self.assertEqual(add_persons["jayatirtha"]["name_sa"], "जयतीर्थः")
        self.assertEqual(set(add_aliases), {"जयतीर्थः", "जयतीर्थ"})

    def test_parampara_node_name_is_used_for_a_proposed_person(self):
        para = {"nodes": [{"id": "jayatirtha", "name": "Jayatirtha"}]}
        _, add_persons = s.propose_alias_changes(
            self.cat, {"persons": {}, "aliases": {}}, para, self.person_of, self.source)
        self.assertEqual(add_persons["jayatirtha"]["name_en"], "Jayatirtha")


class LibraryAuthorNormalisation(unittest.TestCase):
    ALIASES = {
        "persons": {"madhva": {"name_sa": "श्रीमदानन्दतीर्थभगवत्पादाचार्यः",
                                "name_en": "Madhvācārya"}},
        "aliases": {"Sri Madhvacharya": "madhva"},
    }

    def test_english_and_devanagari_spellings_both_reach_the_canonical_name(self):
        m = s.canonical_author_map(self.ALIASES)
        import import_dvaita_grantha_anukramani as imp
        target = "श्रीमदानन्दतीर्थभगवत्पादाचार्यः"
        self.assertEqual(m[imp.join_key(imp.iast("Sri Madhvacharya"))], target)
        self.assertEqual(m[imp.join_key(imp.iast("Madhvācārya"))], target)
        self.assertEqual(m[imp.join_key(imp.iast(target))], target)

    def test_a_person_with_no_devanagari_name_is_never_a_target(self):
        # Normalising towards a bare English name would be a regression for a
        # reader that transliterates from Devanagari.
        m = s.canonical_author_map({"persons": {"x": {"name_en": "Someone"}},
                                     "aliases": {"Some One": "x"}})
        self.assertEqual(m, {})

    def test_scope_covers_the_dvaita_subtree_only(self):
        # The lead's rule: not the Vedas, not kavya, not dasa sahitya.
        self.assertTrue("dge/data/darshana/vedanta/dvaita/Anandamakaranda/x/data.json"
                        .startswith(s.LIBRARY_AUTHOR_SCOPE))
        for outside in ("dge/data/veda/rigveda/mula/data.json",
                        "dge/data/kavya/raghuvamsha/mula/data.json",
                        "dge/data/darshana/vedanta/advaita/x/data.json"):
            self.assertFalse(outside.startswith(s.LIBRARY_AUTHOR_SCOPE), outside)


class PatchDefaultAuthor(unittest.TestCase):
    def write(self, text):
        import tempfile
        fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        fh.write(text)
        fh.close()
        return fh.name

    def test_only_the_author_line_changes(self):
        # A json round-trip would reformat files up to 2.6 MB; the whole point
        # is that the rest of the file survives byte for byte.
        original = ('{\n  "schema": "grantha_mula_text",\n'
                     '  "default_author": "Sri Madhvacharya",\n'
                     '  "items": [ {"a": 1} ]\n}\n')
        p = self.write(original)
        self.assertTrue(s.patch_default_author(p, "श्रीमदानन्दतीर्थः"))
        after = open(p, encoding="utf-8").read()
        self.assertIn('"default_author": "श्रीमदानन्दतीर्थः"', after)
        self.assertEqual(after.replace('"श्रीमदानन्दतीर्थः"', '"Sri Madhvacharya"'), original)
        import json as _j
        self.assertEqual(_j.loads(after)["items"], [{"a": 1}])

    def test_an_unchanged_value_is_left_alone(self):
        p = self.write('{"default_author": "X"}')
        self.assertFalse(s.patch_default_author(p, "X"))

    def test_a_file_without_the_field_is_left_alone(self):
        p = self.write('{"schema": "x"}')
        self.assertFalse(s.patch_default_author(p, "Y"))

    def test_a_missing_file_is_not_an_error(self):
        self.assertFalse(s.patch_default_author("/nonexistent/nope.json", "Y"))


class DasaSahityaProposals(unittest.TestCase):
    CAT = catalogue(
        authors=[author("kar-1", "नरसिंहः")],
        cross={"dasaSahitya": [{"authorId": "kar-1", "canonical": "नरसिंहः",
                                "slug": "narasimha", "composer": "ನರಸಿಂಹ"}],
                "authorAliases": [{"authorId": "kar-1", "personId": "narasimha_t"}]},
    )

    def proposals(self, overrides, aliases=None):
        person_of, _ = s.resolve_person_ids(self.CAT, overrides)
        return s.dasa_alias_proposals(self.CAT, overrides,
                                       aliases or {"persons": {}, "aliases": {}}, person_of)

    def test_an_unconfirmed_join_writes_nothing(self):
        # Matched on a bare given name: a tikakara and a Kannada composer both
        # called नरसिंहः are not thereby one person.
        add, pending = self.proposals({})
        self.assertEqual(add, {})
        self.assertEqual(len(pending), 1)

    def test_a_confirmed_join_proposes_the_kannada_spelling(self):
        add, pending = self.proposals({"links": {"dasa:kar-1": "narasimha"}})
        self.assertEqual(add, {"ನರಸಿಂಹ": "narasimha_t"})
        self.assertEqual(pending, [])

    def test_a_spelling_already_known_is_not_proposed_again(self):
        add, _ = self.proposals({"links": {"dasa:kar-1": "narasimha"}},
                                 {"persons": {}, "aliases": {"ನರಸಿಂಹ": "narasimha_t"}})
        self.assertEqual(add, {})

    def test_a_confirmation_on_an_author_with_no_person_writes_nothing(self):
        # Nothing to hang the spelling on yet.
        cat = catalogue(authors=[author("kar-9", "X")],
                        cross={"dasaSahitya": [{"authorId": "kar-9", "canonical": "X",
                                                 "slug": "y", "composer": "ವೈ"}]})
        person_of, _ = s.resolve_person_ids(cat, {})
        add, _ = s.dasa_alias_proposals(cat, {"links": {"dasa:kar-9": "y"}},
                                         {"persons": {}, "aliases": {}}, person_of)
        self.assertEqual(add, {})

    def test_a_dasa_confirmation_is_not_mistaken_for_a_person_id(self):
        # resolve_person_ids only reads kar- keys; a dasa: key must not leak in.
        person_of, _ = s.resolve_person_ids(self.CAT, {"links": {"dasa:kar-1": "narasimha"}})
        self.assertEqual(person_of["kar-1"], "narasimha_t")


class ParamparaNodeShape(unittest.TestCase):
    def test_nodes_accepted_as_either_a_list_or_a_map(self):
        as_list = s.parampara_nodes({"nodes": [{"id": "a", "name": "A"}]})
        as_map = s.parampara_nodes({"nodes": {"a": {"id": "a", "name": "A"}}})
        self.assertEqual(as_list["a"]["name"], "A")
        self.assertEqual(as_map["a"]["name"], "A")

    def test_missing_nodes_is_not_an_error(self):
        self.assertEqual(s.parampara_nodes({}), {})
        self.assertEqual(s.parampara_nodes(None), {})


if __name__ == "__main__":
    unittest.main()
