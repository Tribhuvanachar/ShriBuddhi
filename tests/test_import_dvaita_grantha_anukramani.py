"""tests for tools/import_dvaita_grantha_anukramani.py's pure logic:
parent resolution (nearest PRECEDING row with a matching title, not just
any row with that title -- see the module docstring for why that matters),
breadcrumb building, and the three-tier duplicate detection."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import import_dvaita_grantha_anukramani as m  # noqa: E402


def row(grantha="", linkRaw="", karta="", vibhaga="", vishayaVibhaga="",
        prasthana="", status="", availability="", mention="", sourceLibrary="",
        row_no=0):
    return {"grantha": grantha, "linkRaw": linkRaw, "karta": karta,
            "vibhaga": vibhaga, "vishayaVibhaga": vishayaVibhaga,
            "prasthana": prasthana, "status": status, "availability": availability,
            "mention": mention, "sourceLibrary": sourceLibrary, "row": row_no}


class ParentResolution(unittest.TestCase):
    def test_child_links_to_nearest_preceding_row_with_matching_title(self):
        # Mirrors the real sheet's "जयतीर्थीय-टीका" pattern: the same title
        # repeats once per mula, and a child must bind to the occurrence
        # right above it, not the first or last one in the sheet.
        rows = [
            row("mula-A", row_no=1),
            row("tika", linkRaw="mula-A", row_no=2),
            row("sub-of-A-tika", linkRaw="tika", row_no=3),
            row("mula-B", row_no=4),
            row("tika", linkRaw="mula-B", row_no=5),
            row("sub-of-B-tika", linkRaw="tika", row_no=6),
        ]
        m.resolve_parents(rows)
        self.assertEqual(rows[2]["parentIdx"], 1)  # binds to row 2 (mula-A's tika)
        self.assertEqual(rows[5]["parentIdx"], 4)  # binds to row 5 (mula-B's tika), not row 2

    def test_unresolved_link_flagged_when_no_row_has_that_title(self):
        rows = [row("solo", linkRaw="इतिहासः", row_no=1)]
        m.resolve_parents(rows)
        self.assertIsNone(rows[0]["parentIdx"])
        self.assertTrue(rows[0]["unresolvedLink"])

    def test_forward_only_match_used_as_fallback(self):
        rows = [
            row("child", linkRaw="later-mula", row_no=1),
            row("later-mula", row_no=2),
        ]
        m.resolve_parents(rows)
        self.assertEqual(rows[0]["parentIdx"], 1)
        self.assertFalse(rows[0]["unresolvedLink"])


class Breadcrumbs(unittest.TestCase):
    def test_path_and_breadcrumb_walk_full_ancestor_chain(self):
        rows = [
            row("root", row_no=1),
            row("mid", linkRaw="root", row_no=2),
            row("leaf", linkRaw="mid", row_no=3),
        ]
        m.resolve_parents(rows)
        m.build_paths(rows)
        self.assertEqual(rows[2]["breadcrumb"], "root › mid › leaf")
        self.assertEqual(rows[2]["path"], ["r1", "r2", "r3"])
        self.assertEqual(rows[2]["depth"], 2)
        self.assertEqual(rows[0]["depth"], 0)

    def test_cycle_does_not_infinite_loop(self):
        # Pathological input only -- resolve_parents never actually produces
        # a cycle, but build_paths must stay safe if it somehow received one.
        rows = [row("a", row_no=1), row("b", row_no=2)]
        rows[0]["parentIdx"] = 1
        rows[1]["parentIdx"] = 0
        m.build_paths(rows)  # must terminate
        self.assertLessEqual(len(rows[0]["path"]), 2)


class DuplicateDetection(unittest.TestCase):
    def test_exact_full_row_duplicate_grouped_as_exact(self):
        rows = [
            row("A", karta="X", vibhaga="मूलम्", row_no=1),
            row("A", karta="X", vibhaga="मूलम्", row_no=2),
        ]
        m.resolve_parents(rows)
        exact, npk, coll = m.detect_duplicates(rows)
        self.assertEqual(len(exact), 1)
        self.assertEqual(set(exact[0]["ids"]), {"r1", "r2"})
        self.assertIsNotNone(rows[0]["exactDuplicateGroup"])
        # a row already counted as an exact duplicate must not also show up
        # in the weaker name+parent+karta tier
        self.assertNotIn("nameParentKartaGroup", rows[0])

    def test_same_name_parent_karta_but_differing_field_is_npk_not_exact(self):
        rows = [
            row("A", karta="X", availability="s", row_no=1),
            row("A", karta="X", availability="n", row_no=2),
        ]
        m.resolve_parents(rows)
        exact, npk, coll = m.detect_duplicates(rows)
        self.assertEqual(exact, [])
        self.assertEqual(len(npk), 1)
        self.assertEqual(set(npk[0]["ids"]), {"r1", "r2"})

    def test_same_title_different_author_is_collision_not_duplicate(self):
        # This is the दशप्रकरण case: same commentary title, legitimately
        # different underlying works (different parent/author) -- must
        # never be reported as a likely duplicate to merge.
        rows = [
            row("टीका", karta="X", row_no=1),
            row("टीका", karta="Y", row_no=2),
        ]
        m.resolve_parents(rows)
        exact, npk, coll = m.detect_duplicates(rows)
        self.assertEqual(exact, [])
        self.assertEqual(npk, [])
        self.assertEqual(len(coll), 1)
        self.assertEqual(set(coll[0]["ids"]), {"r1", "r2"})

    def test_distinct_rows_produce_no_groups(self):
        rows = [row("A", karta="X", row_no=1), row("B", karta="Y", row_no=2)]
        m.resolve_parents(rows)
        exact, npk, coll = m.detect_duplicates(rows)
        self.assertEqual((exact, npk, coll), ([], [], []))

    def test_identical_child_under_different_resolved_parents_is_not_a_duplicate(self):
        # The bug this guards against: linkRaw ("टीका") is the SAME literal
        # text under both mula-A and mula-B (exactly the दशप्रकरण pattern --
        # a commentary title repeated once per mula), and the child rows
        # under each are byte-for-byte identical in every other column too.
        # Keying duplicate detection on linkRaw's raw text would wrongly
        # merge these; keying on the RESOLVED parent (parentIdx) must not.
        rows = [
            row("mula-A", row_no=1),
            row("टीका", linkRaw="mula-A", karta="X", vibhaga="मूलम्", row_no=2),
            row("mula-B", row_no=3),
            row("टीका", linkRaw="mula-B", karta="X", vibhaga="मूलम्", row_no=4),
        ]
        m.resolve_parents(rows)
        exact, npk, coll = m.detect_duplicates(rows)
        self.assertEqual(exact, [])
        self.assertEqual(npk, [])
        # same title AND same author under different parents -- a collision,
        # not a duplicate-to-merge candidate.
        self.assertEqual(len(coll), 1)
        self.assertEqual(set(coll[0]["ids"]), {"r2", "r4"})


class DropExactDuplicates(unittest.TestCase):
    def test_all_columns_identical_keeps_the_first_and_drops_the_rest(self):
        rows = [row("A", karta="X", vibhaga="मूलम्", row_no=1),
                row("A", karta="X", vibhaga="मूलम्", row_no=2),
                row("A", karta="X", vibhaga="मूलम्", row_no=3)]
        m.resolve_parents(rows)
        kept, dropped = m.drop_exact_duplicates(rows)
        self.assertEqual([r["row"] for r in kept], [1])
        self.assertEqual([d["row"] for d in dropped], [2, 3])
        self.assertEqual(dropped[0]["keptRow"], 1)

    def test_a_differing_column_is_not_a_duplicate(self):
        rows = [row("A", karta="X", availability="s", row_no=1),
                row("A", karta="X", availability="n", row_no=2)]
        m.resolve_parents(rows)
        kept, dropped = m.drop_exact_duplicates(rows)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])

    def test_identical_columns_under_different_parents_are_both_kept(self):
        # The 16 real groups this protects: Vyasatirtha's मन्दारमञ्जरी is typed
        # identically four times -- same title, author and Link text -- but each
        # sits under a different prakarana's tika, so all four are real works.
        rows = [row("mula-A", row_no=1),
                row("टीका", linkRaw="mula-A", row_no=2),
                row("मन्दारमञ्जरी", linkRaw="टीका", karta="व्यासतीर्थः", row_no=3),
                row("mula-B", row_no=4),
                row("टीका", linkRaw="mula-B", row_no=5),
                row("मन्दारमञ्जरी", linkRaw="टीका", karta="व्यासतीर्थः", row_no=6)]
        m.resolve_parents(rows)
        kept, dropped = m.drop_exact_duplicates(rows)
        self.assertEqual(dropped, [])
        self.assertEqual([r["row"] for r in kept], [1, 2, 3, 4, 5, 6])

    def test_rows_without_a_title_are_never_dropped(self):
        rows = [row("", karta="X", row_no=1), row("", karta="X", row_no=2)]
        m.resolve_parents(rows)
        kept, dropped = m.drop_exact_duplicates(rows)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])


class Masters(unittest.TestCase):
    def test_spelling_variants_fold_onto_one_canonical_entry(self):
        # The exact complaint this feature exists for: भाष्यम् and भाष्यम
        # must be ONE term, with the commoner spelling canonical.
        rows = [
            row("A", vishayaVibhaga="भाष्यम्", row_no=1),
            row("B", vishayaVibhaga="भाष्यम्", row_no=2),
            row("C", vishayaVibhaga="भाष्यम", row_no=3),
        ]
        masters = m.build_masters(rows)
        cats = masters["categories"]
        self.assertEqual(len(cats), 1)
        self.assertEqual(cats[0]["canonical"], "भाष्यम्")
        self.assertEqual(cats[0]["count"], 3)
        self.assertEqual([v["value"] for v in cats[0]["variants"]], ["भाष्यम्", "भाष्यम"])

    def test_category_vocabulary_is_shared_across_all_three_tag_columns(self):
        # मूलम् appears in both विभागः and विषयविभागः and is one term, not two.
        rows = [
            row("A", vibhaga="मूलम्", row_no=1),
            row("B", vishayaVibhaga="मूलम्", row_no=2),
        ]
        cats = m.build_masters(rows)["categories"]
        self.assertEqual(len(cats), 1)
        self.assertEqual(cats[0]["count"], 2)
        self.assertEqual(cats[0]["usedIn"], ["vibhaga", "vishayaVibhaga"])

    def test_author_honorific_variants_fold_together(self):
        rows = [
            row("A", karta="श्रीजयतीर्थः", row_no=1),
            row("B", karta="जयतीर्थः", row_no=2),
            row("C", karta="जयतीर्थः", row_no=3),
        ]
        authors = m.build_masters(rows)["authors"]
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0]["canonical"], "जयतीर्थः")
        self.assertEqual(authors[0]["count"], 3)

    def test_distinct_authors_are_not_merged(self):
        rows = [row("A", karta="जयतीर्थः", row_no=1), row("B", karta="व्यासतीर्थः", row_no=2)]
        self.assertEqual(len(m.build_masters(rows)["authors"]), 2)

    def test_master_ids_are_attached_to_rows(self):
        rows = [row("A", karta="श्रीजयतीर्थः", vibhaga="मूलम्", row_no=1)]
        masters = m.build_masters(rows)
        m.attach_master_ids(rows, masters)
        self.assertEqual(rows[0]["kartaId"], masters["authors"][0]["id"])
        self.assertEqual(rows[0]["vibhagaId"], masters["categories"][0]["id"])
        self.assertEqual(rows[0]["titleId"], masters["titles"][0]["id"])


class ParentSuggestions(unittest.TestCase):
    def test_commentary_title_suggests_its_base_work_as_parent(self):
        # 'प्रमाणपद्धतिटीका' with no Link at all, while 'प्रमाणपद्धतिः' is a
        # row of its own -- the real shape of ~2,180 unlinked rows.
        rows = [
            row("प्रमाणपद्धतिः", row_no=1),
            row("प्रमाणपद्धतिटीका", row_no=2),
        ]
        m.resolve_parents(rows)
        s = m.suggest_parents(rows, m.build_masters(rows))
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["id"], "r2")
        self.assertEqual(s[0]["candidates"], ["r1"])
        self.assertEqual(s[0]["confidence"], "high")

    def test_a_row_that_already_has_a_parent_is_not_suggested(self):
        rows = [
            row("प्रमाणपद्धतिः", row_no=1),
            row("प्रमाणपद्धतिटीका", linkRaw="प्रमाणपद्धतिः", row_no=2),
        ]
        m.resolve_parents(rows)
        self.assertEqual(m.suggest_parents(rows, m.build_masters(rows)), [])

    def test_a_work_in_its_own_right_is_not_suggested_a_parent(self):
        # 'सङ्ग्रहः' and 'दीपिका' are deliberately NOT commentary markers:
        # तारतम्यसङ्ग्रहः is its own work, not a commentary on तारतम्य.
        rows = [row("तारतम्य", row_no=1), row("तारतम्यसङ्ग्रहः", row_no=2)]
        m.resolve_parents(rows)
        self.assertEqual(m.suggest_parents(rows, m.build_masters(rows)), [])

    def test_no_suggestion_when_the_base_work_is_absent(self):
        rows = [row("प्रमाणपद्धतिटीका", row_no=1)]
        m.resolve_parents(rows)
        self.assertEqual(m.suggest_parents(rows, m.build_masters(rows)), [])


class Transliteration(unittest.TestCase):
    def test_devanagari_becomes_iast(self):
        self.assertEqual(m.iast("प्रमाणलक्षणम्"), "pramāṇalakṣaṇam")

    def test_non_devanagari_passes_through_untouched(self):
        # A few cells hold latin codes like 'S.M.T'.
        self.assertEqual(m.iast("S.M.T"), "S.M.T")
        self.assertEqual(m.iast(""), "")

    def test_join_key_bridges_iast_and_bare_english(self):
        # One side of every join is IAST, the other bare English.
        self.assertEqual(m.join_key("Jayatīrthaḥ"), m.join_key("Jayatirtha"))
        self.assertEqual(m.join_key("Tattvapradīpa"), "tattvapradipa")


if __name__ == "__main__":
    unittest.main()
