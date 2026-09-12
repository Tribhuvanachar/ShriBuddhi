#!/usr/bin/env python3
"""Build dge/data/vedanga/vyakarana/ashtadhyayi/kaumudi_order/data.json -- the
correspondence between the standard Ashtadhyayi sutra numbering (1.1.1, ...)
and the Siddhanta Kaumudi's own reading order, with the Kaumudi's 70
traditional prakarana divisions.

v2 -- REPLACES the earlier text-matching build, and fixes a real data bug.

The first version of this tool matched our sutrapatha text against
ashtadhyayi-com/data's ska/data.txt on the belief that that file was the
Siddhanta Kaumudi's own text; only ~1,100 sutras matched and the result was
shipped as an honestly-partial mapping. Checked directly this time: ska's
own row 48 reads a sutra that is NOT what the Siddhanta Kaumudi numbers 48
(and ska's opening sutra is not the SK's opening either) -- ska is some
other sutra collection entirely, so the old mapping's numbers were not SK
positions at all. What IS the SK position is sutraani/data.txt's own `skn`
field (with `lskn` for the Laghu-Siddhanta-Kaumudi and `sk_chapter` for the
prakarana): verified against a phone screenshot of ashtadhyayi.com's reader,
where sutra 8.4.47 displays "कौमुदी-४८" and skn for 8.4.47 is 48, inside
sk_chapter 3 whose heading their reader shows as अच्सन्धिप्रकरणम्.

Coverage: 3,978 of the source's 3,983 sutras carry a non-zero skn, and
1,269 a Laghu-SK position -- effectively complete, vs the old ~28%.

JOINING BY ID WOULD REINTRODUCE A KNOWN BUG. The source's sutra numbering
disagrees with this repo's sutrapatha inside several padas (ours reads
उञ ऊँ as one sutra where the source counts two, etc.) -- the same
misalignment that once put a quarter of the Ashtadhyayi's glosses on the
wrong sutra (see tools/realign_sutra_enrichment.py's docstring). So this
tool aligns the two lists per pada BY THEIR OWN TEXT (consonant-bag F1 +
Needleman-Wunsch, the realign tool's technique) and only then carries the
skn across. A sutra of ours that aligns to nothing gets no entry; a source
row that aligns to nothing is dropped. Both are reported.

The 70 prakarana names are the Siddhanta Kaumudi's own traditional chapter
names (Bhattoji Dikshita's arrangement, classical tradition); the numbering
matches the source's sk_chapter field, cross-checked against the actual
sutra content at each boundary (ch. 3 opens इको यणचि = अच्सन्धि; ch. 43
opens वर्तमाने लट् = तिङन्ते भ्वादि; ch. 16 opens
प्रातिपदिकार्थ...प्रथमा = कारक).

Usage:
    python3 tools/build_kaumudi_order.py /path/to/ashtadhyayi-com-data-clone
"""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

SOURCE_NOTE = ("ashtadhyayi-com/data (github.com/ashtadhyayi-com/data, "
               "sutraani/data.txt skn/lskn/sk_chapter fields); its README: "
               "\"free to use ... provided that appropriate credits are mentioned\".")

REPO_ROOT = Path(__file__).resolve().parent.parent
SUTRAPATHA_PATH = REPO_ROOT / "dge/data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json"
OUT_PATH = REPO_ROOT / "dge/data/vedanga/vyakarana/ashtadhyayi/kaumudi_order/data.json"

