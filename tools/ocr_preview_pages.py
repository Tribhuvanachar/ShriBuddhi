#!/usr/bin/env python3
"""
ocr_preview_pages.py — renders specific PDF pages to PNGs so an admin can
visually confirm a start/end/exclude page selection BEFORE committing to a
full (billed) OCR+proofread run. No Gemini or Vision calls -- just
poppler, so it's fast and free to run as often as needed.

Same PDF-input options as gemini_ocr_commentary.py (--pdf / --pdf-url /
--pdf-url-parts). Writes each requested page as <out-dir>/page-<N>.png and
a meta.json with the PDF's total page count (so the UI can validate an
end-page choice against it, e.g. warn if it's typed past the last page).

Usage:
  python3 tools/ocr_preview_pages.py --pdf-url https://example.com/commentary.pdf \
      --pages "1,12,54,55" --out-dir /tmp/preview
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from shutil import copyfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocr_pipeline import get_page_count, parse_page_list, prepare_pdf, render_pages  # noqa: E402


def run(pdf: Path | None, pdf_url: str | None, part_urls: list[str], pages: list[int], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if pdf is None:
            print(f"Preparing PDF ({'url' if pdf_url else 'split 7z parts'}) ...")
            pdf = prepare_pdf(pdf_url, part_urls, tmp_path)

        total_pages = get_page_count(pdf)
        requested = [p for p in pages if 1 <= p <= total_pages]
        out_of_range = sorted(set(pages) - set(requested))

        rendered = render_pages(pdf, requested, tmp_path) if requested else {}
        for page_num, src in rendered.items():
            copyfile(src, out_dir / f"page-{page_num}.png")

        meta = {
            "total_pages": total_pages,
            "rendered_pages": sorted(rendered.keys()),
            "out_of_range_pages": out_of_range,
        }
        with open(out_dir / "meta.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1)

    print(f"PDF has {total_pages} page(s). Rendered {len(rendered)}/{len(pages)} requested page(s) -> {out_dir}")
    if out_of_range:
        print(f"warning: pages {out_of_range} are out of range (PDF has {total_pages} pages)", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", type=Path)
    src.add_argument("--pdf-url")
    src.add_argument("--pdf-url-parts", help="Comma-separated split-7z part URLs (up to 3)")
    p.add_argument("--pages", required=True, help="Comma/range list of pages to render, e.g. '1,12,54-56'")
    p.add_argument("--out-dir", required=True, type=Path)
    args = p.parse_args(argv)

    part_urls = [u.strip() for u in args.pdf_url_parts.split(",") if u.strip()] if args.pdf_url_parts else []
    pages = parse_page_list(args.pages)
    if not pages:
        print("error: --pages produced an empty list", file=sys.stderr)
        return 1

    return run(args.pdf, args.pdf_url, part_urls, pages, args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
