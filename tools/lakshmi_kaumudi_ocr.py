#!/usr/bin/env python3
"""
lakshmi_kaumudi_ocr.py — Stage 1 of the Lakshmī-Vyākhyā pipeline:
PDF pages -> Vision OCR -> Gemini proofreading -> a staged JSON file.

Balkrishna Sharma Pancholi's Lakshmī vyākhyā on the Siddhānta-Kaumudī
(MLBD 1966, 2 volumes in one 878-page scan; imported with case-by-case
permission from the project lead, 2 Sep 2026 — recorded in
admin/config/pending_pdf_sources.json).

Unlike Vasu's translation (tools/vasu_kaumudi_ocr.py) this edition
prints NO per-entry serial numbers: the vyākhyā runs as Sanskrit prose
blocks, each anchored by a bold PRATĪKA — the opening words of the SK
passage being glossed — under prakaraṇa headings, with Panini
references like (६-१-७८) quoted inline. So Stage 1's unit is a
pratīka-anchored BLOCK, and alignment to sutra ids happens in Stage 2
(tools/merge_staged_lakshmi_kaumudi.py) by matching pratīkas against
the corpus's own siddhanta_kaumudi Sanskrit in reading order.

Staged output: dge/data/ocr_staging/lakshmi_kaumudi/ by default.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_client import DEFAULT_MODEL, GeminiError, call_gemini  # noqa: E402
from ocr_pipeline import (  # noqa: E402
    build_ocr_pages_text, ocr_pages, parse_page_list, prepare_pdf, render_pages,
)

ITEM = "Siddhanta_Kaumudi_With_Lakshmi_Vyakhya_Vol_1_and_2_Balkrishna_Panchali"
PDF_NAME = ("Siddhanta Kaumudi with Lakshmi Vyakhya Vol 1 & 2 - "
            "Balkrishna Sharma Panchali 1966 (MLBD).pdf")

PROOFREAD_PROMPT = """You are proofreading raw OCR output from the "Lakshmi Vyakhya" — Balkrishna Sharma Pancholi's Sanskrit commentary on Bhattoji Dikshita's Siddhanta-Kaumudi (Motilal Banarsidass, 1966). The book is Devanagari throughout.

Structure: the commentary follows the Siddhanta-Kaumudi's own order. Each comment BLOCK opens with a bold PRATIKA — the first word(s) of the SK passage being glossed, usually ending with इति or followed by a daṇḍa — and runs until the next pratika. Prakarana section headings appear as "॥ अथ <name>प्रकरणम् ॥". Panini sutra references are quoted inline in the form (६-१-७८) or (८-२-१ सू). One block = one unit.

Rules:
1. Correct OCR mistakes only (misread characters, broken/merged words, scan artifacts). Do not rewrite, paraphrase, or "improve" the Sanskrit. Preserve sentence and paragraph order exactly.
2. The opening pratika of each block goes in "pratika" EXACTLY as printed (best corrected reading). The block's full text (including the pratika) goes in "text".
3. When the current prakarana heading is visible (or continues from the running head), report it in "prakarana"; "" otherwise.
4. When a Panini reference like (६-१-७८) appears in the FIRST sentence of the block, report it in "panini_ref" as digits, e.g. "6.1.78"; "" otherwise. Only from printed digits — never from your own knowledge of grammar.
5. Page-top running heads, bare page numbers, and printer's marks are chrome — drop them.
6. A block may continue across "--- Page N ---" markers. A block whose beginning lies before this batch's first page gets "partial": "tail"; one cut off at the batch's end gets "partial": "head"; complete blocks get "partial": "none".
7. For every block, self-report "classification":
   - "accept": the reading is coherent Sanskrit and plausible as-is.
   - "review": a block boundary or the pratika took a judgment call, or a passage needed heavier reconstruction — likely correct, but a human should glance at it.
   - "unresolved": you cannot determine confident text. Keep your best-guess text regardless; never invent what the scan does not show.
   Brief "note" only when not "accept".
