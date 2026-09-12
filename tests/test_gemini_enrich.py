"""gemini_enrich.py tests. Generic client mechanics (error classification,
fallback) are tested in tests/test_gemini_client.py; this file covers only
gemini_enrich's own logic: span validation, overlap handling, segment
building, --dry-run end-to-end. No network."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import gemini_enrich as ge
from reference_resolution import GranthaRegistry, ReferenceResolver


class TestMockDetectCitations(unittest.TestCase):
    def test_finds_a_quoted_multiword_span(self):
        result = ge.mock_detect_citations("यथोक्तम्- ‘सम्भावितः प्रतिज्ञाया अर्थः’ इति ।")
        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["citations"][0]["quoted_text"], "सम्भावितः प्रतिज्ञाया अर्थः")

    def test_ignores_a_single_word_gloss_in_quotes(self):
        # this commentary style also uses '...' to gloss one term being
        # explained, not only to mark citations -- single words should not
        # be treated as citations by the mock heuristic
        result = ge.mock_detect_citations("निर्दोषेति ।। ‘निर्दोषश्च’ इत्युक्तम् ।")
        self.assertEqual(result["citations"], [])

    def test_no_quotes_means_no_citations(self):
        self.assertEqual(ge.mock_detect_citations("plain prose, no quotes")["citations"], [])


class TestEnrichItem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gemini-enrich-test-")
        data_root = os.path.join(self.tmp, "data")
        os.makedirs(os.path.join(data_root, "darshana", "sutrapatha"), exist_ok=True)
        with open(os.path.join(data_root, "library.json"), "w", encoding="utf-8") as fh:
            json.dump({"granthas": [
                {"path": "dge/data/darshana/sutrapatha/data.json",
                 "populated": True, "title": "Sutrapatha"},
            ]}, fh, ensure_ascii=False)
        with open(os.path.join(data_root, "darshana", "sutrapatha", "data.json"), "w", encoding="utf-8") as fh:
            json.dump({"schema": "grantha_mula_text", "items": [
                {"id": "1.3.1", "sanskrit_text": "भूवादयो धातवः"},
            ]}, fh, ensure_ascii=False)
        self.resolver = ReferenceResolver(
            registry=GranthaRegistry(
                data_root=data_root, library_path=os.path.join(data_root, "library.json")),
            search_scope=["darshana/sutrapatha"],
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_blank_item_is_left_alone(self):
        item = {"id": "x", "sanskrit_text": "   "}
        changed = ge.enrich_item(item, self.resolver, None, "m", True, [0])
        self.assertFalse(changed)
        self.assertNotIn("gemini_enrichment", item)

    def test_verbatim_citation_resolves_and_becomes_a_footnoted_segment(self):
        item = {"id": "x", "sanskrit_text": "प्रारम्भे ‘भूवादयो धातवः’ इत्युक्तम् ।"}
        counter = [0]
        changed = ge.enrich_item(item, self.resolver, None, "m", True, counter)
        self.assertTrue(changed)
        block = item["gemini_enrichment"]
        ref_ids = [s["reference_ids"][0] for s in block["segments"] if "reference_ids" in s]
        self.assertEqual(len(ref_ids), 1)
        ref = block["references"][ref_ids[0]]
        self.assertEqual(ref["status"], "verified")
        self.assertEqual(ref["target_slug"], "darshana/sutrapatha")
        # reassembling the segments' text must reproduce the original exactly
        self.assertEqual("".join(s["text"] for s in block["segments"]), item["sanskrit_text"])

    def test_hallucinated_span_that_is_not_a_real_substring_is_discarded(self):
        # a fake citation-source that always returns a span NOT present in
        # the input text -- must be dropped, never trusted verbatim
        item = {"id": "x", "sanskrit_text": "some real text with no quotes at all"}

        def fake_detector(text):
            return {"citations": [{"quoted_text": "this was never in the text", "type": "quotation"}]}

        real_mock = ge.mock_detect_citations
        ge.mock_detect_citations = fake_detector
        try:
            counter = [0]
            changed = ge.enrich_item(item, self.resolver, None, "m", True, counter)
        finally:
            ge.mock_detect_citations = real_mock
        self.assertTrue(changed)  # still writes a gemini_enrichment block...
        self.assertEqual(item["gemini_enrichment"]["references"], {})  # ...but with nothing fabricated
        self.assertEqual(counter[0], 0)  # no ref id was ever allocated for the discarded span


class TestRunEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gemini-enrich-run-")
        self.target = os.path.join(self.tmp, "data.json")
        with open(self.target, "w", encoding="utf-8") as fh:
            json.dump({"schema": "grantha_tika_text", "items": [
                {"id": "a", "sanskrit_text": "टीका ‘सम्भावितः प्रतिज्ञाया अर्थः’ इत्युक्तम् ।"},
                {"id": "b", "sanskrit_text": "no quoted spans here at all"},
            ]}, fh, ensure_ascii=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dry_run_enriches_every_item_once_and_is_idempotent_on_rerun(self):
        from pathlib import Path
        rc = ge.run(Path(self.target), None, ge.DEFAULT_MODEL, True, False)
        self.assertEqual(rc, 0)
        with open(self.target, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertTrue(all("gemini_enrichment" in it for it in data["items"]))

        # re-run without --force: nothing already-enriched should be touched
        first_pass = json.dumps(data, sort_keys=True)
        rc2 = ge.run(Path(self.target), None, ge.DEFAULT_MODEL, True, False)
        self.assertEqual(rc2, 0)
        with open(self.target, encoding="utf-8") as fh:
            data2 = json.load(fh)
        self.assertEqual(first_pass, json.dumps(data2, sort_keys=True))

    def test_missing_api_key_without_dry_run_is_a_clean_error_not_a_crash(self):
        from pathlib import Path
        os.environ.pop("GEMINI_API_KEY", None)
        rc = ge.run(Path(self.target), None, ge.DEFAULT_MODEL, False, False)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
