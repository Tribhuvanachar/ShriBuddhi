#!/usr/bin/env python3
"""Tests for build_sitemap.py.

Run: python3 tools/test_build_sitemap.py

The one failure mode that matters here is a URL search engines can crawl
but a reader can't reach -- an unpopulated grantha, or one curated out of
the reader nav via a per-entry `hidden` flag or a library-overrides.json
prefix. Everything else (slug derivation, lastmod precedence) exists to
support getting that filter right.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_sitemap import (  # noqa: E402
    grantha_slug, is_hidden_path, entry_lastmod, build_sitemap_xml, load_populated_granthas,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestGranthaSlug(unittest.TestCase):
    def test_strips_dge_data_prefix_and_data_json_suffix(self):
        self.assertEqual(
            grantha_slug("dge/data/agama/kashmir_shaivism/krama/shakta_vijnana/mula/data.json"),
            "agama/kashmir_shaivism/krama/shakta_vijnana/mula",
        )

    def test_matches_dge_core_js_dgeGranthaSlug_on_a_shallow_path(self):
        # dge/js/core.js: dgeLibraryPathToFetchPath strips leading 'dge/',
        # dgeGranthaSlug then strips 'data/' and the '/data.json' suffix.
        self.assertEqual(grantha_slug("dge/data/gita/data.json"), "gita")


class TestIsHiddenPath(unittest.TestCase):
    def test_hidden_when_slug_itself_is_listed(self):
        self.assertTrue(is_hidden_path("darshana/vedanta/dvaita/DvaitaVedantaIn", ["darshana/vedanta/dvaita/DvaitaVedantaIn"]))

    def test_hidden_when_an_ancestor_prefix_is_listed(self):
        self.assertTrue(is_hidden_path("darshana/vedanta/dvaita/DvaitaVedantaIn/sub", ["darshana/vedanta/dvaita"]))

    def test_not_hidden_when_no_prefix_matches(self):
        self.assertFalse(is_hidden_path("agama/kashmir_shaivism/krama", ["darshana/vedanta/dvaita"]))

    def test_not_hidden_when_prefix_list_is_empty(self):
        self.assertFalse(is_hidden_path("anything/at/all", []))


class TestEntryLastmod(unittest.TestCase):
    def test_prefers_the_later_of_addedAt_and_git_date(self):
        git_dates = {"p": "2026-08-27"}
        self.assertEqual(entry_lastmod("p", "2026-08-01", git_dates), "2026-08-27")

    def test_uses_addedAt_when_git_date_is_older(self):
        git_dates = {"p": "2026-08-01"}
        self.assertEqual(entry_lastmod("p", "2026-08-27", git_dates), "2026-08-27")

    def test_falls_back_to_addedAt_when_git_has_no_record(self):
        self.assertEqual(entry_lastmod("p", "2026-08-27", {}), "2026-08-27")

    def test_falls_back_to_git_date_when_addedAt_missing(self):
        self.assertEqual(entry_lastmod("p", None, {"p": "2026-08-27"}), "2026-08-27")

    def test_omits_lastmod_when_neither_is_known(self):
        self.assertIsNone(entry_lastmod("p", None, {}))


class TestLoadPopulatedGranthas(unittest.TestCase):
    def test_only_populated_entries_are_included(self):
        granthas = load_populated_granthas()
        self.assertTrue(granthas, "expected at least one populated grantha in the real library.json")
        for _, g in granthas:
            self.assertTrue(g.get("populated"))
            self.assertFalse(g.get("hidden"))


class TestBuildSitemapXml(unittest.TestCase):
    ORIGIN = "https://example.org"

    def test_is_well_formed_and_lists_every_populated_grantha(self):
        import xml.etree.ElementTree as ET
        xml_text = build_sitemap_xml(self.ORIGIN)
        root = ET.fromstring(xml_text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [el.text for el in root.findall("sm:url/sm:loc", ns)]
        self.assertEqual(len(locs), len(set(locs)), "no duplicate URLs")
        expected_count = len(load_populated_granthas())
        self.assertGreater(len(locs), expected_count, "static pages plus every populated grantha")
        self.assertTrue(any(loc.endswith("/dge/index.html") for loc in locs))

    def test_every_loc_is_under_the_given_origin(self):
        xml_text = build_sitemap_xml(self.ORIGIN)
        self.assertNotIn(self.ORIGIN + "//", xml_text)
        for line in xml_text.splitlines():
            if "<loc>" in line:
                self.assertIn(self.ORIGIN + "/", line)

    def test_is_deterministic(self):
        self.assertEqual(build_sitemap_xml(self.ORIGIN), build_sitemap_xml(self.ORIGIN))


if __name__ == "__main__":
    unittest.main()
