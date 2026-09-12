"""
DGE VedaWeb Diagnostic — checking the "aufrecht" witness + the gacchati bug
=============================================================================
Run in the same Colab session as before (reuses the already-downloaded
zip if it's still there — if not, it'll re-download automatically).

What this checks:
1. Whether the "aufrecht" witness has proper sandhi (euphonic combination)
   for mantra 1.1.01 and 1.1.04 — comparing against what "zurich" gave us,
   which we've confirmed does NOT apply sandhi (word-tokenized, built for
   morphological analysis, not continuous reading).
2. The exact raw IAST for mantra 1.1.04 across every witness available,
   to find where "gacchati" turned into "gachati" — whether that's a
   VedaWeb source quirk or something introduced downstream.
3. Lists which OTHER witnesses exist at all in this TEI, in case there's
   an even better option than "aufrecht" we haven't considered.
"""

import re
from pathlib import Path
from lxml import etree

import requests, zipfile

ZENODO_ZIP_URL = "https://zenodo.org/records/4601264/files/cceh/c-salt_vedaweb_tei-v.1.0.0.zip?download=1"
WORK_DIR = Path("./vedaweb_work")


def ensure_downloaded():
    WORK_DIR.mkdir(exist_ok=True)
    zip_path = WORK_DIR / "vedaweb_tei.zip"
    if not zip_path.exists():
        print("Zip not found locally, downloading fresh...")
        r = requests.get(ZENODO_ZIP_URL, timeout=180)
        r.raise_for_status()
        zip_path.write_bytes(r.content)
        print(f"Downloaded {len(r.content):,} bytes.")
    else:
        print("Using already-downloaded zip.")

    extract_dir = WORK_DIR / "extracted"
    if not extract_dir.exists():
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)

    candidates = list(extract_dir.glob("*vedaweb_tei*"))
    if not candidates:
        raise FileNotFoundError(f"Expected an extracted folder under {extract_dir}")
    return candidates[0]


def local_tag(elem):
    return etree.QName(elem).localname


def get_text_content(elem):
    text = "".join(elem.itertext())
    return re.sub(r"\s+", " ", text).strip()


def find_stanza(root, hymn_num, stanza_num):
    hymns = [e for e in root.iter() if local_tag(e) == "div" and e.get("type") == "hymn"]
    hymn = hymns[hymn_num - 1]
    stanzas = [e for e in hymn if local_tag(e) == "div" and e.get("type") == "stanza"]
    return stanzas[stanza_num - 1]


def list_witnesses(stanza):
    """Every <lg> witness layer actually present on this stanza, with its 'source' attribute."""
    result = []
    for lg in stanza:
        if local_tag(lg) == "lg":
            result.append((lg.get("source"), lg.get("{http://www.w3.org/XML/1998/namespace}lang")))
    return result


def extract_witness_text(stanza, source):
    for lg in stanza:
        if local_tag(lg) != "lg" or lg.get("source") != source:
            continue
        lines = []
        for l in lg:
            if local_tag(l) != "l":
                continue
            elid = l.get("{http://www.w3.org/XML/1998/namespace}id") or ""
            if elid.endswith("_tokens"):
                continue
            text = get_text_content(l)
            if text:
                lines.append(text)
        return " / ".join(lines)
    return None


def main():
    extract_dir = ensure_downloaded()
    book1_path = extract_dir / "rv_book_01.tei"
    print(f"Parsing {book1_path.name}...")
    parser = etree.XMLParser(recover=True, huge_tree=True)
    tree = etree.parse(str(book1_path), parser)
    root = tree.getroot()

    print("\n" + "=" * 70)
    print("MANTRA 1.1.01 — every witness available, and its raw text")
    print("=" * 70)
    stanza1 = find_stanza(root, 1, 1)
    witnesses1 = list_witnesses(stanza1)
    print("Witnesses present:", witnesses1)
    for source, lang in witnesses1:
        if source is None:
            continue
        text = extract_witness_text(stanza1, source)
        print(f"\n[{source}] ({lang}):")
        print(f"  {text}")

    print("\n" + "=" * 70)
    print("MANTRA 1.1.04 — every witness available, and its raw text")
    print("=" * 70)
    stanza4 = find_stanza(root, 1, 4)
    witnesses4 = list_witnesses(stanza4)
    print("Witnesses present:", witnesses4)
    for source, lang in witnesses4:
        if source is None:
            continue
        text = extract_witness_text(stanza4, source)
        print(f"\n[{source}] ({lang}):")
        print(f"  {text}")
        if "gach" in (text or "").lower() or "gacch" in (text or "").lower():
            print(f"  *** Contains 'gach'/'gacch' — this is the word we're chasing ***")

    print("\n" + "=" * 70)
    print("DONE — paste this whole output back.")
    print("=" * 70)


if __name__ == "__main__":
    main()
