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


def segments(w: dict):
    """The work's page range split where the dominant script changes.

    Sarvam takes one language per request. The Kannada in these books is a
    front-matter preface or a back-matter appendix -- contiguous, never
    interleaved -- so a chunk can respect it exactly. Sending those ~205 pages
    as sa-IN would make Sarvam disagree with Vision on every one of them, and
    the conflict router would forward the lot to Gemini as if the OCR were bad.
    """
    first, last = w["ocr_range"]
    default = w.get("default_language", "sa-IN")
    blocks = sorted((max(first, b["pages"][0]), min(last, b["pages"][1]), b["language"])
                    for b in w.get("language_blocks", []))
    out, cur = [], first
    for start, end, lang in blocks:
        if start > cur:
            out.append((cur, start - 1, default))
        out.append((start, end, lang))
        cur = end + 1
    if cur <= last:
        out.append((cur, last, default))
    covered = sum(b - a + 1 for a, b, _ in out)
    assert covered == last - first + 1, covered
    return out


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
    ap.add_argument("--with-language", action="store_true",
                    help="add a 4th column, the language to dispatch that chunk with "
                         "(ocr_batch.py --preflight wants the plain 3-column form)")
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
        seen = set()
        for lo, hi, lang in segments(w):
            for a, b in chunks(lo, hi, CAP[args.engine]):
                assert not (seen & set(range(a, b + 1))), "%s: %d-%d overlaps" % (slug, a, b)
                seen |= set(range(a, b + 1))
                row = "%s\t%s\t%d-%d" % (slug, w["pdf_url"], a, b)
                rows.append(row + ("\t" + lang if args.with_language else ""))
        assert seen == set(range(first, last + 1)), "%s: chunks do not cover the range" % slug
    print("\n".join(rows))
    print("%d work(s), %d chunk(s), %d page(s)" % (len(wanted), len(rows), pages), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
