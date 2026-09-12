#!/usr/bin/env python3
"""Tests for set_site_url.py.

Run: python3 tools/test_set_site_url.py

This script rewrites URLs inside shipped HTML, so the cases that matter
most are the ones where it must NOT rewrite something: a marker with no
tag after it, an unmarked URL, a marker whose tag was deleted. A
find-and-replace that quietly hits the wrong line is worse than one that
refuses to run.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from set_site_url import (  # noqa: E402
    SiteUrlError, build_url, normalize_origin, rewrite_text, load_config, MANAGED_FILES,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

GH = "https://tribhuvanachar.github.io/bhumandala"
CUSTOM = "https://www.sarvamula.org"


class TestNormalizeOrigin(unittest.TestCase):
    def test_strips_trailing_slashes(self):
        self.assertEqual(normalize_origin("https://x.org/"), "https://x.org")
        self.assertEqual(normalize_origin("https://x.org///"), "https://x.org")

    def test_keeps_a_path_prefix(self):
        # GitHub Pages serves this project under /bhumandala, so the origin
        # legitimately carries a path. Stripping it would break every URL.
        self.assertEqual(normalize_origin(GH + "/"), GH)

    def test_trims_surrounding_whitespace(self):
        self.assertEqual(normalize_origin("  https://x.org  "), "https://x.org")

    def test_rejects_anything_that_is_not_an_origin(self):
        for bad in ["", "   ", "sarvamula.org", "ftp://x.org", "//x.org", "https://"]:
            with self.assertRaises(SiteUrlError, msg=f"{bad!r} should be rejected"):
                normalize_origin(bad)


class TestBuildUrl(unittest.TestCase):
    def test_joins_origin_and_path(self):
        self.assertEqual(build_url(CUSTOM, "dge/images/x.jpg"), CUSTOM + "/dge/images/x.jpg")

    def test_does_not_double_the_slash(self):
        self.assertEqual(build_url(CUSTOM + "/", "/dge/x.jpg"), CUSTOM + "/dge/x.jpg")

    def test_preserves_a_path_prefix_in_the_origin(self):
        self.assertEqual(build_url(GH, "dge/x.jpg"), GH + "/dge/x.jpg")


class TestRewrite(unittest.TestCase):
    def test_rewrites_a_marked_tag(self):
        html = ('<!-- site-url: dge/images/g.jpg -->\n'
                '<meta property="og:image" content="https://old.example/dge/images/g.jpg">\n')
        out, changes = rewrite_text(html, CUSTOM)
        self.assertIn(f'content="{CUSTOM}/dge/images/g.jpg"', out)
        self.assertEqual(len(changes), 1)

    def test_reports_no_change_when_already_correct(self):
        html = (f'<!-- site-url: dge/x.jpg -->\n'
                f'<meta property="og:image" content="{CUSTOM}/dge/x.jpg">\n')
        out, changes = rewrite_text(html, CUSTOM)
        self.assertEqual(changes, [])
        self.assertEqual(out, html)

    def test_is_idempotent(self):
        html = ('<!-- site-url: dge/x.jpg -->\n'
                '<meta property="og:image" content="https://old.example/dge/x.jpg">\n')
        once, _ = rewrite_text(html, CUSTOM)
        twice, changes = rewrite_text(once, CUSTOM)
        self.assertEqual(once, twice)
        self.assertEqual(changes, [])

    def test_round_trips_between_domains(self):
        html = (f'<!-- site-url: dge/x.jpg -->\n'
                f'<meta property="og:image" content="{GH}/dge/x.jpg">\n')
        to_custom, _ = rewrite_text(html, CUSTOM)
        self.assertIn(f'content="{CUSTOM}/dge/x.jpg"', to_custom)
        back, _ = rewrite_text(to_custom, GH)
        self.assertEqual(back, html)

    def test_leaves_unmarked_urls_completely_alone(self):
        # Fonts, CDNs, and any third-party absolute URL must never be
        # touched — only what a marker explicitly claims.
        html = ('<link href="https://fonts.googleapis.com/css2?family=Inter">\n'
                '<script src="https://cdn.jsdelivr.net/npm/thing@1/x.js"></script>\n')
        out, changes = rewrite_text(html, CUSTOM)
        self.assertEqual(out, html)
        self.assertEqual(changes, [])

    def test_rewrites_only_the_tag_the_marker_governs(self):
        html = ('<!-- site-url: dge/a.jpg -->\n'
                '<meta property="og:image" content="https://old.example/dge/a.jpg">\n'
                '<link href="https://fonts.googleapis.com/css2">\n')
        out, _ = rewrite_text(html, CUSTOM)
        self.assertIn("https://fonts.googleapis.com/css2", out)
        self.assertIn(f'content="{CUSTOM}/dge/a.jpg"', out)

    def test_handles_several_markers(self):
        html = ('<!-- site-url: a.jpg -->\n<meta content="https://old.example/a.jpg">\n'
                '<!-- site-url: b.jpg -->\n<meta content="https://old.example/b.jpg">\n')
        out, changes = rewrite_text(html, CUSTOM)
        self.assertEqual(len(changes), 2)
        self.assertIn(f'content="{CUSTOM}/a.jpg"', out)
        self.assertIn(f'content="{CUSTOM}/b.jpg"', out)

    def test_works_with_single_quoted_attributes(self):
        html = ("<!-- site-url: a.jpg -->\n<meta content='https://old.example/a.jpg'>\n")
        out, _ = rewrite_text(html, CUSTOM)
        self.assertIn(f"content='{CUSTOM}/a.jpg'", out)

    def test_handles_href_and_src_too(self):
        for attr in ["href", "src"]:
            html = (f'<!-- site-url: a.jpg -->\n<tag {attr}="https://old.example/a.jpg">\n')
            out, _ = rewrite_text(html, CUSTOM)
            self.assertIn(f'{attr}="{CUSTOM}/a.jpg"', out)

    def test_refuses_a_marker_with_no_tag_after_it(self):
        # Someone deleted the tag but left the marker. Rewriting nothing
        # silently would hide that; rewriting the next URL found further
        # down would corrupt an unrelated tag.
        html = '<!-- site-url: a.jpg -->\n<p>no url here</p>\n'
        with self.assertRaises(SiteUrlError):
            rewrite_text(html, CUSTOM)

    def test_refuses_when_the_nearest_url_is_far_below(self):
        html = ('<!-- site-url: a.jpg -->\n' + '<p>filler</p>\n' * 10 +
                '<link href="https://fonts.googleapis.com/css2">\n')
        with self.assertRaises(SiteUrlError):
            rewrite_text(html, CUSTOM)

    def test_tolerates_whitespace_variation_in_the_marker(self):
        for marker in ['<!-- site-url: a.jpg -->', '<!--site-url:a.jpg-->', '<!--  site-url:   a.jpg  -->']:
            html = f'{marker}\n<meta content="https://old.example/a.jpg">\n'
            out, _ = rewrite_text(html, CUSTOM)
            self.assertIn(f'content="{CUSTOM}/a.jpg"', out, f"marker form failed: {marker}")

    def test_empty_document_is_a_no_op(self):
        out, changes = rewrite_text("", CUSTOM)
        self.assertEqual(out, "")
        self.assertEqual(changes, [])


class TestAgainstTheRealRepo(unittest.TestCase):
    """The tool is only useful if it actually governs the real file."""

    def test_config_is_valid_and_loadable(self):
        cfg = load_config()
        self.assertTrue(normalize_origin(cfg["siteOrigin"]))

    def test_every_managed_file_exists(self):
        for rel in MANAGED_FILES:
            self.assertTrue((REPO_ROOT / rel).exists(), f"managed file missing: {rel}")

    def test_the_og_image_is_actually_marked(self):
        # The whole point. If someone adds an og:image without a marker,
        # it silently stops being managed and rots on the next domain move.
        html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("site-url:", html, "index.html has no site-url marker")
        for line in html.splitlines():
            if "og:image" in line and "http" in line:
                self.assertIn("/dge/images/guru/guruji.jpg", line)

    def test_the_repo_is_currently_in_sync(self):
        cfg = load_config()
        origin = normalize_origin(cfg["siteOrigin"])
        for rel in MANAGED_FILES:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            _, changes = rewrite_text(text, origin)
            self.assertEqual(changes, [], f"{rel} is out of sync — run tools/set_site_url.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
