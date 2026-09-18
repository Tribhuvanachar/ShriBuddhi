#!/usr/bin/env python3
"""
find_text_start.py — find the page a book's actual text begins on, from OCR
output that already exists.

WHY. The lead's instruction for every scan is "see from where the actual
shloka begins, run it till the end". Title pages, dedications, publisher
imprints, prefaces and contents are not corpus, and on a 22,000-page batch
they are also the cheapest pages to stop paying for. But guessing a start
page from the page count is how a run ends up missing three sargas.

Vision runs first and its output is page-indexed, so by the time the
expensive layout engine is dispatched the answer is already sitting in a
staged file, for free. This reads it.

HOW. Front matter and body differ in punctuation, not in script. A title page
is Devanagari, often a lot of it, with almost no danda -- it is nouns in a
column. Verse and commentary carry dandas constantly, because that is what
marks a pada and a verse end. So the signal is danda DENSITY, sustained: the
first page with enough dandas per character, where the next pages agree. One
page is noise (a contents page can list "॥ १ ॥"); three in a row is a book.

    python3 tools/find_text_start.py --staging data/ocr_staging/<slug>
    python3 tools/find_text_start.py --all data/ocr_staging --tsv
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

DEVA = re.compile(r"[ऀ-ॿಀ-೿]")   # Devanagari or Kannada
DANDA = re.compile(r"[।॥]")

# LENGTH is the signal, not punctuation. The first version of this keyed on danda
# density, which works beautifully on a Sanskrit verse text and fails on a Kannada
# one: in the 108 Upanishad Sarvasva scan, page 58 is already commentary -- 1,487
# characters of Kannada glossing Sanskrit mantras -- but Kannada prose carries far
# fewer dandas per character than Sanskrit verse, so it scored below the threshold
# and the detector proposed starting at page 64. That would have silently dropped
# sixty pages of real text.
#
# Length survives the script change. Front matter is short by nature -- a title, a
# dedication, an imprint, a contents line -- and body pages are full. Measured:
# Pasandakhandanam front matter 215-312 characters, body 1,000-1,400; the 108
# Upanishad body 1,400-1,700. A danda still has to appear somewhere on the page,
# which rules out a full page of Latin-script preface, but its DENSITY is not asked
# to carry the decision.
MIN_CHARS = 700
# At least one danda on the page. Not a density -- that is what broke.
MIN_DANDA = 1
# How many consecutive qualifying pages make it a body rather than a stray
# contents line that happens to print a verse number.
# Two consecutive full pages, not three. The cost of starting one page early is one
# page of OCR; the cost of starting one page late is lost text. When those are the
# two errors available, take the cheap one.
RUN = 2


def page_stats(text: str) -> tuple[int, int, float]:
    t = text or ""
    deva = len(DEVA.findall(t))
    danda = len(DANDA.findall(t))
    return deva, danda, (danda / deva if deva else 0.0)


def find_start(pages: dict) -> tuple[int | None, list]:
    """(first body page, per-page stats). None when nothing qualifies."""
    stats = []
    for n in sorted(pages):
        deva, danda, density = page_stats(pages[n])
        ok = deva >= MIN_CHARS and danda >= MIN_DANDA
        stats.append({"page": n, "deva": deva, "danda": danda,
                      "density": round(density, 5), "body": ok})
    run = 0
    for s in stats:
        if s["body"]:
            run += 1
            if run >= RUN:
                return s["page"] - RUN + 1, stats
        else:
            run = 0
    # A short work may simply not have RUN qualifying pages; fall back to the
    # first one that qualifies rather than reporting nothing at all.
    for s in stats:
        if s["body"]:
            return s["page"], stats
    return None, stats


def load_vision(staging_dir: str) -> dict:
    hits = sorted(glob.glob(os.path.join(staging_dir, "vision_pages*.json")))
    if not hits:
        return {}
    with open(hits[0], encoding="utf-8") as fh:
        doc = json.load(fh)
    return {int(p["page"]): (p.get("text") or "")
            for p in doc.get("pages", []) if p.get("page") is not None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--staging", default="", help="one work's staging folder")
    ap.add_argument("--all", default="", help="a folder of staging folders")
    ap.add_argument("--tsv", action="store_true", help="slug<TAB>start<TAB>last")
    ap.add_argument("--explain", action="store_true", help="per-page numbers for one work")
    args = ap.parse_args(argv)

    dirs = []
    if args.staging:
        dirs = [args.staging]
    elif args.all:
        dirs = sorted(d for d in glob.glob(os.path.join(args.all, "*")) if os.path.isdir(d))
    else:
        print("give --staging or --all", file=sys.stderr)
        return 2

    for d in dirs:
        pages = load_vision(d)
        if not pages:
            continue
        start, stats = find_start(pages)
        last = max(pages)
        slug = os.path.basename(d.rstrip("/"))
        if args.tsv:
            print("%s\t%s\t%d" % (slug, start if start else 1, last))
        else:
            skipped = (start - 1) if start else 0
            print("%-48s text starts p%-5s of %-5d  (%d front page(s) skipped)"
                  % (slug[:48], start if start else "?", last, skipped))
        if args.explain:
            for s in stats[:24]:
                print("   p%-4d deva=%-6d danda=%-4d density=%-8.5f %s"
                      % (s["page"], s["deva"], s["danda"], s["density"],
                         "BODY" if s["body"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
