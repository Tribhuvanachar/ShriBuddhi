#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DGE — Dasa Sahitya "personal-collection export" importer (source 3)
=====================================================================

Converts a Firestore-shaped personal-collection export — one `index.json`
manifest (dasaru id/name/jsonPath) plus one `<slug>.json` per dasaru holding
`collections.{padagalu,vachanagalu,shlokagalu}` arrays of doc-shaped
records ({id, title:{en,kn}, description:{en,kn}, category, subcategory,
addedOn, isFavorite}) — into the same per-dasaru JSON shape the other
dasa_sahitya_local assets use.

Distinguishing feature of this source: `description.kn`/`description.en`
carry clean parallel Kannada + English-transliteration text side by side —
neither the web crawl nor the Android-app SQLite source has that pairing
reliably. `description` is the verse body despite the field name (it holds
the full lyric, sometimes with embedded ಶ್ಲೋಕ/ಪಲ್ಲವಿ section markers), not a
summary.

Usage:
    python3 import_dasa_sahitya_collection_json.py --src-dir /path/to/export \
        --out dge/data/dasa_sahitya_local --asset-name collection_padagalu
"""
import argparse
import datetime as _dt
import json
import os
import re
import unicodedata

try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate as _tr
    _HAVE_TR = True
except Exception:
    _HAVE_TR = False

    class _SanscriptShim:
        KANNADA = "kannada"
        IAST = "iast"
        DEVANAGARI = "devanagari"

    sanscript = _SanscriptShim()

FORM_BY_COLLECTION = {"padagalu": "pada", "vachanagalu": "vachana", "shlokagalu": "shloka"}


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text or "", flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "_", text)
    return text or "untitled"


def kn_to(target, kn_text):
    if not _HAVE_TR or not (kn_text or "").strip():
        return ""
    try:
        return _tr(kn_text, sanscript.KANNADA, target)
    except Exception:
        return ""


def ascii_slug(kn_text):
    iast = kn_to(sanscript.IAST, kn_text)
    if not iast:
        return slugify(kn_text)
    decomposed = unicodedata.normalize("NFKD", iast)
    ascii_form = "".join(c for c in decomposed if not unicodedata.combining(c))
    return slugify(ascii_form)


def stanzas_of(text):
    """Split on blank lines into stanzas, then on newlines into lines."""
    text = (text or "").strip()
    if not text:
        return []
    blocks = re.split(r"\n\s*\n", text)
    out = []
    for b in blocks:
        lines = [l.strip() for l in b.split("\n") if l.strip()]
        if lines:
            out.append(lines)
    return out


def build_record(dasaru_kn_name, dasaru_en_name, collection, item, asset_name, fetch_date):
    title_kn = (item.get("title", {}) or {}).get("kn", "") or ""
    title_en = (item.get("title", {}) or {}).get("en", "") or ""
    body_kn = (item.get("description", {}) or {}).get("kn", "") or ""
    body_en = (item.get("description", {}) or {}).get("en", "") or ""
    tags = [f"composer:{dasaru_kn_name}", f"source:personal_collection_export:{asset_name}",
            f"collection:{collection}"]
    if item.get("category"):
        tags.append(f"deity:{item['category']}")
    if item.get("isFavorite"):
        tags.append("favorite")

    rec = {
        "id": ascii_slug(dasaru_kn_name) + "__" + asset_name + "_" + str(item.get("id", "")),
        "form": FORM_BY_COLLECTION.get(collection, "pada"),
        "title": {
            "kn": title_kn,
            "latin": title_en,
            "iast": kn_to(sanscript.IAST, title_kn) if title_kn else "",
            "devanagari": kn_to(sanscript.DEVANAGARI, title_kn) if title_kn else "",
        },
        "composer": dasaru_kn_name,
        "composer_latin": dasaru_en_name,
        "deity": item.get("category", "") or "",
        "tags": tags,
        "raga": "", "tala": "",
        "language": "kn",
        "text": {
            "kannada": stanzas_of(body_kn),
            "iast": [],
            "devanagari": [],
            "source_roman": stanzas_of(body_en),
        },
        "meaning": "",
        "source": {
            "site": f"personal_collection_export:{asset_name}",
            "url": "",
            "attribution": (f"Imported from a local personal-collection export ({asset_name}); "
                             "non-commercial dharma-prachara / education / research."),
            "fetched": fetch_date,
        },
        "app_meta": {
            "asset": asset_name,
            "doc_id": item.get("id", ""),
            "collection": collection,
            "subcategory": item.get("subcategory"),
            "added_on": item.get("addedOn", ""),
            "favorite": bool(item.get("isFavorite")),
        },
        "_needs_review": not bool(stanzas_of(body_kn)),
    }
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-dir", required=True, help="dir with index.json + one <slug>.json per dasaru")
    ap.add_argument("--out", default="dge/data/dasa_sahitya_local")
    ap.add_argument("--asset-name", required=True)
    ap.add_argument("--fetch-date", default=None)
    args = ap.parse_args()

    fetch_date = args.fetch_date or _dt.date.today().isoformat()
    with open(os.path.join(args.src_dir, "index.json"), encoding="utf-8") as f:
        index = json.load(f)

    out_dir = os.path.join(args.out, args.asset_name)
    comp_dir = os.path.join(out_dir, "dasaru")
    os.makedirs(comp_dir, exist_ok=True)

    manifest = {"asset": args.asset_name, "generated": fetch_date, "count_total": 0,
                "counts_by_collection": {}, "needs_review_count": 0, "dasaru": []}

    for entry in index["dasaru"]:
        with open(os.path.join(args.src_dir, entry["jsonPath"]), encoding="utf-8") as f:
            data = json.load(f)
        dasaru_kn = entry["name"]["kn"]
        dasaru_en = entry["name"]["en"]
        records = []
        for collection, items in data.get("collections", {}).items():
            for item in items:
                rec = build_record(dasaru_kn, dasaru_en, collection, item, args.asset_name, fetch_date)
                records.append(rec)
                manifest["counts_by_collection"][collection] = manifest["counts_by_collection"].get(collection, 0) + 1
                if rec["_needs_review"]:
                    manifest["needs_review_count"] += 1
        slug = ascii_slug(dasaru_kn)
        fname = f"{slug}.json"
        with open(os.path.join(comp_dir, fname), "w", encoding="utf-8") as f:
            json.dump({"composer": dasaru_kn, "composer_latin": dasaru_en, "dasaru_id": entry["id"],
                       "count": len(records), "compositions": records}, f, ensure_ascii=False, indent=2)
        manifest["dasaru"].append({"slug": slug, "dasaru_id": entry["id"], "composer": dasaru_kn,
                                    "composer_latin": dasaru_en, "count": len(records), "file": f"dasaru/{fname}"})
        manifest["count_total"] += len(records)

    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[{args.asset_name}] {manifest['count_total']} compositions -> {len(manifest['dasaru'])} dasaru files under {comp_dir}")
    print(f"  by collection: {manifest['counts_by_collection']}")
    print(f"  needs_review: {manifest['needs_review_count']}")


if __name__ == "__main__":
    main()
