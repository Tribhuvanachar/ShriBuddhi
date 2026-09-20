#!/usr/bin/env python3
"""
attach_commentary.py -- hang each commentary block on the padya it is about.

NOT ON THE NUMBER IT PRINTS. The printed number is what a naive pass would
key on and it is wrong often enough to matter: sandhi 12's commentary prints
ಪದ್ಯ ೮೧ and ಪದ್ಯ ೮೩ where the verse quoted underneath is padya 41 and 43 --
೪ read as ೮, one stroke. Keyed by number, that commentary lands on verses
that do not exist; keyed by the verse it quotes, it lands where it belongs.

So every block is matched on the TEXT it quotes. Each block opens with the
padya itself before the commentary starts, which makes the block carry its
own answer, and a number is then only a check on the match rather than the
basis for it.

WHY CONTAINMENT AND NOT SIMILARITY. The two editions do not agree on where a
padya begins. This library's sandhi 17 padya 1 carries the avataranika and
the pallavi ahead of the verse, so it is 243 characters where the commentary
volume quotes 155 -- the same verse, one of them with a preamble. Ratio-based
similarity scores that pair at 0.20 and throws away a correct match. What is
actually true of them is that the shorter sits INSIDE the longer, so the
score used here is the longest common run over the length of the shorter
text, which reads that pair at over 0.9.

THE SANDHI NUMBER IS NOT USED AT ALL, and that is the second thing a naive
pass gets wrong. The two editions do not agree on the ORDER of the sandhis,
never mind the numbering within them. The commentary set makes the eighteenth
ಸರ್ವಸ್ವಾತಂತ್ರ್ಯ and the nineteenth ಕರ್ಮವಿಮೋಚನ; the mula's own table of
contents makes the eighteenth ಕ್ರೀಡಾವಿಲಾಸ and puts ಕರ್ಮವಿಮೋಚನ twenty-first.
It is not an offset that could be corrected by adding one -- the twentieth is
ಗುಣತಾರತಮ್ಯ in both. Several volumes number themselves ಸಂಪುಟ, a volume in a
series, which need never have agreed with a sandhi number in the first place.

So a block is matched against EVERY padya in the work, not against the
sandhi its folder claims. Doing that honestly is 634 x 1,010 comparisons of
long strings, so a cheap 4-gram overlap shortlists the plausible padyas and
the expensive comparison runs only on those.

WHAT IS REFUSED.
  * a match below --threshold: reported, not attached
  * two blocks whose best match is the same padya: both reported, neither
    attached, because one of them is wrong and nothing here knows which
  * a block whose quoted verse is too short to identify anything

A commentary on the wrong verse is worse than a missing one. It reads as
authoritative and nothing on the page says otherwise.

    python3 tools/hks/attach_commentary.py --segmented <file> --report
    python3 tools/hks/attach_commentary.py --segmented <file> --write
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import os
import re
import sys

WORK = "data/Tattvavada/Itara/DasaSahitya/harikathamrutasara/data.json"
MIN_VERSE = 40          # characters of Kannada; shorter identifies nothing
LABELS = {
    "bhavaprakashika": "ಭಾವಪ್ರಕಾಶಿಕೆ",
    "bhavadarpana": "ಭಾವದರ್ಪಣ",
    "bhavadarshana": "ಭಾವದರ್ಶನ",
    "guruhrdaya_prakashika": "ಶ್ರೀಗುರುಹೃದಯಪ್ರಕಾಶಿಕೆ",
    "sankarshana_odeyara_vyakhyana": "ಶ್ರೀಸಂಕರ್ಷಣ ಒಡೆಯರ ವ್ಯಾಖ್ಯಾನ",
    "vyasadasa_siddhanta_kaumudi": "ಶ್ರೀವ್ಯಾಸದಾಸ ಸಿದ್ಧಾಂತ ಕೌಮುದೀ",
    "pratipadartha": "ಪ್ರತಿಪದಾರ್ಥ",
    "vyakhyana": "ವ್ಯಾಖ್ಯಾನ",
}


def bare(t) -> str:
    """Kannada letters only. Dandas, digits, spaces and the scanner's Latin
    litter all vary between the two editions and none of them identify a verse."""
    return re.sub(r"[^ಀ-೿]", "", str(t or ""))


def containment(short: str, long: str) -> float:
    """Longest common run, over the length of the shorter text. autojunk is
    off: it discards anything appearing in more than 1% of a sequence over
    200 elements, which for Kannada prose is most of the alphabet."""
    if not short or not long:
        return 0.0
    if len(short) > len(long):
        short, long = long, short
    # The TOTAL of the matching runs, not the longest single one. A verse
    # with one OCR typo in the middle of it still shares everything either
    # side of the typo, and the longest single run measures only one side --
    # which scores a correct pair at half what it deserves.
    sm = difflib.SequenceMatcher(None, short, long, autojunk=False)
    return sum(b.size for b in sm.get_matching_blocks()) / len(short)


def load(root, segmented):
    doc = json.load(open(os.path.join(root, WORK), encoding="utf-8"))
    seg = json.load(open(segmented, encoding="utf-8"))
    blocks = [b for v in seg["volumes"] for b in v["blocks"]]
    return doc, blocks


def grams(t: str, n: int = 4) -> set:
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def match(doc, blocks, threshold, shortlist=25):
    texts = {it["id"]: bare(it["sa"]) for it in doc["items"]}
    gram_index = collections.defaultdict(set)
    for pid, t in texts.items():
        for g in grams(t):
            gram_index[g].add(pid)

    decided, skipped = {}, []
    proposals = collections.defaultdict(list)

    for b in blocks:
        verse = bare(b.get("verse"))
        if len(verse) < MIN_VERSE:
            skipped.append((b, "quoted verse too short to identify a padya"))
            continue
        # Shortlist by shared 4-grams, then score only those properly. Every
        # padya in the work is a candidate: the two editions do not agree on
        # which sandhi a verse belongs to, so filtering by sandhi first would
        # rule out the right answer before it was ever considered.
        counts = collections.Counter()
        for g in grams(verse):
            for pid in gram_index.get(g, ()):
                counts[pid] += 1
        best, score = None, 0.0
        for pid, _ in counts.most_common(shortlist):
            sc = containment(verse, texts[pid])
            if sc > score:
                best, score = pid, sc
        if best is None or score < threshold:
            skipped.append((b, "no padya in the work matches (best %.2f)" % score))
            continue
        proposals[best].append((score, b))

    for pid, cands in proposals.items():
        if len(cands) > 1:
            cands.sort(key=lambda c: -c[0])
            # Two blocks claiming one padya means one of them is wrong and
            # nothing here can tell which. Both are refused.
            for _, b in cands:
                skipped.append((b, "%d blocks claim %s; none attached"
                                % (len(cands), pid)))
            continue
        decided[pid] = cands[0][1]
    return decided, skipped


def layers(b) -> dict:
    out = {}
    for k in ("vyakhyana", "pratipadartha"):
        if str(b.get(k, "")).strip():
            out[k] = b[k].strip()
    for k, v in (b.get("commentaries") or {}).items():
        if str(v).strip():
            out[k] = v.strip()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--segmented", default="data/ocr_staging/harikathamrutasara/commentary_segmented.json")
    ap.add_argument("--root", default=".")
    ap.add_argument("--threshold", type=float, default=0.55)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    doc, blocks = load(args.root, args.segmented)
    decided, skipped = match(doc, blocks, args.threshold)

    renumbered = sum(1 for pid, b in decided.items()
                     if int(pid.rsplit("-", 1)[1]) != b["padya"])
    resandhied = sum(1 for pid, b in decided.items()
                     if int(pid.split("-")[1]) != b["sandhi"])
    print("commentary blocks      : %d" % len(blocks))
    print("attached to a padya    : %d  (%.0f%% of the work's %d padyas)"
          % (len(decided), 100 * len(decided) / len(doc["items"]), len(doc["items"])))
    print("  printed padya number disagreed : %d" % renumbered)
    print("  printed sandhi number disagreed: %d" % resandhied)
    print("not attached           : %d" % len(skipped))
    why = collections.Counter(re.sub(r"\d+", "N", r) for _, r in skipped)
    for r, n in why.most_common(6):
        print("    %4d  %s" % (n, r))

    per = collections.Counter()
    for b in decided.values():
        for k in layers(b):
            per[k] += 1
    print("\nlayers attached:")
    for k, n in per.most_common():
        print("    %-32s %d" % (LABELS.get(k, k), n))

    if not args.write:
        print("\nnot written -- pass --write")
        return 0

    n = 0
    for it in doc["items"]:
        b = decided.get(it["id"])
        if not b:
            continue
        lay = layers(b)
        if not lay:
            continue
        it["commentaries"] = lay
        it["commentary_source"] = {"volume": b.get("volume", ""), "page": b["page"],
                                   "printed_padya": b["padya"]}
        n += 1
    meta = doc.setdefault("source_meta", {})
    meta["commentary"] = {
        "edition": "ಸರ್ವವ್ಯಾಖ್ಯಾನಸಾರಸಂಗ್ರಹ",
        "padyas_with_commentary": n,
        "matched_by": "the verse each block quotes, not the number it prints",
        "tool": "tools/hks/attach_commentary.py",
    }
    sys.path.insert(0, os.path.join(args.root, "tools"))
    import format_data_json as F
    text = F.canonical(doc)
    if text is None:
        raise SystemExit("format_data_json will not canonicalise this shape")
    open(os.path.join(args.root, WORK), "w", encoding="utf-8").write(text)
    print("\nwrote %s -- %d padyas now carry commentary" % (WORK, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
