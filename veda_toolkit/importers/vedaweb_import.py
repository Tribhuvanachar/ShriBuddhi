"""
DGE VedaWeb Rigveda Importer — v0.4 (switched primary text source to the
"eichler" witness after confirming against real diagnostic output that it
has proper sandhi, correct spelling, and standard Unicode accent marks —
"zurich" (the original choice) is word-tokenized for morphological
analysis and never applies sandhi at all, and several witnesses including
zurich share a genuine spelling inconsistency ("gachati" instead of
"gacchati") that's present in VedaWeb's own source data.)
================================================================================
Run this in Google Colab (or any local Python 3 with internet access).

v0.2 CHANGES FROM v0.1 — everything below was corrected against real
diagnostic output from an actual run, not guessed:
  - vedaweb_corpus.tei is just a metadata shell (empty <body>) that
    XIncludes 10 separate per-book files (rv_book_01.tei .. rv_book_10.tei,
    10-43MB each) — this version reads those 10 files directly instead.
  - rishi/devata are NOT per-stanza attributes/notes as first guessed —
    they live once per HYMN, inside a <div type="dedication"> block
    (addressee = devata, group = rishi), and apply to every stanza in
    that hymn.
  - The actual mantra text lives inside <lg source="zurich"> as a set of
    <l> lines (one per pada/quarter-verse) — each followed by a SIBLING
    <l id="..._tokens"> line holding word-by-word morphology, which must
    be skipped, not extracted as text.
  - The "zurich" witness text is in ROMANIZED ISO-15919 transliteration
    (e.g. "agním īḷe puróhitaṁ"), not Devanagari. Since DGE is
    Devanagari-first elsewhere (see DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha/data.json), this version
    converts to Devanagari via the `indic_transliteration` library and
    keeps the original IAST alongside it for cross-checking.
  - Large files are processed ONE BOOK AT A TIME so memory use stays
    reasonable regardless of total corpus size.

Usage:
    pip install requests lxml indic_transliteration
    python vedaweb_import.py
"""

import json
import re
import sys
import zipfile
import shutil
from pathlib import Path

try:
    import requests
except ImportError:
    print("Run: pip install requests lxml indic_transliteration")
    sys.exit(1)

try:
    from lxml import etree
except ImportError:
    print("Run: pip install requests lxml indic_transliteration")
    sys.exit(1)

try:
    from indic_transliteration import sanscript
    HAVE_TRANSLIT = True
except ImportError:
    print("indic_transliteration not installed — run: pip install indic_transliteration")
    print("Continuing WITHOUT Devanagari conversion (samhita_patha will stay in IAST).")
    HAVE_TRANSLIT = False

ZENODO_ZIP_URL = "https://zenodo.org/records/4601264/files/cceh/c-salt_vedaweb_tei-v.1.0.0.zip?download=1"
WORK_DIR = Path("./vedaweb_work")
OUTPUT_DIR = Path("./dge_vedaweb_output")
OUTPUT_ZIP = Path("./dge_vedaweb_import.zip")

XML_NS = "{http://www.w3.org/XML/1998/namespace}"


def download_and_extract():
    WORK_DIR.mkdir(exist_ok=True)
    zip_path = WORK_DIR / "vedaweb_tei.zip"
    if not zip_path.exists():
        print(f"Downloading {ZENODO_ZIP_URL} ...")
        r = requests.get(ZENODO_ZIP_URL, timeout=180)
        r.raise_for_status()
        zip_path.write_bytes(r.content)
        print(f"Downloaded {len(r.content):,} bytes.")
    else:
        print("Zip already downloaded, skipping.")

    extract_dir = WORK_DIR / "extracted"
    if not extract_dir.exists():
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)

    # The zip's top folder name includes a commit hash suffix that can
    # change between downloads — find it by pattern instead of hardcoding.
    candidates = list(extract_dir.glob("*vedaweb_tei*"))
    if not candidates:
        raise FileNotFoundError(f"Expected an extracted folder under {extract_dir} — list it manually to check.")
    return candidates[0]


def local_tag(elem):
    return etree.QName(elem).localname


def get_text_content(elem):
    text = "".join(elem.itertext())
    return re.sub(r"\s+", " ", text).strip()


PRECOMPOSED_ACCENTED_RL = {
    "\u0155": "r\u0301",  # ŕ -> r + combining acute (un-precompose before the regex below)
    "\u013a": "l\u0301",  # ĺ -> l + combining acute (not observed yet, handled defensively)
}


