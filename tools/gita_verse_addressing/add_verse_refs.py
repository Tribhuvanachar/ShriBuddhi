#!/usr/bin/env python3
"""Give DvaitaVedantaIn's Gītā spine verse addresses, additively.

WHY. `gita_prasthana/gita_bhashya/mula` IS the Gītā text — 655 units whose
only identity is the importer's own `SM26:N` counter. Every sibling ṭīkā in
that folder joins it by that id and keeps working untouched. What the id
CANNOT do is join anything that came from outside the DvaitaVedanta.in crawl:
the Gītā Supersite bhāṣyas and the five Dvaita vyākhyānas of the Gītā
Vyākhyāna Saṅgraha are all addressed the way the tradition addresses the
Gītā — adhyāya.śloka — and shared nothing with `SM26:*`, so they could not be
stitched onto this spine at all (measured: 0 of 700 joined).

This tool adds a SECOND address per unit and touches nothing else. The unit
keeps its `SM26:N` id, so the eleven existing layers are unaffected; it gains
`verse_refs`, a list because the site groups verses into one unit wherever
Madhva's bhāṣya treats them together ("श्लोक ४०, ४१" -> ["2.40", "2.41"]),
and a layer keyed to EITHER verse must land on it.

WHERE THE NUMBERS COME FROM. Not from parsing the verse text — from the
importer's own `section` field, which carries the site's printed heading
("श्लोक ४२"), with the adhyāya read off the `breadcrumb` ordinal
("द्वितीयोऽध्यायः"). Verified against the canonical per-adhyāya verse counts:
adhyāyas 2–18 come out COMPLETE, every one of their 653 verses addressed.

WHAT IS DELIBERATELY NOT ADDRESSED (20 units):
  * the 18 adhyāya colophons (`section` is the adhyāya name, no verse)
  * `SM26:1` + `SM26:2` — adhyāya 1 and the upodghāta. DvaitaVedanta.in
    carries Madhva's first-adhyāya bhāṣya as ONE summary unit
    ("प्रथमाध्याये गीताक्षरार्थ:"), not verse by verse, so adhyāya 1 has no
    verse-level spine unit to hang 1.1–1.47 on. That is the edition's
    structure, not a hole in this tool: a Supersite layer's adhyāya-1
    commentary therefore has nowhere to join, and is reported, not forced.

Writes by textual insertion after each item's `"id":"…",` token — the file is
one item per line and must stay byte-identical elsewhere (see CLAUDE.md: never
json.load then json.dump a data/*.json).

Usage: python3 tools/gita_verse_addressing/add_verse_refs.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SPINE = Path("data/darshana/vedanta/dvaita/DvaitaVedantaIn/gita_prasthana"
             "/gita_bhashya/mula/data.json")

# Canonical verse count per adhyāya (Bhīṣma-parva recension, the one every
# edition in this corpus follows). Used as a RANGE CHECK: a number outside it
# is a mis-read heading, not a verse, and is dropped rather than published.
VERSES = {1: 47, 2: 72, 3: 43, 4: 42, 5: 29, 6: 47, 7: 30, 8: 28, 9: 34,
          10: 42, 11: 55, 12: 20, 13: 35, 14: 27, 15: 20, 16: 24, 17: 28,
          18: 78}

ORDINALS = {
    "प्रथम": 1, "द्वितीय": 2, "तृतीय": 3, "चतुर्थ": 4, "पञ्चम": 5, "षष्ठ": 6,
    "सप्तम": 7, "अष्टम": 8, "नवम": 9, "दशम": 10, "एकादश": 11, "द्वादश": 12,
    "त्रयोदश": 13, "चतुर्दश": 14, "पञ्चदश": 15, "षोडश": 16, "सप्तदश": 17,
    "अष्टादश": 18,
}

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
# Anchored: the heading must OPEN with श्लोक. A "श्लोक" appearing later in a
# heading is prose about a verse, not the heading's own number.
SECTION = re.compile(r"^\s*श्लोक\s*([०-९\d,\-–—\s]+)")
NUMBER = re.compile(r"[०-९\d]+")
ID_TOKEN = re.compile(r'^\{"id":"[^"]+",')


def adhyaya_of(breadcrumb) -> int | None:
    """Read the adhyāya number off the breadcrumb's ordinal segment.

    Matches on the ordinal STEM, never the whole word: sandhi welds the
    ordinal to अध्यायः differently in each one — द्वितीयोऽध्यायः,
    प्रथमाध्याये, षष्ठोऽध्यायः — so `seg == ordinal + "ोऽध्यायः"` would miss
    most of them.
    """
    for seg in breadcrumb or []:
        if "ध्याय" not in seg:
            continue
        for word, n in ORDINALS.items():
            if seg.startswith(word):
                return n
    return None


def verse_refs(item) -> list[str]:
    """["2.40", "2.41"] for a unit whose heading reads "श्लोक ४०, ४१"; [] if
    the unit is not verse-addressable (colophon, upodghāta, adhyāya 1)."""
    adhyaya = adhyaya_of(item.get("breadcrumb"))
    if not adhyaya:
        return []
    m = SECTION.match(item.get("section") or "")
    if not m:
        return []
    out = []
    for raw in NUMBER.findall(m.group(1)):
        v = int(raw.translate(DEVANAGARI_DIGITS))
        if 1 <= v <= VERSES[adhyaya]:
            ref = f"{adhyaya}.{v}"
            if ref not in out:
                out.append(ref)
    return out


def rewrite(text: str) -> tuple[str, int, int]:
    """Insert "verse_refs":[…] after each item line's id token."""
    lines = text.split("\n")
    addressed = 0
    refs_written = 0
    for i, line in enumerate(lines):
        m = ID_TOKEN.match(line)
        if not m:
            continue
        if '"verse_refs"' in line:
            raise SystemExit(f"line {i+1} already carries verse_refs — refusing "
                             "to write a second copy")
        body = line.rstrip(",")
        trailing = line[len(body):]
        refs = verse_refs(json.loads(body))
        if not refs:
            continue
        addressed += 1
        refs_written += len(refs)
        # Brace-stripped one-key dict, compact separators so the inserted key
        # matches the file's own style: every other key in these lines is
        # written with no space after the colon or the comma.
        injected = json.dumps({"verse_refs": refs}, ensure_ascii=False,
                              separators=(",", ":"))[1:-1]
        lines[i] = m.group(0) + injected + "," + body[m.end():] + trailing
    return "\n".join(lines), addressed, refs_written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what would change; write nothing")
    args = ap.parse_args()

    if not SPINE.is_file():
        print(f"missing {SPINE}", file=sys.stderr)
        return 1
    original = SPINE.read_text(encoding="utf-8")
    updated, addressed, refs = rewrite(original)

    total = original.count('\n{"id":"') + (1 if original.startswith('{"id":"') else 0)
    print(f"{SPINE}")
    print(f"  {addressed} of {total} units addressed, {refs} verse refs")
    if original.count("\n") != updated.count("\n"):
        print("  REFUSED: line count changed", file=sys.stderr)
        return 1
    if args.check:
        print("  --check: " + ("would rewrite" if updated != original else "no change"))
        return 0
    SPINE.write_text(updated, encoding="utf-8")
    print("  written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
