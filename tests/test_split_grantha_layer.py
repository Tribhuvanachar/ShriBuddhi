"""Tests for tools/split_grantha_layer.py — scholar-sized layer part files.

Properties that matter (each mirrors a real case measured on the corpus,
see the tool's own docstring):

- a ref's units, when contiguous, never split across two parts;
- a ref value that recurs later, non-contiguously, is NOT pulled together
  with its earlier occurrence — reading order is never rewritten
  (tippani_vakyartharatnamala's "1.1.0" bucket does exactly this);
- concatenating every part's units, in part order, reconstructs the
  original units list exactly;
- data.json becomes a grantha_layer_v2_index pointing at the parts, at the
  SAME path, so nothing that already points there needs to change.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from split_grantha_layer import group_by_ref, plan_parts, split_layer  # noqa: E402


def unit(ref, text="पाठः"):
    return {"id": ref + ".p1", "ref": ref, "text": text}


class TestGroupByRef(unittest.TestCase):
    def test_contiguous_runs_grouped(self):
        units = [unit("1.1.1"), unit("1.1.1"), unit("1.1.2")]
        groups = group_by_ref(units)
        self.assertEqual([r for r, _ in groups], ["1.1.1", "1.1.2"])
        self.assertEqual(len(groups[0][1]), 2)

    def test_non_contiguous_recurrence_not_merged(self):
        # "1.1.0" appears, then other refs, then "1.1.0" again -- must stay
        # as two separate groups in original order, not one merged group.
        units = [unit("1.1.0"), unit("1.2.0"), unit("1.1.0")]
        groups = group_by_ref(units)
        self.assertEqual([r for r, _ in groups], ["1.1.0", "1.2.0", "1.1.0"])

    def test_concatenation_reconstructs_original_order(self):
        units = [unit("1.1.0"), unit("1.1.0"), unit("1.2.0"),
                 unit("1.1.0"), unit("1.3.0")]
        groups = group_by_ref(units)
        flat = [u for _, g in groups for u in g]
        self.assertEqual(flat, units)


class TestPlanParts(unittest.TestCase):
    def test_never_splits_a_group(self):
        # A single ref's group whose own size already exceeds the target
        # still lands whole in one part, never divided.
        big_text = "अ" * 500
        units = [unit("1.1.1", big_text), unit("1.1.1", big_text), unit("1.1.2")]
        parts = plan_parts(units, target_bytes=200)
        # group (1.1.1, 1.1.1) stays together as its own part despite
        # exceeding the 200-byte target
        self.assertEqual(len(parts[0]), 2)
        self.assertTrue(all(u["ref"] == "1.1.1" for u in parts[0]))

    def test_splits_at_group_boundary_once_target_exceeded(self):
        units = [unit(f"1.1.{i}", "अ" * 50) for i in range(1, 6)]
        parts = plan_parts(units, target_bytes=150)
        self.assertGreater(len(parts), 1)
        # every unit still present, in order, none duplicated or dropped
        flat = [u for p in parts for u in p]
        self.assertEqual(flat, units)

    def test_empty_part_never_produced(self):
        units = [unit("1.1.1", "अ" * 1000)]
        parts = plan_parts(units, target_bytes=10)
        self.assertEqual(len(parts), 1)
        self.assertEqual(len(parts[0]), 1)


class TestSplitLayer(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "tika_x"
        self.dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, units):
        (self.dir / "data.json").write_text(json.dumps({
            "schema": "grantha_layer_v2", "work": "w", "layer": "tika_x",
            "units": units,
        }, ensure_ascii=False), encoding="utf-8")

    def test_round_trip_identical_units_same_order(self):
        units = [unit(f"1.1.{i}", "पाठः " * 20) for i in range(1, 30)]
        self._write(units)
        changed = split_layer(self.dir, target_bytes=500, check=False)
        self.assertTrue(changed)

        index = json.loads((self.dir / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schema"], "grantha_layer_v2_index")
        self.assertEqual(index["units_total"], len(units))
        self.assertGreater(len(index["parts"]), 1)

        reconstructed = []
        for name in index["parts"]:
            part = json.loads((self.dir / name).read_text(encoding="utf-8"))
            self.assertEqual(part["schema"], "grantha_layer_v2")
            reconstructed.extend(part["units"])
        self.assertEqual(reconstructed, units)

    def test_small_file_left_untouched(self):
        units = [unit("1.1.1")]
        self._write(units)
        changed = split_layer(self.dir, target_bytes=800_000, check=False)
        self.assertFalse(changed)
        doc = json.loads((self.dir / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "grantha_layer_v2")  # unchanged, not an index

    def test_already_split_is_skipped(self):
        (self.dir / "data.json").write_text(json.dumps({
            "schema": "grantha_layer_v2_index", "work": "w", "layer": "tika_x",
            "units_total": 1, "parts": ["part-001.json"],
        }, ensure_ascii=False), encoding="utf-8")
        changed = split_layer(self.dir, target_bytes=1, check=False)
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
