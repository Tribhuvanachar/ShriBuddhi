#!/usr/bin/env python3
"""Build dge/guru-parampara/data/pratima.json -- the deity/pratima layer
that DGE_Madhva_Acquisition_Architecture.md §26 calls for and that,
until now, did not exist anywhere in this corpus (parampara.json and
mathas.json model saints and institutions, not individual worshipped
images).

Unlike mathas.json/parampara.json's people/places, this file is NOT
auto-derived from parampara.json -- it is built from acquired source data
(currently: dge/sources/vyasaraja_anjaneya_app/), one source per run, never
guessed. Re-run this after adding a new pratima source to dge/sources/.

Current source: the ~732-idol Hanuman/Anjaneya network traditionally
attributed to Sri Vyasatirtha's consecrations (see parampara.json's
vyasatirtha node: "traditionally consecrated 732 Mukhyaprana icons" --
this file is the first structured data backing that prose claim). 323 of
the ~732 are in the source app; the rest are not yet acquired anywhere.

gps is deliberately left null here: the source only gives a Google Maps
share-link and a *local* Plus Code (e.g. "6RPH+V8 <place>"), which cannot
be decoded to real lat/lng without a reference point per entry (a local
Plus Code is only unambiguous relative to a known nearby location) --
guessing that reference would risk a wrong coordinate, which is worse than
none. map_url and plus_code are kept as-is for a human (or a future,
careful geocoding pass) to resolve.

Usage: python3 tools/build_pratima.py
"""
from __future__ import annotations

import html
import json
import os
import re
import sqlite3

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/.."
HANUMAN_SRC = os.path.join(ROOT, "dge/sources/vyasaraja_anjaneya_app/vyasaraja_hanuman_installations.json")
UTTARADI_DB = os.path.join(ROOT, "dge/sources/uttaradi_matha/panchanga/2024-2027/um_app_seed.db")
OUT = os.path.join(ROOT, "dge/guru-parampara/data/pratima.json")

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_WS = re.compile(r"[ \t]+")


def slugify(text):
    return _SLUG_STRIP.sub("-", text.lower()).strip("-") or "unnamed"


def strip_html(raw_html):
    """Convert the app's rendered HTML (blockquote/p/ol/li/br) to plain text:
    <br> and block boundaries become newlines, everything else is dropped."""
    if not raw_html:
        return None
    text = _BR.sub("\n", raw_html)
    text = re.sub(r"</(p|li|blockquote)>", "\n", text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = "\n".join(_WS.sub(" ", line).strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def build_vyasaraja_hanuman_entries():
    rows = json.load(open(HANUMAN_SRC, encoding="utf-8"))
    seen_ids = {}
    entries = []
    for row in rows:
        base = slugify(f"{row['place']}-{row['district']}") if row["place"] else slugify(row["district"])
        seen_ids[base] = seen_ids.get(base, 0) + 1
        suffix = "" if seen_ids[base] == 1 else f"-{seen_ids[base]}"
        entries.append({
            "id": f"vyasaraja-hanuman-{base}{suffix}",
            "deity": "Hanuman (Anjaneya / Mukhyaprana)",
            "type": "installed_idol",
            "installed_by_saint_id": "vyasatirtha",
            "matha_id": None,
            "state": row["state"],
            "district": row["district"],
            "place": row["place"],
            "address": row["address"],
            "map_url": row["map_url"],
            "plus_code": row["plus_code"],
            "gps": None,
            "sloka": None,
            "description": None,
            "image": None,
            "source": {
                "artifact": "dge/sources/vyasaraja_anjaneya_app/vyasaraja_hanuman_installations.json",
                "manifest": "dge/sources/vyasaraja_anjaneya_app/source-manifest.json",
            },
        })
    return entries


UTTARADI_DEITY_TYPES = {
    "Sri Moola Rama": "moola_pratima",
    "Sri Moola Sita": "moola_pratima",
    "Sri Digvijaya Rama": "sthana_pratima",
    "Sri Vyasamushti": "saligrama",
    "Sri Vamsha Rama": "sthana_pratima",
    "Sri Prasanna Vittala": "sthana_pratima",
}


def build_uttaradi_deity_entries():
    con = sqlite3.connect(UTTARADI_DB)
    cur = con.cursor()
    cur.execute("select id, name, sloka, image_path, content from main_deities_table")
    cols = [d[0] for d in cur.description]
    entries = []
    for row in cur.fetchall():
        r = dict(zip(cols, row))
        entries.append({
            "id": f"uttaradi-{slugify(r['name'])}",
            "deity": r["name"],
            "type": UTTARADI_DEITY_TYPES.get(r["name"], "sthana_pratima"),
            "installed_by_saint_id": None,
            "matha_id": "uttaradi",
            "state": None,
            "district": None,
            "place": None,
            "address": None,
            "map_url": None,
            "plus_code": None,
            "gps": None,
            "sloka": strip_html(r["sloka"]),
            "description": strip_html(r["content"]),
            "image": r["image_path"],
            "source": {
                "artifact": "dge/sources/uttaradi_matha/panchanga/2024-2027/um_app_seed.db",
                "manifest": "dge/sources/uttaradi_matha/panchanga/2024-2027/source-manifest.json",
                "table": "main_deities_table",
                "row_id": r["id"],
                "image_rights_note": "image field is a live URL on the matha's own official CDN "
                                      "(cdn.umath.in), referenced not re-hosted; rights_status "
                                      "otherwise UNKNOWN per the source manifest",
            },
        })
    con.close()
    return entries


def main():
    entries = build_vyasaraja_hanuman_entries() + build_uttaradi_deity_entries()
    out = {
        "_readme": [
            "Deity/pratima layer per DGE_Madhva_Acquisition_Architecture.md §26.",
            "NOT auto-derived from parampara.json like mathas.json is -- built from",
            "acquired source data in dge/sources/, one source at a time, by",
            "tools/build_pratima.py. Re-run after adding a new source rather than",
            "hand-editing entries this script generates. gps is left null where the",
            "source only gives a Maps link/local Plus Code -- do not guess a",
            "coordinate; resolve it with a real geocoding pass instead.",
            "installed_by_saint_id and matha_id are foreign keys into",
            "parampara.json's node ids and mathas.json's matha ids respectively;",
            "exactly one of them is expected to be set per entry (a pratima is",
            "either tied to an institution's own seat, or to a saint's broader",
            "installation network -- not modelled as both here).",
        ],
        "pratima": entries,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"wrote {len(entries)} entries -> {OUT}")


if __name__ == "__main__":
    main()
