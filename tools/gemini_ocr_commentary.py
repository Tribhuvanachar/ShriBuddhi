#!/usr/bin/env python3
"""
gemini_ocr_commentary.py — Stage 1 of the server-side OCR pipeline: PDF
pages -> Vision OCR -> Gemini proofreading -> a staged JSON file. Exists
because dge/convert/ (the browser admin tool) has no server-side
equivalent, times out on a real book in a browser tab, and has no bypass
for its manual review step.

Two-stage architecture: this script does NOT write into a kavya's
data.json. It produces one staged JSON file (default under
dge/data/ocr_staging/<work-slug>/) holding Gemini's proofread output plus
enough metadata to reproduce the run. tools/merge_staged_commentary.py is
the separate Stage 2 that reads a staged file and actually merges it into
a canto -- kept separate so a human (or the browser admin tool) can
inspect/download/email a staged file before anything touches the corpus.
Pass --merge to also run Stage 2 immediately, for a one-shot CLI run.

Input is a PDF, given one of three ways:
  --pdf PATH              already-local file (mainly for local testing)
  --pdf-url URL           direct-download link -- downloaded, never committed
  --pdf-url-parts U1,U2,U3   a split 7z archive's part links (this project's
                           sources have always come as exactly 3 parts) --
                           downloaded and combined via 7z before proceeding

Classification-gated: Gemini's own "accept" / "review" / "unresolved"
self-classification (see tools/ocr_pipeline.py's PROOFREAD_PROMPT) is
staged as-is for every shloka; which of those actually get merged into the
corpus is Stage 2's decision, not this script's.

Usage:
  GEMINI_API_KEY=... VISION_API_KEY=... python3 tools/gemini_ocr_commentary.py \
      --pdf-url https://example.com/commentary.pdf \
      --start-page 12 --end-page 54 --exclude-pages "13,40-42" \
      --canto 1 --commentary-key tika_someauthor --display-label "Someone's Sanskrit Tika" \
      --context-anchor "Raghavendra Vijaya, Sanskrit tika by Someone, Sarga 1" \
      --work-slug raghavendra_vijaya
  python3 tools/gemini_ocr_commentary.py --pdf x.pdf --start-page 1 --end-page 3 \
      --canto 1 --commentary-key x --display-label X --work-slug x --dry-run
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
from gemini_client import DEFAULT_MODEL, GeminiError  # noqa: E402
from ocr_pipeline import (  # noqa: E402
    ocr_and_proofread, ocr_pages, parse_page_list, prepare_pdf, render_pages,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_staged_path(work_slug: str, commentary_key: str, canto: int,
                         start_page: int, end_page: int) -> Path:
    return Path("dge/data/ocr_staging") / work_slug / \
        f"{commentary_key}_canto{canto}_pages{start_page}-{end_page}.json"


def run(pdf: Path | None, pdf_url: str | None, part_urls: list[str], start_page: int, end_page: int,
        exclude_pages: list[int], work_slug: str, canto: int, commentary_key: str, display_label: str,
        context_anchor: str, content_field: str, model: str, pages_per_gemini_batch: int,
        out_path: Path | None, dry_run: bool, do_merge: bool, sarga_dir: Path | None,
        include_review: bool, include_unresolved: bool, force: bool,
        no_proofread: bool = False) -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    vision_key = os.environ.get("VISION_API_KEY")
    # Vision-only mode (--no-proofread) stages the raw Vision OCR text and never
    # calls Gemini, so it needs only VISION_API_KEY — the intended path when the
    # Gemini credits are exhausted (the operator proofreads/aligns downstream).
    if not dry_run and no_proofread and not vision_key:
        print("error: VISION_API_KEY must be set for --no-proofread", file=sys.stderr)
        return 1
    if not dry_run and not no_proofread and (not api_key or not vision_key):
        print("error: GEMINI_API_KEY and VISION_API_KEY must both be set (pass --dry-run to test without them)",
              file=sys.stderr)
        return 1

    pages = [p for p in range(start_page, end_page + 1) if p not in set(exclude_pages)]
    if not pages:
        print("error: no pages left to process after applying --exclude-pages", file=sys.stderr)
        return 1

    usage_totals: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if dry_run:
            page_texts = {p: f"[dry-run mock OCR text for page {p}]" for p in pages}
        else:
            if pdf is None:
                print(f"Preparing PDF ({'url' if pdf_url else 'split 7z parts'}) ...")
                pdf = prepare_pdf(pdf_url, part_urls, tmp_path)
            print(f"Rendering {len(pages)} page(s) of {pdf} ...")
            page_paths = render_pages(pdf, pages, tmp_path)
            missing = set(pages) - set(page_paths.keys())
            if missing:
                print(f"error: pages {sorted(missing)} could not be rendered (PDF may have fewer pages "
                      f"than requested)", file=sys.stderr)
                return 1
            print(f"Running Vision OCR on {len(page_paths)} page(s) ...")
            page_texts = ocr_pages(page_paths, vision_key)

        if no_proofread:
            # Vision-only: stage one entry per page carrying the raw OCR text in
            # the target field. No Gemini call; a human aligns these to the
            # mula verses downstream. classification 'raw' keeps it out of any
            # automatic merge (merge only ever takes accept/review/unresolved).
            shlokas = [
                {"number": None, "page": n,
                 "sa": page_texts[n] if content_field == "sa" else "",
                 "commentary": page_texts[n] if content_field == "commentary" else "",
                 "classification": "raw",
                 "note": "Vision-only OCR, no Gemini proofread — align to verses by hand"}
                for n in sorted(page_texts)
            ]
        else:
            try:
                shlokas = ocr_and_proofread(page_texts, model, context_anchor, pages_per_gemini_batch,
                                             api_key, dry_run, usage_totals)
            except GeminiError as e:
                print(f"error: proofreading failed ({e.kind}): {e}", file=sys.stderr)
                return 1

    staged = {
        "source": {
            "pdf_url": pdf_url, "pdf_url_parts": part_urls or None, "local_pdf": str(pdf) if pdf else None,
            "start_page": start_page, "end_page": end_page, "exclude_pages": exclude_pages,
        },
        "work_slug": work_slug,
        "canto": canto,
        "commentary_key": commentary_key,
        "display_label": display_label,
        "context_anchor": context_anchor,
        "content_field": content_field,
        "model": model,
        "model_version": usage_totals.get("model_version"),
        "generated_at": now_iso(),
        "usage": usage_totals or None,
        "shlokas": shlokas,
    }

    out_path = out_path or default_staged_path(work_slug, commentary_key, canto, start_page, end_page)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(staged, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    counts = {"accept": 0, "review": 0, "unresolved": 0}
    for s in shlokas:
        counts[s.get("classification", "unresolved")] = counts.get(s.get("classification", "unresolved"), 0) + 1
    print(f"Staged {len(shlokas)} shloka(s) ({counts['accept']} accept, {counts['review']} review, "
          f"{counts['unresolved']} unresolved) -> {out_path}")
    if usage_totals:
        print(f"Gemini usage: {usage_totals.get('calls', 0)} call(s), "
              f"{usage_totals.get('total_tokens', 0):,} total tokens "
              f"(model={usage_totals.get('model_version') or model})")

    if do_merge:
        from merge_staged_commentary import merge_staged_file
        if sarga_dir is None:
            print("error: --merge requires --sarga-dir", file=sys.stderr)
            return 1
        report = merge_staged_file(out_path, sarga_dir, include_review, include_unresolved, force)
        print(f"canto {canto}: linked {report['linked']}, "
              f"held back {report['held_review']} review + {report['held_unresolved']} unresolved, "
              f"skipped {report['skipped_existing']} already-linked, {report['skipped_blank']} blank")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", type=Path, help="Already-local PDF file")
    src.add_argument("--pdf-url", help="Direct-download URL for the PDF")
    src.add_argument("--pdf-url-parts", help="Comma-separated split-7z part URLs (up to 3)")
    p.add_argument("--start-page", required=True, type=int)
    p.add_argument("--end-page", required=True, type=int)
    p.add_argument("--exclude-pages", default="", help="Comma/range list of pages to skip, e.g. '13,40-42'")
    p.add_argument("--work-slug", required=True,
                    help="Folder name under dge/data/ocr_staging/ for this work, e.g. raghavendra_vijaya")
    p.add_argument("--canto", required=True, type=int)
    p.add_argument("--commentary-key", required=True,
                    help="Key under shlokas[n].commentaries this will eventually merge into")
    p.add_argument("--display-label", required=True)
    p.add_argument("--context-anchor", default="")
    p.add_argument("--content-field", default="commentary", choices=["commentary", "sa"])
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--pages-per-batch", type=int, default=6)
    p.add_argument("--out", type=Path, default=None,
                    help="Staged JSON output path (default: dge/data/ocr_staging/<work-slug>/<key>_canto<N>_pages<a>-<b>.json)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-proofread", action="store_true",
                    help="Vision-only: stage raw Vision OCR per page and skip the Gemini proofread "
                         "(needs only VISION_API_KEY; ₹0 Gemini). Align to verses downstream by hand.")
    p.add_argument("--merge", action="store_true",
                    help="Also run Stage 2 (merge into the corpus) immediately after staging")
    p.add_argument("--sarga-dir", type=Path, default=None, help="Required if --merge is given")
    p.add_argument("--include-review", action="store_true")
    p.add_argument("--include-unresolved", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    part_urls = [u.strip() for u in args.pdf_url_parts.split(",") if u.strip()] if args.pdf_url_parts else []
    exclude_pages = parse_page_list(args.exclude_pages)

    return run(args.pdf, args.pdf_url, part_urls, args.start_page, args.end_page, exclude_pages,
               args.work_slug, args.canto, args.commentary_key, args.display_label, args.context_anchor,
               args.content_field, args.model, args.pages_per_batch, args.out, args.dry_run, args.merge,
               args.sarga_dir, args.include_review, args.include_unresolved, args.force,
               no_proofread=args.no_proofread)


if __name__ == "__main__":
    raise SystemExit(main())
