"""Merge tests: the rules that keep an import from damaging the repo."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from kavya.merge import ShrinkError, merge_into_existing
from kavya.schema import (make_grantha, make_item, make_layer, make_shloka,
                          recount)


def layer(work="raghuvamsha", lid="mula", kind="mula", rows=(), commentator=""):
    g = make_grantha(lid, work, kind, commentator=commentator)
    L = make_layer(g)
    by_item = {}
    for uid, text in rows:
        item_id = uid.split(".")[0]
        it = by_item.get(item_id)
        if it is None:
            it = make_item(item_id)
            it["id"] = item_id
            by_item[item_id] = it
            L["items"].append(it)
        sh = make_shloka(uid)
        if kind == "mula":
            sh["sanskrit_text"] = text
        elif kind == "tika":
            sh["bhashya"] = [{"commentator": commentator, "text": text}]
        else:
            sh["artha"] = text
        it["shlokas"].append(sh)
    recount(L)
    return L


class TestMerge(unittest.TestCase):
    def test_absent_target_returns_incoming(self):
        inc = layer(rows=[("1.1", "अ")])
        out, rep = merge_into_existing(None, inc)
        self.assertIs(out, inc)
        self.assertEqual(out["grantha"]["counts"]["shlokas"], 1)

    def test_existing_text_wins_over_a_different_reading(self):
        cur = layer(rows=[("1.1", "वागर्थाविव सम्पृक्तौ")])
        inc = layer(rows=[("1.1", "वागर्थाविव संयुक्तौ")])
        out, rep = merge_into_existing(cur, inc)
        sh = out["items"][0]["shlokas"][0]
        self.assertEqual(sh["sanskrit_text"], "वागर्थाविव सम्पृक्तौ")
        self.assertEqual(rep.conflicts, [("1.1", "sanskrit_text")])

    def test_truncated_existing_is_repaired_and_recorded(self):
        cur = layer(rows=[("1.1", "वागर्थाविव")])
        inc = layer(rows=[("1.1", "वागर्थाविव सम्पृक्तौ वागर्थप्रतिपत्तये")])
        out, rep = merge_into_existing(cur, inc)
        sh = out["items"][0]["shlokas"][0]
        self.assertIn("प्रतिपत्तये", sh["sanskrit_text"])
        self.assertEqual(sh["repaired_from"]["sanskrit_text"], "वागर्थाविव")
        self.assertEqual(rep.repaired, ["1.1"])
        self.assertEqual(rep.conflicts, [])

    def test_repair_ignores_whitespace_and_danda_differences(self):
        cur = layer(rows=[("1.1", "वागर्थाविव ॥")])
        inc = layer(rows=[("1.1", "वागर्थाविव  सम्पृक्तौ")])
        out, rep = merge_into_existing(cur, inc)
        self.assertEqual(rep.repaired, ["1.1"])

    def test_identical_text_is_kept_not_counted_as_conflict(self):
        cur = layer(rows=[("1.1", "वागर्थाविव सम्पृक्तौ")])
        inc = layer(rows=[("1.1", "वागर्थाविव  सम्पृक्तौ ")])
        out, rep = merge_into_existing(cur, inc)
        self.assertEqual(rep.conflicts, [])
        self.assertEqual(rep.repaired, [])
        self.assertEqual(rep.kept, 1)

    def test_new_verses_are_added_and_sorted_numerically(self):
        cur = layer(rows=[("1.10", "क"), ("1.2", "ख")])
        inc = layer(rows=[("1.3", "ग"), ("2.1", "घ")])
        out, rep = merge_into_existing(cur, inc)
        ids = [sh["id"] for it in out["items"] for sh in it["shlokas"]]
        self.assertEqual(ids, ["1.2", "1.3", "1.10", "2.1"])
        self.assertEqual(rep.added_shlokas, 2)
        self.assertEqual(rep.added_items, 1)

    def test_empty_field_is_filled_without_being_a_conflict(self):
        cur = layer(rows=[("1.1", "")])
        inc = layer(rows=[("1.1", "वागर्थाविव")])
        out, rep = merge_into_existing(cur, inc)
        self.assertEqual(rep.filled_fields, 1)
        self.assertEqual(rep.conflicts, [])

    def test_shrink_guard_fires_when_content_is_lost_for_any_reason(self):
        """merge_into_existing only ever adds, so the guard is a backstop.
        Simulate loss inside the merge (a bad sort, a bad parser, a future
        edit) and prove the write is refused rather than silently smaller."""
        import kavya.merge as m
        cur = layer(rows=[("1.1", "\u0915"), ("1.2", "\u0916")])
        inc = layer(rows=[("1.1", "\u0915")])
        real_sort = m._sort

        def lossy_sort(L):
            real_sort(L)
            L["items"][0]["shlokas"] = L["items"][0]["shlokas"][:1]

        m._sort = lossy_sort
        try:
            with self.assertRaises(ShrinkError):
                m.merge_into_existing(cur, inc)
        finally:
            m._sort = real_sort

    def test_merge_alone_never_reduces_filled_count(self):
        cur = layer(rows=[("1.1", "\u0915"), ("1.2", "\u0916")])
        inc = layer(rows=[("1.1", "")])
        out, rep = merge_into_existing(cur, inc)
        self.assertEqual(out["grantha"]["counts"]["filled"], 2)

    def test_second_commentator_is_added_alongside_the_first(self):
        cur = layer(lid="tika", kind="tika", commentator="मल्लिनाथः",
                    rows=[("1.1", "सञ्जीविनी")])
        inc = layer(lid="tika", kind="tika", commentator="वल्लभदेवः",
                    rows=[("1.1", "वल्लभदेवटीका")])
        out, rep = merge_into_existing(cur, inc)
        sh = out["items"][0]["shlokas"][0]
        self.assertEqual([b["commentator"] for b in sh["bhashya"]],
                         ["मल्लिनाथः", "वल्लभदेवः"])

    def test_duplicate_bhashya_is_not_appended_twice(self):
        cur = layer(lid="tika", kind="tika", commentator="मल्लिनाथः",
                    rows=[("1.1", "सञ्जीविनी")])
        inc = layer(lid="tika", kind="tika", commentator="मल्लिनाथः",
                    rows=[("1.1", "सञ्जीविनी")])
        out, rep = merge_into_existing(cur, inc)
        self.assertEqual(len(out["items"][0]["shlokas"][0]["bhashya"]), 1)

    def test_truncated_bhashya_is_repaired_in_place(self):
        cur = layer(lid="tika", kind="tika", commentator="मल्लिनाथः",
                    rows=[("1.1", "सञ्जीविनी")])
        inc = layer(lid="tika", kind="tika", commentator="मल्लिनाथः",
                    rows=[("1.1", "सञ्जीविनी व्याख्या पूर्णा")])
        out, rep = merge_into_existing(cur, inc)
        b = out["items"][0]["shlokas"][0]["bhashya"]
        self.assertEqual(len(b), 1)
        self.assertIn("पूर्णा", b[0]["text"])
        self.assertEqual(b[0]["repaired_from"], "सञ्जीविनी")

    def test_padaccheda_does_not_overwrite_an_existing_one(self):
        cur = layer(lid="padaccheda", kind="padaccheda", rows=[("1.1", "")])
        cur["items"][0]["shlokas"][0]["padaccheda"] = [{"w": "पूर्वम्"}]
        inc = layer(lid="padaccheda", kind="padaccheda", rows=[("1.1", "")])
        inc["items"][0]["shlokas"][0]["padaccheda"] = [{"w": "नवम्"}]
        out, rep = merge_into_existing(cur, inc)
        self.assertEqual(out["items"][0]["shlokas"][0]["padaccheda"][0]["w"],
                         "पूर्वम्")

    def test_allow_new_false_only_fills_existing_units(self):
        cur = layer(rows=[("1.1", "")])
        inc = layer(rows=[("1.1", "क"), ("1.2", "ख")])
        out, rep = merge_into_existing(cur, inc, allow_new=False)
        ids = [sh["id"] for it in out["items"] for sh in it["shlokas"]]
        self.assertEqual(ids, ["1.1"])

    def test_counts_are_refreshed_after_merge(self):
        cur = layer(rows=[("1.1", "क")])
        inc = layer(rows=[("1.2", "ख")])
        out, rep = merge_into_existing(cur, inc)
        self.assertEqual(out["grantha"]["counts"]["shlokas"], 2)
        self.assertEqual(out["grantha"]["counts"]["filled"], 2)


class TestSchemaGuards(unittest.TestCase):
    def test_cannot_build_an_ai_flagged_commentary(self):
        with self.assertRaises(ValueError):
            make_grantha("sanjivini", "raghuvamsha", "tika", ai_generated=True)

    def test_ai_flag_is_fine_on_a_generated_layer(self):
        g = make_grantha("saaramsha", "raghuvamsha", "saaramsha",
                         ai_generated=True)
        self.assertTrue(g["ai_generated"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestPrePackageShapeBridge(unittest.TestCase):
    """A layer written before this package existed must UPDATE, not double.

    dge/data's own kavyas carry no grantha block, name a chapter sarga_01 and
    key a verse by number. Merged naively that is 19 sargas becoming 38 in a
    published grantha, which is why this is pinned by name.
    """

    def _existing(self):
        return {
            "schema": "itihasa_purana_text",
            "default_author": "Kalidasa",
            "items": [{"id": "sarga_01", "reference": "सर्गः १", "shlokas": [
                {"number": 1, "sanskrit_text": "वागर्थाविव सम्पृक्तौ"},
                {"number": 2, "sanskrit_text": "क्व सूर्यप्रभवो वंशः"},
            ]}],
        }

    def _incoming(self):
        layer = make_layer(make_grantha("mula", "raghuvamsha", "mula"))
        it = make_item("1")
        it["shlokas"] = [
            make_shloka("1.1"), make_shloka("1.2"), make_shloka("1.3"),
        ]
        it["shlokas"][0]["sanskrit_text"] = "वागर्थाविव सम्पृक्तौ वागर्थप्रतिपत्तये"
        it["shlokas"][1]["sanskrit_text"] = "क्व सूर्यप्रभवो वंशः"
        it["shlokas"][2]["sanskrit_text"] = "क्व चाल्पविषया मतिः"
        layer["items"] = [it]
        return layer

    def test_chapters_are_matched_not_appended(self):
        merged, _ = merge_into_existing(self._existing(), self._incoming())
        self.assertEqual(len(merged["items"]), 1, "sarga_01 and 1 are one sarga")

    def test_existing_verses_are_matched_by_number(self):
        merged, rep = merge_into_existing(self._existing(), self._incoming())
        shlokas = merged["items"][0]["shlokas"]
        self.assertEqual(len(shlokas), 3, "two matched, one genuinely new")
        self.assertEqual(rep.added_shlokas, 1)

    def test_a_truncated_reading_is_repaired_across_the_bridge(self):
        merged, rep = merge_into_existing(self._existing(), self._incoming())
        first = merged["items"][0]["shlokas"][0]
        self.assertIn("वागर्थप्रतिपत्तये", first["sanskrit_text"])
        self.assertEqual(rep.repaired, ["1.1"], "repaired records which verse")

    def test_what_the_old_file_said_about_itself_survives(self):
        merged, _ = merge_into_existing(self._existing(), self._incoming())
        self.assertEqual(merged["default_author"], "Kalidasa")
        self.assertEqual(merged["grantha"]["work_id"], "raghuvamsha")
