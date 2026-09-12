#!/usr/bin/env python3
"""
vasu_kaumudi_ocr.py — Stage 1 of the Vasu Siddhānta-Kaumudī pipeline:
PDF pages -> Vision OCR -> Gemini proofreading -> a staged JSON file.

The SK-mode sibling of tools/gemini_ocr_commentary.py (same two-stage
architecture, same Vision+Gemini machinery from tools/ocr_pipeline.py),
built for Śrīśa Chandra Vasu's English translation of the
Siddhānta-Kaumudī (Pāṇini Office, 4 volumes, 1905-07 — public domain;
archive.org item Siddhanta_Kaumudi_English_Translation-SC_Vasu).

Why a separate prompt/unit model: that book's unit is not a shloka but
one SK ENTRY — a serial number (Vasu's "S." number, verified identical
to this corpus's kaumudi_order kaumudiIndex on every cross-reference
probed), the Devanagari sutra, then the English translation with its
commentary and Note:— blocks. The Devanagari in this 1906 letterpress
scan OCRs badly; the corpus already holds the authoritative sutra text,
so Stage 2 keys purely on the SK number and the staged Devanagari is
kept only as an audit trail, never displayed.

Stage 2 is tools/merge_staged_vasu_kaumudi.py. Staged output goes under
dge/data/ocr_staging/vasu_siddhanta_kaumudi/ by default.

Usage (the workflow .github/workflows/ocr-vasu-kaumudi.yml drives this):
  GEMINI_API_KEY=... VISION_API_KEY=... python3 tools/vasu_kaumudi_ocr.py \
      --volume 1 --start-page 60 --end-page 90 --out staged.json
  python3 tools/vasu_kaumudi_ocr.py --pdf local.pdf --volume 1 \
      --start-page 60 --end-page 62 --dry-run
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

ITEM = "Siddhanta_Kaumudi_English_Translation-SC_Vasu"
VOLUMES = {
    "1":   ("SiddhantaKaumudiEngTranslationScVasuVolume1-1906.pdf",      "Volume 1 (1906), SK 1-2150"),
    "2.1": ("SiddhantaKaumudiEngTranslationScVasuVolume2Part1-1906.pdf", "Volume 2 Part 1 (1906), SK 2151-2828"),
    "2.2": ("SiddhantaKaumudiEngTranslationScVasuVolume2Part2-1907.pdf", "Volume 2 Part 2 (1907), SK 2829-3386"),
    "3":   ("SiddhantaKaumudiEngTranslationScVasuVolume3-1905.pdf",      "Volume 3 (1905), SK 3387-end"),
}

PROOFREAD_PROMPT = """You are proofreading raw OCR output from "The Siddhanta Kaumudi of Bhattoji Dikshita", English translation by Srisa Chandra Vasu (Panini Office, 1905-07) — an English grammar book with embedded Devanagari, scanned from 1906 letterpress.

The book is organised as numbered ENTRIES. One entry = one unit:
  * a Devanagari line: the Panini sutra with the entry's serial number (often with a Panini reference like "। १ । १ ।"),
  * a bold English heading opening with the SAME serial number, e.g. "4. A vowel whose time is that of short u ...",
  * the English translation, running commentary, examples (often containing Devanagari words), and "Note:—" paragraphs, all belonging to that entry until the next entry's heading.

