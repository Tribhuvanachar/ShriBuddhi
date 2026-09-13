"""The staged-OCR index the admin pages read.

The interesting part is not that it lists files — it is which files, and how it
counts them. Three real shapes in data/ocr_staging/ disagree about what `pages`
means, and getting that wrong puts entries in the dropdown that open to an
error, or reports a 20-page slice as "2 pages".
"""
import json
import os
import tempfile
import unittest

from build_ocr_staging_index import build, engine_of, scan, shape_of


def write(root, rel, obj):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return p


class Shape(unittest.TestCase):
    def test_pages_of_objects_is_the_content(self):
        self.assertEqual(shape_of({"pages": [{"page": 1, "html": "<p>a</p>"}]}), "pages")

    def test_a_two_number_pages_is_a_range_not_the_content(self):
        # vasu_siddhanta_kaumudi carries pages:[9, 28] beside the real entries[].
        d = {"pages": [9, 28], "entries": [{"page": 11, "sk": "…"}]}
        self.assertEqual(shape_of(d), "entries")

    def test_an_integer_pages_is_a_statistic_and_is_not_offered(self):
        # upanishad_tippani/*/summary.json is a count, not a staged reading.
        self.assertEqual(shape_of({"pages": 290, "blocks": 549}), "")

    def test_a_file_with_no_readable_shape_is_not_offered(self):
        # the bhagavata_saroddhara verification queues are items[].
        self.assertEqual(shape_of({"items": [{"id": "BS_V163"}]}), "")

    def test_empty_lists_do_not_count(self):
        self.assertEqual(shape_of({"entries": []}), "")


class Engine(unittest.TestCase):
    def test_sarvam_names_itself(self):
        self.assertEqual(engine_of({"engine": "sarvam-docai"}), "sarvam")

    def test_a_gemini_model_means_vision_text_it_proofread(self):
        # Gemini never reads a scan; it proofreads Vision's output.
        self.assertEqual(engine_of({"model": "gemini-flash-latest"}), "vision")

    def test_a_file_that_says_nothing_says_nothing(self):
        self.assertEqual(engine_of({"pdf": "x.pdf"}), "")


class Counting(unittest.TestCase):
    def test_entries_are_counted_by_distinct_page(self):
        d = {"entries": [{"page": 11}, {"page": 11}, {"page": 12}]}
        with tempfile.TemporaryDirectory() as td:
            write(td, "work/a.json", d)
            (e,) = scan(td)
        self.assertEqual(e["pages"], 2)
        self.assertEqual(e["shape"], "entries")
        self.assertEqual(e["work"], "work")

    def test_a_declared_range_is_kept(self):
        d = {"pages": [9, 28], "entries": [{"page": 11}]}
        with tempfile.TemporaryDirectory() as td:
            write(td, "work/a.json", d)
            (e,) = scan(td)
        self.assertEqual(e["range"], [9, 28])


class Index(unittest.TestCase):
    def test_the_index_never_lists_itself(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "work/a.json", {"pages": [{"page": 1}]})
            write(td, "index.json", {"files": ["stale"]})
            self.assertEqual(build(td)["files"], ["work/a.json"])

    def test_files_is_a_plain_sorted_path_list(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "w/b.json", {"pages": [{"page": 1}]})
            write(td, "w/a.json", {"pages": [{"page": 1}]})
            idx = build(td)
        self.assertEqual(idx["files"], ["w/a.json", "w/b.json"])
        self.assertEqual(idx["count"], 2)

    def test_unreadable_json_is_skipped_rather_than_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "w/good.json", {"pages": [{"page": 1}]})
            with open(os.path.join(td, "w", "bad.json"), "w", encoding="utf-8") as fh:
                fh.write("{not json")
            self.assertEqual(build(td)["files"], ["w/good.json"])


if __name__ == "__main__":
    unittest.main()
