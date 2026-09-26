#!/usr/bin/env python3
"""Segment the staged Rukmiṇīśa Vijaya OCR into addressed verses.

Vādirāja Tīrtha's mahākāvya, 19 sargas, printed with a Sanskrit vyākhyā.
712 pages of Sarvam Document AI output (no Vision pass exists for this work),
complete from page 19 to 712 with no gaps.

THREE THINGS THE EDITION GIVES US, and one it does not:

  * The SARGA is a running header on (almost) every page, tagged
    data-layout="header". So a page declares its own sarga and there is no
    need to track section starts. Two spellings occur: षष्ठ सर्गः for the
    sixth, without the visarga the others carry, and one page OCR'd
    सप्तदशः as ससदशः.
  * The VERSE NUMBER is a ॥ N ॥ marker, in either Devanāgarī or ASCII digits.
  * The COMMENTARY announces itself: a block beginning व्या.

  * What it does NOT give is a layout tag separating verse from commentary.
    data-layout="section-title" looked like it did -- the first page examined
    had the verse under exactly that tag -- but there are only 78 of them in
    the whole book against ~2,480 verse markers. Sampling one page and
    generalising would have produced a 37-verse text out of 1,143.

WHY THIS DOES NOT WRITE TO THE SHELF YET. 1,143 verses are addressed and 97
are missing -- sarga 5 alone is short 9 of 59. Every gap is a verse whose
॥ N ॥ the OCR dropped or garbled; the text is almost certainly on the page.
Maṇimañjarī set the standard here: it landed only once all three layers hit
their canonical counts, and the two verses that did not were repaired against
the page images and recorded in provenance. A 92%-complete mahākāvya on the
shelf is worse than none, because nothing downstream would ever flag it.

    python3 tools/rukminisha/segment.py --staged-dir data/ocr_staging/rukminisha_vijaya
    python3 tools/rukminisha/segment.py --staged-dir <dir> --json report.json
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

ORDINALS = {
    "प्रथमः": 1, "द्वितीयः": 2, "तृतीयः": 3, "चतुर्थः": 4, "पञ्चमः": 5,
    "षष्ठः": 6, "षष्ठ": 6, "सप्तमः": 7, "अष्टमः": 8, "नवमः": 9, "दशमः": 10,
    "एकादशः": 11, "द्वादशः": 12, "त्रयोदशः": 13, "चतुर्दशः": 14,
    "पञ्चदशः": 15, "षोडशः": 16, "सप्तदशः": 17, "ससदशः": 17,
    "अष्टादशः": 18, "एकोनविंशः": 19,
}
DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
VERSE_NUM = re.compile(r"॥\s*([0-9०-९]+)\s*॥")
BLOCK = re.compile(r'<(\w+)[^>]*data-layout="([^"]+)"[^>]*>(.*?)</\1>', re.S)
TEXT_BLOCKS = ("paragraph", "section-title", "headline")


def untag(html: str) -> str:
    """HTML to text, keeping <br> as the line break it stands for."""
    return re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>", "\n", html)).strip()


def load_pages(staged_dir: str) -> dict[int, str]:
    """Every page that actually came back, across all staged files.

    A page can appear in several files -- overlapping dispatch ranges, and
    re-runs of pages an earlier batch failed on. A page whose `ok` is false
    carries no html; one that succeeded wins over one that did not, so the
    later file never erases a page the earlier one delivered.
    """
    pages: dict[int, str] = {}
    for path in sorted(glob.glob(os.path.join(staged_dir, "*.json"))):
        try:
            doc = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        for page in doc.get("pages") or []:
            html = page.get("html") or page.get("text") or ""
            if page.get("ok") and html.strip():
                pages[page["page"]] = html
    return pages


def sarga_of(text: str) -> int | None:
    if "सर्ग" not in text:
        return None
    return ORDINALS.get(text.split()[0])


def segment(pages: dict[int, str]) -> dict:
    """Walk the pages in order, carrying the sarga forward from the headers."""
    current = None
    verses: dict[tuple[int, int], dict] = {}
    commentary = 0
    unknown_headers: collections.Counter = collections.Counter()

    for page in sorted(pages):
        for m in BLOCK.finditer(pages[page]):
            kind, body = m.group(2), untag(m.group(3))
            if kind == "header":
                s = sarga_of(body)
                if s:
                    current = s
                elif "सर्ग" in body:
                    unknown_headers[body] += 1
                continue
            if kind not in TEXT_BLOCKS or not body:
                continue
            if body.startswith("व्या"):
                commentary += 1
                continue
            if current is None:
                continue
            for raw in VERSE_NUM.findall(body):
                n = int(raw.translate(DEV_DIGITS))
                verses.setdefault((current, n), {"sarga": current, "verse": n,
                                                 "page": page, "text": body})

    per = collections.defaultdict(list)
    for (s, n) in verses:
        per[s].append(n)

    sargas = []
    for s in sorted(per):
        got = sorted(per[s])
        high = max(got)
        missing = [i for i in range(1, high + 1) if i not in set(got)]
        sargas.append({"sarga": s, "found": len(got), "highest": high,
                       "missing": missing})
    return {
        "pages": len(pages),
        "page_range": [min(pages), max(pages)] if pages else [],
        "page_gaps": [n for n in range(min(pages), max(pages) + 1)
                      if n not in pages] if pages else [],
        "commentary_blocks": commentary,
        "unknown_sarga_headers": dict(unknown_headers),
        "sargas": sargas,
        "verses_found": sum(s["found"] for s in sargas),
        "verses_missing": sum(len(s["missing"]) for s in sargas),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir", required=True)
    ap.add_argument("--json", help="write the full report here")
    args = ap.parse_args(argv)

    pages = load_pages(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    rep = segment(pages)

    print(f"pages {rep['pages']} ({rep['page_range'][0]}-{rep['page_range'][1]}), "
          f"gaps {len(rep['page_gaps'])}")
    print(f"commentary blocks {rep['commentary_blocks']}")
    if rep["unknown_sarga_headers"]:
        print("unrecognised sarga headers:", rep["unknown_sarga_headers"])
    for s in rep["sargas"]:
        flag = "" if not s["missing"] else f"  MISSING {len(s['missing'])}: {s['missing'][:8]}"
        print(f"  sarga {s['sarga']:<3} {s['found']:>4} verses, highest {s['highest']:>3}{flag}")
    print(f"\n{rep['verses_found']} verses addressed, {rep['verses_missing']} missing")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, ensure_ascii=False, indent=1)
        print("report written to", args.json)

    # Non-zero while anything is missing: this is the gate that keeps an
    # incomplete mahakavya off the shelf.
    return 0 if rep["verses_missing"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