def normalize_iast_variants(text):
    """
    v0.3 correction — the v0.2 fix (reordering ring-below to sit directly
    after r/l, keeping any accent as a separate trailing mark) was tested
    on real output and did NOT work: "vŕ̥ṣaṇaṁ" / "dūredŕ̥śaṁ" still leaked
    raw Latin letters into the Devanagari output after that fix. So it
    wasn't about the ORDER of the two marks — the library apparently can't
    recognize vocalic r/l at all once a SECOND diacritic touches the same
    letter, regardless of arrangement.

    What's confirmed to work throughout this corpus: precomposed vowel +
    ONE trailing accent mark (e.g. "ī" + acute = "ī́", converts correctly
    everywhere). So instead of trying to make the library accept three
    stacked marks on a plain letter, this converts r/l + ring-below
    straight into the STANDARD precomposed IAST retroflex/vocalic
    character (ṛ / ḷ — same family as ā/ī/ū) BEFORE transliteration, with
    any accent left as a single trailing mark on that precomposed letter —
    matching the exact shape already proven to work, rather than a new
    untested shape.
    """
    for precomposed, decomposed in PRECOMPOSED_ACCENTED_RL.items():
        text = text.replace(precomposed, decomposed)

    def repl(match):
        base, accent_before, accent_after = match.group(1), match.group(2), match.group(3)
        accent = accent_before or accent_after or ""
        retroflex = "\u1e5b" if base == "r" else "\u1e37"  # ṛ or ḷ
        return retroflex + accent

    text = re.sub(r"([rl])(\u0301)?\u0325(\u0301)?", repl, text)
    return text


def fix_retroflex_l(devanagari_text):
    """
    Backstop only now (the real fix moved upstream into
    normalize_iast_variants) — kept in case any 'ḷ' reaches transliteration
    without going through normalization first, e.g. text that already used
    the precomposed dot-below form natively rather than ring-below.
    """
    """
    Targeted fix for a confirmed bug: the transliteration library reads
    IAST 'ḷ' as the vocalic-ḷ VOWEL LETTER (ऌ) instead of the Vedic
    retroflex lateral CONSONANT (ळ) it almost always actually is in real
    Rigvedic words (true vocalic ḷ is vanishingly rare in the corpus).
    Confirmed against real output: "īḷe" -> wrongly "ईऌए", should be "ईळे".
    This rewrites ऌ + [an independent vowel letter] into ळ + the matching
    dependent vowel sign (or plain ळ for the inherent 'a'), which is what
    the syllable actually needed.
    """
    independent_to_matra = {
        "अ": "", "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
        "ऋ": "ृ", "ॠ": "ॄ", "ए": "े", "ऐ": "ै", "ओ": "ो", "औ": "ौ",
    }
    for vowel, matra in independent_to_matra.items():
        devanagari_text = devanagari_text.replace("ऌ" + vowel, "ळ" + matra)
    return devanagari_text


def dgeSanitizeVedicAccents(text):
    """
    Same fix as the app's own client-side sanitizer: remaps the little-
    supported Vedic Extensions codepoints (U+1CD3, U+1CD9) to the
    standard, universally-supported core-Devanagari-block equivalents
    (U+0951, U+0952). Confirmed via real rendered output that fonts
    almost never have glyphs for the former. No-op if neither appears.
    """
    if not text:
        return text
    return text.replace("\u1CD3", "\u0951").replace("\u1CD9", "\u0952")


def to_devanagari(iast_text):
    if not HAVE_TRANSLIT or not iast_text:
        return ""
    try:
        result = sanscript.transliterate(normalize_iast_variants(iast_text), sanscript.IAST, sanscript.DEVANAGARI)
        return fix_retroflex_l(result)
    except Exception as e:
        print(f"  (transliteration failed for '{iast_text[:40]}...': {e})")
        return ""


def extract_hymn_metadata(hymn_div):
    """rishi/devata live once per hymn, inside <div type="dedication">."""
    rishi, devata = "", ""
    for child in hymn_div:
        if local_tag(child) != "div" or child.get("type") != "dedication":
            continue
        for sub in child:
            if local_tag(sub) != "div":
                continue
            eng_p = None
            for p in sub:
                if local_tag(p) == "p" and p.get(XML_NS + "lang") == "eng":
                    eng_p = p
                    break
            text = get_text_content(eng_p) if eng_p is not None else ""
            if sub.get("type") == "addressee":
                devata = text
            elif sub.get("type") == "group":
                rishi = text
    return rishi, devata


def extract_witness_text(stanza_div, source):
    """
    Joins the actual pada lines for a given witness (source="zurich" etc),
    skipping the sibling "_tokens" lines that hold word-by-word morphology
    rather than text.
    """
    for lg in stanza_div:
        if local_tag(lg) != "lg" or lg.get("source") != source:
            continue
        lines = []
        for l in lg:
            if local_tag(l) != "l":
                continue
            elid = l.get(XML_NS + "id") or ""
            if elid.endswith("_tokens"):
                continue
            text = get_text_content(l)
            if text:
                lines.append(text)
        return " / ".join(lines)
    return ""


