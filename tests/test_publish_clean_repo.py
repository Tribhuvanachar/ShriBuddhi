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
            ("firebase/functions/index.js", "exports.sendOtp = 1;"),
            ("firebase/functions/workflows.json", '{"workflows":[]}'),
            ("firebase-hosting.json", '{"hosting":{"public":"."}}'),
            ("sitemap.xml", "<loc>https://tribhuvanachar.github.io/Buddhi/x.html</loc>"),
            ("js/entity-linker.test.js", "assert(1)"),
            ("js/test-parity.js", "assert(1)"),
            ("js/audio.js", "cdn.jsdelivr.net/gh/Tribhuvanachar/buddhi-audio-data@main/"),
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

    def test_the_server_side_is_not_content_and_does_not_ship(self):
        """firebase/ is the site's backend, not text anyone reads.

        workflows.json in particular is a plain-English catalogue of the
        corpus pipeline; it was the most revealing file in the public tree.
        firebase-hosting.json is deploy config whose ignore list names
        private-side directories. Both belong to the private repository, and
        deploy-firebase-hosting.yml copies the config in at deploy time.
        """
        published = {rel for _, rel in publish.walk(self.src)}
        for excluded in ("firebase/functions/index.js",
                         "firebase/functions/workflows.json",
                         "firebase-hosting.json",
                         "js/entity-linker.test.js", "js/test-parity.js"):
            self.assertNotIn(excluded, published, excluded)
        # ...but js/ itself still publishes, the site runs on it
        self.assertIn("js/app.js", published)

    def test_the_old_repository_name_is_caught_and_stops_the_build(self):
        """A release that still points at the old repository is simply wrong.

        It tells a reader where to go looking and sends real traffic to a URL
        that is about to stop existing. The first version of this scanner only
        looked for the PRIVATE side, so the repository's own former name walked
        past it while sitemap.xml carried 1,245 absolute URLs under it.
        """
        hits = publish.scan(self.src)
        stale = [h for h in hits if h[1] in publish.STALE_NAMES]
        self.assertTrue(any(h[0] == "sitemap.xml" for h in stale), stale)
        # and --scan says so in its exit code, so a script cannot miss it
        self.assertEqual(1, publish.main(["--source", self.src, "--scan"]))

    def test_a_longer_repository_name_is_not_a_false_positive(self):
        """buddhi-audio-data and buddhi-kosha-data are separate repositories.

        They serve audio and dictionary data over jsDelivr. Renaming them
        would break live URLs, so whether they keep the old name is the
        lead's call -- but a checker that flags them as the site repository
        would push someone into making that call by accident.
        """
        hits = publish.scan(self.src)
        self.assertFalse([h for h in hits if h[0] == "js/audio.js"], hits)

    def test_it_refuses_to_build_while_the_old_name_is_there(self):
        self.assertEqual(3, publish.main(
            ["--source", self.src, "--out", self.out,
             "--author", "A Person <a@example.com>", "--message", "Release"]))
        self.assertFalse(os.path.exists(self.out), "nothing should have been written")

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
