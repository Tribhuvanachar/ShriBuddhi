#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DGE — Dasa Sahitya "flat raw-text dump" importer (source 4)
===============================================================

Converts the plainest of the four dasa-sahitya sources: a JSON array per
file, each item just `{"keerthane": "<raw text>"}` (or `{"Title": ..,
"Keerthane": ..}`, or `{"ugabhoga": "<raw text>"}`), no composer field on
the record itself — composer/form is implied entirely by which file it's
in. No titles, no metadata, no source URL: just verse text, `\n`-joined,
sometimes with embedded ॥೧॥-style verse numbering.

One file (ugabhoga.json in the observed batch) isn't composer-scoped at
all — a genre-only dump, composer left blank, flagged for the same
cross-source dedup review as everything else.

One row can be a composer bio blurb rather than a song (observed: a
"ಪರಿಚಯ" / "introduction" titled item as the first entry of a Title-bearing
file) — tagged form="note" rather than folded in as pada #1.

Usage:
    python3 import_dasa_sahitya_flat_json.py --src-dir /path/to/files \
        --out dge/data/dasa_sahitya_local --asset-name raw_dump \
        --composer-map kanakadasa.json=ಕನಕದಾಸರು purandara.json=ಪುರಂದರದಾಸರು \
                       gopaladasa.json=ಗೋಪಾಲದಾಸರು \
        --no-composer-files ugabhoga.json --no-composer-form ugabhoga
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

BIO_TITLE_MARKERS = {"ಪರಿಚಯ"}  # "introduction" — a composer bio, not a song


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


def derive_title(text):
    for line in (text or "").split("\n"):
        line = line.strip()
        if line:
            return re.split(r"[|।॥]", line)[0].strip()[:80]
    return ""


def build_record(composer_kn, form, item, idx, asset_name, fname, fetch_date):
    raw = item.get("Keerthane") or item.get("keerthane") or item.get("ugabhoga") or ""
    title = (item.get("Title") or "").strip()
    is_bio = title in BIO_TITLE_MARKERS
    title_kn = title or derive_title(raw)

    tags = [f"source:flat_text_dump:{asset_name}", f"file:{fname}"]
    if composer_kn:
        tags.append(f"composer:{composer_kn}")

    rec = {
        "id": (ascii_slug(composer_kn) if composer_kn else slugify(fname)) + f"__{asset_name}_{idx}",
        "form": "note" if is_bio else form,
        "title": {
            "kn": title_kn, "latin": "",
            "iast": kn_to(sanscript.IAST, title_kn) if title_kn else "",
            "devanagari": kn_to(sanscript.DEVANAGARI, title_kn) if title_kn else "",
        },
        "composer": composer_kn,
        "deity": "",
        "tags": tags,
        "raga": "", "tala": "",
        "language": "kn",
        "text": {"kannada": stanzas_of(raw), "iast": [], "devanagari": [], "source_roman": []},
        "meaning": "",
        "source": {
            "site": f"flat_text_dump:{asset_name}",
            "url": "",
            "attribution": (f"Imported from a local flat-JSON text dump ({asset_name}/{fname}); "
                             "non-commercial dharma-prachara / education / research."),
            "fetched": fetch_date,
        },
        "app_meta": {"asset": asset_name, "file": fname, "index_in_file": idx, "is_bio_note": is_bio,
                      "had_explicit_title": bool(title)},
        "_needs_review": not bool(stanzas_of(raw)),
    }
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-dir", required=True)
    ap.add_argument("--out", default="dge/data/dasa_sahitya_local")
    ap.add_argument("--asset-name", required=True)
    ap.add_argument("--composer-map", nargs="*", default=[],
                     help="filename.json=ಕನ್ನಡ ಹೆಸರು pairs")
    ap.add_argument("--no-composer-files", nargs="*", default=[],
                     help="filenames with no composer (genre-only dumps)")
    ap.add_argument("--no-composer-form", default="pada",
                     help="form to assign to --no-composer-files entries")
    ap.add_argument("--fetch-date", default=None)
    args = ap.parse_args()

    fetch_date = args.fetch_date or _dt.date.today().isoformat()
    composer_map = {}
    for pair in args.composer_map:
        fname, kn = pair.split("=", 1)
        composer_map[fname] = kn
    no_composer = set(args.no_composer_files)

    out_dir = os.path.join(args.out, args.asset_name)
    comp_dir = os.path.join(out_dir, "dasaru")
    os.makedirs(comp_dir, exist_ok=True)

    manifest = {"asset": args.asset_name, "generated": fetch_date, "count_total": 0,
                "needs_review_count": 0, "bio_notes": 0, "dasaru": []}

    for fname in sorted(os.listdir(args.src_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(args.src_dir, fname), encoding="utf-8") as f:
            items = json.load(f)
        composer_kn = "" if fname in no_composer else composer_map.get(fname, "")
        form = args.no_composer_form if fname in no_composer else "pada"
        records = []
        for i, item in enumerate(items):
            rec = build_record(composer_kn, form, item, i, args.asset_name, fname, fetch_date)
            records.append(rec)
            if rec["_needs_review"]:
                manifest["needs_review_count"] += 1
            if rec["app_meta"]["is_bio_note"]:
                manifest["bio_notes"] += 1
        slug = ascii_slug(composer_kn) if composer_kn else slugify(fname.replace(".json", ""))
        out_fname = f"{slug}.json"
        with open(os.path.join(comp_dir, out_fname), "w", encoding="utf-8") as f:
            json.dump({"composer": composer_kn, "source_file": fname, "count": len(records),
                       "compositions": records}, f, ensure_ascii=False, indent=2)
        manifest["dasaru"].append({"slug": slug, "composer": composer_kn, "source_file": fname,
                                    "count": len(records), "file": f"dasaru/{out_fname}"})
        manifest["count_total"] += len(records)

    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[{args.asset_name}] {manifest['count_total']} items -> {len(manifest['dasaru'])} files under {comp_dir}")
    print(f"  needs_review: {manifest['needs_review_count']}, bio notes: {manifest['bio_notes']}")


if __name__ == "__main__":
    main()
