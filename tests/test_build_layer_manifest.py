"""Tests for tools/build_layer_manifest.py — the stitchable-layer manifest.

Synthetic corpus, no network. The properties that matter (each mirrors a
real case measured on the live corpus, see MULTI_LAYER_READER_ARCHITECTURE.md):

- a grantha whose tika ids join its mula ids gets an entry, with per-layer
  matched counts (nyaya_sudha's shape);
- the importer's -N duplicate suffix still joins (anuvyakhyana's folded ids);
- a grantha whose tika uses a different id scheme entirely gets NO entry
  (tarkasangraha: mula sutra_N vs tika prakarana_N);
- an unjoinable layer inside a joinable grantha is listed with matched 0,
  so the drawer keeps its row instead of folding it away
  (nyaya_sudha's one-item tika_<adhikaranam> folders);
- labels come from the items' own tika_title/source.layer majority, and a
  body-text-sentence "label" (the karmavijaya-class mis-split folders) is
  truncated to stay a label.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from build_layer_manifest import build, base_id, layer_label  # noqa: E402


def write_layer(gdir: Path, folder: str, items, default_author=""):
    d = gdir / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / "data.json").write_text(json.dumps({
        "schema": "grantha_tika_text" if folder.startswith("tika_") else "grantha_mula_text",
        "default_author": default_author,
        "items": items,
    }, ensure_ascii=False), encoding="utf-8")


def item(iid, text="पाठः", layer="", tika_title=None):
    it = {"id": iid, "sanskrit_text": text, "source": {"layer": layer}}
    if tika_title is not None:
        it["tika_title"] = tika_title
    return it


class TestBaseId(unittest.TestCase):
    def test_strips_collision_suffix_only(self):
        self.assertEqual(base_id("DV_978-2"), "DV_978")
        self.assertEqual(base_id("DV_978"), "DV_978")
        self.assertEqual(base_id("sutra_1"), "sutra_1")  # trailing _N is not -N


class TestBuild(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_joinable_grantha_gets_entry_with_matched_counts(self):
        g = self.root / "sec" / "sudha_like"
        write_layer(g, "mula", [item("DV_1", layer="मूलम्"), item("DV_2", layer="मूलम्")],
                    "श्रीमदानन्दतीर्थभगवत्पादाचार्यः")
        write_layer(g, "tika_sudha",
                    [item("DV_1", layer="सुधा", tika_title="सुधा")], "श्रीजयतीर्थः")
        # joins via the -N duplicate suffix, both directions
        write_layer(g, "tika_parimala",
                    [item("DV_2-3", layer="परिमळ", tika_title="परिमळ")])
        # a one-item folder from a DIFFERENT leaf page: no id in mula
        write_layer(g, "tika_adhikarana",
                    [item("DV_99", layer="जिज्ञासाधिकरणम्")])
        out = build(self.root, {})
        self.assertIn("sec/sudha_like", out)
        entry = out["sec/sudha_like"]
        by_folder = {l["folder"]: l for l in entry["layers"]}
        self.assertEqual(by_folder["tika_sudha"]["matched"], 1)
        self.assertEqual(by_folder["tika_sudha"]["label"], "सुधा")
        self.assertEqual(by_folder["tika_parimala"]["matched"], 1)
        self.assertEqual(by_folder["tika_adhikarana"]["matched"], 0)
        self.assertEqual(entry["mulaItems"], 2)
        # sorted by matched desc: the unjoinable folder comes last
        self.assertEqual(entry["layers"][-1]["folder"], "tika_adhikarana")

    def test_disjoint_id_scheme_gets_no_entry(self):
        g = self.root / "nyaya" / "tarkasangraha_like"
        write_layer(g, "mula", [item("sutra_1"), item("sutra_2")])
        write_layer(g, "tika_dipika", [item("prakarana_1"), item("prakarana_2")])
        self.assertEqual(build(self.root, {}), {})

    def test_mula_only_grantha_gets_no_entry(self):
        g = self.root / "sec" / "solo"
        write_layer(g, "mula", [item("DV_1")])
        self.assertEqual(build(self.root, {}), {})

    def test_title_from_library_catalog_strips_layer_suffix(self):
        g = self.root / "sec" / "titled"
        write_layer(g, "mula", [item("DV_1")])
        write_layer(g, "tika_x", [item("DV_1", tika_title="टीका")])
        titles = {"dge/data/sec/titled/mula/data.json": "श्रीमन्न्यायसुधा — mula"}
        out = build(self.root, titles)
        self.assertEqual(out["sec/titled"]["title"], "श्रीमन्न्यायसुधा")

    def test_garbage_author_withheld(self):
        g = self.root / "sec" / "misattributed"
        write_layer(g, "mula", [item("DV_1")])
        write_layer(g, "tika_y", [item("DV_1", tika_title="टीका")],
                    default_author="आद्यसूत्रापव्याख्यानस्य " * 10)
        out = build(self.root, {})
        self.assertEqual(out["sec/misattributed"]["layers"][0]["author"], "")


class TestLayerLabel(unittest.TestCase):
    def test_majority_wins(self):
        items = [item("a", tika_title="सुधा"), item("b", tika_title="सुधा"),
                 item("c", tika_title="अन्यत्")]
        self.assertEqual(layer_label(items, "tika_sudha"), "सुधा")

    def test_body_text_sentence_is_truncated(self):
        long = "ॐ न प्रयोजनवत्त्वात् ॐ ।। प्रयोजनवत्त्वहेतोरिति । सूत्रे प्रयोजनवत्त्वादित्यस्य हि"
        label = layer_label([item("a", tika_title=long)], "tika_om")
        self.assertLessEqual(len(label), 40)
        self.assertTrue(label.endswith("…"))

    def test_falls_back_to_folder_slug(self):
        self.assertEqual(layer_label([item("a")], "tika_sudha"), "sudha")


if __name__ == "__main__":
    unittest.main()
