#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DGE — Dasa Sahitya "local assets" importer
============================================

Converts a Dasara-Padagalu SQLite asset shipped inside an Android app
(schema: dasaru(id,name), Keerthanas(id,title,txt,dasaru_id,category,favorite))
into the same JSON-per-composer shape the web-crawled corpus already uses
(data/DvaitaVedanta/Itara/DasaSahitya/), but written to a SEPARATE output folder so the two
sources stay distinguishable until a human has reviewed and merged them.

Why a separate folder instead of merging straight in
------------------------------------------------------
* The app DB's composer names are in Kannada with no consistent romanization;
  matching them 1:1 against the 34 web-scraped composer slugs is a fuzzy
  problem (see cross_source_duplicates.json for the automated first pass —
  it WILL contain false positives and needs a human pass before anything is
  merged).
* The `category` column's mapping to a song "form" (pada/suladi/ugabhoga/...)
  is inferred from a handful of samples, not documented anywhere — flagged
  "guess, pending confirmation" in the manifest.
* The `txt` column mixes a variable, per-row metadata header (composer name,
  a one-line description, a genre word, sometimes raga/tala/singer for
  category 4) with the verse body, separated by "<br>". Header-stripping
  here is heuristic, not exact.

Usage
-----
    python3 import_dasa_sahitya_local_db.py --db /path/to/dasa1.db \
        --out data/dasa_sahitya_local --asset-name dasa1

