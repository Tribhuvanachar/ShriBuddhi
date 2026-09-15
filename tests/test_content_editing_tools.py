"""tests for the two tools a content editor's work passes through:
normalize_data_json.py (the Enter key) and dge_text.py (explode/implode).

The property that matters for both is that nothing is lost. The normalizer may
only change characters that were illegal; implode may only change body text.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import normalize_data_json as N  # noqa: E402
import dge_text as T  # noqa: E402
import format_data_json  # noqa: E402,F401


def doc(*texts):
    return {"schema": "grantha_tika_text", "default_author": "श्रीराघवेन्द्रतीर्थः",
            "items": [{"id": "SM9:%d" % (n + 2), "reference": "a > b",
                       "section": "मङ्गलाचरणम्", "unit_title": "t%d" % n,
                       "sanskrit_text": t,
                       "source": {"site": "example", "url": "https://example/%d" % n}}
                      for n, t in enumerate(texts)]}


class Normalizer(unittest.TestCase):
    def test_a_raw_newline_inside_a_string_becomes_an_escape(self):
        broken = '{"a":"one\ntwo"}'
        self.assertRaises(ValueError, json.loads, broken)
        fixed, n = N.normalize(broken)
        self.assertEqual(n, 1)
        self.assertEqual(json.loads(fixed), {"a": "one\ntwo"})

    def test_the_line_break_survives_as_a_line_break(self):
        # The whole point: the editor's Enter must still be a <br> on the page.
        fixed, _ = N.normalize('{"a":"one\ntwo"}')
        self.assertEqual(json.loads(fixed)["a"].count("\n"), 1)

    def test_tabs_and_carriage_returns_and_exotic_controls(self):
        fixed, n = N.normalize('{"a":"x\ty\rz\x01w"}')
        self.assertEqual(n, 3)          # tab, carriage return, and the 0x01
        self.assertEqual(json.loads(fixed)["a"], "x\ty\rz\x01w")

    def test_structural_whitespace_is_left_alone(self):
        pretty = '{\n  "a": "b"\n}'
        fixed, n = N.normalize(pretty)
        self.assertEqual(n, 0)
        self.assertEqual(fixed, pretty)

    def test_an_escaped_backslash_before_a_quote_does_not_confuse_the_scanner(self):
        # "a\\" ends the string; the following newline is structural, not content.
        src = '{"a":"back\\\\",\n"b":"c\nd"}'
        fixed, n = N.normalize(src)
        self.assertEqual(n, 1)
        self.assertEqual(json.loads(fixed), {"a": "back\\", "b": "c\nd"})

    def test_a_valid_file_is_returned_byte_for_byte(self):
        src = json.dumps(doc("a\nb", "c"), ensure_ascii=False, separators=(",", ":"))
        fixed, n = N.normalize(src)
        self.assertEqual(n, 0)
        self.assertEqual(fixed, src)

    def test_damage_it_cannot_repair_is_reported_not_papered_over(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "data.json")
            open(p, "w", encoding="utf-8").write('{"a": "b",}')   # trailing comma
            count, msg = N.process(p, check_only=True)
            self.assertEqual(count, -1)
            self.assertIn("not because of a raw control character", msg)

    def test_check_mode_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "data.json")
            broken = '{"a":"one\ntwo"}'
            open(p, "w", encoding="utf-8").write(broken)
            N.process(p, check_only=True)
            self.assertEqual(open(p, encoding="utf-8").read(), broken)
            N.process(p, check_only=False)
            self.assertNotEqual(open(p, encoding="utf-8").read(), broken)


class ExplodeImplode(unittest.TestCase):
    def roundtrip(self, d):
        import format_data_json as F
        tmp = tempfile.mkdtemp()
        src = os.path.join(tmp, "data.json")
        with open(src, "w", encoding="utf-8", newline="") as fh:
            fh.write(F.canonical(d))          # the shape implode writes back
        before = open(src, "rb").read()
        md = os.path.join(tmp, "data.md")
        T.explode_one(src, md)
        return src, md, before

    def test_untouched_roundtrip_is_byte_identical(self):
        src, md, before = self.roundtrip(doc("one\ntwo", "three"))
        T.implode_one(md)
        self.assertEqual(open(src, "rb").read(), before)

    def test_an_edit_lands_and_nothing_else_moves(self):
        d = doc("one\ntwo", "three")
        src, md, _ = self.roundtrip(d)
        s = open(md, encoding="utf-8").read().replace("three", "**three**\n\nfour")
        open(md, "w", encoding="utf-8").write(s)
        _, changed = T.implode_one(md)
        self.assertEqual(changed, 1)
        got = json.load(open(src, encoding="utf-8"))
        self.assertEqual(got["items"][1]["sanskrit_text"], "**three**\n\nfour")
        self.assertEqual(got["items"][0]["sanskrit_text"], "one\ntwo")
        # everything that is not body text came across untouched
        self.assertEqual(got["items"][1]["source"], d["items"][1]["source"])
        self.assertEqual(got["schema"], d["schema"])
        self.assertEqual([i["id"] for i in got["items"]], [i["id"] for i in d["items"]])

    def test_the_result_is_always_strict_json(self):
        src, md, _ = self.roundtrip(doc("a"))
        s = open(md, encoding="utf-8").read().replace("\na\n", "\nline one\nline two\n")
        open(md, "w", encoding="utf-8").write(s)
        T.implode_one(md)
        raw = open(src, encoding="utf-8").read()
        json.loads(raw)                                   # strict: no exception
        # The newlines that remain are structure -- one per unit. None of them
        # is inside a string, which is what would break the parser.
        self.assertEqual(N.escape_control_chars_in_strings(raw)[1], 0)
        self.assertEqual(json.loads(raw)["items"][0]["sanskrit_text"], "line one\nline two")

    def test_context_lines_are_ignored_not_imported(self):
        src, md, _ = self.roundtrip(doc("a"))
        T.implode_one(md)
        self.assertEqual(json.load(open(src, encoding="utf-8"))["items"][0]["sanskrit_text"], "a")

    def test_a_deleted_marker_refuses_rather_than_guesses(self):
        src, md, _ = self.roundtrip(doc("a", "b"))
        s = "\n".join(l for l in open(md, encoding="utf-8").read().split("\n")
                      if not l.startswith("<!-- dge:unit 1"))
        open(md, "w", encoding="utf-8").write(s)
        with self.assertRaises(SystemExit) as cm:
            T.implode_one(md)
        self.assertIn("refusing to guess", str(cm.exception))

    def test_a_mismatched_id_refuses(self):
        src, md, _ = self.roundtrip(doc("a"))
        s = open(md, encoding="utf-8").read().replace("id=SM9:2", "id=SM9:999")
        open(md, "w", encoding="utf-8").write(s)
        with self.assertRaises(SystemExit) as cm:
            T.implode_one(md)
        self.assertIn("out of step", str(cm.exception))

    def test_a_file_that_is_not_ours_is_rejected_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "notes.md")
            open(p, "w", encoding="utf-8").write("# just some markdown\n")
            with self.assertRaises(SystemExit) as cm:
                T.implode_one(p)
            self.assertIn("dge:file", str(cm.exception))


class Formatter(unittest.TestCase):
    def canon(self, d):
        import format_data_json as F
        return F.canonical(d)

    def test_one_unit_per_line(self):
        text = self.canon(doc("a", "b", "c"))
        self.assertEqual(text.count("\n"), 5)      # open, 3 units, close, trailing
        self.assertEqual(json.loads(text), doc("a", "b", "c"))

    def test_a_change_to_one_unit_is_a_one_line_diff(self):
        before = self.canon(doc("a", "b", "c")).split("\n")
        after = self.canon(doc("a", "CHANGED", "c")).split("\n")
        differing = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
        self.assertEqual(len(differing), 1, "a one-unit edit must touch exactly one line")

    def test_the_legacy_shloka_dict_shape_is_handled_too(self):
        d = {"metadata": {"t": "x"}, "shlokas": {"1": {"sa": "a"}, "2": {"sa": "b"}}}
        text = self.canon(d)
        self.assertEqual(json.loads(text), d)
        self.assertEqual(text.count("\n"), 4)

    def test_a_shape_we_do_not_own_is_left_alone(self):
        self.assertIsNone(self.canon({"index": ["a", "b"]}))
        self.assertIsNone(self.canon([1, 2, 3]))

    def test_escaped_newlines_inside_text_do_not_become_real_ones(self):
        text = self.canon(doc("one\ntwo"))
        self.assertEqual(text.count("\n"), 3)      # structure only
        self.assertEqual(json.loads(text)["items"][0]["sanskrit_text"], "one\ntwo")

    def test_it_is_idempotent(self):
        once = self.canon(doc("a", "b"))
        self.assertEqual(self.canon(json.loads(once)), once)

    def test_the_whole_corpus_is_already_canonical(self):
        import format_data_json as F
        off = []
        for p in F.all_data_json(os.path.join(REPO, "data")):
            raw = open(p, encoding="utf-8").read()
            try:
                want = F.canonical(json.loads(raw))
            except ValueError:
                off.append(p); continue
            if want is not None and want != raw:
                off.append(os.path.relpath(p, REPO))
        self.assertEqual(off[:10], [], f"{len(off)} file(s) not in canonical shape")


class AgainstTheRealCorpus(unittest.TestCase):
    """A synthetic fixture cannot show that this survives real Devanagari,
    real footnotes and a 350 KB single line. A real file can."""

    def test_roundtrip_of_a_real_data_json_is_byte_identical(self):
        import glob
        files = sorted(glob.glob(os.path.join(REPO, "data", "**", "data.json"),
                                 recursive=True))[:25]
        checked = 0
        for src in files:
            try:
                d = json.load(open(src, encoding="utf-8"))
            except ValueError:
                continue
            items = T.find_items(d)
            if not items or not T.body_field(items):
                continue
            with tempfile.TemporaryDirectory() as tmp:
                copy = os.path.join(tmp, "data.json")
                raw = open(src, "rb").read()
                open(copy, "wb").write(raw)
                md = os.path.join(tmp, "data.md")
                T.explode_one(copy, md)
                T.implode_one(md, src_override=copy)
                self.assertEqual(json.load(open(copy, encoding="utf-8")), d, src)
            checked += 1
        self.assertGreater(checked, 0, "no real corpus file was exercised")

    def test_every_data_json_in_the_corpus_is_strict_json(self):
        import glob
        bad = []
        for p in glob.glob(os.path.join(REPO, "data", "**", "data.json"), recursive=True):
            try:
                json.load(open(p, encoding="utf-8"))
            except ValueError as e:
                bad.append(f"{os.path.relpath(p, REPO)}: {e}")
        self.assertEqual(bad, [], "files a browser's JSON.parse would reject")


if __name__ == "__main__":
    unittest.main()
