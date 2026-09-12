#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Builds dge/data/vedanga/vyakarana/dhatupatha/data.json from vidyut's own bundled
Dhatupatha (MIT), matching the item shape dge/js/dhatu.js (stage-15 zip)
expects: {id, dhatu, dhatu_slp, artha, gana(1-10), pada, pada_code,
pada_iast}.

pada (parasmaipada/aatmanepada) is derived from the upadesha's own
"\\" (anudatta-it) marker per 1.3.12 -- an EARLIER attempt treated "~"
as interchangeable with "\\" for this and was flat-out wrong (it called
"paWa~" = paTh, "to read" -- a root that is genuinely PARASMAIPADA
(paThati, not paThate) -- aatmanepada, and its overall P:A ratio of
181:2048 was implausible on its face for the real Dhatupatha). "~" on
its own actually tracks something else (seT augment-taking, not pada)
-- confirmed by cross-checking "eDa~\\" (eDa, aatmanepada AND seT:
eDate / eDiSyate) against "paWa~" (paTh, seT but parasmaipada: paWati /
paWiSyati) against "BU" (bhU, neither marker, parasmaipada+aniT: Bavati
/ BaviSyati) against "nftI~" (nRt, seT but parasmaipada: nRtyati).
Given one wrong hypothesis already slipped through here, pada is
shipped ONLY after that cross-check, with an honest caveat in the
"note" field rather than a claim of certainty; ubhayapada roots are NOT
distinguished from parasmaipada by this rule alone (a real, flagged
gap); seT/aniT is left out entirely -- it has far more real exceptions/
vikalpa than pada does, and the "~"-alone signal wasn't cross-checked
against enough known seT/aniT exception roots to ship with confidence.

Requires the vidyut Python package + its downloadable data package:
    pip install vidyut
    python3 -c "import vidyut; vidyut.download_data('/tmp/vidyut_data')"
then run this script (defaults below assume that path; override via argv).
"""
import json, os, sys

from vidyut.prakriya import Data
from vidyut import lipi

DATA_DIR = os.path.join(sys.argv[1] if len(sys.argv) > 1 else "/tmp/vidyut_data", "prakriya")
OUT = sys.argv[2] if len(sys.argv) > 2 else "dge/data/vedanga/vyakarana/dhatupatha/data.json"

GANA_NAME_TO_NUM = {
    "BvAdi": 1, "adAdi": 2, "juhotyAdi": 3, "divAdi": 4, "svAdi": 5,
    "tudAdi": 6, "ruDAdi": 7, "tanAdi": 8, "kryAdi": 9, "curAdi": 10,
}

def dev(s):
    return lipi.transliterate(s, lipi.Scheme.Slp1, lipi.Scheme.Devanagari)

def pada_of(upadesha):
    if "\\" in upadesha:
        return ("A", "आत्मनेपदम्", "Atmanepada")
    return ("P", "परस्मैपदम्", "Parasmaipada")

def main():
    d = Data(DATA_DIR)
    entries = d.load_dhatu_entries()

    items = []
    gana_counts = {}
    pada_counts = {"P": 0, "A": 0}
    for e in entries:
        upadesha = e.dhatu.aupadeshika
        gana_num = GANA_NAME_TO_NUM[str(e.dhatu.gana)]
        pada_code, pada_dev, pada_iast = pada_of(upadesha)
        gana_counts[gana_num] = gana_counts.get(gana_num, 0) + 1
        pada_counts[pada_code] += 1
        items.append({
            "id": e.code,
            "dhatu": dev(upadesha),
            "dhatu_slp": upadesha,
            "artha": dev(e.artha),
            "gana": gana_num,
            "pada": pada_dev,
            "pada_code": pada_code,
            "pada_iast": pada_iast,
        })

    data = {
        "schema": "vyakarana_dhatupatha",
        "source": "vidyut (ambuda-org/vidyut), MIT licence",
        "licence": "MIT",
        "count": len(items),
        "note": (
            "pada derived from the upadesha's own anudatta-it marker (1.3.12), "
            "cross-checked against bhU/eDa/paWa/nRt -- not exhaustively verified, "
            "and genuine ubhayapada roots are not distinguished from parasmaipada "
            "by this rule alone (a real, flagged gap, not fabricated). seT/aniT "
            "intentionally left out -- see PENDING.md for why. Multi-source "
            "meanings[] (Dhaval/vrtti) enrichment not yet merged in either."
        ),
        "items": items,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"wrote {OUT}")
    print(f"total items: {len(items)}")
    print(f"gana distribution: { {k: gana_counts[k] for k in sorted(gana_counts)} }")
    print(f"pada distribution: {pada_counts}")

if __name__ == "__main__":
    main()
