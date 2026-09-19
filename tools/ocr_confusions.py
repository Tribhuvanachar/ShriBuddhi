#!/usr/bin/env python3
"""
ocr_confusions.py -- mine the character confusions this corpus actually makes.

Not a replacement table. A replacement table for OCR is a corpus-destroying
idea: ghrANa is misread as prANa, but prANa is itself a real word appearing
correctly hundreds of times, and replacing it everywhere would be worse than
the original error.

What this builds is a table of which glyph pairs get confused, HOW OFTEN, and
-- where a third reading has adjudicated -- WHICH WAY. That feeds suspicion,
never substitution: "this looks like the pair that goes wrong 400 times in your
books, look here" is useful; "replace all X with Y" is vandalism.

Two sources of evidence, and they are not equally strong:

  DISAGREEMENT   two engines read the same page differently. Says the pair is
                 confusable. Does not say which is right.
  ADJUDICATED    a resolved file where the third reading chose. Directed: the
                 rejected form is the misread, the kept form is the reading.

Both come from this project's own books, so the table describes these fonts,
these scans and these scripts rather than OCR in general -- and it grows with
every volume processed.

    python3 tools/ocr_confusions.py --conflicts 'scratch/*/conflicts.json' \
        --resolved 'data/ocr_staging/_gemini/resolved_*.json' --out table.json
"""
from __future__ import annotations

import argparse
import collections
import difflib
import glob
import json
import re
import sys

TAG = re.compile(r"<[^>]+>")
ENT = re.compile(r"&[a-z]+;")
DEVA = (0x0900, 0x097F)
KNDA = (0x0C80, 0x0CFF)


def clean(s: str) -> str:
    return " ".join(ENT.sub(" ", TAG.sub(" ", s or "")).split())


def script_of(s: str) -> str:
    d = sum(1 for c in s if DEVA[0] <= ord(c) <= DEVA[1])
    k = sum(1 for c in s if KNDA[0] <= ord(c) <= KNDA[1])
    return "devanagari" if d >= k else "kannada"


def is_letters(s: str) -> bool:
    """True only if every character is a Devanagari or Kannada letter/mark.

    Without this the table is 80% punctuation: the engines disagree about
    comma-versus-full-stop 687 times and about how to write a double danda 620
    times, and those drown the rows that matter -- ba/va confused 122 times,
    Kannada i/ii 163 times. Punctuation disagreement is real but it is a
    normalisation problem with a deterministic fix, not a reading problem
    needing a human eye.
    """
    if not s:
        return False
    return all(DEVA[0] <= ord(c) <= DEVA[1] or KNDA[0] <= ord(c) <= KNDA[1]
               for c in s)


def pairs(a: str, b: str, max_len: int = 12):
    """Substituted stretches between two readings of the same page.

    Only replacements are taken. An insertion or deletion tells us an engine
    dropped or added something, which is a different fault from misreading a
    glyph, and mixing them makes the table useless for its one job.
    """
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "replace":
            continue
        x, y = a[i1:i2].strip(), b[j1:j2].strip()
        if not x or not y or len(x) > max_len or len(y) > max_len:
            continue
        if not (is_letters(x) and is_letters(y)):
            continue
        yield x, y


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--conflicts", nargs="*", default=[])
    ap.add_argument("--resolved", nargs="*", default=[])
    ap.add_argument("--out", default="")
    ap.add_argument("--min-count", type=int, default=3)
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args(argv)

    def expand(pats):
        out = []
        for p in pats:
            out.extend(sorted(glob.glob(p)) or ([p] if glob.glob(p) else []))
        return out

    undirected = collections.Counter()      # {frozenset-ish "x|y"} -> n
    directed = collections.Counter()        # (misread, reading) -> n
    by_script = collections.Counter()
    pages = 0

    for f in expand(args.conflicts):
        try:
            c = json.load(open(f, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for x in c.get("conflicts", []):
            a, b = clean(x.get("sarvam", "")), clean(x.get("vision", ""))
            if not a or not b:
                continue
            pages += 1
            sc = script_of(a + b)
            for p, q in pairs(a, b):
                undirected["%s\t%s" % tuple(sorted((p, q)))] += 1
                by_script[sc] += 1

    # Adjudicated evidence: the resolved text kept one form and dropped another.
    for f in expand(args.resolved):
        try:
            r = json.load(open(f, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for p in r.get("pages", []):
            for e in (p.get("emendations") or []):
                a, b = clean(e.get("from", "")), clean(e.get("to", ""))
                if a and b and a != b and len(a) <= 40:
                    for x, y in pairs(a, b):
                        directed[(x, y)] += 1
            # A suspect is a proposal, not a decision -- recorded separately by
            # the caller if wanted, never mixed into evidence here.

    table = {
        "_readme": [
            "Character confusions measured in THIS corpus. Feeds suspicion, never",
            "substitution: several of these forms are real words that appear",
            "correctly far more often than they appear as errors.",
            "",
            "undirected: the two engines read this pair differently on the same",
            "  page. Evidence the pair is confusable; no claim about which is right.",
            "directed: a third reading adjudicated and rejected `misread` in favour",
            "  of `reading`. Stronger, and far rarer.",
        ],
        "pages_compared": pages,
        "by_script": dict(by_script),
        "undirected": [
            {"a": k.split("\t")[0], "b": k.split("\t")[1], "count": v}
            for k, v in undirected.most_common() if v >= args.min_count
        ],
        "directed": [
            {"misread": a, "reading": b, "count": v}
            for (a, b), v in directed.most_common() if v >= 1
        ],
    }
    if args.out:
        json.dump(table, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    print("pages compared: %d   (%s)" % (pages, dict(by_script)))
    print("\nmost confused pairs (either direction, count >= %d):" % args.min_count)
    print("  %-18s %-18s %6s" % ("reading A", "reading B", "count"))
    for row in table["undirected"][:args.top]:
        print("  %-18s %-18s %6d" % (row["a"][:18], row["b"][:18], row["count"]))
    if table["directed"]:
        print("\nadjudicated (a third reading rejected the first):")
        for row in table["directed"][:args.top]:
            print("  %-18s -> %-18s %6d" % (row["misread"][:18], row["reading"][:18], row["count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
