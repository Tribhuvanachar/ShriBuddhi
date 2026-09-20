#!/usr/bin/env python3
"""
ocr_quality.py -- how good is the OCR, measured rather than assumed.

Written because the assumption was backwards. Sandhis 2-9 went through one
engine where the rest went through two, so they were treated as the weak
part of the work and a second Sarvam pass over all 2,969 of their pages was
about to be paid for. They are in fact the CLEANEST scans in the book.

THREE MEASUREMENTS, in descending order of how much they can be trusted.

1. QUOTED-VERSE FIDELITY -- the only one with real ground truth.
   Every commentary block opens by quoting its padya, and we hold the mula
   independently, so the OCR'd quotation can be scored against a text that
   did not come from OCR at all.

   Score by CONTAINMENT, not ratio. The verse span in the vision-only
   volumes often fails to terminate -- one runs 8,816 characters where the
   padya is 142 -- and ratio reads that as a catastrophic misread when it
   is a segmentation fault with a perfectly good verse sitting at its head.
   Scored by ratio the eight volumes look disastrous (mean 0.62 against
   0.92); scored by containment they are level with everything else.

2. VISION'S OWN PER-WORD CONFIDENCE -- free, covers every page, and
   compares the same engine across volumes, so it answers "are these worse
   scans" rather than "are these less checked". It is a weak predictor of
   the verse score (0.948 below 0.82 confidence against 0.957 above), so it
   is used here to RANK pages for attention, never to condemn one.

3. WHAT THE WEAK PAGES ACTUALLY ARE. Confidence collapses on tables, where
   the text may be perfectly legible and only the grid is lost. A table is
   not a job for a language model; it is a job for a layout engine. Sorting
   the weak pages into table / prose / near-empty is what turns "173 weak
   pages" into "112 prose pages worth a second reading".

WHAT THIS DELIBERATELY DOES NOT DO: recommend a single-engine model pass.
With two readings and a disagreement, a model adjudicates. With one reading
it generates, and invented Kannada in a Dvaita commentary reads as
authoritative when it is not.

    python3 tools/hks/ocr_quality.py --staging <dir-of-per-volume-ocr>
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import os
import re
import statistics
import sys

KANNADA = re.compile(r"[ಀ-೿]+")
KANNADA_CH = re.compile(r"[ಀ-೿]")
MULA = "data/Tattvavada/Itara/DasaSahitya/harikathamrutasara/data.json"
SEGMENTED = "data/ocr_staging/harikathamrutasara/commentary_segmented.json"

# The eight volumes that carry sandhis 2-9 and have only Vision behind them.
ONE_ENGINE = {"hks__%d_hks" % n for n in range(2, 10)}

# Below this, a page is worth a human or a second engine looking at it.
WEAK_CONFIDENCE = 0.80
# A page whose lines are mostly this short is a grid, not prose.
GRID_LINE_CHARS = 12
GRID_LINE_SHARE = 0.55
# Below this many Kannada characters a page is a plate, a blank or a failure.
MIN_KANNADA = 120


def kannada_only(text):
    return "".join(KANNADA.findall(text or ""))


def containment(a, b):
    """Longest matching runs over the length of the SHORTER text. Survives
    one side carrying a preamble or an unterminated span; ratio does not."""
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    total = sum(block.size for block in sm.get_matching_blocks())
    return total / max(1, min(len(a), len(b)))


class Mula:
    """The canonical padyas, indexed by 4-gram so a quotation can be matched
    against all 1,010 of them without 1,010 expensive comparisons."""

    def __init__(self, path):
        data = json.load(open(path, encoding="utf-8"))
        self.by_id = {}
        self.index = collections.defaultdict(set)
        for item in data["items"]:
            text = kannada_only(item.get("sa", ""))
            if len(text) < 40:
                continue
            self.by_id[item["id"]] = text
            for gram in {text[i:i + 4] for i in range(len(text) - 3)}:
                self.index[gram].add(item["id"])

    def best(self, quoted, shortlist=25):
        # Only the head can be the quotation -- past a few hundred
        # characters we are reading commentary, not verse.
        head = quoted[:400]
        if len(head) < 40:
            return None, 0.0
        hits = collections.Counter()
        for gram in {head[i:i + 4] for i in range(len(head) - 3)}:
            for pid in self.index.get(gram, ()):
                hits[pid] += 1
        best_id, best_score = None, 0.0
        for pid, _ in hits.most_common(shortlist):
            score = containment(head, self.by_id[pid])
            if score > best_score:
                best_id, best_score = pid, score
        return best_id, best_score


def read_vision(staging):
    """{(volume, page): {...}} from every vision_*.json under staging."""
    pages = {}
    for volume in sorted(os.listdir(staging)):
        vdir = os.path.join(staging, volume)
        if not os.path.isdir(vdir) or volume.startswith("_"):
            continue
        for name in sorted(os.listdir(vdir)):
            if "vision" not in name:
                continue
            blob = json.load(open(os.path.join(vdir, name), encoding="utf-8"))
            for page in blob.get("pages", []):
                words = [w for w in (page.get("words") or [])
                         if w.get("confidence") is not None]
                text = page.get("text") or ""
                lines = [l for l in text.split("\n") if l.strip()]
                short = sum(1 for l in lines
                            if len(l.strip()) <= GRID_LINE_CHARS)
                pages[(volume, str(page.get("page")))] = {
                    "volume": volume,
                    "page": str(page.get("page")),
                    "confidence": (statistics.mean(w["confidence"] for w in words)
                                   if words else 0.0),
                    "words": len(words),
                    "text": text,
                    "grid_share": short / max(1, len(lines)),
                    "kannada": sum(1 for c in text if KANNADA_CH.match(c)),
                }
    return pages


def classify(page):
    if page["kannada"] < MIN_KANNADA:
        return "near-empty / plate"
    if page["grid_share"] >= GRID_LINE_SHARE:
        return "table (grid layout)"
    return "prose"


def volume_order(name):
    m = re.search(r"__(\d+)", name)
    return int(m.group(1)) if m else 99


def report(staging, root):
    pages = read_vision(staging)
    if not pages:
        sys.exit("no vision_*.json found under %s" % staging)

    # ---- 1. quoted-verse fidelity, the one real ground truth
    mula = Mula(os.path.join(root, MULA))
    segmented = json.load(open(os.path.join(root, SEGMENTED), encoding="utf-8"))
    groups = collections.defaultdict(list)
    for volume in segmented["volumes"]:
        name = volume["volume"]
        label = ("one engine (sandhis 2-9)" if name in ONE_ENGINE
                 else "two engines + Gemini")
        for block in volume["blocks"]:
            _, score = mula.best(kannada_only(block.get("verse", "")))
            if score > 0:
                groups[label].append(score)

    print("1. QUOTED-VERSE FIDELITY against the canonical mula [containment]")
    print("   %-26s %6s %8s %8s %9s" % ("", "blocks", "mean", "median", "<0.90"))
    for label in sorted(groups):
        vals = groups[label]
        print("   %-26s %6d %8.3f %8.3f %8.1f%%" % (
            label, len(vals), statistics.mean(vals), statistics.median(vals),
            100 * sum(1 for v in vals if v < 0.90) / len(vals)))

    # ---- 2. Vision's own confidence, same engine across volumes
    by_volume = collections.defaultdict(list)
    for page in pages.values():
        by_volume[page["volume"]].append(page["confidence"])
    print("\n2. VISION PER-WORD CONFIDENCE  (* = one engine only)")
    print("   %-20s %6s %8s %11s" % ("volume", "pages", "mean", "pages<%.2f" % WEAK_CONFIDENCE))
    for name in sorted(by_volume, key=volume_order):
        vals = by_volume[name]
        print("   %-20s%s%5d %8.3f %10.1f%%" % (
            name, "*" if name in ONE_ENGINE else " ", len(vals),
            statistics.mean(vals),
            100 * sum(1 for v in vals if v < WEAK_CONFIDENCE) / len(vals)))

    split = collections.defaultdict(list)
    for page in pages.values():
        split["one engine (2-9)" if page["volume"] in ONE_ENGINE
              else "two engines"].append(page["confidence"])
    print("   %-20s %6s %8s %11s" % ("-" * 20, "-" * 6, "-" * 8, "-" * 11))
    for label in sorted(split):
        vals = split[label]
        print("   %-20s %6d %8.3f %10.1f%%" % (
            label, len(vals), statistics.mean(vals),
            100 * sum(1 for v in vals if v < WEAK_CONFIDENCE) / len(vals)))

    # ---- 3. what the weak pages actually are
    weak = [p for p in pages.values()
            if p["volume"] in ONE_ENGINE and p["confidence"] < WEAK_CONFIDENCE]
    total = sum(1 for p in pages.values() if p["volume"] in ONE_ENGINE)
    kinds = collections.Counter(classify(p) for p in weak)
    print("\n3. WHAT THE %d WEAK PAGES OF 2-9 ARE (of %d pages)" % (len(weak), total))
    for kind, n in kinds.most_common():
        print("   %-22s %4d   %.1f%% of the eight volumes" % (kind, n, 100 * n / total))
    print("   a table is a layout problem, not a reading problem -- and not")
    print("   a job for a language model.")
    return pages, weak


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staging", required=True,
                    help="directory holding one subdirectory of OCR json per volume")
    ap.add_argument("--root", default=".", help="repository root")
    args = ap.parse_args()
    report(args.staging, args.root)


if __name__ == "__main__":
    main()
