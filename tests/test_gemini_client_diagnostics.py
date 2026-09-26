"""A parse failure must say why it failed.

Run 36261738151 lost 246 of 581 Aitareya blocks to the single line

    could not parse Gemini response: Unterminated string starting at: line 2 column 11

repeated 246 times, carrying nothing to diagnose with: not the finishReason,
not the token counts, not how much text actually arrived. Two very different
causes produce that same message -- an answer truncated because the output
budget went on the model's own thinking, and an answer the model declined to
give -- and only one of them is fixable by spending more.
"""
import importlib.util
import json
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "gemini_client.py"
_spec = importlib.util.spec_from_file_location("gemini_client", TOOL)
gc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gc)


class FakeResponse:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def post(monkeypatch, payload):
    monkeypatch.setattr(gc.urllib.request, "urlopen", lambda *a, **k: FakeResponse(payload))
    with pytest.raises(gc.GeminiError) as ei:
        gc._post("m", {}, "key", None)
    return ei.value


def truncated(finish="MAX_TOKENS", visible='{\n  "text": "', thoughts=8100):
    return {
        "candidates": [{"finishReason": finish,
                        "content": {"parts": [{"text": visible}]}}],
        "usageMetadata": {"thoughtsTokenCount": thoughts,
                          "candidatesTokenCount": 6,
                          "promptTokenCount": 1200},
        "modelVersion": "gemini-3.7-flash",
    }


def test_it_names_the_finish_reason(monkeypatch):
    assert "finishReason='MAX_TOKENS'" in str(post(monkeypatch, truncated()))


def test_it_reports_how_little_text_arrived(monkeypatch):
    visible = '{\n  "text": "'
    err = str(post(monkeypatch, truncated(visible=visible)))
    assert f"visible_chars={len(visible)}" in err
    # The point of the number: it distinguishes "we got a long answer with a
    # broken tail" from "we got nothing but the opening brace".
    assert len(visible) < 20


def test_it_reports_the_thinking_tokens_that_ate_the_budget(monkeypatch):
    err = str(post(monkeypatch, truncated()))
    assert "thoughts=8100" in err and "candidate=6" in err


def test_it_names_the_model_that_actually_served(monkeypatch):
    assert "gemini-3.7-flash" in str(post(monkeypatch, truncated()))


def test_a_refusal_is_distinguishable_from_a_truncation(monkeypatch):
    """SAFETY is not fixable by raising the token budget. The message has to
    let a reader tell the two apart, which the old one did not."""
    err = str(post(monkeypatch, truncated(finish="SAFETY", visible="", thoughts=0)))
    assert "finishReason='SAFETY'" in err
    assert "visible_chars=0" in err


def test_it_survives_a_payload_with_no_candidates_at_all(monkeypatch):
    err = str(post(monkeypatch, {"usageMetadata": {}}))
    assert "finishReason=None" in err and "visible_chars=0" in err


def test_the_original_exception_is_still_reported(monkeypatch):
    assert "Unterminated string" in str(post(monkeypatch, truncated()))


def test_a_good_response_still_parses(monkeypatch):
    payload = {"candidates": [{"content": {"parts": [{"text": '{"text": "ok"}'}]}}],
               "usageMetadata": {}}
    monkeypatch.setattr(gc.urllib.request, "urlopen", lambda *a, **k: FakeResponse(payload))
    assert gc._post("m", {}, "key", None) == {"text": "ok"}
