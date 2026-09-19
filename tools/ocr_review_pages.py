#!/usr/bin/env python3
"""
ocr_review_pages.py -- put one page's three readings side by side, for a human.

ocr_invention_check.py finds where the model departed from both engines. It
cannot say whether a departure is a correction or a conjecture -- on one page
of the Harikathamrutasara the flagged stretch was the book's own running title,
which both engines garbled and the model got right; on another it was 'smin,
which nobody read and the model supplied because the Sanskrit wanted it.

Telling those apart needs someone who can read the text. This lays out what
they need: both engine readings, the model's output, and the exact stretch that
came from neither, aligned around the same passage.

    python3 tools/ocr_review_pages.py --resolved r.json --conflicts c.json \
        --pages 148 48            # the flagged ones
    python3 tools/ocr_review_pages.py ... --random 3    # unflagged, for a
                                                        # blind spot check

--random matters as much as the flagged list. The invention check only sees
departures FROM the engines; where both engines made the same mistake and the
model faithfully kept it, nothing is flagged and the page is still wrong.
"""
from __future__ import annotations

import argparse
import glob
import json
import random
import re
import sys

TAG = re.compile(r"<[^>]+>")
ENT = re.compile(r"&[a-z]+;")


def flat(s: str) -> str:
    return " ".join(ENT.sub(" ", TAG.sub(" ", s or "")).split())


def window(text: str, needle: str, width: int) -> str:
    """The passage around a stretch, so the three readings line up by eye."""
    if not needle:
        return text[:width]
    i = text.find(needle[:12])
    if i < 0:
        core = re.sub(r"[^ऀ-ॿಀ-೿]", "", needle[:12])
        i = max(0, text.find(core[:8])) if core else 0
    return text[max(0, i - width // 2):i + width // 2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--resolved", required=True)
    ap.add_argument("--conflicts", nargs="+", required=True)
    ap.add_argument("--pages", nargs="*", type=int, default=[])
    ap.add_argument("--random", type=int, default=0)
    ap.add_argument("--width", type=int, default=420)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    src = {}
    files = []
    for pat in args.conflicts:
        files.extend(sorted(glob.glob(pat)) or [pat])
    for f in files:
        c = json.load(open(f, encoding="utf-8"))
        for x in c.get("conflicts", []):
            src[(c.get("work"), x["page"])] = (x.get("sarvam", ""), x.get("vision", ""),
                                               x.get("ratio"))

    res = json.load(open(args.resolved, encoding="utf-8"))
    pages = {(p.get("work"), p.get("page")): p for p in res.get("pages", [])}

    want = [k for k in pages if k[1] in args.pages] if args.pages else []
    if args.random:
        pool = [k for k in pages if k not in want and k in src]
        random.Random(args.seed).shuffle(pool)
        want += pool[:args.random]
    if not want:
        print("no pages selected", file=sys.stderr)
        return 2

    for key in want:
        p = pages[key]
        if key not in src:
            continue
        a, b, ratio = src[key]
        g = p.get("text") or ""
        print("=" * 100)
        print("%s  page %s   engine similarity %s   model confidence %s"
              % (key[0], key[1], ratio, p.get("confidence")))
        if p.get("note"):
            print("model note: %s" % p["note"])
        print("-" * 100)
        anchor = g[:0]
        for label, text in (("SARVAM", flat(a)), ("VISION", flat(b)), ("GEMINI", flat(g))):
            print("%-7s %s" % (label, window(text, anchor, args.width)))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
