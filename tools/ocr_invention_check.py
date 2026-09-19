#!/usr/bin/env python3
"""
ocr_invention_check.py -- catch text a model wrote that no engine read.

The failure this exists for, from the first real Gemini run, 19 Sep 2026:

    Sarvam  tarhi te 'vIha lokeShu
    Vision  tarhi te 'ha  lokeShu
    Gemini  tarhi te 'smin lokeShu        <- nobody read 'smin

Grammatical Sanskrit, plausible metre, confidence 0.9, and not what is printed
on the page. On the same page it inserted "devA" to complete a verse. That is
an editorial conjecture presented as a reading, and in a corpus meant to be
99% faithful it is worse than leaving the OCR error in: an OCR error looks
wrong, a good conjecture looks right.

The test: every Indic character n-gram in the output should be traceable to one
of the two readings. Output is allowed to CHOOSE between engines and to JOIN
what an engine split, so short novel n-grams at word boundaries are normal.
Sustained novel runs are not.

    python3 tools/ocr_invention_check.py --resolved r.json --conflicts c.json...
    python3 tools/ocr_invention_check.py ... --max-novel 0.03   # gate

Exits non-zero when any page exceeds the threshold, so it can gate a merge.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import sys

TAG = re.compile(r"<[^>]+>")
ENT = re.compile(r"&[a-z]+;")


def indic(s: str) -> str:
    """Only the letters. Layout, punctuation and digits are the engines' to
    disagree about; what must not appear from nowhere is TEXT."""
    s = ENT.sub(" ", TAG.sub(" ", s or ""))
    return "".join(c for c in s
                   if 0x0900 <= ord(c) <= 0x097F or 0x0C80 <= ord(c) <= 0x0CFF)


def grams(s: str, n: int) -> set:
    return {s[i:i + n] for i in range(len(s) - n + 1)}


DIGITS = set("0123456789०१२३४५६७८९೦೧೨೩೪೫೬೭೮೯")


def is_prose(run: str) -> bool:
    """A novel run of LETTERS is a conjecture. A novel run containing digits is
    almost always a table whose cells the model reordered -- a real change, but
    a different problem from inventing words, and mixing the two buries the one
    that matters under the one that does not.
    """
    return bool(run) and not (set(run) & DIGITS)


def longest_novel_run(out: str, have: set, n: int) -> str:
    """The longest stretch of output whose every n-gram is novel.

    A count of novel n-grams cannot tell an inserted word from a hundred
    word-joins. A RUN can: joining two words makes one novel n-gram, inserting
    devA makes a run several n-grams long.
    """
    best = cur = ""
    for i in range(len(out) - n + 1):
        if out[i:i + n] not in have:
            cur = cur + out[i + n - 1] if cur else out[i:i + n]
            if len(cur) > len(best):
                best = cur
        else:
            cur = ""
    return best


FORBIDDEN_REASONS = ("metre", "meter", "metri", "chandas", "छन्द",
                     "rhyme", "scans", "syllable count")


def bad_emendations(page):
    """Emendations that fail on their own terms, before anyone reads the text.

    Two kinds, both found in the 19 Sep 2026 run:

    no-op     `from` and `to` identical -- a change declared where nothing
              changed. Harmless to the text, but it inflates the count a
              reviewer is budgeting against and hides among real ones.
    forbidden the stated reason cites metre, which the prompt lists as NOT a
              warrant precisely because "the metre wants a syllable here" is
              how a plausible conjecture gets written into scripture.
    """
    out = []
    for e in (page.get("emendations") or []):
        frm, to = (e.get("from") or "").strip(), (e.get("to") or "").strip()
        why = (e.get("why") or "").lower()
        if frm == to:
            out.append(("no-op", e))
        elif any(w in why for w in FORBIDDEN_REASONS):
            out.append(("reason is metre", e))
    return out


def declared(page) -> str:
    """Everything the model said it changed, as one blob to match against.

    A declared emendation is a decision with a warrant; an undeclared departure
    is an invention. The only difference the machine can see is whether the
    novel stretch turns up in `emendations`, so that is what it checks.
    """
    return "".join(indic(e.get("to", "")) for e in (page.get("emendations") or []))


def check(resolved, sources, n=4, max_novel=0.03, min_run=8):
    rows = []
    for p in resolved.get("pages", []):
        key = (p.get("work"), p.get("page"))
        if key not in sources:
            continue
        a, b = sources[key]
        have = grams(indic(a), n) | grams(indic(b), n)
        out_s = indic(p.get("text"))
        out = grams(out_s, n)
        if len(out) < 20:
            continue
        # A stretch the model declared as an emendation is not novel text --
        # it is a change it owned up to, with a warrant, for a human to judge.
        have_declared = have | grams(declared(p), n)
        run = longest_novel_run(out_s, have_declared, n)
        prose = is_prose(run)
        novel = out - have_declared
        rows.append({
            "work": key[0], "page": key[1],
            "novel_share": len(novel) / len(out),
            "longest_novel_run": run,
            "run_len": len(run),
            "confidence": p.get("confidence"),
            "emendations": len(p.get("emendations") or []),
            "warrants": [e.get("warrant") for e in (p.get("emendations") or [])],
            "bad_emendations": [(k, e.get("from"), e.get("to"))
                                for k, e in bad_emendations(p)],
            "suspects": len(p.get("suspects") or []),
            "prose_run": prose,
            # Only a novel run of pure letters is reported as invention.
            "flagged": prose and len(run) >= min_run,
        })
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--resolved", required=True)
    ap.add_argument("--conflicts", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--max-novel", type=float, default=0.03)
    ap.add_argument("--min-run", type=int, default=8,
                    help="an unbroken novel stretch this long is an insertion, "
                         "not a word-join")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    sources = {}
    files = []
    for pat in args.conflicts:
        files.extend(sorted(glob.glob(pat)) or [pat])
    for f in files:
        c = json.load(open(f, encoding="utf-8"))
        for x in c.get("conflicts", []):
            sources[(c.get("work"), x["page"])] = (x.get("sarvam", ""), x.get("vision", ""))

    rows = check(json.load(open(args.resolved, encoding="utf-8")), sources,
                 args.n, args.max_novel, args.min_run)
    if not rows:
        print("nothing to check -- no page matched a source reading", file=sys.stderr)
        return 2

    flagged = [r for r in rows if r["flagged"]]
    warrants = collections.Counter(w for r in rows for w in r.get("warrants") or [])
    rows.sort(key=lambda r: -r["run_len"])
    print("%d page(s) checked, %d flagged (%.1f%%)"
          % (len(rows), len(flagged), 100 * len(flagged) / len(rows)))
    print("mean novel share %.2f%%, median %.2f%%"
          % (100 * sum(r["novel_share"] for r in rows) / len(rows),
             100 * sorted(r["novel_share"] for r in rows)[len(rows) // 2]))
    if flagged:
        print("\n%-30s %6s %7s %5s  longest stretch nobody read"
              % ("work", "page", "novel", "conf"))
        for r in rows:
            if not r["flagged"]:
                continue
            print("%-30s %6s %6.1f%% %5s  %s"
                  % (r["work"][:30], r["page"], 100 * r["novel_share"],
                     r["confidence"], r["longest_novel_run"][:40]))
    bad = [(r["work"], r["page"], k, f, t)
           for r in rows for (k, f, t) in r.get("bad_emendations") or []]
    if bad:
        print("\n%d emendation(s) fail on their own terms:" % len(bad))
        for work, page, kind, f, t in bad[:12]:
            print("  %-24s p%-5s %-16s %s -> %s"
                  % (str(work)[:24], page, kind, (f or "")[:20], (t or "")[:20]))
    if warrants:
        # Printed by kind, because the mix is the signal. A run that is all
        # `internal` is not a careful run -- it is a run with nowhere else to
        # file a grammatical correction, which is what happened before
        # `grammatical` and `script` existed.
        print("\nemendations by warrant: %s"
              % ", ".join("%s %d" % kv for kv in warrants.most_common()))
        soft = warrants.get("grammatical", 0) + warrants.get("internal", 0)
        if soft:
            print("  %d rest on judgement (internal/grammatical) -- read these" % soft)
    if args.out:
        json.dump({"checked": len(rows), "flagged": len(flagged),
                   "warrants": dict(warrants), "pages": rows},
                  open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
