"""Reference Resolution Engine tests.

Uses a synthetic corpus under a tempdir (own library.json + data.json files)
rather than the live dge/data/, so these stay deterministic if the real
corpus grows or a text gets re-edited. One additional test at the bottom
checks the proposal's own worked example ("dharma-kshetre kuru-kshetre" ->
Bhagavad Gita 1.1) against the real corpus, since that is the concrete claim
this whole feature was built to satisfy.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from reference_resolution import GranthaRegistry, ReferenceResolver


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


class TestSyntheticCorpus(unittest.TestCase):
    """A tiny two-grantha corpus: one flat-items text, one nested-shlokas text."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="refres-test-")
        self.data_root = os.path.join(self.tmp, "data")

        _write_json(os.path.join(self.data_root, "library.json"), {
            "granthas": [
                {"path": "dge/data/darshana/sutrapatha/data.json",
                 "populated": True, "title": "Sutrapatha"},
                {"path": "dge/data/itihasa/demo_epic/adhyaya_01/data.json",
                 "populated": True, "title": "Demo Epic"},
            ]
        })
        _write_json(os.path.join(self.data_root, "darshana", "sutrapatha", "data.json"), {
            "schema": "grantha_mula_text",
            "items": [
                {"id": "1.1.1", "sanskrit_text": "वृद्धिरादैच्"},
                {"id": "1.1.2", "sanskrit_text": "अदेङ् गुणः"},
            ],
        })
        _write_json(os.path.join(self.data_root, "itihasa", "demo_epic", "adhyaya_01", "data.json"), {
            "schema": "itihasa_purana_text",
            "items": [
                {"id": "adhyaya_01", "shlokas": [
                    {"number": 1, "sanskrit_text": "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः"},
                    {"number": 2, "sanskrit_text": "मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय"},
                ]},
            ],
        })

        self.registry = GranthaRegistry(
            data_root=self.data_root,
            library_path=os.path.join(self.data_root, "library.json"),
        )
        # search_scope must be real slugs for this synthetic corpus, not the
        # (real-corpus) DEFAULT_SEARCH_SCOPE
        self.resolver = ReferenceResolver(
            registry=self.registry,
            search_scope=["darshana/sutrapatha", "itihasa/demo_epic/adhyaya_01"],
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- priority 1: exact canonical match -----------------------------------

    def test_exact_match_on_a_real_unit_id_is_verified(self):
        result = self.resolver.resolve_exact("darshana/sutrapatha", "1.1.1")
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.resolution_method, "exact_canonical")
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(result.matched_text, "वृद्धिरादैच्")

    def test_exact_match_on_a_missing_unit_id_is_unresolved(self):
        result = self.resolver.resolve_exact("darshana/sutrapatha", "9.9.9")
        self.assertEqual(result.status, "unresolved")
        self.assertIsNone(result.matched_text)

    def test_exact_match_against_an_unknown_slug_is_unresolved_not_a_crash(self):
        result = self.resolver.resolve_exact("nonexistent/slug", "1.1.1")
        self.assertEqual(result.status, "unresolved")

    def test_exact_match_reaches_verses_nested_under_an_itihasa_item(self):
        result = self.resolver.resolve_exact("itihasa/demo_epic/adhyaya_01", "adhyaya_01:1")
        self.assertEqual(result.status, "verified")
        self.assertIn("धर्मक्षेत्रे", result.matched_text)

    # -- priority 2/3: text search --------------------------------------------

    def test_verbatim_quote_resolves_as_verified_lexical_match(self):
        result = self.resolver.resolve_text("धर्मक्षेत्रे कुरुक्षेत्रे")
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.resolution_method, "lexical_search")
        self.assertEqual(result.target_slug, "itihasa/demo_epic/adhyaya_01")
        self.assertEqual(result.target_unit_id, "adhyaya_01:1")

    def test_quote_with_no_match_anywhere_in_scope_is_unresolved(self):
        result = self.resolver.resolve_text("this text does not appear anywhere")
        self.assertEqual(result.status, "unresolved")
        self.assertEqual(result.resolution_method, "unresolved")
        # honest about what it actually searched, for the caller to log/show
        self.assertEqual(
            sorted(result.scope_searched),
            sorted(["darshana/sutrapatha", "itihasa/demo_epic/adhyaya_01"]),
        )

    def test_hint_slugs_are_searched_before_the_default_scope(self):
        result = self.resolver.resolve_text(
            "अदेङ् गुणः", hint_slugs=["darshana/sutrapatha"])
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.scope_searched[0], "darshana/sutrapatha")

    def test_a_short_exact_match_is_capped_at_possible_not_verified(self):
        # single short words are the actual failure mode a real (non-mock)
        # Gemini run hit: this commentary style repeats one term from the
        # base text before explaining it, which Gemini sometimes flags as a
        # "quotation" -- and a short string coincidentally substring-matches
        # almost anything in a nontrivial search scope. "अदेङ्" is 5 chars,
        # under the default min_verified_length of 8.
        result = self.resolver.resolve_text("अदेङ्", hint_slugs=["darshana/sutrapatha"])
        self.assertIn(result.status, ("possible", "unresolved"))
        self.assertNotEqual(result.status, "verified")

    def test_a_long_exact_match_wrapped_in_quote_marks_still_verifies(self):
        # the actual bug found in the real run: quoted_text came back WITH
        # the surrounding quote punctuation Gemini saw in the source prose
        # (e.g. "'अदेङ् गुणः'" rather than "अदेङ् गुणः") -- the corpus's own
        # text never has that punctuation, so left unstripped this diluted
        # an otherwise-exact match down to "possible" (0.517 in the real
        # run) instead of "verified". Must still resolve "verified" once
        # the marks are stripped before searching.
        result = self.resolver.resolve_text("‘अदेङ् गुणः’", hint_slugs=["darshana/sutrapatha"])
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.target_unit_id, "1.1.2")

    # -- resolve(): the full priority ladder ----------------------------------

    def test_resolve_prefers_a_verified_exact_hint_over_text_search(self):
        result = self.resolver.resolve({
            "target_slug": "darshana/sutrapatha", "unit_id": "1.1.1",
            "quoted_text": "something unrelated",
        })
        self.assertEqual(result.resolution_method, "exact_canonical")

    def test_resolve_falls_back_to_text_search_when_the_exact_hint_is_wrong(self):
        result = self.resolver.resolve({
            "target_slug": "darshana/sutrapatha", "unit_id": "9.9.9",
            "quoted_text": "धर्मक्षेत्रे कुरुक्षेत्रे",
        })
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.resolution_method, "lexical_search")

    def test_resolve_with_only_a_source_guess_narrows_the_search(self):
        result = self.resolver.resolve({
            "quoted_text": "अदेङ् गुणः", "source_guess": "Sutrapatha",
        })
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.target_slug, "darshana/sutrapatha")

    def test_resolve_with_nothing_resolvable_is_unresolved_not_fabricated(self):
        result = self.resolver.resolve({"quoted_text": "not in this corpus at all"})
        self.assertEqual(result.status, "unresolved")
        self.assertIsNone(result.target_slug)


class TestRealCorpusWorkedExample(unittest.TestCase):
    """The proposal's own example: dharma-kshetre kuru-kshetre -> Gita 1.1."""

    def test_dharmakshetre_kurukshetre_resolves_to_bhagavad_gita_1_1(self):
        resolver = ReferenceResolver()  # default registry + default scope
        result = resolver.resolve_text("धर्मक्षेत्रे कुरुक्षेत्रे")
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.target_slug, "itihasa/bhagavad_gita/adhyaya_01")
        self.assertEqual(result.target_unit_id, "adhyaya_01:1")


if __name__ == "__main__":
    unittest.main()