def parse_book_file(book_path, book_num):
    print(f"Parsing {book_path.name} ({book_path.stat().st_size:,} bytes)...")
    parser = etree.XMLParser(recover=True, huge_tree=True)
    tree = etree.parse(str(book_path), parser)
    root = tree.getroot()

    hymns = [e for e in root.iter() if local_tag(e) == "div" and e.get("type") == "hymn"]
    print(f"  {len(hymns)} hymn(s) found.")

    items = []
    diagnostic_printed = False

    for hymn in hymns:
        rishi, devata = extract_hymn_metadata(hymn)
        stanzas = [e for e in hymn if local_tag(e) == "div" and e.get("type") == "stanza"]
        for stanza in stanzas:
            stanza_id = stanza.get(XML_NS + "id") or ""
            # id looks like "b01_h001_01" -- pull the stanza number off the end.
            m = re.search(r"_(\d+)$", stanza_id)
            stanza_num = m.group(1) if m else str(len(items) + 1)

            # "eichler" is a native-Devanagari witness with proper sandhi
            # and correct spelling ("गच्छति", not "गछति" like several other
            # witnesses share) — confirmed against real diagnostic output,
            # not assumed. Used as primary text now instead of "zurich"
            # (which is word-tokenized for morphological analysis, so it
            # never applies sandhi at all). Falls back to the old
            # zurich-transliteration pipeline only if eichler is missing
            # for a specific stanza, so nothing goes silently empty.
            eichler_text = extract_witness_text(stanza, "eichler")
            iast_text = extract_witness_text(stanza, "zurich")
            pada_iast = extract_witness_text(stanza, "padapatha")

            if eichler_text:
                # Already Devanagari -- no transliteration needed. Still run
                # the accent sanitizer defensively in case it uses the same
                # obscure Vedic Extensions codepoints somewhere we haven't
                # seen yet; this is a no-op if the marks are already fine.
                devanagari = dgeSanitizeVedicAccents(eichler_text)
            else:
                devanagari = to_devanagari(iast_text)

            # All translation witnesses confirmed present in this dataset.
            # The three English and two German ones are late-19th/early-20th
            # century and long out of copyright; Elizarenkova's Russian is
            # more recent but is included in the same CC-licensed VedaWeb
            # distribution we're already sourcing everything else from.
            # Stored keyed by source name so the app's existing
            # multi-commentary display (built for PNS's 5 commentaries)
            # picks them all up with no new UI code — see
            # dgeNormalizeGranthaData in core.js.
            TRANSLATION_WITNESSES = [
                "griffith",      # English, 1889
                "macdonell",     # English
                "oldenberg",     # English
                "geldner",       # German
                "grassmann",     # German
                "elizarenkova",  # Russian
            ]
            commentaries = {}
            for w in TRANSLATION_WITNESSES:
                text = extract_witness_text(stanza, w)
                if text:
                    commentaries[w] = text

            items.append({
                "id": f"{book_num}.{hymn.get('ana') or ''}.{stanza_num}",
                "samhita_patha": devanagari,
                "samhita_patha_iast": iast_text,
                "pada_patha": to_devanagari(pada_iast) if pada_iast else "",
                "pada_patha_iast": pada_iast,
                "rishi": rishi,
                "devata": devata,
                "chandas": "",  # not found in this encoding -- see README note below
                "translation": [],
                "commentaries": commentaries,
                "audio": [],
                "references": [],
                "tags": []
            })

            if not diagnostic_printed:
                print("\n" + "=" * 60)
                print(f"DIAGNOSTIC — first stanza of book {book_num}, CHECK THIS:")
                print("=" * 60)
                print(json.dumps(items[0], ensure_ascii=False, indent=2))
                print("=" * 60 + "\n")
                diagnostic_printed = True

    return items


def write_output(mandalas):
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    base = OUTPUT_DIR / "data" / "vedas" / "rigveda" / "shakala_shakha" / "samhita"

    for mandala_key, items in mandalas.items():
        d = base / mandala_key
        d.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "vedic_text",
            "default_author": "Apaurusheya (traditionally unauthored / eternally revealed; rishi per hymn noted in each item)",
            "source": "VedaWeb 1.0 TEI dataset (Zenodo 4601264) — Zurich witness, IAST kept alongside a Devanagari conversion; see that file's teiHeader for exact CC licence terms",
            "note": "chandas (metre) was not found in this dataset's encoding and is left blank -- may need a separate source or manual/AI fill-in later.",
            "items": items
        }
        with open(d / "data.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in OUTPUT_DIR.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(OUTPUT_DIR))

    print(f"\nWrote {OUTPUT_ZIP} — upload this via the Admin panel's Upload Zip, "
          f"standing at the  root, same as every other delivery in this project.")


def main():
    extract_dir = download_and_extract()
    mandalas = {}
    for book_num in range(1, 11):
        book_path = extract_dir / f"rv_book_{book_num:02d}.tei"
        if not book_path.exists():
            print(f"WARNING: {book_path.name} not found, skipping.")
            continue
        items = parse_book_file(book_path, book_num)
        mandalas[f"mandala_{book_num:02d}"] = items
        print(f"  -> {len(items)} stanza(s) in mandala_{book_num:02d}\n")

    total = sum(len(v) for v in mandalas.values())
    print(f"\nTotal stanzas parsed: {total} (Rigveda has ~10,552 -- if this is drastically "
          f"different, something's off in one of the books; check the per-book counts above).")
    write_output(mandalas)


if __name__ == "__main__":
    main()