8. Report the page (from the "--- Page N ---" markers) where each block BEGINS, in "page".
9. Output ONLY valid JSON — no markdown fences, no commentary:
{"blocks": [{"pratika": "...", "prakarana": "...", "panini_ref": "", "text": "...", "page": 100, "partial": "none", "classification": "accept", "note": ""}]}
"""

LK_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pratika": {"type": "string"},
                    "prakarana": {"type": "string"},
                    "panini_ref": {"type": "string"},
                    "text": {"type": "string"},
                    "page": {"type": "integer"},
                    "partial": {"type": "string", "enum": ["none", "head", "tail"]},
                    "classification": {"type": "string",
                                       "enum": ["accept", "review", "unresolved"]},
                    "note": {"type": "string"},
                },
                "required": ["pratika", "text", "page", "classification"],
            },
        },
    },
    "required": ["blocks"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def proofread_lk_batch(batch_text: str, api_key: str, model: str,
                       context_anchor: str, usage_totals: dict | None) -> list[dict]:
    anchor = f"Context anchor: {context_anchor}.\n\n" if context_anchor else ""
    prompt = anchor + PROOFREAD_PROMPT + "\n\nRaw OCR text follows:\n\n" + batch_text
    data = call_gemini(
        "You are a meticulous OCR proofreader for classical Sanskrit texts.",
        prompt, LK_RESPONSE_SCHEMA, api_key, model,
        temperature=0.1, max_output_tokens=32768, usage_totals=usage_totals,
    )
    blocks = data.get("blocks") or []
    if not isinstance(blocks, list):
        raise GeminiError("proofread returned no blocks list")
    for b in blocks:
        if b.get("partial") == "none":
            b["partial"] = ""
    return blocks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", help="already-local PDF (testing); otherwise fetched")
    ap.add_argument("--start-page", type=int, required=True)
    ap.add_argument("--end-page", type=int, required=True)
    ap.add_argument("--exclude-pages", default="")
    ap.add_argument("--context-anchor", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--pages-per-gemini-batch", type=int, default=3)
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    api_key = os.environ.get("GEMINI_API_KEY")
    vision_key = os.environ.get("VISION_API_KEY")
    if not args.dry_run and (not api_key or not vision_key):
        print("error: GEMINI_API_KEY and VISION_API_KEY must both be set "
              "(pass --dry-run to test without them)", file=sys.stderr)
        return 1

    import urllib.parse
    pdf_url = f"https://archive.org/download/{ITEM}/" + urllib.parse.quote(PDF_NAME)
    pages = [p for p in range(args.start_page, args.end_page + 1)
             if p not in set(parse_page_list(args.exclude_pages))]
    if not pages:
        print("error: empty page range", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else (
        Path("dge/data/ocr_staging/lakshmi_kaumudi") /
        f"pages{args.start_page}-{args.end_page}.json")

    with tempfile.TemporaryDirectory(prefix="lakshmi_") as td:
        workdir = Path(td)
        pdf_path = Path(args.pdf) if args.pdf else prepare_pdf(pdf_url, [], workdir)
        print(f"Rendering {len(pages)} page(s) from {pdf_path.name} ...")
        pages_dir = workdir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        page_paths = render_pages(pdf_path, pages, pages_dir)
        if args.dry_run:
            print(f"[dry-run] would OCR {len(page_paths)} page image(s); "
                  f"staged file would be {out_path}")
            page_texts = {n: f"(dry-run: page {n} not OCR'd)" for n in page_paths}
        else:
            print("Vision OCR ...")
            page_texts = ocr_pages(page_paths, vision_key)

        usage: dict = {}
        blocks: list[dict] = []
        nums = sorted(page_texts)
        anchor = "Lakshmi Vyakhya on Siddhanta Kaumudi (MLBD 1966)"
        if args.context_anchor:
            anchor += "; " + args.context_anchor

        def proofread(subset):
            batch_text = build_ocr_pages_text({n: page_texts[n] for n in subset})
            print(f"Proofreading page(s) {subset[0]}-{subset[-1]} ...")
            if args.dry_run:
                return [{"pratika": "", "prakarana": "", "panini_ref": "",
                         "text": batch_text[:200], "page": subset[0], "partial": "",
                         "classification": "unresolved", "note": "dry-run mock"}]
            return proofread_lk_batch(batch_text, api_key, args.model, anchor, usage)

        for i in range(0, len(nums), args.pages_per_gemini_batch):
            batch = nums[i:i + args.pages_per_gemini_batch]
            try:
                blocks.extend(proofread(batch))
            except (GeminiError, TimeoutError, OSError) as e:
                print(f"  batch failed ({e}); retrying page-by-page")
                for n in batch:
                    blocks.extend(proofread([n]))

    staged = {
        "_readme": "Stage-1 output of tools/lakshmi_kaumudi_ocr.py -- inspect, then "
                   "align+merge with tools/merge_staged_lakshmi_kaumudi.py. Blocks "
                   "are pratika-anchored; sutra alignment happens at Stage 2.",
        "work": "lakshmi_kaumudi",
        "source_url": pdf_url,
        "pages": [args.start_page, args.end_page],
        "model": args.model,
        "generated": now_iso(),
        "counts": {c: sum(1 for b in blocks if b.get("classification") == c)
                   for c in ("accept", "review", "unresolved")},
        # Real token burn for this run (Gemini usageMetadata) -- the project
        # lead budgets prepaid credits from these numbers.
        "usage": usage,
        "blocks": blocks,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(staged, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"staged {len(blocks)} block(s) -> {out_path}  {staged['counts']}")
    print(f"gemini usage: {usage}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
