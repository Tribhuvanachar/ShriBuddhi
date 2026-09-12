"""
gemini_client.py — shared Gemini REST client for DGE's batch enrichment
scripts (tools/gemini_enrich.py, tools/gemini_summarize.py, and any future
one). Mirrors dge/js/gemini.js's request shape and its deliberately
retry-less, one-fallback-attempt error handling (see
dge/GEMINI_ERROR_HANDLING.md for why this codebase does not build a
backoff loop around Gemini's own quota errors). Uses only the standard
library (urllib) -- no new dependency, and no state of its own: every
call takes its own api_key/model, so callers control retries/concurrency.

This module makes no policy decisions about WHAT to ask Gemini for --
system instruction, prompt, and response schema are all caller-supplied.
It only owns the HTTP mechanics and the shared error taxonomy, so two
different enrichment tasks (citation detection vs. padaccheda/summary)
don't each reimplement the same request-building/error-classification
code with a chance to drift apart.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
DEFAULT_MODEL = "gemini-flash-latest"
FALLBACK_MODEL = "gemini-flash-lite-latest"
# same three kinds dge/js/gemini.js falls back on -- see shouldFallback() there
FALLBACK_ELIGIBLE = {"quota", "model_missing", "overloaded"}


class GeminiError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def classify_error(status: int) -> str:
    # same status -> kind mapping as dge/js/gemini.js's classifyError()
    if status == 400:
        return "bad_request"
    if status in (401, 403):
        return "permission"
    if status == 404:
        return "model_missing"
    if status == 429:
        return "quota"
    if status in (500, 503):
        return "overloaded"
    return "unknown"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Guards usage_totals dict mutation -- callers may run call_gemini() from a
# thread pool for concurrency (see gemini_summarize.py's --concurrency), and
# plain dict increments are not atomic across threads.
_usage_lock = threading.Lock()


def _accumulate_usage(usage_totals: dict, usage_metadata: dict, model_version: str | None = None) -> None:
    """Adds one call's usageMetadata (Gemini's own token accounting, as
    returned alongside the response) into a running totals dict, so a batch
    script can report real consumption instead of an estimate. Only called
    on a successful response -- a failed attempt (e.g. quota/overloaded)
    isn't billed output tokens and Gemini doesn't return usageMetadata for
    it, so it is correctly left uncounted here. Thread-safe.

    `output_tokens` is candidatesTokenCount only (the visible completion).
    A thinking-capable model (observed: gemini-flash-latest resolving to
    gemini-3.7-flash) also bills a `thoughtsTokenCount` -- internal
    reasoning tokens, which tools/gemini_bench.py found can be *larger*
    than the visible output and is not optional/toggleable via this API.
    That's tracked separately in `thoughts_tokens` rather than folded into
    `output_tokens`, since the two may have different names/behaviour
    across models -- but both are billed at the output token rate, so a
    cost calculation must add them together (see gemini_bench.py's
    _cost()). `total_tokens` always comes straight from Gemini's own
    totalTokenCount and needs no reconciliation."""
    with _usage_lock:
        usage_totals["calls"] = usage_totals.get("calls", 0) + 1
        usage_totals["prompt_tokens"] = usage_totals.get("prompt_tokens", 0) + usage_metadata.get("promptTokenCount", 0)
        usage_totals["output_tokens"] = usage_totals.get("output_tokens", 0) + usage_metadata.get("candidatesTokenCount", 0)
        usage_totals["thoughts_tokens"] = usage_totals.get("thoughts_tokens", 0) + usage_metadata.get("thoughtsTokenCount", 0)
        usage_totals["total_tokens"] = usage_totals.get("total_tokens", 0) + usage_metadata.get("totalTokenCount", 0)
        if model_version:
            # the concrete model an alias like "gemini-flash-latest" resolved
            # to -- last call wins, which is fine for a same-alias batch run
            usage_totals["model_version"] = model_version


def _post(model: str, body: dict, api_key: str, usage_totals: dict | None = None) -> dict:
    url = API_URL_TMPL.format(model=model, key=api_key)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        # GEMINI_HTTP_TIMEOUT: long structured generations (dense book
        # pages) can exceed the 60s default; behavior unchanged unless set
        with urllib.request.urlopen(
                req, timeout=int(os.environ.get("GEMINI_HTTP_TIMEOUT", "60"))) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise GeminiError(classify_error(e.code), f"HTTP {e.code}: {detail[:300]}")
    except urllib.error.URLError as e:
        raise GeminiError("network", str(e.reason))
    except (ConnectionError, TimeoutError, OSError) as e:
        # A dropped/reset connection (e.g. http.client.RemoteDisconnected)
        # is an OSError but NOT a urllib.error.URLError, so it fell through
        # both clauses above uncaught -- observed crashing a multi-hour
        # batch run outright instead of being logged as a per-call warning
        # like every other transient failure here. Not retried (this
        # module's whole design is one attempt + one fallback-model
        # attempt, no backoff loop -- see call_gemini's docstring), just
        # classified so a caller's batch loop can log and move on.
        raise GeminiError("network", str(e))
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise GeminiError("bad_response", f"could not parse Gemini response: {e}")
    if usage_totals is not None:
        _accumulate_usage(usage_totals, payload.get("usageMetadata") or {}, payload.get("modelVersion"))
    return result


def call_gemini(
    system_instruction: str,
    prompt: str,
    response_schema: dict,
    api_key: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_output_tokens: int = 4096,
    usage_totals: dict | None = None,
) -> dict:
    """One attempt against `model`; one fallback attempt against
    FALLBACK_MODEL only for quota/model_missing/overloaded -- deliberately no
    retry/backoff loop beyond that, matching dge/js/gemini.js's generate().
    Returns the parsed JSON object Gemini's structured output produced.

    Pass a `usage_totals` dict (e.g. {}) to have this call's real token
    consumption added into it in place -- see _accumulate_usage. Omit it
    (the default) for zero behaviour change."""
    body = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }
    try:
        return _post(model, body, api_key, usage_totals)
    except GeminiError as e:
        if e.kind in FALLBACK_ELIGIBLE and model != FALLBACK_MODEL:
            return _post(FALLBACK_MODEL, body, api_key, usage_totals)
        raise
