"""gemini_client.py tests. No network: call_gemini's fallback logic is
tested by swapping in a fake _post()."""
import http.client
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import gemini_client as gc


class TestClassifyError(unittest.TestCase):
    def test_maps_known_statuses(self):
        self.assertEqual(gc.classify_error(400), "bad_request")
        self.assertEqual(gc.classify_error(401), "permission")
        self.assertEqual(gc.classify_error(403), "permission")
        self.assertEqual(gc.classify_error(404), "model_missing")
        self.assertEqual(gc.classify_error(429), "quota")
        self.assertEqual(gc.classify_error(500), "overloaded")
        self.assertEqual(gc.classify_error(503), "overloaded")

    def test_unknown_status_falls_back_to_unknown(self):
        self.assertEqual(gc.classify_error(418), "unknown")


class TestCallGeminiFallback(unittest.TestCase):
    """Mirrors dge/js/gemini.js: one attempt, one fallback attempt only for
    quota/model_missing/overloaded, no retry loop beyond that."""

    def setUp(self):
        self._real_post = gc._post
        self.calls = []

    def tearDown(self):
        gc._post = self._real_post

    def test_success_on_first_attempt_never_calls_fallback(self):
        def fake_post(model, body, api_key, usage_totals=None):
            self.calls.append(model)
            return {"ok": True}
        gc._post = fake_post
        result = gc.call_gemini("sys", "prompt", {"type": "object"}, "key", model="gemini-flash-latest")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(self.calls, ["gemini-flash-latest"])

    def test_quota_error_falls_back_once_to_the_lite_model(self):
        def fake_post(model, body, api_key, usage_totals=None):
            self.calls.append(model)
            if model == "gemini-flash-latest":
                raise gc.GeminiError("quota", "429")
            return {"ok": True}
        gc._post = fake_post
        result = gc.call_gemini("sys", "prompt", {"type": "object"}, "key", model="gemini-flash-latest")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(self.calls, ["gemini-flash-latest", "gemini-flash-lite-latest"])

    def test_bad_request_does_not_trigger_a_fallback_attempt(self):
        def fake_post(model, body, api_key, usage_totals=None):
            self.calls.append(model)
            raise gc.GeminiError("bad_request", "400")
        gc._post = fake_post
        with self.assertRaises(gc.GeminiError) as cm:
            gc.call_gemini("sys", "prompt", {"type": "object"}, "key", model="gemini-flash-latest")
        self.assertEqual(cm.exception.kind, "bad_request")
        self.assertEqual(self.calls, ["gemini-flash-latest"])

    def test_fallback_attempt_failing_too_still_raises(self):
        def fake_post(model, body, api_key, usage_totals=None):
            self.calls.append(model)
            raise gc.GeminiError("overloaded", "503")
        gc._post = fake_post
        with self.assertRaises(gc.GeminiError):
            gc.call_gemini("sys", "prompt", {"type": "object"}, "key", model="gemini-flash-latest")
        self.assertEqual(self.calls, ["gemini-flash-latest", "gemini-flash-lite-latest"])


class TestAccumulateUsage(unittest.TestCase):
    def test_sums_across_multiple_calls(self):
        totals = {}
        gc._accumulate_usage(totals, {"promptTokenCount": 100, "candidatesTokenCount": 40, "totalTokenCount": 140})
        gc._accumulate_usage(totals, {"promptTokenCount": 50, "candidatesTokenCount": 10, "totalTokenCount": 60})
        self.assertEqual(totals, {"calls": 2, "prompt_tokens": 150, "output_tokens": 50,
                                   "thoughts_tokens": 0, "total_tokens": 200})

    def test_missing_fields_default_to_zero(self):
        totals = {}
        gc._accumulate_usage(totals, {})
        self.assertEqual(totals, {"calls": 1, "prompt_tokens": 0, "output_tokens": 0,
                                   "thoughts_tokens": 0, "total_tokens": 0})

    def test_thinking_model_thoughts_tokens_tracked_separately_from_output(self):
        # observed for real with gemini-3.7-flash: totalTokenCount can be
        # far larger than promptTokenCount + candidatesTokenCount alone --
        # the gap is thoughtsTokenCount, billed at the output rate but not
        # part of the visible completion (see tools/gemini_bench.py)
        totals = {}
        gc._accumulate_usage(totals, {"promptTokenCount": 4856, "candidatesTokenCount": 2105,
                                       "thoughtsTokenCount": 7175, "totalTokenCount": 14136})
        self.assertEqual(totals["thoughts_tokens"], 7175)
        self.assertEqual(totals["output_tokens"], 2105)
        self.assertEqual(totals["total_tokens"], 14136)

    def test_call_gemini_populates_usage_totals_when_given(self):
        def fake_post(model, body, api_key, usage_totals=None):
            if usage_totals is not None:
                gc._accumulate_usage(usage_totals, {"promptTokenCount": 5, "candidatesTokenCount": 2, "totalTokenCount": 7})
            return {"ok": True}
        real_post = gc._post
        gc._post = fake_post
        try:
            totals = {}
            gc.call_gemini("sys", "prompt", {"type": "object"}, "key", usage_totals=totals)
            self.assertEqual(totals["total_tokens"], 7)
        finally:
            gc._post = real_post


class TestPostNetworkErrors(unittest.TestCase):
    """A dropped connection (e.g. http.client.RemoteDisconnected) is an
    OSError but not a urllib.error.URLError, so it fell through both of
    _post()'s original except clauses uncaught -- observed crashing a
    multi-hour gemini_dhatu_lexicon.py batch run outright instead of
    being classified like every other transient failure here."""

    def test_remote_disconnected_is_classified_as_network_error(self):
        with patch("urllib.request.urlopen", side_effect=http.client.RemoteDisconnected("closed")):
            with self.assertRaises(gc.GeminiError) as ctx:
                gc._post("model", {}, "key")
        self.assertEqual(ctx.exception.kind, "network")

    def test_connection_reset_is_classified_as_network_error(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionResetError("reset")):
            with self.assertRaises(gc.GeminiError) as ctx:
                gc._post("model", {}, "key")
        self.assertEqual(ctx.exception.kind, "network")

    def test_network_error_is_not_fallback_eligible(self):
        self.assertNotIn("network", gc.FALLBACK_ELIGIBLE)


if __name__ == "__main__":
    unittest.main()
