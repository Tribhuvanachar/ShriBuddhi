"""publish_direct_fetch_rewrite.py: every listed string exists exactly
once in the real source, and the rewrite itself behaves."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import publish_direct_fetch_rewrite as rewriter  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class EveryListedStringStillMatchesTheRealSource(unittest.TestCase):
    """The whole point of listing an exact old string, rather than a
    pattern, is that source drift is caught here -- at test time -- instead
    of silently doing nothing (or rewriting the wrong span) at build time.
    """
    def test_each_rewrite_target_is_found_exactly_once(self):
        by_file = {}
        problems = []
        for rel, old, _new in rewriter.REWRITES:
            path = os.path.join(REPO, rel)
            if rel not in by_file:
                if not os.path.isfile(path):
                    problems.append(f"{rel}: file does not exist")
                    by_file[rel] = ""
                    continue
                with open(path, encoding="utf-8") as fh:
                    by_file[rel] = fh.read()
            count = by_file[rel].count(old)
            if count != 1:
                problems.append(f"{rel}: found {count} time(s), expected 1: {old!r}")
        self.assertEqual([], problems, "\n".join(problems))

    def test_no_rewrite_pair_is_a_no_op(self):
        for rel, old, new in rewriter.REWRITES:
            self.assertNotEqual(old, new, rel)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "js"))
        with open(os.path.join(self.root, "js", "x.js"), "w") as fh:
            fh.write("const a = 1;\nfetch('admin/config/x.json');\nconst b = 2;\n")

    def tearDown(self):
        shutil.rmtree(self.root)


class RewriteApplies(Fixture):
    def test_the_listed_string_is_replaced_and_nothing_else_moves(self):
        pairs = (("js/x.js", "fetch('admin/config/x.json');", "fetch('config/x.json');"),)
        n = rewriter.rewrite(self.root, pairs=pairs)
        self.assertEqual(1, n)
        text = open(os.path.join(self.root, "js", "x.js")).read()
        self.assertIn("fetch('config/x.json');", text)
        self.assertNotIn("admin/config", text)
        self.assertIn("const a = 1;", text)
        self.assertIn("const b = 2;", text)

    def test_a_missing_string_raises_rather_than_silently_skipping(self):
        pairs = (("js/x.js", "this text is not in the fixture", "whatever"),)
        with self.assertRaises(SystemExit):
            rewriter.rewrite(self.root, pairs=pairs)

    def test_a_duplicated_string_raises_rather_than_guessing_which_one(self):
        with open(os.path.join(self.root, "js", "x.js"), "w") as fh:
            fh.write("fetch('admin/config/x.json');\nfetch('admin/config/x.json');\n")
        pairs = (("js/x.js", "fetch('admin/config/x.json');", "fetch('config/x.json');"),)
        with self.assertRaises(SystemExit):
            rewriter.rewrite(self.root, pairs=pairs)

    def test_a_missing_file_raises(self):
        pairs = (("js/does_not_exist.js", "x", "y"),)
        with self.assertRaises(SystemExit):
            rewriter.rewrite(self.root, pairs=pairs)


if __name__ == "__main__":
    unittest.main()