Rules:
1. Correct OCR mistakes in the ENGLISH text only (misread characters, broken/merged words, 1906-typography artifacts like "fanini"->"Panini", "sfltra"->"sutra"). Do not rewrite, summarize, modernize, or "improve" the wording — Vasu's Victorian English stays exactly as he wrote it.
2. Devanagari in this scan OCRs as garbage ("*<rfa?$m" and the like). Where a Devanagari fragment is embedded in an English sentence, transcribe your best reading of what the original Devanagari word must have been ONLY when the surrounding English states it plainly (e.g. "the root ^ 'to increase'" where the English names the meaning); otherwise leave the fragment as the placeholder "‹?›". NEVER invent Devanagari the context does not establish. The main sutra line's Devanagari goes to "sutra_ocr" as best-effort; downstream this corpus supplies the authoritative sutra text from its own sutrapatha, so an imperfect "sutra_ocr" is acceptable — an invented one is not.
3. Preserve paragraph order exactly. Keep "Note:—" paragraphs with their entry. Keep "Vart:—" (vartika) paragraphs with their entry.
4. Entry serial numbers increase by exactly 1. That strict sequence is your anchor, exactly like verse markers in a verse text: if a number looks misread (OCR turning 318 into "3*8"), use the sequence to fix it. A heading whose number would break the sequence is either a misread (fix it) or a cross-reference inside prose (not a new entry).
5. An entry may span page boundaries: continue it across the "--- Page N ---" markers until the next entry heading.
6. Page-top running heads ("Siddhanta Kaumudi [ Chapter I.", "Chapter. I. ] Definitions"), page numbers, and printer's marks are chrome — drop them, but when a chapter/section title changes in the running head, report it as that entry's "chapter".
7. For every entry, self-report a "classification":
   - "accept": the English reading is unambiguous and plausible as-is.
   - "review": the serial-number sequence needed repair, an entry boundary took a judgment call, or embedded Devanagari had to be reconstructed from clear context — likely correct, but a human should glance at it.
   - "unresolved": you cannot determine confident text (illegible source, contradictory sequence). Keep your best-guess text regardless, but do not invent details.
   Add a brief "note" explaining why, only when classification is not "accept" (empty string otherwise).
