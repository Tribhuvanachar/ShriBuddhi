"""
DGE — Inspect the Taittiriya (Krishna Yajurveda) source files
==============================================================
Before writing any parser: check what these files actually contain.
Two things specifically need verifying, not assuming:

  1. STRUCTURE — how kanda/prapathaka/anuvaka divisions are marked, and
     whether individual mantras are separable. Krishna Yajurveda is
     structurally messier than Rigveda: it interleaves mantra with
     Brahmana prose rather than keeping them cleanly separate, so
     "one item per mantra" may not map as neatly as it did before.

  2. ACCENTS — these are ITRANS-encoded (.itx), not Devanagari. ITRANS
     represents Vedic accents with its own markers (\\_ for anudatta,
     \\' or " for svarita etc). We need to see the real markers used
     here before trusting any transliteration step, because getting
     accents wrong is exactly the bug that took several rounds to catch
     on the Rigveda import.

Files (sanskritdocuments.org, used with permission):
  taittirIyasamhitA  — Taittiriya Samhita, "with Vedic accents"
  taittirIyabrAhmaNam — Taittiriya Brahmana, "with Vedic accents"
  taittirIyaAraNyaka  — Taittiriya Aranyaka, "with Vedic accents"

Usage (Colab):
    !pip install requests
"""

import re
import unicodedata
from collections import Counter

import requests

FILES = {
    "TaittiriyaSamhita": "https://sanskritdocuments.org/doc_veda/taittirIyasamhitA.itx",
    "TaittiriyaBrahmana": "https://sanskritdocuments.org/doc_veda/taittirIyabrAhmaNam.itx",
    "TaittiriyaAranyaka": "https://sanskritdocuments.org/doc_veda/taittirIyaAraNyaka.itx",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


def fetch(name, url):
    print(f"Fetching {name} ...")
    r = requests.get(url, timeout=180, headers=HEADERS)
    r.raise_for_status()
    # These files are usually ITRANS/ASCII, but declare encoding defensively.
    text = r.content.decode("utf-8", errors="replace")
    print(f"  {len(r.content):,} bytes, {len(text.splitlines()):,} lines")
    return text


def inspect(name, text):
    lines = text.splitlines()
    print("\n" + "=" * 70)
    print(f"FILE: {name}")
    print("=" * 70)

    print("\n--- FIRST 40 LINES (header + start of text) ---")
    for ln in lines[:40]:
        print(f"  {ln[:150]}")

    # Find where the actual body starts — sanskritdocuments .itx files
    # carry a metadata header, often ending at a \myfooter or similar.
    body_start = 0
    for i, ln in enumerate(lines[:200]):
        if re.match(r"^\s*\\", ln) is None and len(ln.strip()) > 20 and i > 5:
            body_start = i
            break

    print(f"\n--- 30 LINES FROM APPROX BODY START (line {body_start}) ---")
    for ln in lines[body_start:body_start + 30]:
        print(f"  {ln[:150]}")

    print("\n--- 20 LINES FROM THE MIDDLE ---")
    mid = len(lines) // 2
    for ln in lines[mid:mid + 20]:
        print(f"  {ln[:150]}")

    # Structural markers: how are divisions numbered?
    print("\n--- CANDIDATE STRUCTURE MARKERS ---")
    patterns = {
        "|| n.n.n ||  (three-part refs)": r"\|\|\s*[\d\.]+\s*\|\|",
        "|| n ||      (single numbers)": r"\|\|\s*\d+\s*\|\|",
        "(n.n.n)      (parenthesised)": r"\(\s*[\d\.]+\s*\)",
        "## markers": r"##",
        "backslash commands": r"^\s*\\[a-zA-Z]+",
    }
    for label, pat in patterns.items():
        hits = re.findall(pat, text, flags=re.MULTILINE)
        print(f"  {label}: {len(hits):,} matches")
        if hits:
            print(f"      samples: {hits[:6]}")

    # Accent markers actually present — this is the critical unknown.
    print("\n--- ACCENT / SPECIAL CHARACTER FREQUENCY ---")
    interesting = [c for c in text if not c.isalnum() and not c.isspace()]
    freq = Counter(interesting)
    for ch, n in freq.most_common(25):
        try:
            uname = unicodedata.name(ch)
        except ValueError:
            uname = "?"
        print(f"  {ch!r}  U+{ord(ch):04X}  {n:>8,}  {uname}")

    # Is any of it already Devanagari rather than ITRANS?
    deva = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    print(f"\n  Devanagari characters present: {deva:,}")
    print(f"  (0 means pure ITRANS — needs transliteration;")
    print(f"   a large number means it's already Devanagari)")


def main():
    for name, url in FILES.items():
        try:
            text = fetch(name, url)
            inspect(name, text)
        except Exception as e:
            print(f"\n{name}: FAILED — {e}")
            print("  If this is a 406, download the .itx in a browser and")
            print("  upload it to Colab, then adapt this script to read locally.")

    print("\n" + "=" * 70)
    print("Paste this back. What matters:")
    print("  - how kanda/prapathaka/anuvaka/mantra divisions are marked")
    print("  - which accent markers appear, and how often")
    print("  - whether the text is ITRANS or already Devanagari")
    print("=" * 70)


if __name__ == "__main__":
    main()