# The Siddhanta Kaumudi's 70 prakaranas, in sk_chapter order.
CHAPTERS = [
    "संज्ञाप्रकरणम्", "परिभाषाप्रकरणम्", "अच्सन्धिप्रकरणम्", "अच्सन्धौ प्रकृतिभावः",
    "हल्सन्धिप्रकरणम्", "विसर्गसन्धिप्रकरणम्", "स्वादिसन्धिप्रकरणम्",
    "अजन्तपुंलिङ्गप्रकरणम्", "अजन्तस्त्रीलिङ्गप्रकरणम्", "अजन्तनपुंसकलिङ्गप्रकरणम्",
    "हलन्तपुंलिङ्गप्रकरणम्", "हलन्तस्त्रीलिङ्गप्रकरणम्", "हलन्तनपुंसकलिङ्गप्रकरणम्",
    "अव्ययप्रकरणम्", "स्त्रीप्रत्ययप्रकरणम्", "कारकप्रकरणम्",
    "अव्ययीभावसमासप्रकरणम्", "तत्पुरुषसमासप्रकरणम्", "बहुव्रीहिसमासप्रकरणम्",
    "द्वन्द्वसमासप्रकरणम्", "एकशेषप्रकरणम्", "सर्वसमासशेषप्रकरणम्",
    "सर्वसमासान्तप्रकरणम्", "अलुक्समासप्रकरणम्", "समासाश्रयविधिप्रकरणम्",
    "तद्धिताधिकारप्रकरणम्", "तद्धितेषु चातुरर्थिकप्रकरणम्", "तद्धितेषु शैषिकप्रकरणम्",
    "तद्धितेषु प्राग्दीव्यतीयप्रकरणम्", "तद्धितेषु प्राग्वहतीयप्रकरणम्",
    "तद्धितेषु प्राग्घितीयप्रकरणम्", "तद्धितेषु छयद्विधिप्रकरणम्",
    "तद्धितेष्वार्हीयप्रकरणम्", "तद्धितेषु कालाधिकारप्रकरणम्",
    "तद्धितेषु ठञ्विधिप्रकरणम्", "तद्धितेषु भावकर्मार्थाः",
    "तद्धितेषु पाञ्चमिकप्रकरणम्", "तद्धितेषु मत्वर्थीयप्रकरणम्",
    "तद्धितेषु प्राग्दिशीयप्रकरणम्", "तद्धितेषु प्रागिवीयप्रकरणम्",
    "तद्धितेषु स्वार्थिकप्रकरणम्", "द्विरुक्तप्रकरणम्",
    "तिङन्ते भ्वादिप्रकरणम्", "तिङन्ते अदादिप्रकरणम्", "तिङन्ते जुहोत्यादिप्रकरणम्",
    "तिङन्ते दिवादिप्रकरणम्", "तिङन्ते स्वादिप्रकरणम्", "तिङन्ते तुदादिप्रकरणम्",
    "तिङन्ते रुधादिप्रकरणम्", "तिङन्ते तनादिप्रकरणम्", "तिङन्ते क्र्यादिप्रकरणम्",
    "तिङन्ते चुरादिप्रकरणम्", "तिङन्ते णिच्प्रकरणम्", "तिङन्ते सन्प्रकरणम्",
    "तिङन्ते यङ्प्रकरणम्", "तिङन्ते यङ्लुक्प्रकरणम्", "तिङन्ते नामधातुप्रकरणम्",
    "तिङन्ते कण्ड्वादिप्रकरणम्", "तिङन्ते प्रत्ययमालाप्रकरणम्",
    "तिङन्ते आत्मनेपदप्रकरणम्", "तिङन्ते परस्मैपदप्रकरणम्",
    "भावकर्मतिङ्प्रकरणम्", "कर्मकर्तृतिङ्प्रकरणम्", "लकारार्थप्रकरणम्",
    "कृदन्ते कृत्यप्रकरणम्", "पूर्वकृदन्तप्रकरणम्", "उणादयः",
    "उत्तरकृदन्तप्रकरणम्", "वैदिकीप्रक्रिया", "स्वरप्रक्रिया",
]

CONS = re.compile('[क-ह]')
GAP = -0.45
FLOOR = 0.34


def cons(text):
    return CONS.findall(unicodedata.normalize('NFC', text or ''))


def sim(a_text, b_text):
    a, b = cons(a_text), cons(b_text)
    if not a or not b:
        return 0.0
    inter = sum((Counter(a) & Counter(b)).values())
    return 2.0 * inter / (len(a) + len(b))


