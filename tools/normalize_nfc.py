#!/usr/bin/env python3
"""
normalize_nfc.py -- put every JSON file under data/ into Unicode NFC.

Why this matters for a text corpus. Kannada vowel signs were being stored
decomposed: ಕೆ followed by a length mark, where NFC writes the single
character ಕೈ. The two render identically and are canonically equivalent, so no
reader ever noticed -- but they are different byte sequences, so search misses,
deduplication misses, a diff between two editions shows phantom changes, and
any downstream tokenizer treats them as unrelated. 67,841 items were affected,
most of them in itihasa.

NFC is safe by definition: Unicode requires canonically equivalent strings to
be rendered and interpreted identically. What it does here is compose those
vowel signs and put Vedic accent marks into canonical order.

It rewrites the FILE TEXT, not a re-serialised parse. JSON's own syntax is
ASCII and unaffected by NFC, so every non-ASCII character it touches is inside
a string literal -- and this way the repository's formatting survives
untouched, which matters because format_data_json.py --check gates CI on one
unit per line and a re-serialise would fail it on every file it touched.

    python3 tools/normalize_nfc.py --check    # report, exit 1 if any remain
    python3 tools/normalize_nfc.py --fix
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata as U


def json_files(root):
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if fn.endswith(".json"):
                yield os.path.join(dirpath, fn)


def check_file(path):
    """(needs_change, safe, why). Safe means: NFC changes the text, the result
    still parses, and it parses to something canonically equal to the original."""
    raw = open(path, encoding="utf-8").read()
    out = U.normalize("NFC", raw)
    if out == raw:
        return False, True, ""
    try:
        before, after = json.loads(raw), json.loads(out)
    except Exception as e:  # noqa: BLE001
        return True, False, "does not parse after normalising: %s" % e
    # The parsed structures must differ ONLY by normalisation. If NFC on the
    # raw text changed anything else -- a key merging into another, a number
    # or a structure -- this is not the safe rewrite it claims to be.
    def norm(o):
        if isinstance(o, str):
            return U.normalize("NFC", o)
        if isinstance(o, list):
            return [norm(x) for x in o]
        if isinstance(o, dict):
            d = {U.normalize("NFC", k): norm(v) for k, v in o.items()}
            if len(d) != len(o):
                raise ValueError("two keys normalise to the same string")
            return d
        return o
    try:
        if norm(before) != after:
            return True, False, "normalising the text is not the same as normalising the data"
    except ValueError as e:
        return True, False, str(e)
    return True, True, ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--check", action="store_true", help="report only (the default)")
    ap.add_argument("--root", default="data")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    todo, unsafe = [], []
    for p in sorted(json_files(args.root)):
        needs, safe, why = check_file(p)
        if not needs:
            continue
        (todo if safe else unsafe).append((p, why))

    if unsafe:
        print("%d file(s) cannot be normalised safely -- not touching them:" % len(unsafe))
        for p, why in unsafe:
            print("  %s\n    %s" % (p, why))

    if not todo:
        if not args.quiet and not unsafe:
            print("every JSON file under %s is already NFC." % args.root)
        return 1 if unsafe else 0

    if not args.fix:
        print("%d file(s) are not NFC. Run with --fix." % len(todo))
        for p, _ in todo[:10]:
            print("  %s" % p)
        if len(todo) > 10:
            print("  ... and %d more" % (len(todo) - 10))
        return 1

    for p, _ in todo:
        raw = open(p, encoding="utf-8").read()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(U.normalize("NFC", raw))
    print("normalised %d file(s)." % len(todo))
    return 1 if unsafe else 0


if __name__ == "__main__":
    raise SystemExit(main())
