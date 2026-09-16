"""publish_clean_repo.py: one commit, no parent, and an honest scan."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import publish_clean_repo as publish  # noqa: E402


class Fixture(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.src = os.path.join(self.root, "site")
        self.out = os.path.join(self.root, "clean")
        for rel, text in (
            ("index.html", "<h1>नमः</h1>"),
            ("js/app.js", "// reads BrahmaBuddhi through the gate\n"),
            ("data/ok.json", '{"sa":"धर्मः"}'),
            (".claude/settings.json", "{}"),
            ("docs/HANDOFF.md", "internal"),
            ("tools/build.py", "print(1)"),
            ("CLAUDE.md", "instructions"),
        ):
            full = os.path.join(self.src, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            open(full, "w").write(text)

    def tearDown(self):
        shutil.rmtree(self.root)


class WhatGetsPublished(Fixture):
    def test_tooling_and_process_directories_are_left_behind(self):
        published = {rel for _, rel in publish.walk(self.src)}
        self.assertIn("index.html", published)
        self.assertIn("data/ok.json", published)
        for excluded in (".claude/settings.json", "docs/HANDOFF.md",
                         "tools/build.py", "CLAUDE.md"):
            self.assertNotIn(excluded, published, excluded)

    def test_the_scan_names_the_private_side_without_editing_it(self):
        hits = publish.scan(self.src)
        self.assertTrue(any(h[1] == "BrahmaBuddhi" for h in hits))
        # and the file is untouched
        self.assertIn("BrahmaBuddhi", open(os.path.join(self.src, "js/app.js")).read())


class TheCommitHasNoParent(Fixture):
    def build(self):
        publish.stage(self.src, self.out)
        return publish.commit(self.out, "A Person <a@example.com>", "Release")

    def test_exactly_one_commit_and_it_has_no_parent(self):
        sha = self.build()
        log = subprocess.run(["git", "log", "--format=%H %P"], cwd=self.out,
                             capture_output=True, text=True).stdout.strip().split("\n")
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0].split(), [sha])      # a SHA and no parent after it

    def test_the_author_is_the_one_we_asked_for(self):
        self.build()
        who = subprocess.run(["git", "log", "-1", "--format=%an <%ae>"], cwd=self.out,
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(who, "A Person <a@example.com>")

    def test_the_published_tree_carries_no_git_directory_from_the_source(self):
        publish.stage(self.src, self.out)
        self.assertFalse(os.path.exists(os.path.join(self.out, ".git")))

    def test_staging_twice_does_not_accumulate(self):
        publish.stage(self.src, self.out)
        open(os.path.join(self.out, "stray.txt"), "w").write("left over")
        publish.stage(self.src, self.out)
        self.assertFalse(os.path.exists(os.path.join(self.out, "stray.txt")))


if __name__ == "__main__":
    unittest.main()
