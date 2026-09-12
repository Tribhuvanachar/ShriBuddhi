"""End-to-end: import (offline) -> build index -> verify.

Uses --offline-dir so the whole pipeline is exercised without network, which
is what makes it runnable in CI and in a sandbox with no scraping egress.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from kavya import build_kavya_index, import_kavya, validate_data, verify_kavya

F = os.path.join(os.path.dirname(__file__), "fixtures")


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kavya-test-")
        self.data = os.path.join(self.tmp, "data")
        self.report = os.path.join(self.tmp, "report.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _import(self, works, sources):
        return import_kavya.main([
            "--works", works, "--sources", sources,
            "--data-root", self.data, "--offline-dir", F,
            "--report", self.report])

    def _layer(self, work, layer):
        with open(os.path.join(self.data, "kavya_alankara", work, layer,
                               "data.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_full_run(self):
        self.assertEqual(self._import("meghaduta", "sanskritsahitya"), 0)
        self.assertEqual(self._import("raghuvamsha", "gretil"), 0)

        # -- layers landed where the reader expects them ------------------
        base = os.path.join(self.data, "kavya_alankara")
        self.assertEqual(sorted(os.listdir(base)), ["meghaduta", "raghuvamsha"])
        self.assertEqual(
            sorted(os.listdir(os.path.join(base, "meghaduta"))),
            ["anvaya", "mula", "padaccheda", "translation_en",
             "translation_hi", "vallabhadeva"])

        # -- commentary is bhashya, mula is sanskrit_text -----------------
        vd = self._layer("meghaduta", "vallabhadeva")
        self.assertEqual(vd["grantha"]["layer_kind"], "tika")
        self.assertEqual(vd["grantha"]["commentator"], "वल्लभदेवः")
        self.assertTrue(vd["items"][0]["shlokas"][0]["bhashya"])

        # -- provenance is recorded on every layer ------------------------
        for lid in os.listdir(os.path.join(base, "meghaduta")):
            g = self._layer("meghaduta", lid)["grantha"]
            self.assertTrue(g["source"].get("url"), lid)
            self.assertTrue(g["license"], lid)

        # -- schema validation --------------------------------------------
        self.assertEqual(validate_data.main(["--data-root", self.data]), 0)

        # -- index ---------------------------------------------------------
        self.assertEqual(
            build_kavya_index.main(["--data-root", self.data]), 0)
        with open(os.path.join(base, "_index.json"), encoding="utf-8") as fh:
            idx = json.load(fh)
        self.assertEqual(idx["totals"]["works"], 2)
        ids = [w["id"] for w in idx["works"]]
        self.assertEqual(ids, ["meghaduta", "raghuvamsha"])
        megha = idx["works"][0]
        self.assertEqual(megha["name_sa"], "मेघदूतम्")
        self.assertEqual(megha["genre_path"][1], "shravya")
        self.assertEqual([u["id"] for u in megha["units"]], ["1", "2"])
        self.assertTrue(idx["taxonomy"])

        # -- layer order: mula, then the commentary, then the rest --------
        order = [l["id"] for l in megha["layers"]]
        self.assertEqual(order[0], "mula")
        self.assertEqual(order[1], "vallabhadeva")

        # -- reader paths resolve -----------------------------------------
        for l in megha["layers"]:
            self.assertTrue(os.path.exists(
                os.path.join(self.data, l["path"].replace("data/", "", 1))),
                l["path"])

        # -- verify ---------------------------------------------------------
        self.assertEqual(verify_kavya.main(["--data-root", self.data]), 0)

    def test_rerun_is_idempotent(self):
        self._import("meghaduta", "sanskritsahitya")
        first = self._layer("meghaduta", "mula")
        self._import("meghaduta", "sanskritsahitya")
        second = self._layer("meghaduta", "mula")
        self.assertEqual(first["grantha"]["counts"], second["grantha"]["counts"])
        self.assertEqual(first["items"], second["items"])

    def test_probe_writes_nothing_and_names_the_undeclared_key(self):
        rc = import_kavya.main([
            "--works", "meghaduta", "--sources", "sanskritsahitya",
            "--data-root", self.data, "--offline-dir", F,
            "--probe-only", "--report", self.report])
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(os.path.join(self.data, "kavya_alankara")))
        with open(self.report, encoding="utf-8") as fh:
            rep = json.load(fh)
        probe = rep["works"]["meghaduta"]["sources"]["sanskritsahitya"]
        self.assertIn("zz", probe["unknown_keys"])

    def test_verify_fails_on_an_ai_flagged_commentary(self):
        self._import("meghaduta", "sanskritsahitya")
        build_kavya_index.main(["--data-root", self.data])
        path = os.path.join(self.data, "kavya_alankara", "meghaduta",
                            "vallabhadeva", "data.json")
        with open(path, encoding="utf-8") as fh:
            layer = json.load(fh)
        layer["grantha"]["ai_generated"] = True
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(layer, fh, ensure_ascii=False)
        self.assertEqual(
            verify_kavya.main(["--data-root", self.data, "--no-index-check"]), 1)

    def test_verify_fails_on_a_commentary_that_misses_the_mula(self):
        self._import("meghaduta", "sanskritsahitya")
        build_kavya_index.main(["--data-root", self.data])
        path = os.path.join(self.data, "kavya_alankara", "meghaduta",
                            "vallabhadeva", "data.json")
        with open(path, encoding="utf-8") as fh:
            layer = json.load(fh)
        layer["items"][0]["shlokas"][0]["id"] = "9.9"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(layer, fh, ensure_ascii=False)
        self.assertEqual(
            verify_kavya.main(["--data-root", self.data, "--no-index-check"]), 1)

    def test_verify_fails_on_a_stale_index(self):
        self._import("meghaduta", "sanskritsahitya")
        build_kavya_index.main(["--data-root", self.data])
        self._import("raghuvamsha", "gretil")     # index now stale
        self.assertEqual(verify_kavya.main(["--data-root", self.data]), 1)

    def test_scan_only_works_are_reported_not_silently_dropped(self):
        import_kavya.main([
            "--all", "--sources", "nothing", "--data-root", self.data,
            "--offline-dir", F, "--report", self.report])
        with open(self.report, encoding="utf-8") as fh:
            rep = json.load(fh)
        ids = [w["id"] for w in rep["skipped_scan_only"]]
        # No machine-readable source anywhere -> must appear in the register.
        self.assertIn("anandavrindavanachampu", ids)
        self.assertIn("yashastilaka", ids)
        # Has a GRETIL mula even though its commentary is scan-only, so it is
        # NOT a scan-only work.
        # Anandavrindavanacampu is the stable example: no digital text of it
        # exists anywhere, so it will be in the register whatever a later
        # source hunt turns up. Naishadhiyacarita used to stand here and no
        # longer belongs -- sa.wikisource has all 22 sargas, in five pages.
        self.assertIn("anandavrindavanachampu", ids)
        note = [w for w in rep["skipped_scan_only"]
                if w["id"] == "anandavrindavanachampu"][0]
        self.assertIn("NO digital text", note["register"]["status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
