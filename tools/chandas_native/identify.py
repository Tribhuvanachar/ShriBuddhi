"""
Clean-room metre identifier: scans a verse (scan.py) and matches it against
the independently-compiled database (build_db.py / data.json).
No code or data from hrishikeshrt/chanda -- standard difflib is used for
fuzzy fallback instead of python-Levenshtein.
"""
import json
import difflib
import sys

from scan import scan, matches


def load_db(path="data.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_anushtubh(pattern, rule):
    """pattern: full L/G/X string for a 4x8 = 32 syllable verse."""
    if len(pattern) != 32:
        return False
    padas = [pattern[i * 8:(i + 1) * 8] for i in range(4)]
    for i, pada in enumerate(padas):
        pos5 = pada[4]
        if pos5 not in ("L", "X"):
            return False
        pos6, pos7 = pada[5], pada[6]
        if pos6 == "L" and pos7 == "L":
            return False
        if i % 2 == 1:  # even pada (2nd, 4th), 0-indexed odd
            if not matches(pada[4:8], "LGLG"):
                return False
    return True


def identify(text, db):
    pattern, syllables = scan(text)
    n = len(pattern)

    if n == 32 and check_anushtubh(pattern, db["anushtubh"]):
        return {"name": db["anushtubh"]["vrutta_names"][0], "match": "rule", "akshara": n}

    # A sama-vrutta has all padas identical: the input may be one pada, a
    # half-verse (2 padas), or a full verse (4 padas) of that length --
    # check that every pada-slice matches the per-pada template.
    def pada_slices(total_len):
        for e in db["sama_vrutta"]:
            L = e["akshara_sankhya"]
            if L and total_len % L == 0 and total_len // L in (1, 2, 4):
                yield e, [pattern[i * L:(i + 1) * L] for i in range(total_len // L)]

    exact_hits = []
    for e, slices in pada_slices(n):
        template = "".join("G" if c == "ग" else "L" for c in e["lakshana"])
        if all(matches(s, template) for s in slices):
            exact_hits.append(e["vrutta_names"][0])
    if exact_hits:
        return {"name": exact_hits, "match": "exact", "akshara": n}

    # fuzzy fallback: closest sama-vrutta whose per-pada length divides n
    best = None
    best_ratio = 0.0
    for e, slices in pada_slices(n):
        template = "".join("G" if c == "ग" else "L" for c in e["lakshana"])
        ratios = [
            difflib.SequenceMatcher(None, s.replace("X", "G"), template).ratio()
            for s in slices
        ]
        ratio = min(ratios)
        if ratio > best_ratio:
            best_ratio = ratio
            best = e["vrutta_names"][0]
    if best_ratio > 0.85:
        return {"name": best, "match": "fuzzy", "ratio": round(best_ratio, 3), "akshara": n}

    return {"name": None, "match": "none", "akshara": n, "pattern": pattern}


if __name__ == "__main__":
    db = load_db()
    text = sys.argv[1] if len(sys.argv) > 1 else "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय"
    print(text)
    print(identify(text, db))
