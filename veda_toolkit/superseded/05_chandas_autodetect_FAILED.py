"""
DGE Chandas (metre) accuracy test
===================================
Before generating chandas for all 10,552 mantras, this checks whether the
"chanda" Python library (syllable-pattern based metre identification)
actually gets Vedic metre right — Vedic metre is more flexible than the
classical Sanskrit metre these tools are usually built for, so this isn't
assumed to work, it's tested.

Ground truth verses below are from Wikipedia's "Vedic metre" article,
which cites specific known-metre example verses for each major metre —
not guessed. Test data is pulled directly from your OWN already-uploaded
live site, so this is testing the real end-to-end scenario.

Usage (Colab):
    !pip install requests chanda
    then run this script
"""

import requests

# {mandala}.{hymn}.{stanza} -> expected metre, per Wikipedia's Vedic metre
# article's cited examples (each metre's own example-verse list).
KNOWN_METRE_VERSES = {
    "1.1.01": "gāyatrī",     # Rigveda 1.1.1 -- also independently confirmed via Wisdom Lib earlier
    "4.50.04": "triṣṭubh",   # Rigveda 4.50.4
    "1.51.13": "jagatī",     # Rigveda 1.51.13
    "10.136.07": "anuṣṭubh", # Rigveda 10.136.7
}

MANDALA_FOR = {
    "1.1.01": 1,
    "4.50.04": 4,
    "1.51.13": 1,
    "10.136.07": 10,
}

BASE_URL = "https://tribhuvanachar.github.io/bhumandala/data/vedas/rigveda/shakala_shakha/samhita/mandala_{:02d}/data.json"


def fetch_mandala(num):
    url = BASE_URL.format(num)
    print(f"Fetching {url} ...")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def find_item(data, ref_id):
    for item in data["items"]:
        if item.get("id") == ref_id:
            return item
    return None


def main():
    try:
        from chanda import analyze_line
        HAVE_CHANDA = True
    except ImportError:
        print("chanda library not installed -- run: pip install chanda")
        HAVE_CHANDA = False

    mandala_cache = {}
    results = []

    for ref_id, expected in KNOWN_METRE_VERSES.items():
        mandala_num = MANDALA_FOR[ref_id]
        if mandala_num not in mandala_cache:
            mandala_cache[mandala_num] = fetch_mandala(mandala_num)
        data = mandala_cache[mandala_num]
        item = find_item(data, ref_id)

        print("\n" + "=" * 60)
        print(f"Verse {ref_id} — expected metre: {expected}")
        print("=" * 60)
        if not item:
            print(f"  COULD NOT FIND this verse id in mandala_{mandala_num:02d} -- check the id format.")
            results.append((ref_id, expected, None, False))
            continue

        text = item.get("samhita_patha", "")
        print(f"  Text: {text}")

        if not HAVE_CHANDA:
            results.append((ref_id, expected, "(chanda not installed)", None))
            continue

        try:
            # Vedic text has pada separators as " / " -- analyze pada by
            # pada, since these tools generally expect single lines.
            padas = [p.strip() for p in text.split("/") if p.strip()]
            detected_per_pada = []
            for pada in padas:
                result = analyze_line(pada)
                meters = [name for name, _ in result.chanda] if result.chanda else []
                detected_per_pada.append(meters)
            print(f"  Detected per pada: {detected_per_pada}")
            results.append((ref_id, expected, detected_per_pada, None))
        except Exception as e:
            print(f"  ERROR running chanda: {e}")
            results.append((ref_id, expected, f"ERROR: {e}", False))

    print("\n" + "=" * 60)
    print("SUMMARY — compare 'expected' against what was actually detected")
    print("=" * 60)
    for ref_id, expected, detected, _ in results:
        print(f"  {ref_id}: expected={expected!r}  detected={detected!r}")

    print("\nPaste this whole output back — we'll decide from here whether")
    print("this library is reliable enough to trust for all 10,552 mantras,")
    print("needs a different approach, or needs per-metre spot-checking.")


if __name__ == "__main__":
    main()
