#!/usr/bin/env python3
"""
ocr_plan_from_sources.py -- turn admin/config/ocr_sources.json into a plan
ocr_batch.py can preflight.

The plan for a batch used to be typed out by hand from whatever the session
happened to remember. That is how the 18 Sep 2026 batch lost an hour: the
source URLs existed only in a chat transcript, and one of them, recovered by
title alone, pointed at the wrong edition. A plan built from the manifest
cannot drift from the manifest.

    python3 tools/ocr_plan_from_sources.py --engine sarvam \
        --works rukminisha_vijaya kena_upanishad_bhashya_tippani > plan.tsv
"""
from __future__ import annotations

import argparse
import json
import sys

SOURCES = "admin/config/ocr_sources.json"
# Sarvam's own documented per-request ceiling; Vision's is far higher but a
# smaller chunk fails cheaper.
CAP = {"sarvam": 200, "vision": 2000}


def chunks(first: int, last: int, cap: int):
    """Even chunks no larger than cap.

    Even, not greedy: greedy splitting leaves tails like 201-218, and an
    18-page run costs the same runner minutes as a 200-page one.
    """
    n = last - first + 1
    count = -(-n // cap)
    size = -(-n // count)
    start = first
    while start <= last:
        end = min(start + size - 1, last)
        yield start, end
        start = end + 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--engine", required=True, choices=sorted(CAP))
    ap.add_argument("--works", nargs="*", help="work slugs; default every work in the manifest")
    ap.add_argument("--sources", default=SOURCES)
    args = ap.parse_args(argv)

    works = json.load(open(args.sources))["works"]
    wanted = args.works or sorted(works)
    missing = [w for w in wanted if w not in works]
    if missing:
        print("not in %s: %s" % (args.sources, ", ".join(missing)), file=sys.stderr)
        return 2

    rows, pages = [], 0
    for slug in wanted:
        w = works[slug]
        first, last = w["ocr_range"]
        pages += last - first + 1
        for a, b in chunks(first, last, CAP[args.engine]):
            rows.append("%s\t%s\t%d-%d" % (slug, w["pdf_url"], a, b))
    print("\n".join(rows))
    print("%d work(s), %d chunk(s), %d page(s)" % (len(wanted), len(rows), pages), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
