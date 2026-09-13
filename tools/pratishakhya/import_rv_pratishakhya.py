#!/usr/bin/env python3
"""Import the Rgveda-Pratishakhya into DGE's data.json schema.

Source: The Sanskrit Library, "Rgveda-Pratisakhya: First XML Edition",
ed. Peter M. Scharf, 2010 (Version 0.1); underlying digital text credited
there to George Cardona's "First digital edition" (Philadelphia, 1993-94).
CC BY-NC-SA 3.0. See SOURCES.md in this directory for how this was found
and why the endpoint below is used instead of a "download the XML" step.

There is no published API or downloadable file for this text. The
reader page's own JavaScript (sl.js / sl.model.js, fetched directly from
sanskritlibrary.org and read, not documented anywhere) resolves to this
endpoint, which returns the whole 1,067-sutra work in one response:

    GET https://sanskritlibrary.org/LoadText
        ?text=fgveda_prAtiSAKya&texttype=forTranslation

Each of the 1,067 lines is one numbered sutra ("sN.M", patala N sutra M),
word-tokenized in SLP1, followed by a scholarly apparatus (cross-
references to the Taittiriya- and Vajasaneyi-Pratisakhyas, and to Rgveda
verses) split across "Cross ref./Allusions in/Allusions to/Parallels/
Comments" segments. The source's own OCR-uncertainty marker "[?]" stands
in for characters it could not read confidently (overwhelmingly "U",
judging by which words it appears in -- p[?]rva/purva, br[?]yat/bruyat,
s[?]kta/sukta -- but that is an inference this script deliberately does
NOT make: a sutra containing "[?]" is left untransliterated, with
has_uncertain_reading=true, rather than silently guessing the source's
own gap. Fix those by hand once cross-checked against Layer B
(vedavishtaram.in) or C (the RV-Pratishakhya project), not by pattern-
matching here.

Run: python3 tools/pratishakhya/import_rv_pratishakhya.py
Writes: dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json
"""
import json
import re
import sys
from pathlib import Path

import requests
from indic_transliteration import sanscript

ENDPOINT = "https://sanskritlibrary.org/LoadText"
PARAMS = {"text": "fgveda_prAtiSAKya", "texttype": "forTranslation"}

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = (
    REPO_ROOT
    / "dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json"
)

# Names per the secondary sources cross-checked in
# dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.2.1 (vedavishtaram.in,
# sites.google.com/view/rv-pratishakhya) -- Layer A itself carries no
# patala-title strings, only sutra numbers.
PATALA_NAMES = {
    1: "Samjna-Paribhasha", 2: "Samhita", 3: "Svara", 4: "Sandhi",
    5: "Nati", 6: "Dhvanyagama", 7: "Pluti (I)", 8: "Pluti (II)",
    9: "Pluti (III)", 10: "Krama", 11: "Kramahetu", 12: "Sima",
    13: "Siksha", 14: "Uccharana-Dosha", 15: "Omkara",
    16: "Chandah (I)", 17: "Chandah (II)", 18: "Chandah (III)",
}

SUTRA_LINE_RE = re.compile(r"^s(\d+)\.(\d+)<br/>(.*)$")
LABEL_RE = re.compile(
    r"^(Cross ref\.|Allusions in|Allusions to|Parallels\.|Comments\.)\s*(.*)$"
)
APPARATUS_KEYS = {
    "Cross ref.": "cross_ref",
    "Allusions in": "allusions_in",
    "Allusions to": "allusions_to",
    "Parallels.": "parallels",
    "Comments.": "comments",
}
BOILERPLATE_APPARATUS = {"", "[?]Pr."}


def fetch_lines():
    resp = requests.get(ENDPOINT, params=PARAMS, timeout=60)
    resp.raise_for_status()
    return resp.json()["lines"]


def split_apparatus(segments):
    apparatus = {v: "" for v in APPARATUS_KEYS.values()}
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        m = LABEL_RE.match(seg)
        if not m:
            raise ValueError(f"unrecognized apparatus segment: {seg!r}")
        apparatus[APPARATUS_KEYS[m.group(1)]] = m.group(2).strip()
    return apparatus


def parse_line(line):
    tokens = list(line)
    m = SUTRA_LINE_RE.match(tokens[0])
    if not m:
        raise ValueError(f"line does not start with sN.M<br/>: {tokens[0]!r}")
    patala, sutra = int(m.group(1)), int(m.group(2))
    tokens[0] = m.group(3)
    full = " ".join(tokens)
    segments = full.split("<br/>")
    sutra_text_slp1 = segments[0].strip()
    apparatus = split_apparatus(segments[1:])
    return patala, sutra, sutra_text_slp1, apparatus


