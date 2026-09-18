#!/usr/bin/env python3
"""
ocr_conflicts.py — find the pages where two OCR engines disagree, and stage
ONLY those for a later Gemini pass.

WHY THIS EXISTS. Sending every page to Gemini is how the last top-up was
consumed. But most pages do not need it: where Sarvam and Vision independently
read the same thing, that agreement is already strong evidence, and a third
model adds cost without adding information. The pages worth paying for are the
ones where the two readings differ.

So this reads both engines' staged output for a work, compares page by page,
and writes a conflicts file holding both readings for the disagreeing pages
only. Nothing here calls an API or spends anything. The Gemini step consumes
this file when there is budget for it; until then the conflicts file is itself
useful, because a page both engines misread the same way is invisible but a
page they disagree on is exactly where a human reviewer should look first.

    python3 tools/ocr_conflicts.py --work data/ocr_staging/<slug>
    python3 tools/ocr_conflicts.py --work <dir> --threshold 0.94 --out <file>

The prompt that consumes this already exists, in convert/gemini.js: it takes
two readings per page, uses their agreement where they agree, resolves by
context where they differ, and self-reports accept/review/unresolved. This
supplies its input without the pages that would have been "accept" anyway.
"""
from __future__ import annotations

import argparse
import difflib
import glob
import json
import os
import re
import sys

# Sarvam returns HTML to keep layout; Vision returns flat text. Comparing those
# as-is reports a conflict on every page, which is the same as reporting none.
TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")
# Devanagari digits, dandas and the Latin digits an engine may substitute for
# them are compared loosely: a page is not "in conflict" because one engine
# wrote ॥२॥ and the other ॥ 2 ॥.
DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
PUNCT = re.compile(r"[।॥|,.\-–—:;'\"()\[\]]")


def normalise(text: str) -> str:
    if not text:
        return ""
    t = TAG.sub(" ", text)
    t = t.translate(DIGITS)
    t = PUNCT.sub(" ", t)
    return WS.sub(" ", t).strip()


def load_pages(path: str) -> dict:
    """{page number: text} from either engine's staged file."""
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    out = {}
    for p in doc.get("pages", []):
        n = p.get("page")
        if n is None:
            continue
        # engines name the field differently; take the first that has content
        for key in ("text", "html", "markdown", "content", "md"):
            if isinstance(p.get(key), str) and p[key].strip():
                out[int(n)] = p[key]
                break
        else:
            out[int(n)] = ""
    return out


def find(work_dir: str):
    """(sarvam file, vision file) inside a staging folder."""
    def pick(pattern):
        hits = sorted(glob.glob(os.path.join(work_dir, pattern)))
        return hits[0] if hits else None
    return pick("sarvam_pages*.json"), pick("vision_pages*.json")


def compare(sarvam: dict, vision: dict, threshold: float):
    """Pages needing a third opinion, with both readings and why."""
    conflicts, agreed, only_one = [], 0, 0
    for n in sorted(set(sarvam) | set(vision)):
        a, b = sarvam.get(n, ""), vision.get(n, "")
        na, nb = normalise(a), normalise(b)
        if not na and not nb:
            continue
        if not na or not nb:
            # One engine produced nothing. Not a disagreement about content —
            # a failure — but it still needs the other engine's reading checked,
            # so it goes in the file flagged for what it is.
            only_one += 1
            conflicts.append({"page": n, "reason": "one engine returned nothing",
                              "ratio": 0.0, "sarvam": a, "vision": b})
            continue
        ratio = difflib.SequenceMatcher(None, na, nb).ratio()
        if ratio >= threshold:
            agreed += 1
        else:
            conflicts.append({"page": n, "reason": "readings differ",
                              "ratio": round(ratio, 3), "sarvam": a, "vision": b})
    return conflicts, agreed, only_one


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--work", required=True, help="staging folder holding both engines' files")
    ap.add_argument("--threshold", type=float, default=0.92,
                    help="similarity at or above which the two readings count as agreeing")
    ap.add_argument("--out", default="", help="where to write the conflicts file")
    args = ap.parse_args(argv)

    s_path, v_path = find(args.work)
    if not s_path or not v_path:
        print("need both engines' output in %s (found sarvam=%s vision=%s)"
              % (args.work, bool(s_path), bool(v_path)), file=sys.stderr)
        return 2

    sarvam, vision = load_pages(s_path), load_pages(v_path)
    conflicts, agreed, only_one = compare(sarvam, vision, args.threshold)
    total = agreed + len(conflicts)

    out = args.out or os.path.join(args.work, "conflicts.json")
    payload = {
        "_readme": "Pages where Sarvam and Vision disagree. Only these need a third "
                   "reading; where the two agreed, that agreement is the evidence. "
                   "Consumed by the Gemini reconciliation step.",
        "work": os.path.basename(args.work.rstrip("/")),
        "sarvam_file": os.path.basename(s_path),
        "vision_file": os.path.basename(v_path),
        "threshold": args.threshold,
        "pages_total": total,
        "pages_agreed": agreed,
        "pages_conflicting": len(conflicts),
        "pages_one_engine_empty": only_one,
        "conflicts": conflicts,
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    pct = (100.0 * len(conflicts) / total) if total else 0.0
    chars = sum(len(c["sarvam"]) + len(c["vision"]) for c in conflicts)
    print("%s: %d page(s), %d agreed, %d need a third reading (%.1f%%)"
          % (payload["work"], total, agreed, len(conflicts), pct))
    if only_one:
        print("  of those, %d had one engine return nothing at all" % only_one)
    print("  %s" % out)
    print("  a Gemini pass on this work would send ~%d characters, not ~%d"
          % (chars, sum(len(t) for t in list(sarvam.values()) + list(vision.values()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
