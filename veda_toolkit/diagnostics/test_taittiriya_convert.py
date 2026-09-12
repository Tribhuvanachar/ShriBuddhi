"""
DGE — Taittiriya ITRANS -> Devanagari conversion PROTOTYPE
===========================================================
Verifies accent conversion on a handful of real passages BEFORE running
anything across 30,541 lines. Vedic accent handling is exactly where the
Rigveda import went wrong twice, so this is checked against real output
rather than assumed.

THE THREE THINGS BEING TESTED
-----------------------------
1. Accent markers survive transliteration. ITRANS Vedic accents (\\` for
   anudatta, \\' for svarita, \\" for dirgha svarita) are almost certainly
   NOT understood by standard ITRANS converters. The approach here is to
   swap them for Unicode Private Use Area placeholders first, transliterate,
   then swap the placeholders for the real Devanagari accent marks
   (U+0952 anudatta, U+0951 svarita) — the same standard core-block marks
   that were confirmed to render correctly in the Rigveda import.
   If the PUA placeholders do NOT survive intact, this whole approach is
   wrong and the output will show it.

2. The duplicate-text trap is avoided. Each file contains the entire text
   twice: accented, then again unaccented after a "(niHsvaraH)" chapter
   marker. Only the first half must be used.

3. Structure parses. kanda from \\chapter, prashna from \\section,
   anuvakas as numbered paragraphs ending "|| k| p| a||".

Usage (Colab):
    !pip install requests indic_transliteration
"""

import re

import requests
from indic_transliteration import sanscript

URL = "https://sanskritdocuments.org/doc_veda/taittirIyasamhitA.itx"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DGE-importer/1.0)", "Accept": "*/*"}

# Private Use Area placeholders — chosen because they carry no meaning in
# any transliteration scheme, so a converter has no reason to alter them.
PUA = {
    "anudatta": "\ue000",
    "svarita": "\ue001",
    "dirgha_svarita": "\ue002",
    "nasal_m": "\ue003",
}

# What each placeholder becomes in the final Devanagari.
FINAL = {
    PUA["anudatta"]: "\u0952",        # ॒ DEVANAGARI STRESS SIGN ANUDATTA
    PUA["svarita"]: "\u0951",         # ॑ DEVANAGARI STRESS SIGN UDATTA (used for svarita here)
    # Dirgha svarita properly needs its own mark, but the dedicated Vedic
    # Extensions codepoint is the poorly-supported kind that broke rendering
    # before. Mapped to plain svarita for now — flagged, not silently done.
    PUA["dirgha_svarita"]: "\u0951",
    PUA["nasal_m"]: "\ua8f3",         # ꣳ DEVANAGARI SIGN CANDRABINDU VIRAMA
}


def preprocess(itrans):
    """Swap ITRANS Vedic markers for placeholders before transliteration."""
    t = itrans
    t = t.replace("{\\m+}", PUA["nasal_m"])
    t = t.replace('\\"', PUA["dirgha_svarita"])
    t = t.replace("\\`", PUA["anudatta"])
    t = t.replace("\\'", PUA["svarita"])
    t = t.replace("\\-", "")          # ITRANS soft word-break
    t = re.sub(r"o\((\d)\)m", r"ओ\1म्", t)  # o(3)m / o(4)m pluta forms
    return t


def postprocess(devanagari):
    out = devanagari
    for ph, real in FINAL.items():
        out = out.replace(ph, real)
    return out


def convert(itrans):
    pre = preprocess(itrans)
    deva = sanscript.transliterate(pre, sanscript.ITRANS, sanscript.DEVANAGARI)
    return postprocess(deva)


def strip_nihsvara(text):
    """Keep only the accented half (everything before the niHsvaraH repeat)."""
    m = re.search(r"\\chapter\{[^}]*niHsvaraH", text)
    return text[:m.start()] if m else text


def parse(text):
    """
    Yields (kanda_label, prashna_label, anuvaka_ref, itrans_body).
    Anuvakas are numbered paragraphs terminated by "|| k| p| a||".
    """
    text = strip_nihsvara(text)
    kanda = prashna = None
    buf = []
    results = []

    for line in text.splitlines():
        ch = re.match(r"\s*\\chapter\{(.*)\}", line)
        if ch:
            kanda = ch.group(1).strip().strip("|").strip()
            continue
        sec = re.match(r"\s*\\section\{(.*)\}", line)
        if sec:
            prashna = sec.group(1).strip()
            continue
        if line.strip().startswith("\\") or line.strip().startswith("%") or line.strip().startswith("#"):
            continue
        buf.append(line)
        # An anuvaka closes with a reference like "|| 1| 1| 1||"
        endm = re.search(r"\|\|\s*([\d\|\s]+?)\s*\|\|\s*$", line.strip())
        if endm and buf:
            body = "\n".join(buf).strip()
            ref = re.sub(r"\s+", "", endm.group(1)).strip("|")
            results.append((kanda, prashna, ref, body))
            buf = []
    return results


def main():
    print("Fetching Taittiriya Samhita ...")
    r = requests.get(URL, timeout=180, headers=HEADERS)
    r.raise_for_status()
    text = r.content.decode("utf-8", errors="replace")
    print(f"  {len(text):,} chars, {len(text.splitlines()):,} lines")

    full_lines = len(text.splitlines())
    accented = strip_nihsvara(text)
    print(f"\nDuplicate-text check:")
    print(f"  accented half: {len(accented.splitlines()):,} lines "
          f"({len(accented.splitlines()) / full_lines * 100:.0f}% of file)")
    print(f"  (should be roughly half — if it's 100%, the niHsvara marker")
    print(f"   wasn't found and duplicates WOULD have been imported)")

    print("\nPlaceholder survival test (the critical unknown):")
    probe = "a" + PUA["anudatta"] + "gnimI" + PUA["svarita"] + "Le"
    out = sanscript.transliterate(probe, sanscript.ITRANS, sanscript.DEVANAGARI)
    survived = all(p in out for p in (PUA["anudatta"], PUA["svarita"]))
    print(f"  placeholders survive transliteration: {survived}")
    if not survived:
        print("  *** If False, this approach cannot work as written — stop here. ***")

    units = parse(text)
    print(f"\nParsed {len(units):,} anuvaka-level units from the accented half.")

    kandas = {}
    for k, p, ref, body in units:
        kandas.setdefault(k, 0)
        kandas[k] += 1
    print(f"Kandas found ({len(kandas)}):")
    for k, n in kandas.items():
        print(f"  {k}  -> {n} units")

    print("\n" + "=" * 70)
    print("SAMPLE CONVERSIONS — check the Devanagari carefully")
    print("=" * 70)
    for idx in [0, 1, len(units) // 3, len(units) // 2, len(units) - 1]:
        if idx >= len(units):
            continue
        k, p, ref, body = units[idx]
        snippet = body[:260]
        print("\n" + "-" * 66)
        print(f"  kanda   : {k}")
        print(f"  prashna : {p}")
        print(f"  ref     : {ref}")
        print(f"  ITRANS  : {snippet[:200]}")
        print(f"  DEVA    : {convert(snippet)[:200]}")

    print("\n" + "=" * 70)
    print("Check specifically:")
    print("  - do accent marks appear as small strokes above/below letters")
    print("    (॑ ॒) rather than stray quotes, backticks or boxes?")
    print("  - does the first unit read 'इषे त्वोर्जे त्वा...' (TS 1.1.1)?")
    print("  - is the kanda/prashna/ref structure sensible?")
    print("=" * 70)


if __name__ == "__main__":
    main()
