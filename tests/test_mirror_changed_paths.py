"""mirror_changed_paths.py: the mirror must survive a rebuild that deletes."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import mirror_changed_paths as mirror  # noqa: E402


def status_blob(*entries):
    """What `git status --porcelain -z` writes for these records."""
    return b"\0".join(e.encode() for e in entries) + b"\0"


class Parsing(unittest.TestCase):
    def test_a_path_with_a_space_survives(self):
        # awk '{print $2}' took "vrtta" and dropped " reports.json".
        got = mirror.records(status_blob(" M data/vrtta reports.json"))
        self.assertEqual(got, [(" M", "data/vrtta reports.json", None)])

    def test_a_rename_carries_its_old_path(self):
        got = mirror.records(status_blob("R  new.json", "old.json"))
        self.assertEqual(got, [("R ", "new.json", "old.json")])

    def test_a_rename_does_not_swallow_the_next_entry(self):
        got = mirror.records(status_blob("R  new.json", "old.json",
                                         " M other.json"))
        self.assertEqual([r[1] for r in got], ["new.json", "other.json"])


class Mirroring(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.source = os.path.join(self.root, "source")
        self.destination = os.path.join(self.root, "destination")
        os.makedirs(os.path.join(self.source, "shards"))
        os.makedirs(os.path.join(self.destination, "shards"))
        self.cwd = os.getcwd()
        os.chdir(self.source)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.root)

    def write(self, where, path, text="{}"):
        full = os.path.join(where, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as handle:
            handle.write(text)

    def test_a_deleted_shard_is_removed_not_copied(self):
        # The actual failure: a dhatu lost its last prayoga, its shard was
        # deleted, and the old `cp` died with "cannot stat".
        self.write(self.destination, "shards/01.0344.json", "stale")
        copied, removed = mirror.mirror(
            mirror.records(status_blob(" D shards/01.0344.json")),
            self.destination)
        self.assertEqual((copied, removed), (0, 1))
        self.assertFalse(os.path.exists(
            os.path.join(self.destination, "shards/01.0344.json")))

    def test_a_deletion_the_mirror_never_had_is_not_an_error(self):
        copied, removed = mirror.mirror(
            mirror.records(status_blob(" D shards/absent.json")),
            self.destination)
        self.assertEqual((copied, removed), (0, 0))

    def test_a_changed_shard_is_copied_over(self):
        self.write(self.source, "shards/01.0001.json", "fresh")
        mirror.mirror(mirror.records(status_blob(" M shards/01.0001.json")),
                      self.destination)
        with open(os.path.join(self.destination, "shards/01.0001.json")) as f:
            self.assertEqual(f.read(), "fresh")

    def test_a_rename_leaves_no_copy_behind(self):
        self.write(self.source, "shards/new.json", "moved")
        self.write(self.destination, "shards/old.json", "moved")
        copied, removed = mirror.mirror(
            mirror.records(status_blob("R  shards/new.json",
                                       "shards/old.json")),
            self.destination)
        self.assertEqual((copied, removed), (1, 1))
        self.assertFalse(os.path.exists(
            os.path.join(self.destination, "shards/old.json")))

    def test_a_new_directory_is_created_for_a_new_shard(self):
        self.write(self.source, "deep/nest/new.json", "new")
        mirror.mirror(mirror.records(status_blob("?? deep/nest/new.json")),
                      self.destination)
        self.assertTrue(os.path.exists(
            os.path.join(self.destination, "deep/nest/new.json")))


class AgainstRealGit(unittest.TestCase):
    """The parser reads what git actually writes, not what we think it does."""

    def test_a_real_delete_and_a_real_rename_round_trip(self):
        root = tempfile.mkdtemp()
        try:
            run = lambda *a: subprocess.run(a, cwd=root, check=True,
                                            capture_output=True)
            run("git", "init", "-q")
            run("git", "config", "user.email", "t@example.com")
            run("git", "config", "user.name", "t")
            for name in ("gone.json", "old name.json"):
                with open(os.path.join(root, name), "w") as handle:
                    handle.write("{}")
            run("git", "add", "-A")
            run("git", "commit", "-qm", "seed")
            os.remove(os.path.join(root, "gone.json"))
            run("git", "mv", "old name.json", "new name.json")
            blob = subprocess.run(["git", "status", "--porcelain", "-z"],
                                  cwd=root, check=True,
                                  capture_output=True).stdout
            got = {r[1]: r for r in mirror.records(blob)}
            self.assertIn("gone.json", got)
            self.assertIn(got["gone.json"][0], mirror.DELETED)
            self.assertEqual(got["new name.json"][2], "old name.json")
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
