#!/usr/bin/env python3
"""Import the Taittiriya-Pratishakhya (Black Yajurveda) from the Sanskrit
Library's LoadText endpoint into DGE's data.json schema.

Source: The Sanskrit Library, "The Taittiriya-Pratisakhya: First XML
Edition", ed. Peter M. Scharf, 2010 (Version 0.1). Underlying text credited
there to Jost Gippert's TITUS 2008 edition, itself based on Makoto
Fushimi's Osaka edition of William Dwight Whitney's "The Taittiriya-
Pratisakhya With its Commentary the Tribhasyaratna: Text, Translation and
Notes" (New Haven 1863, repr. Delhi 1973). CC BY-NC-SA 3.0, same terms
verified for the Rgveda-Pratishakhya import (see
dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.4a.1). Catalog page:
sanskritlibrary.org/catalogsText/titus/vedic/tp.html -- confirmed live and
its licence terms read directly (not assumed from the Rgveda one).

Same undocumented endpoint pattern as the Rgveda import, different
abbreviation:

    GET https://sanskritlibrary.org/LoadText
        ?text=titus/vedic/tp&texttype=forTranslation

Structure here is DIFFERENT from the Rgveda source, not a copy-paste of
that importer's assumptions:
- 1,090 lines, strictly alternating: even index = Sanskrit sutra (first
  token prefixed "c"), odd index = Whitney's English translation (first
  token prefixed "s"). 545 sutra/translation pairs.
- NO chapter/sutra numbers are embedded anywhere in this data (checked:
  no adhyaya-marker tokens, no digit-bearing tokens). Whitney's own
  printed edition numbers sutras by adhyaya (Taittiriya-Pratishakhya has
  24), but that numbering was not carried into this digital transcription.
  This importer does NOT invent adhyaya.sutra numbers to match Whitney's
  printed edition -- doing so from a description rather than the actual
  page images would be exactly the kind of guess this project's own
  standing discipline rejects. Items are given a sequential id (seq_001..)
  instead; mapping to the traditional numbering is real follow-up work,
  not done here.
- The Sanskrit sutra lines carry NO "[?]" OCR-uncertainty markers at all
  (checked: 0 of 545) -- cleaner than the Rgveda source on that axis. The
  English TRANSLATION lines do carry some ("[?]" for OCR-unclear letters
  in Whitney's translation/notes prose) -- kept as raw text, not fixed.
- No "x"-for-retroflex-la quirk observed in this text (checked: 0
  occurrences) -- the Rgveda source's SLP1 x-remap fix does not apply
  here, but transliterate_sutra() is reused as-is (it's a no-op remap
  when "x" never appears) rather than duplicating the function.

Run: python3 tools/pratishakhya/import_taittiriya_pratishakhya.py
Writes: dge/data/vedanga/shiksha/pratishakhya/taittiriya_pratishakhya/data.json
"""
import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_rv_pratishakhya import transliterate_sutra  # noqa: E402

ENDPOINT = "https://sanskritlibrary.org/LoadText"
PARAMS = {"text": "titus/vedic/tp", "texttype": "forTranslation"}

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = (
    REPO_ROOT / "dge/data/vedanga/shiksha/pratishakhya/taittiriya_pratishakhya/data.json"
)


def fetch_lines():
    resp = requests.get(ENDPOINT, params=PARAMS, timeout=60)
    resp.raise_for_status()
    return resp.json()["lines"]


def strip_prefix(line, prefix):
    tokens = list(line)
    assert tokens[0].startswith(prefix), tokens[0]
    tokens[0] = tokens[0][len(prefix):]
    return tokens


def clean_join(tokens):
    """Join tokens into one string, tidying the '..'/','-style punctuation
    this source uses (distinct from the Rgveda source's '.'/'[,]')."""
    text = " ".join(tokens)
    text = text.replace(" ..", ".").replace("..", ".")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_items(lines):
    items = []
    for i in range(0, len(lines), 2):
        sutra_tokens = strip_prefix(lines[i], "c")
        trans_tokens = strip_prefix(lines[i + 1], "s")
        sutra_slp1 = clean_join(sutra_tokens)
        translation = clean_join(trans_tokens)
        deva, iast = transliterate_sutra(sutra_slp1)
        items.append({
            "id": f"seq_{i // 2 + 1:03d}",
            "sequence": i // 2 + 1,
            "adhyaya": None,
            "sutra": None,
            "text_devanagari": deva or "",
            "text_iast": iast or "",
            "text_slp1": sutra_slp1,
            "has_uncertain_reading": deva is None,
            "translation_whitney": translation,
            "crosscheck": "",
        })
    return items


def main():
    print(f"Fetching {ENDPOINT} ...", file=sys.stderr)
    lines = fetch_lines()
    print(f"{len(lines)} lines returned ({len(lines)//2} sutra/translation pairs)", file=sys.stderr)

    items = build_items(lines)
    n_uncertain = sum(1 for it in items if it["has_uncertain_reading"])
    print(f"{n_uncertain}/{len(items)} sutras have an unresolved [?] reading in the Sanskrit "
          f"(expect 0 -- this source's Sanskrit lines carry no [?] markers)", file=sys.stderr)

    data = {
        "schema": "generic",
        "default_author": "Traditionally attributed (Taittiriya school); not confirmed by name on the Sanskrit Library catalog card",
        "source": (
            "The Sanskrit Library, \"The Taittiriya-Pratisakhya: First XML Edition\", "
            "ed. Peter M. Scharf, 2010, Version 0.1; text per Jost Gippert's TITUS 2008 "
            "edition (Frankfurt), based on Makoto Fushimi's Osaka edition of William "
            "Dwight Whitney's \"The Taittiriya-Pratisakhya With its Commentary the "
            "Tribhasyaratna\" (New Haven 1863, repr. Delhi 1973)"
        ),
        "source_url": "https://sanskritlibrary.org/catalogsText/titus/vedic/tp.html",
        "licence": "Creative Commons Attribution Non-Commercial Share Alike 3.0 (CC BY-NC-SA 3.0) -- https://creativecommons.org/licenses/by-nc-sa/3.0/",
        "note": (
            "Fetched via the same undocumented LoadText endpoint as the Rgveda-"
            "Pratishakhya import (see tools/pratishakhya/import_taittiriya_pratishakhya.py "
            "for the endpoint and full methodology). IMPORTANT LIMITATION: this source "
            "carries NO traditional adhyaya.sutra numbering -- items are given a bare "
            "sequential id (seq_001..seq_545) instead of a citable 'TPr N.M' reference. "
            "Mapping to Whitney's printed edition's numbering is real follow-up work, not "
            "done here (would need the actual numbered edition, not a guess from its "
            "description). translation_whitney is Whitney's own 1863 English translation, "
            "carried in this digitization with some OCR noise ('[?]' markers) in the "
            "translation text itself -- the Sanskrit sutra text has none. This is a "
            "separate work from rigveda_pratishakhya/ (a different Veda's Pratishakhya "
            "tradition) and from vajasaneyi_pratishakhya/ (Sukla, not Krishna, Yajurveda)."
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