8. Report which page (from the "--- Page N ---" markers) each entry's HEADING sits on, in "page". An entry visible only as a tail continuation from before the first page in this batch gets "sk" of that earlier entry and "partial": "tail"; an entry whose text is cut off by the end of the batch gets "partial": "head". All complete entries report "partial": "none".
9. Never invent text that isn't grounded in the OCR reading, beyond fixing an obvious OCR-level error that context clearly resolves.
10. The Devanagari sutra line prints the entry as "<SK number> । <sutra> । <adhyaya> । <pada> । <sutra-number> ॥" — the trailing three numbers are the sutra's Ashtadhyayi reference. Digits OCR far more reliably than Devanagari letters: report them as "panini_ref" in the form "6.1.128" whenever legible, "" otherwise. Do not guess it from your own knowledge of grammar — only from the printed digits.
11. Output ONLY valid JSON — no markdown fences, no commentary:
{"entries": [{"sk": 92, "sutra_ocr": "...", "panini_ref": "6.1.128", "chapter": "...", "english": "...", "page": 63, "partial": "none", "classification": "accept", "note": ""}]}
"""


SK_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sk": {"type": "integer"},
                    "sutra_ocr": {"type": "string"},
                    "panini_ref": {"type": "string"},
                    "chapter": {"type": "string"},
                    "english": {"type": "string"},
                    "page": {"type": "integer"},
                    "partial": {"type": "string", "enum": ["none", "head", "tail"]},
                    "classification": {"type": "string",
                                       "enum": ["accept", "review", "unresolved"]},
                    "note": {"type": "string"},
                },
                "required": ["sk", "english", "page", "classification"],
            },
        },
    },
    "required": ["entries"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def proofread_sk_batch(batch_text: str, api_key: str, model: str,
                       context_anchor: str, usage_totals: dict | None) -> list[dict]:
    anchor = f"Context anchor: {context_anchor}.\n\n" if context_anchor else ""
    prompt = anchor + PROOFREAD_PROMPT + "\n\nRaw OCR text follows:\n\n" + batch_text
    data = call_gemini(
        "You are a meticulous OCR proofreader for a 1906 English grammar "
        "book with embedded Devanagari.",
        prompt, SK_RESPONSE_SCHEMA, api_key, model,
        temperature=0.1, max_output_tokens=32768, usage_totals=usage_totals,
    )
    entries = data.get("entries") or []
    if not isinstance(entries, list):
        raise GeminiError("proofread returned no entries list")
    for e in entries:
        if e.get("partial") == "none":
            e["partial"] = ""
    return entries


def mock_entries(batch_text: str) -> list[dict]:
    return [{"sk": 0, "sutra_ocr": "", "chapter": "", "english": batch_text[:200],
             "page": 0, "partial": "", "classification": "unresolved",
             "note": "dry-run mock"}]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--volume", required=True, choices=sorted(VOLUMES),
                    help="which archive.org volume (1, 2.1, 2.2, 3)")
    ap.add_argument("--pdf", help="already-local PDF (testing); otherwise fetched from archive.org")
    ap.add_argument("--start-page", type=int, required=True)
    ap.add_argument("--end-page", type=int, required=True)
    ap.add_argument("--exclude-pages", default="")
    ap.add_argument("--context-anchor", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--pages-per-gemini-batch", type=int, default=4,
                    help="pages per proofread call (entries are long; keep small)")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    api_key = os.environ.get("GEMINI_API_KEY")
    vision_key = os.environ.get("VISION_API_KEY")
    if not args.dry_run and (not api_key or not vision_key):
        print("error: GEMINI_API_KEY and VISION_API_KEY must both be set "
              "(pass --dry-run to test without them)", file=sys.stderr)
        return 1

    filename, vol_note = VOLUMES[args.volume]
    pdf_url = f"https://archive.org/download/{ITEM}/{filename}"
    pages = [p for p in range(args.start_page, args.end_page + 1)
             if p not in set(parse_page_list(args.exclude_pages))]
    if not pages:
        print("error: empty page range", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else (
        Path("dge/data/ocr_staging/vasu_siddhanta_kaumudi") /
        f"vol{args.volume}_pages{args.start_page}-{args.end_page}.json")

    with tempfile.TemporaryDirectory(prefix="vasu_sk_") as td:
        workdir = Path(td)
        pdf_path = Path(args.pdf) if args.pdf else prepare_pdf(pdf_url, [], workdir)
        print(f"Rendering {len(pages)} page(s) from {pdf_path.name} ...")
        pages_dir = workdir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)   # render_pages expects it
        page_paths = render_pages(pdf_path, pages, pages_dir)
        if args.dry_run:
            print(f"[dry-run] would OCR {len(page_paths)} page image(s); "
                  f"staged file would be {out_path}")
            page_texts = {n: f"(dry-run: page {n} not OCR'd)" for n in page_paths}
        else:
            print("Vision OCR ...")
            page_texts = ocr_pages(page_paths, vision_key)

        usage: dict = {}
        entries: list[dict] = []
        nums = sorted(page_texts)
        anchor = f"Vasu Siddhanta Kaumudi, {vol_note}"
        if args.context_anchor:
            anchor += "; " + args.context_anchor
        def proofread(pages_subset):
            batch_text = build_ocr_pages_text({n: page_texts[n] for n in pages_subset})
            print(f"Proofreading page(s) {pages_subset[0]}-{pages_subset[-1]} ...")
            if args.dry_run:
                return mock_entries(batch_text)
            return proofread_sk_batch(batch_text, api_key, args.model, anchor, usage)

        for i in range(0, len(nums), args.pages_per_gemini_batch):
            batch = nums[i:i + args.pages_per_gemini_batch]
            try:
                entries.extend(proofread(batch))
            except (GeminiError, TimeoutError, OSError) as e:
                # dense pages can outlast the HTTP window as one batch;
                # page-at-a-time is slower but each call stays small
                print(f"  batch failed ({e}); retrying page-by-page")
                for n in batch:
                    entries.extend(proofread([n]))

    staged = {
        "_readme": "Stage-1 output of tools/vasu_kaumudi_ocr.py -- inspect, then "
                   "merge with tools/merge_staged_vasu_kaumudi.py. 'sk' is Vasu's "
                   "serial number == kaumudi_order kaumudiIndex.",
        "work": "vasu_siddhanta_kaumudi",
        "volume": args.volume,
        "source_url": pdf_url,
        "pages": [args.start_page, args.end_page],
        "model": args.model,
        "generated": now_iso(),
        "counts": {c: sum(1 for e in entries if e.get("classification") == c)
                   for c in ("accept", "review", "unresolved")},
        # Real token burn for this run, straight from Gemini's usageMetadata —
        # the project lead budgets prepaid credits from these numbers, so
        # every staged file must carry its own bill.
        "usage": usage,
        "entries": entries,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(staged, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"staged {len(entries)} entrie(s) -> {out_path}  {staged['counts']}")
    print(f"gemini usage: {usage}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