def align(ours, theirs):
    """Needleman-Wunsch over two lists of texts. Returns (i, j) pairs."""
    n, m = len(ours), len(theirs)
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] + GAP
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] + GAP
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = sim(ours[i - 1], theirs[j - 1])
            diag = score[i - 1][j - 1] + (s if s >= FLOOR else GAP * 2)
            score[i][j] = max(diag, score[i - 1][j] + GAP, score[i][j - 1] + GAP)
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            s = sim(ours[i - 1], theirs[j - 1])
            diag = score[i - 1][j - 1] + (s if s >= FLOOR else GAP * 2)
            if abs(score[i][j] - diag) < 1e-9:
                pairs.append((i - 1, j - 1)); i -= 1; j -= 1; continue
        if i > 0 and abs(score[i][j] - (score[i - 1][j] + GAP)) < 1e-9:
            pairs.append((i - 1, None)); i -= 1; continue
        pairs.append((None, j - 1)); j -= 1
    pairs.reverse()
    return pairs


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    src_root = Path(sys.argv[1])
    sut_path = src_root / "sutraani" / "data.txt"
    if not sut_path.exists():
        print(f"Not found: {sut_path}")
        sys.exit(1)

    ours = json.loads(SUTRAPATHA_PATH.read_text(encoding="utf-8"))["items"]
    theirs = json.loads(sut_path.read_text(encoding="utf-8"))["data"]

    ours_by_pada = defaultdict(list)
    for it in ours:
        a, p, _ = it["id"].split(".")
        ours_by_pada[a + "." + p].append(it)
    theirs_by_pada = defaultdict(list)
    for r in theirs:
        theirs_by_pada[r["a"] + "." + r["p"]].append(r)

    items = []
    matched = unmatched_ours = dropped_theirs = 0
    for pada in sorted(ours_by_pada, key=lambda k: [int(x) for x in k.split(".")]):
        o = ours_by_pada[pada]
        t = sorted(theirs_by_pada.get(pada, []), key=lambda r: int(r["n"]))
        pairs = align([x["sanskrit_text"] for x in o], [x["s"] for x in t])
        for i, j in pairs:
            if i is None:
                dropped_theirs += 1
                continue
            if j is None:
                unmatched_ours += 1
                continue
            row = t[j]
            skn = int(row.get("skn") or 0)
            if not skn:
                unmatched_ours += 1
                continue
            entry = {"id": o[i]["id"], "kaumudiIndex": skn}
            lskn = int(row.get("lskn") or 0)
            if lskn:
                entry["laghu"] = lskn
            ch = int(row.get("sk_chapter") or 0)
            if 1 <= ch <= len(CHAPTERS):
                entry["chapter"] = ch
            items.append(entry)
            matched += 1

    items.sort(key=lambda e: e["kaumudiIndex"])

    chapters = []
    by_ch = defaultdict(list)
    for e in items:
        if e.get("chapter"):
            by_ch[e["chapter"]].append(e["kaumudiIndex"])
    for n, name in enumerate(CHAPTERS, 1):
        ks = by_ch.get(n, [])
        chapters.append({"n": n, "name": name,
                         "from": min(ks) if ks else None,
                         "to": max(ks) if ks else None,
                         "count": len(ks)})

    out = {
        "_readme": [
            "Ashtadhyayi sutra id -> Siddhanta Kaumudi position (kaumudiIndex),",
            "Laghu-Siddhanta-Kaumudi position (laghu, where the sutra appears in the",
            "LSK), and SK prakarana number (chapter, 1-70, see `chapters`). Built by",
            "tools/build_kaumudi_order.py; that script's docstring records why this",
            "replaced the earlier partial text-matching build, and how the id join",
            "avoids the source's known numbering misalignment.",
            f"Source: {SOURCE_NOTE}",
        ],
        "v": 2,
        "chapters": chapters,
        "items": items,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")

    print(f"matched {matched} of {len(ours)} sutras "
          f"({unmatched_ours} of ours without a SK position, "
          f"{dropped_theirs} source rows unaligned)")
    laghu = sum(1 for e in items if "laghu" in e)
    print(f"laghu positions: {laghu}; chapters populated: "
          f"{sum(1 for c in chapters if c['count'])}/70")
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
