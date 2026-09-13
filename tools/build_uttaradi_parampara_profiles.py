#!/usr/bin/env python3
"""Build dge/guru-parampara/data/uttaradi_app_profiles.json -- a companion
enrichment file for parampara.json's Uttaradi-lineage nodes, sourced from
the Uttaradi Matha app's own parampara_table (42 pontiffs, Madhvacharya
through the present).

Kept as a SEPARATE keyed-by-node-id file rather than merged into
parampara.json's nodes directly, matching the existing
brindavana_images.json pattern: parampara.json is a carefully hand-curated
primary file, and this is source-derived supplementary material (audio,
the matha's own narrative bio, contact info) that a consumer can choose to
show alongside it, not fold into it silently.

The id mapping below (app row id -> parampara.json node id) was built by
name-matching all 42 titles against existing node names, then INDEPENDENTLY
verified two ways before trusting it: (1) every matched node's `matha`
field is `uttaradi` or `core` (catches wrong-matha false matches -- this
actually caught 3 real ones: Vedavyasa/Vidyadhisha/Vedanidhi Tirtha each
have same-named pontiffs in other mathas, e.g. Shirur/Kaniyooru/Adamaru,
and a naive match would have picked those); (2) the resulting node
sequence's own `guru` links reproduce the app's row order for all 41
consecutive pairs with zero mismatches. Do not extend this map without
the same two checks -- a name match alone is not enough in a corpus with
this many recurring pontifical names across different mathas.

Usage: python3 tools/build_uttaradi_parampara_profiles.py
"""
from __future__ import annotations

import html
import json
import os
import re
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "dge/sources/uttaradi_matha/panchanga/2024-2027/um_app_seed.db")
OUT = os.path.join(ROOT, "dge/guru-parampara/data/uttaradi_app_profiles.json")

_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_WS = re.compile(r"[ \t]+")

# app parampara_table.id -> parampara.json node id. See module docstring
# for how this was built and verified.
APP_ID_TO_NODE_ID = {
    1: "madhva", 2: "padmanabha", 3: "narahari", 4: "madhavatirtha",
    5: "akshobhya", 6: "jayatirtha", 7: "vidyadhiraja", 8: "kavindra",
    9: "vageesha", 10: "ramachandra_u", 11: "vidyanidhi_u", 12: "raghunatha_u",
    13: "raghuvarya", 14: "raghuttama", 15: "vedavyasa_u", 16: "vidyadhisha_u",
    17: "vedanidhi_u", 18: "satyavrata_u", 19: "satyanidhi_u", 20: "satyanatha",
    21: "satyabhinava", 22: "satyapurna", 23: "satyavijaya", 24: "satyapriya",
    25: "satyabodha", 26: "satyasandha", 27: "satyavara", 28: "satyadharma",
    29: "satyasankalpa", 30: "satyasanthushta", 31: "satyaparayana",
    32: "satyakama", 33: "satyeshti", 34: "satyaparakrama", 35: "satyaveera",
    36: "satyadheera", 37: "satyajnana", 38: "satyadhyana", 39: "satyaprajna_u",
    40: "satyabhijna", 41: "satyapramoda", 42: "satyatma",
}


def strip_html(raw_html):
    if not raw_html:
        return None
    text = _BR.sub("\n", raw_html)
    text = re.sub(r"</(p|li|blockquote|h[1-6])>", "\n", text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = "\n".join(_WS.sub(" ", line).strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("select id, title, audio_url, content, sloka_sanskrit, sloka_english, "
                "poorvasharama_name, preceptor, years_in_pitha, brindavana_at, aradhane, "
                "works, contact_details, contact_map from parampara_table order by id")
    cols = [d[0] for d in cur.description]

    profiles = {}
    for row in cur.fetchall():
        r = dict(zip(cols, row))
        node_id = APP_ID_TO_NODE_ID.get(r["id"])
        if not node_id:
            continue
        profiles[node_id] = {
            "app_title": r["title"],
            "audio_url": r["audio_url"],
            "bio": strip_html(r["content"]),
            "sloka_sanskrit": r["sloka_sanskrit"],
            "sloka_english": r["sloka_english"],
            "poorvasharama_name": r["poorvasharama_name"],
            "years_in_pitha": r["years_in_pitha"],
            "brindavana_at": r["brindavana_at"],
            "aradhane": r["aradhane"],
            "contact_details": r["contact_details"],
            "contact_map": r["contact_map"],
        }
    con.close()

    out = {
        "_note": [
            "Companion enrichment for parampara.json's Uttaradi-lineage nodes, sourced from "
            "the Uttaradi Matha app's own parampara_table -- NOT merged into parampara.json's "
            "nodes directly (that file is hand-curated; this is source material a consumer can "
            "choose to show alongside it). Keyed by parampara.json node id. See "
            "tools/build_uttaradi_parampara_profiles.py for how the id mapping was built and "
            "verified, and dge/sources/uttaradi_matha/panchanga/2024-2027/source-manifest.json "
            "for the underlying artifact's provenance.",
            "audio_url points at the matha's own official CDN (cdn.umath.in), referenced not "
            "re-hosted. rights_status for all of this is UNKNOWN per the source manifest -- "
            "not asserted clean.",
        ],
        "profiles": profiles,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"wrote {len(profiles)} profiles -> {OUT}")


if __name__ == "__main__":
    main()
