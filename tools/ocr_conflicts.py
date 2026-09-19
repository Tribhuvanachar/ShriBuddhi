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
    """(sarvam files, vision files) inside a staging folder -- ALL of them.

    A work is OCRed in chunks: Sarvam caps a request at 200 pages, so a
    700-page book arrives as four files. This used to take the first file it
    found and compare that alone, which meant every page outside that one chunk
    had nothing to compare against and was reported as a conflict. On the
    Harikathamrutasara that turned a genuine ~6% disagreement into 50%, and the
    whole point of this tool is to keep pages away from a paid model.
    """
    return (sorted(glob.glob(os.path.join(work_dir, "sarvam_pages*.json"))),
            sorted(glob.glob(os.path.join(work_dir, "vision_pages*.json"))))


def load_all(paths):
    """Every chunk of one engine, merged into one page -> text map."""
    merged = {}
    for p in paths:
        for n, t in load_pages(p).items():
            # A page that appears twice with text in only one copy keeps the
            # text: a re-run of a failed chunk sits beside the failure.
            if t.strip() or n not in merged:
                merged[n] = t
    return merged


CONTEXT_CHARS = 700


def tail(s: str, n: int) -> str:
    return s[-n:] if len(s) > n else s


def normalise_ws(s: str) -> str:
    """Neighbour text is context, not output -- strip its markup and collapse
    whitespace so it costs as few tokens as it can while still reading."""
    return WS.sub(" ", TAG.sub(" ", s or "")).strip()


def compare(sarvam: dict, vision: dict, threshold: float):
    """Pages needing a third opinion, with both readings, why, and neighbours.

    Only pages in conflict are sent on, so a disputed page arrives with no idea
    what sentence was running into it or out of it -- and a commentary crossing
    a page break is exactly where a reading is hardest to judge. The pages
    either side usually AGREED, which means their text is settled and free: we
    already have it, it costs one extra fetch of nothing, and it is the context
    a human proofreader would reach for first.

    Carried as `context_before`/`context_after` and marked in the prompt as
    read-only. The model must not return them or correct them.
    """
    conflicts, agreed, only_one = [], 0, 0
    for n in sorted(set(sarvam) | set(vision)):
        a, b = sarvam.get(n, ""), vision.get(n, "")
        na, nb = normalise(a), normalise(b)
        if not na and not nb:
            continue
        if not na or not nb:
            # One engine has nothing for this page. That is a gap in coverage,
            # not a disagreement, and it must not be priced as one: paying a
            # third model to arbitrate between a reading and a blank buys
            # nothing. Counted and reported, kept out of `conflicts`.
            only_one += 1
            continue
        # autojunk=False is not a tuning knob here, it is the difference
        # between this tool working and not working. SequenceMatcher's default
        # treats any element occurring in more than 1% of a sequence longer
        # than 200 as junk and ignores it -- a heuristic meant for source code,
        # where that catches blank lines. In Devanagari or Kannada prose it
        # catches the space and every common letter, so two readings of one
        # page that differ in a single digit scored 0.0018 instead of 0.9921
        # and were billed to Gemini as a total disagreement. Every test fixture
        # was under 200 characters, which is exactly where the heuristic is
        # switched off, so nothing caught it.
        ratio = difflib.SequenceMatcher(None, na, nb, autojunk=False).ratio()
        if ratio >= threshold:
            agreed += 1
        else:
            # Prefer Sarvam for the neighbour text (it keeps layout), falling
            # back to Vision where Sarvam has nothing for that page.
            before = sarvam.get(n - 1) or vision.get(n - 1) or ""
            after = sarvam.get(n + 1) or vision.get(n + 1) or ""
            conflicts.append({"page": n, "reason": "readings differ",
                              "ratio": round(ratio, 3), "sarvam": a, "vision": b,
                              "context_before": tail(normalise_ws(before), CONTEXT_CHARS),
                              "context_after": normalise_ws(after)[:CONTEXT_CHARS]})
    return conflicts, agreed, only_one


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--work", required=True, help="staging folder holding both engines' files")
    ap.add_argument("--threshold", type=float, default=0.92,
                    help="similarity at or above which the two readings count as agreeing")
    ap.add_argument("--out", default="", help="where to write the conflicts file")
    args = ap.parse_args(argv)

    s_paths, v_paths = find(args.work)
    if not s_paths or not v_paths:
        print("need both engines' output in %s (found sarvam=%d file(s) vision=%d)"
              % (args.work, len(s_paths), len(v_paths)), file=sys.stderr)
        return 2

    sarvam, vision = load_all(s_paths), load_all(v_paths)
    conflicts, agreed, only_one = compare(sarvam, vision, args.threshold)
    # Pages only one engine covered are NOT part of the comparison: the
    # percentage below is out of pages that were actually compared, so a work
    # half-OCRed by one engine cannot masquerade as a work full of conflicts.
    total = agreed + len(conflicts)

    out = args.out or os.path.join(args.work, "conflicts.json")
    payload = {
        "_readme": "Pages where Sarvam and Vision disagree. Only these need a third "
                   "reading; where the two agreed, that agreement is the evidence. "
                   "Consumed by the Gemini reconciliation step.",
        "work": os.path.basename(args.work.rstrip("/")),
        "sarvam_files": [os.path.basename(p) for p in s_paths],
        "vision_files": [os.path.basename(p) for p in v_paths],
        "threshold": args.threshold,
        "pages_total": total,
        "pages_agreed": agreed,
        "pages_conflicting": len(conflicts),
        "pages_only_one_engine": only_one,
        "conflict_chars": sum(len(c["sarvam"]) + len(c["vision"]) for c in conflicts),
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
