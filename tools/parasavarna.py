#!/usr/bin/env python3
"""Parasavarṇa -> anusvāra, for showing Sanskrit in Kannada and other Indic scripts.

Sanskrit written in Devanagari often spells a nasal + a consonant of its own
class as a conjunct: इन्द्र, अङ्ग, कुण्ड, सम्पूर्ण. Kannada, Telugu and the other
scripts write the same sound with an anusvāra: ಇಂದ್ರ, ಅಂಗ, ಕುಂಡ, ಸಂಪೂರ್ಣ.
Converting the Devanagari letter by letter gives ಇನ್ದ್ರ, which is correct but
not how those scripts are written. This rewrites the parasavarṇa conjunct to an
anusvāra BEFORE the script conversion, so the conversion then yields ಇಂದ್ರ.

    class      nasal  followed by
    ka-varga    ङ     क ख ग घ
    ca-varga    ञ     च छ ज झ
    ṭa-varga    ण     ट ठ ड ढ
    ta-varga    न     त थ द ध
    pa-varga    म     प फ ब भ

Rules kept deliberately narrow:
  * only nasal + VIRAMA + a consonant of the SAME class (so न्न, न्य, म्ह, न्स
    are left alone -- they are real conjuncts, not parasavarṇa);
  * IAST/roman output is NOT touched: English readers expect "indra", not "iṃdra".
    Use it only when the target is an Indic script (see INDIC_TARGETS).

The same rule is mirrored in js/transliteration.js (dgeParasavarna) and
library.html (parasavarna); tests/test_parasavarna.py checks all three agree on
the fixed examples, so change them together.

Usage:
    python tools/parasavarna.py "इन्द्रः अङ्गम् सम्पूर्ण"
    python tools/parasavarna.py --file in.txt [--out out.txt]
    python tools/parasavarna.py --json data/x/data.json --show   # count how many strings change
"""
import argparse
import json
import re
import sys

VIRAMA = "्"
ANUSVARA = "ं"

CLASSES = {
    "ङ": "कखगघ",   # ङ : क ख ग घ
    "ञ": "चछजझ",   # ञ : च छ ज झ
    "ण": "टठडढ",   # ण : ट ठ ड ढ
    "न": "तथदध",   # न : त थ द ध
    "म": "पफबभ",   # म : प फ ब भ
}

# Display scripts where anusvāra is the written form. Roman (iast) is excluded.
INDIC_TARGETS = {"kannada", "telugu", "tamil", "malayalam", "bengali", "oriya",
                 "gujarati", "gurmukhi", "sinhala"}

_PATTERN = re.compile(
    "(" + "|".join(CLASSES) + ")" + VIRAMA + "([" + "".join(CLASSES.values()) + "])"
)


def to_anusvara(text):
    """Rewrite same-class nasal + virama + consonant to anusvāra + consonant."""
    def sub(m):
        nasal, cons = m.group(1), m.group(2)
        return ANUSVARA + cons if cons in CLASSES[nasal] else m.group(0)
    return _PATTERN.sub(sub, text)


def for_script(text, script):
    """Apply the rule only when `script` is an Indic display script."""
    return to_anusvara(text) if script in INDIC_TARGETS else text


def _walk(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_walk(x, fn) for x in obj]
    if isinstance(obj, dict):
        return {k: _walk(v, fn) for k, v in obj.items()}
    return obj


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("text", nargs="?", help="Devanagari text to convert")
    ap.add_argument("--file", help="read text from this UTF-8 file")
    ap.add_argument("--out", help="write the result here instead of stdout")
    ap.add_argument("--json", help="report how many strings in this JSON would change")
    ap.add_argument("--show", action="store_true", help="with --json, print the first 15 changes")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    if a.json:
        changed = []
        def probe(s):
            t = to_anusvara(s)
            if t != s:
                changed.append((s, t))
            return s
        _walk(json.load(open(a.json, encoding="utf-8")), probe)
        print(f"{len(changed)} strings would change")
        if a.show:
            for s, t in changed[:15]:
                print(f"  {s}  ->  {t}")
        return 0

    text = open(a.file, encoding="utf-8").read() if a.file else a.text
    if text is None:
        ap.error("give text, --file or --json")
    out = to_anusvara(text)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
