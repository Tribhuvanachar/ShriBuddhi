"""
vision_client.py — shared Google Cloud Vision OCR client for server-side
ingestion scripts (tools/gemini_ocr_commentary.py and any future one).
Ports dge/convert/vision.js's request shape and error handling exactly, so
a scanned page OCR'd here reads identically to one OCR'd through the
browser admin tool -- same DOCUMENT_TEXT_DETECTION feature (tuned for
dense document/book-page text, unlike TEXT_DETECTION's sparse-scene-text
focus), same batched-request shape, same error messages.

Uses only the standard library (urllib) -- no new dependency.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

API_URL_TMPL = "https://vision.googleapis.com/v1/images:annotate?key={key}"


class VisionError(Exception):
    pass


def _extract_words(fta: dict) -> list[dict]:
    words = []
    for page in fta.get("pages") or []:
        for block in page.get("blocks") or []:
            for para in block.get("paragraphs") or []:
                for word in para.get("words") or []:
                    text = "".join(s.get("text", "") for s in (word.get("symbols") or []))
                    if not text:
                        continue
                    words.append({
                        "text": text,
                        "confidence": word.get("confidence"),
                    })
    return words


def ocr_images_batch(images_base64: list[str], api_key: str, language_hints: list[str] | None = None) -> list[dict]:
    """One HTTP call for the whole batch -- Vision's images:annotate endpoint
    accepts multiple entries in its "requests" array, each returning its own
    independent result, cutting per-request overhead over many individual
    calls (mirrors dge/convert/vision.js's ocrImagesBatch(), including its
    deliberate choice to fail the whole batch on one bad/erroring page
    rather than silently reordering around it).

    Returns one {"text": str, "words": [...]} dict per input image, in the
    same order.
    """
    requests = []
    for b64 in images_base64:
        req = {"image": {"content": b64}, "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]}
        if language_hints:
            req["imageContext"] = {"languageHints": language_hints}
        requests.append(req)

    url = API_URL_TMPL.format(key=api_key)
    body = json.dumps({"requests": requests}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if e.code in (401, 403):
            raise VisionError(f"Vision API key rejected, or the API isn't enabled on that project: {detail[:300]}")
        if e.code == 429:
            raise VisionError(f"Vision API quota exceeded: {detail[:300]}")
        raise VisionError(f"Vision API error (HTTP {e.code}): {detail[:300]}")
    except urllib.error.URLError as e:
        raise VisionError(f"Network error reaching Vision API: {e.reason}")

    responses = data.get("responses") or []
    if len(responses) != len(images_base64):
        raise VisionError(f"Vision API returned {len(responses)} result(s) for a batch of {len(images_base64)}.")

    out = []
    for i, annotation in enumerate(responses):
        if annotation.get("error"):
            raise VisionError(f"Vision API returned an error for image {i}: {annotation['error'].get('message')}")
        fta = annotation.get("fullTextAnnotation")
        if not fta:
            out.append({"text": "", "words": []})
            continue
        out.append({"text": fta.get("text", ""), "words": _extract_words(fta)})
    return out
