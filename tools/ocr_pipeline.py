"""
ocr_pipeline.py — shared PDF-prep/OCR/proofread machinery used by
tools/gemini_ocr_commentary.py (the OCR+proofread stage) and
tools/ocr_preview_pages.py (the fast, Gemini/Vision-free page-preview
stage the browser admin tool calls before committing to a full run).

Two-stage architecture: this module's job stops at producing proofread
shloka data (a plain list of dicts) — it does NOT merge into a corpus
data.json. See tools/gemini_ocr_commentary.py for staging that output to
a JSON file, and tools/merge_staged_commentary.py for the separate step
that reads a staged file and actually writes it into a canto.
"""
from __future__ import annotations

import base64
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_client import GeminiError, call_gemini  # noqa: E402
from vision_client import ocr_images_batch  # noqa: E402

LANGUAGE_HINTS = ["sa", "hi", "kn"]

# Ported VERBATIM from dge/convert/gemini.js's PROOFREAD_PROMPT, minus the
# dual-engine (Vision + Tesseract cross-check) branch -- this pipeline only
# ever has one OCR reading (Vision), so every page is the "no engine label"
# case that prompt already describes.
PROOFREAD_PROMPT = """You are proofreading raw OCR output from a scanned Sanskrit/Kannada devotional text.

Rules:
1. Correct OCR mistakes only (misread characters, broken/merged words, obvious scan artifacts). Do not rewrite, summarize, paraphrase, or "improve" the wording.
2. Preserve Sanskrit and Kannada text exactly as intended -- do not modernize or alter it.
3. Preserve the original paragraph and page order for the actual sentences/lines themselves.
4. Verse-number markers ("॥ १॥", "॥ २॥", ...) are a known weak point of the OCR layer, not something to trust blindly: when verse numbers are printed in their own visual column/margin on the page, OCR can read that whole column as one separate block and splice it back in slightly offset, landing a marker after the wrong shloka's last line. If this looks like what happened -- numbers not incrementing where they visually sit, or a shloka reading oddly short or long compared to its neighbors -- use the markers' own strict sequence (they always increase by exactly 1 within one sarga/chapter) together with where each verse's sense, grammar, and metre naturally complete to reattach each marker to its real shloka boundary. This only changes which existing text belongs under which "number" -- it never means inventing, dropping, or actually reordering the underlying sentences (rule 3 still applies to those).
5. Where distinguishable, identify which portions are the mula shloka (verse) text versus commentary/explanation.
6. Never invent text that isn't grounded in the OCR reading for that page, beyond fixing an obvious small OCR-level error (broken characters, merged words) that context clearly resolves.
7. For every shloka, self-report a "classification":
   - "accept": the reading is unambiguous and plausible as-is.
   - "review": a verse-marker boundary needed reattaching per rule 4, or something else needed a judgment call -- likely correct, but a human should still glance at it.
   - "unresolved": you cannot determine confident text (the reading is implausible, contradictory, or the source itself looks illegible). Keep your best-guess text in "sa" regardless, but do not invent details the reading doesn't actually show.
   Add a brief "note" explaining why, but only when classification is not "accept" -- omit it (empty string) otherwise.
8. Also report which page (the number from the "--- Page N ---" marker) each shloka came from, in "page".
9. Watch for two specific structural problems, since they're easy to miss shloka-by-shloka but matter a lot downstream: (a) a chapter/sarga boundary -- a chapter-opening line ("अथ <ordinal> सर्गः") or a closing colophon ("इति ... <ordinal> सर्गः") -- that looks incomplete, garbled, or only half-legible, since that's exactly what breaks automatic chapter splitting later; (b) one verse's text that looks like it was actually split into two separate shlokas (or two verses merged into one) by a misplaced verse-number marker, beyond what rule 4 above already resolves. When either happens, still give your best-effort corrected text, but set "classification" to "review" and say specifically what you noticed in "note" (e.g. "possible sarga boundary here -- colophon text looks incomplete" or "this may be two verses merged into one shloka"), so a human reviewer sees exactly what to double-check instead of having to re-read everything.
10. Output ONLY valid JSON -- no markdown code fences, no explanations before or after, no trailing commentary.

Output exactly this JSON shape:
{
  "shlokas": [
    { "number": 1, "page": 3, "sa": "corrected shloka text", "commentary": "corrected commentary text, or empty string if none", "classification": "accept", "note": "" }
  ]
}

If a page doesn't cleanly split into shloka/commentary, put the whole corrected text in "sa" and leave "commentary" empty -- do not invent a split that isn't actually there in the source.

Raw OCR input follows:
"""