# Sanskrit Library's SLP1 uses lowercase "x" for the Vedic retroflex
# lateral flap ळa (only found in the Rgveda Sakala tradition), not
# standard SLP1's vocalic ḷ (which this corpus never uses -- confirmed:
# no uppercase "X" appears anywhere in it). Confirmed against
# VedaVishtaram's own Uvata Bhasya on 3.23/3.28, which spells the word
# plainly as व्याळिः (vyALiH, "the teacher VyALi") in unambiguous
# Devanagari with no transliteration ambiguity -- indic_transliteration's
# standard SLP1 scheme reads "x" as vocalic ḷ instead and garbles it.
# indic_transliteration's own SLP1 scheme already spells this sound "L"
# (-> ळ / ḻ, correctly composing with a following vowel matra), so
# remap Sanskrit Library's "x" to that before transliterating.
def transliterate_sutra(slp1_text):
    """Devanagari + IAST rendering, or (None, None) if the source itself
    marks a reading uncertain -- see the module docstring on "[?]"."""
    if "[?]" in slp1_text:
        return None, None
    # "." = a danda (verse/clause boundary); "[,]" = a lighter pada break.
    # Neither is SLP1 alphabet, so render them directly rather than feed
    # them to the transliterator.
    parts = slp1_text.replace("[,]", ",").replace("x", "L").split()
    deva_parts, iast_parts = [], []
    for tok in parts:
        if tok in (".", ","):
            punct = "।" if tok == "." else ","
            deva_parts.append(punct)
            iast_parts.append(punct if punct == "," else "|")
            continue
        deva_parts.append(sanscript.transliterate(tok, sanscript.SLP1, sanscript.DEVANAGARI))
        iast_parts.append(sanscript.transliterate(tok, sanscript.SLP1, sanscript.IAST))

    def join(parts_):
        out = ""
        for p in parts_:
            if p in ("।", "|", ",") and out.endswith(" "):
                out = out[:-1]
            out += p + " "
        return out.strip()

    return join(deva_parts), join(iast_parts)


def build_items(records):
    items = []
    for patala, sutra, slp1_text, apparatus in records:
        deva, iast = transliterate_sutra(slp1_text)
        has_apparatus = any(
            v not in BOILERPLATE_APPARATUS for k, v in apparatus.items() if k != "cross_ref"
        )
        items.append({
            "id": f"{patala}.{sutra}",
            "patala": patala,
            "patala_name": PATALA_NAMES.get(patala, ""),
            "sutra": sutra,
            "text_devanagari": deva or "",
            "text_iast": iast or "",
            "text_slp1": slp1_text,
            "has_uncertain_reading": deva is None,
            "apparatus": apparatus,
            "has_cross_reference_content": has_apparatus,
            "domain": "krama" if patala == 10 else ("kramahetu" if patala == 11 else ""),
            "crosscheck": "",
        })
    return items


def main():
    print(f"Fetching {ENDPOINT} ...", file=sys.stderr)
    lines = fetch_lines()
    print(f"{len(lines)} lines returned", file=sys.stderr)

    records = [parse_line(line) for line in lines]
    items = build_items(records)

    n_uncertain = sum(1 for it in items if it["has_uncertain_reading"])
    print(f"{n_uncertain}/{len(items)} sutras have an unresolved [?] reading "
          f"(text_devanagari/text_iast left empty for those)", file=sys.stderr)

    data = {
        "schema": "generic",
        "default_author": "Saunaka (traditional attribution; not confirmed by name on the Sanskrit Library catalog card)",
        "source": "The Sanskrit Library, \"Rgveda-Pratisakhya: First XML Edition\", ed. Peter M. Scharf, 2010, Version 0.1; source text per George Cardona's \"First digital edition\" (Philadelphia, 1993-94)",
        "source_url": "https://sanskritlibrary.org/catalogsText/fgveda_prAtiSAKya.html",
        "licence": "Creative Commons Attribution Non-Commercial Share Alike 3.0 (CC BY-NC-SA 3.0) -- https://creativecommons.org/licenses/by-nc-sa/3.0/",
        "note": (
            "Fetched via the reader page's own (undocumented) LoadText endpoint -- "
            "see tools/pratishakhya/import_rv_pratishakhya.py and SOURCES.md for the "
            "endpoint, methodology, and why it's used instead of a static download. "
            "'Version 0.1' per the source's own catalog card: this is a draft edition. "
            "text_devanagari/text_iast are left empty and has_uncertain_reading is set "
            "wherever the source itself marks an OCR-uncertain character ('[?]') -- "
            "cross-check those against VedaVishtaram (vedavishtaram.in) or the "
            "RV-Pratishakhya project (sites.google.com/view/rv-pratishakhya) before "
            "filling them in; do not guess. The 'crosscheck' field on each item is "
            "deliberately empty for the same reason -- populate it once actually "
            "checked, not preemptively. patala_name is from those secondary sources, "
            "not from this source itself. Distinct from the sibling "
            "shaunakiya_chaturadhyayika/data.json, which is the Atharvaveda-"
            "Pratishakhya (a different work, not touched by this import)."
        ),
        "items": items,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Wrote {len(items)} items to {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
