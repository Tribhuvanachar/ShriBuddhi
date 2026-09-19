#!/usr/bin/env python3
"""
corpus_vocabulary.py -- ask the library whether it has ever seen a word.

USE THIS AS A LOOKUP, NOT AS A GATE. Measured, both ways, before you trust it.

Why it was built: on one page both OCR engines misread Brahma's seven mind-born
rishis, differently and both wrongly, and every check in the pipeline compares
the readings to each other -- so nothing could see it. But the library knows:
Atri appears in 154 files, Pulastya in 94, Marici in 298.

As a LOOKUP it does that job. Asked about the p32 readings it answers:

    atri      27 occurrences   pulastya   7      marici  7
    agu        0  FLAGGED      pulasya    0  FLAGGED

Two of the three misreadings, named as words the library has never seen.

As a GATE it fails, and the numbers are not close. Run over a real 253-page
resolved file it flags 248 pages and 6,424 words. Capped at 8-character words
it still flags 228. Three reasons, all structural rather than fixable by
tuning:

  compounding   Sanskrit forms compounds freely. gItAtAtparyanyAyadIpikATippaNI
                is a perfectly good word that will never occur twice.
  abbreviation  each book has its own citation shorthand -- bhA0dI0, nyA0dI0 --
                real, intended, and unique to that volume.
  transliteration  the same name has a Devanagari and a Kannada spelling, and
                the corpus may hold only one. aMgirasa, spelled CORRECTLY, is
                flagged, because the library has it only as aGgirasa.

And the miss that matters most: on that same page `agni` was read where `atri`
belongs. Agni occurs 70 times and always will. A misreading that lands on a
different REAL word is invisible to this and to everything else automatic --
it needs someone who knows Agni is not one of the seven rishis.

    python3 tools/corpus_vocabulary.py --build           # ~107MB, not committed
    python3 tools/corpus_vocabulary.py --check r.json    # noisy: see above
    python3 tools/corpus_vocabulary.py --lookup <word>   # what it is good at

The built index is large and derived, so it is regenerated rather than stored.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

DEVA = (0x0900, 0x097F)
KNDA = (0x0C80, 0x0CFF)
TAG = re.compile(r"<[^>]+>")
ENT = re.compile(r"&[a-z]+;")
MIN_LEN = 4            # shorter strings are too often fragments to judge
TEXT_FIELDS = ("sa", "sanskrit_text", "text", "samhita_patha", "mula_text",
               "kannada_text", "artha", "bhashya")


def words(s: str):
    s = ENT.sub(" ", TAG.sub(" ", s or ""))
    out, cur = [], []
    for ch in s:
        o = ord(ch)
        if DEVA[0] <= o <= DEVA[1] or KNDA[0] <= o <= KNDA[1]:
            cur.append(ch)
        else:
            if len(cur) >= MIN_LEN:
                out.append("".join(cur))
            cur = []
    if len(cur) >= MIN_LEN:
        out.append("".join(cur))
    return out


def walk_strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, list):
        for x in o:
            yield from walk_strings(x)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k in TEXT_FIELDS or isinstance(v, (list, dict)):
                yield from walk_strings(v)


def build(root="data"):
    vocab = collections.Counter()
    files = 0
    for dirpath, _d, fs in os.walk(root):
        for fn in fs:
            if fn != "data.json" and not fn.startswith("part-"):
                continue
            if not fn.endswith(".json"):
                continue
            try:
                d = json.load(open(os.path.join(dirpath, fn), encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            files += 1
            for s in walk_strings(d):
                for w in words(s):
                    vocab[w] += 1
    return vocab, files


def near(word, vocab, max_edits=1, cap=3):
    """Corpus words one edit away -- the likely intended reading.

    Only distance 1, and only against words the corpus actually has often.
    A suggestion drawn from another hapax is two guesses stacked.
    """
    out = []
    n = len(word)
    for cand, cnt in vocab.items():
        if cnt < 5 or abs(len(cand) - n) > max_edits or cand == word:
            continue
        # cheap bound before the real comparison
        if sum(1 for a, b in zip(cand, word) if a != b) > max_edits + 1:
            continue
        if _edits_within(word, cand, max_edits):
            out.append((cnt, cand))
    out.sort(reverse=True)
    return [c for _n, c in out[:cap]]


def _edits_within(a, b, k):
    if abs(len(a) - len(b)) > k:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > k:
            return False
        prev = cur
    return prev[-1] <= k


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--check")
    ap.add_argument("--vocab", default="admin/config/vocab.json")
    ap.add_argument("--out", default="")
    ap.add_argument("--root", default="data")
    ap.add_argument("--min-count", type=int, default=1,
                    help="a word needs this many corpus occurrences to pass")
    ap.add_argument("--lookup", nargs="*", help="how often the library has each word")
    ap.add_argument("--suggest", action="store_true",
                    help="offer corpus words one edit away (slow)")
    args = ap.parse_args(argv)

    if args.build:
        vocab, files = build(args.root)
        out = args.out or args.vocab
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        # Only words seen at least twice are kept. A corpus hapax is as likely
        # to be an existing OCR error as a real rare word, and keeping them
        # would let today's mistakes vouch for tomorrow's.
        keep = {w: c for w, c in vocab.items() if c >= 2}
        json.dump({"_readme": "Word -> occurrences across the library. Built by "
                              "tools/corpus_vocabulary.py; words seen once are "
                              "dropped, since a hapax cannot vouch for anything.",
                   "files": files, "distinct_kept": len(keep),
                   "vocab": keep}, open(out, "w", encoding="utf-8"),
                  ensure_ascii=False)
        print("%d file(s), %d distinct word(s) seen twice or more -> %s"
              % (files, len(keep), out))
        return 0

    if args.lookup:
        v = json.load(open(args.vocab, encoding="utf-8"))["vocab"]
        for w in args.lookup:
            c = v.get(w, 0)
            print("  %-22s %s" % (w, "%d occurrence(s)" % c if c else
                                  "NEVER SEEN in the library"))
            if not c and args.suggest:
                s2 = near(w, v)
                if s2:
                    print("        did the page mean: %s" % ", ".join(s2))
        return 0

    if not args.check:
        ap.print_help()
        return 2
    v = json.load(open(args.vocab, encoding="utf-8"))["vocab"]
    d = json.load(open(args.check, encoding="utf-8"))
    pages = d.get("pages") or []
    hits = []
    for p in pages:
        unknown = [w for w in words(p.get("text", ""))
                   if v.get(w, 0) < args.min_count]
        if unknown:
            hits.append((p.get("work"), p.get("page"), unknown))
    total = sum(len(u) for _w, _p, u in hits)
    print("%d page(s) checked, %d carry a word the library has never seen (%d words)"
          % (len(pages), len(hits), total))
    for work, page, unknown in hits[:25]:
        show = unknown[:6]
        line = "  %-26s p%-5s %s" % (str(work)[:26], page, ", ".join(show))
        print(line + (" ..." if len(unknown) > len(show) else ""))
        if args.suggest:
            for w in show[:3]:
                s = near(w, v)
                if s:
                    print("        %s -> %s" % (w, ", ".join(s)))
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