PROOFREAD_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "shlokas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"},
                    "page": {"type": "integer"},
                    "sa": {"type": "string"},
                    "commentary": {"type": "string"},
                    "classification": {"type": "string", "enum": ["accept", "review", "unresolved"]},
                    "note": {"type": "string"},
                },
                "required": ["sa", "classification"],
            },
        },
    },
    "required": ["shlokas"],
}


def parse_page_list(spec: str) -> list[int]:
    """Parses '1,2,50' or '1-3,7,10-12' into a sorted, deduped list of ints."""
    out = set()
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-")
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def _filename_from_response(resp, fallback: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    if m:
        return m.group(1)
    return fallback


def download_file(url: str, dest_dir: Path, fallback_name: str) -> Path:
    """Downloads `url` into `dest_dir`, preferring the server's own
    filename (Content-Disposition, then URL path) over `fallback_name` --
    matters for multi-volume 7z detection, which is filename-pattern based
    (needs siblings like name.7z.001/.002/.003 physically present)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        name = _filename_from_response(resp, fallback_name)
        dest = dest_dir / name
        with open(dest, "wb") as fh:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
    print(f"Downloaded {url} -> {dest.name} ({dest.stat().st_size:,} bytes)")
    return dest


def prepare_pdf(pdf_url: str | None, part_urls: list[str], workdir: Path) -> Path:
    """Returns a local Path to the PDF, downloading (and combining split 7z
    parts, if given) as needed. Exactly one of pdf_url / part_urls must be
    given.

    7z combining mirrors the manual process already used once in this
    project (see dge/PENDING.md's Raghavendra Vijaya writeup): all parts
    must sit in the same directory, under their real filenames, before
    `7z x` on the first part will detect the multi-volume set -- so this
    downloads every part first (preserving each server's own filename via
    Content-Disposition when available) rather than extracting as it goes.
    """
    if bool(pdf_url) == bool(part_urls):
        raise ValueError("prepare_pdf: give exactly one of pdf_url or part_urls")

    if pdf_url:
        return download_file(pdf_url, workdir, "input.pdf")

    if len(part_urls) > 3:
        raise ValueError(f"prepare_pdf: {len(part_urls)} part URLs given, but split-7z archives in this "
                          f"project have always come in 3 parts -- refusing to guess at a different split")

    local_parts = []
    for i, url in enumerate(part_urls, 1):
        local_parts.append(download_file(url, workdir, f"part.7z.{i:03d}"))

    first = sorted(local_parts, key=lambda p: p.name)[0]
    print(f"Extracting {first.name} (multi-volume, {len(local_parts)} part(s)) ...")
    subprocess.run(["7z", "x", str(first), f"-o{workdir}", "-y"], check=True, capture_output=True)

    pdfs = list(workdir.rglob("*.pdf"))
    if not pdfs:
        raise RuntimeError(f"7z extraction of {first.name} produced no .pdf file -- check the archive contents")
    if len(pdfs) > 1:
        print(f"warning: extraction produced {len(pdfs)} PDFs, using the largest: "
              f"{sorted(p.name for p in pdfs)}", file=sys.stderr)
        pdfs.sort(key=lambda p: p.stat().st_size, reverse=True)
    return pdfs[0]


def get_page_count(pdf_path: Path) -> int:
    result = subprocess.run(["pdfinfo", str(pdf_path)], check=True, capture_output=True, text=True)
    m = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
    if not m:
        raise RuntimeError(f"pdfinfo output for {pdf_path} had no 'Pages:' line")
    return int(m.group(1))


_PAGE_FILENAME_RE = re.compile(r"page-(\d+)\.png$")


def render_pages(pdf_path: Path, pages: list[int], out_dir: Path) -> dict[int, Path]:
    """Renders exactly the given (possibly non-contiguous) 1-indexed page
    numbers to PNGs via poppler's pdftoppm, at ~200dpi (matches
    dge/convert/pdf.js's default render scale -- plenty for Vision OCR on
    a normal scanned book page). Returns {page_number: png_path}.

    pdftoppm only accepts a contiguous -f/-l range, so an exclude-pages
    gap in the middle still gets rendered here and is filtered out below.
    The real page number is parsed straight out of each output filename
    (pdftoppm names files by actual page number, zero-padded to the
    source PDF's total page count -- confirmed directly: pages 8-12 of a
    20-page PDF come out as page-08.png..page-12.png) rather than assumed
    from position, so this stays correct even if pdftoppm ever produces
    fewer files than the requested range (e.g. a damaged page)."""
    if not pages:
        return {}
    lo, hi = min(pages), max(pages)
    prefix = out_dir / "page"
    subprocess.run(
        ["pdftoppm", "-png", "-r", "200", "-f", str(lo), "-l", str(hi), str(pdf_path), str(prefix)],
        check=True, capture_output=True,
    )
    rendered = sorted(out_dir.glob("page-*.png"))
    if not rendered:
        raise RuntimeError(f"pdftoppm produced no pages for {pdf_path} [{lo}-{hi}]")
    wanted = set(pages)
    out = {}
    for path in rendered:
        m = _PAGE_FILENAME_RE.search(path.name)
        if not m:
            continue
        page_num = int(m.group(1))
        if page_num in wanted:
            out[page_num] = path
    return out


def ocr_pages(page_paths: dict[int, Path], api_key: str, vision_batch_size: int = 10) -> dict[int, str]:
    """Returns {page_number: raw_ocr_text}."""
    page_nums = sorted(page_paths.keys())
    texts: dict[int, str] = {}
    for i in range(0, len(page_nums), vision_batch_size):
        chunk = page_nums[i:i + vision_batch_size]
        b64s = [base64.b64encode(page_paths[n].read_bytes()).decode("ascii") for n in chunk]
        results = ocr_images_batch(b64s, api_key, LANGUAGE_HINTS)
        for n, result in zip(chunk, results):
            texts[n] = result["text"]
    return texts


def build_ocr_pages_text(page_texts: dict[int, str]) -> str:
    parts = [f"--- Page {n} ---\n{page_texts[n]}" for n in sorted(page_texts.keys())]
    return "\n\n".join(parts)


def proofread_batch(ocr_pages_text: str, api_key: str, model: str, context_anchor: str,
                     max_output_tokens: int, usage_totals: dict | None = None) -> dict:
    anchor = f"Context anchor: this text is from {context_anchor}.\n\n" if context_anchor else ""
    prompt = anchor + PROOFREAD_PROMPT + "\n\n" + ocr_pages_text
    return call_gemini(
        "You are a meticulous OCR proofreader for classical Sanskrit/Kannada texts.",
        prompt, PROOFREAD_RESPONSE_SCHEMA, api_key, model,
        temperature=0.1, max_output_tokens=max_output_tokens, usage_totals=usage_totals,
    )


def mock_proofread_batch(ocr_pages_text: str, *args, **kwargs) -> dict:
    """--dry-run stand-in, same spirit as gemini_summarize.py's mock."""
    return {"shlokas": [
        {"number": 1, "page": 1, "sa": "[dry-run mock] " + ocr_pages_text[:40],
         "commentary": "[dry-run mock] commentary placeholder", "classification": "accept", "note": ""},
    ]}


def ocr_and_proofread(page_texts: dict[int, str], model: str, context_anchor: str,
                       pages_per_gemini_batch: int, api_key: str | None, dry_run: bool,
                       usage_totals: dict | None = None) -> list[dict]:
    """Runs the proofread step over `page_texts` (already-OCR'd raw text,
    keyed by page number) in batches of `pages_per_gemini_batch`. Returns
    the concatenated shloka list across all batches. Raises GeminiError on
    a failed batch -- callers decide whether to abort or report partial
    results."""
    all_shlokas: list[dict] = []
    page_nums = sorted(page_texts.keys())
    for i in range(0, len(page_nums), pages_per_gemini_batch):
        batch_pages = page_nums[i:i + pages_per_gemini_batch]
        batch_text = build_ocr_pages_text({n: page_texts[n] for n in batch_pages})
        print(f"Proofreading page(s) {batch_pages} ...")
        if dry_run:
            result = mock_proofread_batch(batch_text)
        else:
            result = proofread_batch(batch_text, api_key, model, context_anchor,
                                      max_output_tokens=16384, usage_totals=usage_totals)
        all_shlokas.extend(result.get("shlokas") or [])
    return all_shlokas