Re-run once per Android asset file (there are reportedly 4-5); pass a
different --asset-name each time and outputs land in the same --out tree
under a per-asset subfolder so nothing overwrites a sibling asset's data.
"""

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sqlite3
import sys
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


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text or "", flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "_", text)
    return text or "untitled"


def ascii_slug(kn_text):
    """Latin, diacritic-free slug (matches the naming convention already used
    by data/DvaitaVedanta/Itara/DasaSahitya/composers/*.json), via IAST with combining marks
    stripped. Falls back to the raw-Kannada slugify() if transliteration is
    unavailable — Python's \\w does not treat Kannada vowel-sign/virama marks
    as word characters, so that fallback alone is lossy; only used as a last
    resort here."""
    iast = kn_to(sanscript.IAST, kn_text)
    if not iast:
        return slugify(kn_text)
    decomposed = unicodedata.normalize("NFKD", iast)
    ascii_form = "".join(c for c in decomposed if not unicodedata.combining(c))
    return slugify(ascii_form)


def kn_to(target, kn_text):
    if not _HAVE_TR or not (kn_text or "").strip():
        return ""
    try:
        return _tr(kn_text, sanscript.KANNADA, target)
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# category -> form. Inferred from sampling ~30 rows per bucket; NOT confirmed
# against app source/docs. Treat as a starting point for human review.
# --------------------------------------------------------------------------- #
CATEGORY_FORM_GUESS = {
    0: "pada",       # default/general kirtane bucket — by far the largest (~88%)
    1: "ugabhoga",   # rows carry a "ಉಗಾಭೋಗಗಳು" header
    2: "mundige",    # rows carry a "ಮುಂಡಿಗೆಗಳು" header (riddle-padas, mostly Kanakadasa)
    3: "pada",       # no consistent header keyword found in samples — unclear bucket
    4: "devaranama", # rows carry explicit ಹಾಡಿನ ಹೆಸರು/ಹಾಡಿದವರ ಹೆಸರು/ರಾಗ/ತಾಳ/ಶೈಲಿ fields —
                     # reads as modern rendered songs, not classical dasa-sahitya per se
    5: "suladi",     # rows carry a "ಸುಳಾದಿ"/"ಸುಳಾದಿಗಳು" header
}
CATEGORY_CONFIDENCE = {
    0: "default bucket, not a positive signal",
    1: "sampled, consistent header keyword",
    2: "sampled, consistent header keyword; 'mundige' is not in the existing dasa_pada_text form enum",
    3: "sampled, NO consistent header keyword found — least confident mapping",
    4: "sampled, consistent structured header (song/singer/raga/tala/style)",
    5: "sampled, consistent header keyword",
}

_HEADER_KEYWORD_RE = re.compile(
    r"^(ಕೀರ್ತನೆ|ಸುಳಾದಿ|ಉಗಾಭೋಗ|ಪದಗಳು|ಮುಂಡಿಗೆ|ಹಾಡುಗಳು|ಕೃತಿಗಳು|ರಚನೆಗಳು|ಧ್ರುವತಾಳ"
    r"|ಭಾವ\s*[:：]|ಈ\s|\*+$)"
)
# category==4 rows carry a trailing "label <br> : <br> value" metadata block
# (song name / singer / raga / tala / style / music-director / studio) — it
# can appear anywhere in the line list (observed: always at the END, after
# the verse), so it is extracted with a full-list scan, not a leading-lines-
# only one. Any field can be BLANK, in which case its ':' is immediately
# followed by the next label rather than a value — extract_meta_kv() below
# has to peek ahead to tell a real value from the next label.
_META_LABELS = ["ಹಾಡಿನ ಹೆಸರು", "ಹಾಡಿದವರ ಹೆಸರು", "ರಾಗ", "ತಾಳ", "ಶೈಲಿ",
                "ಸಂಗೀತ ನಿರ್ದೇಶಕರು", "ಸ್ಟುಡಿಯೋ"]
_META_KV_RE = re.compile("^(" + "|".join(re.escape(l) for l in _META_LABELS) + ")$")
# A bare trailing "ನಿರ್ಗಮನ" ("exit") after the metadata block reads like a
# leaked Android UI button label, not song content — dropped if it's the
# very last line.
_TRAILING_UI_JUNK = {"ನಿರ್ಗಮನ"}
KANNADA_RE = re.compile(r"[ಀ-೿]")


def strip_leading_header(lines, composer_name, title):
    """Best-effort removal of leading non-verse lines: the composer name
    repeated verbatim, a bare '*' divider, or a known genre/section keyword
    (ಸುಳಾದಿ/ಉಗಾಭೋಗ/ಮುಂಡಿಗೆ/...). Only looks at the first 6 lines and stops at
    the first line that doesn't match — under-strips rather than over-strips,
    since a residual header line in the body is easier for a human to spot
    later than silently-eaten verse text."""
    header, i = [], 0
    while i < len(lines) and i < 6:
        ln = lines[i]
        if ln == composer_name.strip() or ln == "*":
            header.append(ln)
            i += 1
            continue
        if _HEADER_KEYWORD_RE.match(ln) and ln != title.strip():
            header.append(ln)
            i += 1
            continue
        break
    return header, lines[i:]


def extract_meta_kv(lines):
    """Pull every 'label / : / value' triple (category==4's trailing
    song-name/singer/raga/tala/style/music-director/studio block) out of the
    line list, wherever it occurs. A field is only consumed as 'label: value'
    when a literal ':' line directly follows the label; if the line after
    that ':' is itself another recognized label, the field was blank in the
    source and is recorded as "" without swallowing the next label.
    Returns (meta_kv dict, remaining lines with those consumed)."""
    meta_kv, remaining, i, n = {}, [], 0, len(lines)
    while i < n:
        ln = lines[i]
        m = _META_KV_RE.match(ln)
        if m and i + 1 < n and lines[i + 1] == ":":
            label = m.group(1)
            j = i + 2
            if j < n and not _META_KV_RE.match(lines[j]):
                meta_kv[label] = lines[j]
                i = j + 1
            else:
                meta_kv[label] = ""
                i = j
            continue
        remaining.append(ln)
        i += 1
    return meta_kv, remaining


def parse_txt(raw_txt, composer_name, title):
    lines = [l.strip() for l in (raw_txt or "").split("<br>")]
    lines = [l for l in lines if l]
    header, body_lines = strip_leading_header(lines, composer_name, title)
    meta_kv, body_lines = extract_meta_kv(body_lines)
    if body_lines and body_lines[-1] in _TRAILING_UI_JUNK:
        header = header + [body_lines[-1]]
        body_lines = body_lines[:-1]
    kn_lines = [l for l in body_lines if KANNADA_RE.search(l)]
    non_kn_lines = [l for l in body_lines if not KANNADA_RE.search(l)]
    return {
        "header_stripped": header,
        "meta_kv": meta_kv,          # only populated for category==4 rows
        "kannada_lines": kn_lines,
        "other_lines": non_kn_lines,  # anything left that wasn't classified Kannada
    }


def build_record(row, dasaru_name, asset_name, fetch_date):
    kid, title, txt, dasaru_id, category, favorite = row
    parsed = parse_txt(txt, dasaru_name, title or "")
    form = CATEGORY_FORM_GUESS.get(category, "pada")

    tags = [f"composer:{dasaru_name}", f"source:android_app_local:{asset_name}",
            f"category_raw:{category}", f"form:{form}"]
    if favorite:
        tags.append("favorite")
    # Category 4 rows carry a singer/raga/tala/music-director/studio block --
    # a modern recorded rendition of a song, not the song itself as a piece of
    # classical literature. Tagged (not filed separately) so it stays part of
    # the one merged corpus but can be queried, filtered, relabeled or
    # dropped independently later without re-deriving which rows these were.
    is_recorded_rendition = category == 4
    if is_recorded_rendition:
        tags.append("rendition:studio_recording")

    rec = {
        "id": ascii_slug(dasaru_name) + "__" + asset_name + "_" + str(kid),
        "form": form,
        "form_confidence": CATEGORY_CONFIDENCE.get(category, "unknown"),
        "title": {
            "kn": title or "",
            "latin": "",
            "iast": kn_to(sanscript.IAST, title) if title else "",
            "devanagari": kn_to(sanscript.DEVANAGARI, title) if title else "",
        },
        "composer": dasaru_name,
        "composer_iast": kn_to(sanscript.IAST, dasaru_name),
        "deity": "",
        "tags": tags,
        "raga": parsed["meta_kv"].get("ರಾಗ", ""),
        "tala": parsed["meta_kv"].get("ತಾಳ", ""),
        "singer": parsed["meta_kv"].get("ಹಾಡಿದವರ ಹೆಸರು", ""),
        "style": parsed["meta_kv"].get("ಶೈಲಿ", ""),
        "music_director": parsed["meta_kv"].get("ಸಂಗೀತ ನಿರ್ದೇಶಕರು", ""),
        "studio": parsed["meta_kv"].get("ಸ್ಟುಡಿಯೋ", ""),
        "language": "kn",
        "text": {
            "kannada": [parsed["kannada_lines"]] if parsed["kannada_lines"] else [],
            "iast": [],
            "devanagari": [],
            "source_roman": [],
        },
        "meaning": "",
        "source": {
            "site": f"android_app_local_asset:{asset_name}",
            "url": "",
            "attribution": ("Imported from a local Android app database asset "
                             f"({asset_name}); non-commercial dharma-prachara / "
                             "education / research."),
            "fetched": fetch_date,
        },
        "app_meta": {
            "asset": asset_name,
            "dasaru_id": dasaru_id,
            "keerthana_id": kid,
            "category_raw": category,
            "is_recorded_rendition": is_recorded_rendition,
            "favorite": bool(favorite),
            "header_stripped": parsed["header_stripped"],
            "unclassified_lines": parsed["other_lines"],
        },
        "_needs_review": bool(parsed["other_lines"]) or not parsed["kannada_lines"],
    }
    return rec


def main():
    ap = argparse.ArgumentParser(description="Import a Dasa-Sahitya Android-app SQLite asset")
    ap.add_argument("--db", required=True, help="path to the .db asset (e.g. dasa1.db)")
    ap.add_argument("--out", default="data/dasa_sahitya_local")
    ap.add_argument("--asset-name", required=True, help="short id for this asset, e.g. dasa1")
    ap.add_argument("--fetch-date", default=None)
    args = ap.parse_args()

    fetch_date = args.fetch_date or _dt.date.today().isoformat()
    con = sqlite3.connect(args.db)
    cur = con.cursor()

    cur.execute("SELECT id, name FROM dasaru")
    dasaru = {i: n for i, n in cur.fetchall()}

    cur.execute("SELECT id, title, txt, dasaru_id, category, favorite FROM Keerthanas ORDER BY dasaru_id, id")
    rows = cur.fetchall()

    by_dasaru = {}
    for row in rows:
        dasaru_id = row[3]
        name = dasaru.get(dasaru_id, f"unknown_dasaru_{dasaru_id}")
        rec = build_record(row, name, args.asset_name, fetch_date)
        by_dasaru.setdefault(dasaru_id, {"name": name, "records": []})
        by_dasaru[dasaru_id]["records"].append(rec)

    out_dir = os.path.join(args.out, args.asset_name)
    comp_dir = os.path.join(out_dir, "dasaru")
    os.makedirs(comp_dir, exist_ok=True)

    manifest = {
        "asset": args.asset_name,
        "source_db": os.path.basename(args.db),
        "generated": fetch_date,
        "count_total": len(rows),
        "count_dasaru": len(by_dasaru),
        "category_form_guess": CATEGORY_FORM_GUESS,
        "category_confidence": CATEGORY_CONFIDENCE,
        "counts_by_category_raw": {},
        "counts_by_dasaru": {},
        "needs_review_count": 0,
        "dasaru": [],
    }
    for did, d in sorted(by_dasaru.items(), key=lambda kv: -len(kv[1]["records"])):
        slug = ascii_slug(d["name"])
        fname = f"{slug}.json"
        with open(os.path.join(comp_dir, fname), "w", encoding="utf-8") as f:
            json.dump({"composer": d["name"], "dasaru_id": did, "count": len(d["records"]),
                       "compositions": d["records"]}, f, ensure_ascii=False, indent=2)
        manifest["counts_by_dasaru"][d["name"]] = len(d["records"])
        manifest["dasaru"].append({"slug": slug, "dasaru_id": did, "composer": d["name"],
                                    "count": len(d["records"]), "file": f"dasaru/{fname}"})
        for r in d["records"]:
            cat = r["app_meta"]["category_raw"]
            manifest["counts_by_category_raw"][str(cat)] = manifest["counts_by_category_raw"].get(str(cat), 0) + 1
            if r["_needs_review"]:
                manifest["needs_review_count"] += 1

    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[{args.asset_name}] {len(rows)} keerthanas -> {len(by_dasaru)} dasaru files under {comp_dir}")
    print(f"  needs_review flagged: {manifest['needs_review_count']}")
    print(f"  by category_raw: {manifest['counts_by_category_raw']}")


if __name__ == "__main__":
    main()
