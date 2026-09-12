"""vision_client.py tests. No network: real HTTP behaviour is tested by
swapping in a fake urlopen, mirroring tests/test_gemini_client.py's pattern."""
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import vision_client as vc


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestOcrImagesBatch(unittest.TestCase):
    def test_parses_full_text_annotation(self):
        payload = {"responses": [{"fullTextAnnotation": {
            "text": "रामः",
            "pages": [{"blocks": [{"paragraphs": [{"words": [
                {"symbols": [{"text": "रामः"}], "confidence": 0.97}
            ]}]}]}],
        }}]}
        with patch("vision_client.urllib.request.urlopen", return_value=FakeResponse(payload)):
            result = vc.ocr_images_batch(["fakeb64"], "key")
        self.assertEqual(result[0]["text"], "रामः")
        self.assertEqual(result[0]["words"][0]["text"], "रामः")

    def test_page_with_no_text_returns_empty(self):
        payload = {"responses": [{}]}
        with patch("vision_client.urllib.request.urlopen", return_value=FakeResponse(payload)):
            result = vc.ocr_images_batch(["fakeb64"], "key")
        self.assertEqual(result[0]["text"], "")
        self.assertEqual(result[0]["words"], [])

    def test_per_image_error_raises(self):
        payload = {"responses": [{"error": {"message": "bad image"}}]}
        with patch("vision_client.urllib.request.urlopen", return_value=FakeResponse(payload)):
            with self.assertRaises(vc.VisionError):
                vc.ocr_images_batch(["fakeb64"], "key")

    def test_response_count_mismatch_raises(self):
        payload = {"responses": []}
        with patch("vision_client.urllib.request.urlopen", return_value=FakeResponse(payload)):
            with self.assertRaises(vc.VisionError):
                vc.ocr_images_batch(["fakeb64", "fakeb64_2"], "key")

    def test_language_hints_included_in_request(self):
        captured = {}
        real_request_cls = vc.urllib.request.Request

        def fake_request(url, data=None, headers=None, method=None):
            captured["body"] = json.loads(data)
            return real_request_cls(url, data=data, headers=headers, method=method)

        payload = {"responses": [{}]}
        with patch("vision_client.urllib.request.Request", side_effect=fake_request), \
             patch("vision_client.urllib.request.urlopen", return_value=FakeResponse(payload)):
            vc.ocr_images_batch(["fakeb64"], "key", language_hints=["sa", "kn"])
        self.assertEqual(captured["body"]["requests"][0]["imageContext"]["languageHints"], ["sa", "kn"])


if __name__ == "__main__":
    unittest.main()
