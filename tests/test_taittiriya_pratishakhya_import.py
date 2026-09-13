"""dge/data/vedanga/shiksha/pratishakhya/taittiriya_pratishakhya/data.json

Checks the committed output of
tools/pratishakhya/import_taittiriya_pratishakhya.py (no network here, per
run_tests.sh). Guards the total count and a few hand-checked sutras with
Whitney's own translation, and that the file is honest about its one real
limitation: no traditional adhyaya.sutra numbering survived into this
digitization.
"""

import json
import os
import unittest

REPO = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(
    REPO, "dge", "data", "vedanga", "shiksha", "pratishakhya",
    "taittiriya_pratishakhya", "data.json",
)


class TaittiriyaPratishakhyaData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA_PATH, encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.by_id = {item["id"]: item for item in cls.data["items"]}

    def test_total_count(self):
        self.assertEqual(len(self.data["items"]), 545)

    def test_licence_and_provenance_recorded(self):
        self.assertIn("CC BY-NC-SA", self.data["licence"])
        self.assertIn("sanskritlibrary.org", self.data["source_url"])

    def test_missing_numbering_documented_not_invented(self):
        # No item should have a fabricated adhyaya/sutra number -- this
        # source carries none, and the importer must not guess one.
        for item in self.data["items"]:
            self.assertIsNone(item["adhyaya"])
            self.assertIsNone(item["sutra"])
        self.assertIn("NO traditional adhyaya.sutra numbering", self.data["note"])

    def test_opening_sutras_with_whitney_translation(self):
        expected = {
            "seq_001": ("अथ वर्णसमाम्नायः।", "Now the list of sounds."),
            "seq_002": ("अथ नवादितः समानाक्षराणि।", "Now the nine at the beginning are simple vowels."),
        }
        for seq_id, (deva, translation) in expected.items():
            with self.subTest(sutra=seq_id):
                self.assertEqual(self.by_id[seq_id]["text_devanagari"], deva)
                self.assertEqual(self.by_id[seq_id]["translation_whitney"], translation)
                self.assertFalse(self.by_id[seq_id]["has_uncertain_reading"])

    def test_sequential_ids_match_order(self):
        for i, item in enumerate(self.data["items"], start=1):
            self.assertEqual(item["id"], f"seq_{i:03d}")
            self.assertEqual(item["sequence"], i)


if __name__ == "__main__":
    unittest.main()
