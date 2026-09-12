#!/usr/bin/env python3
"""Merge seT/aniT (iT-augment) and karma (transitivity) classification into
dge/data/vedanga/vyakarana/dhatupatha/data.json.

vidyut's own dhatupatha (already the source of that file, see its own
"source" field) does not carry these two fields, and dg/tools/build_dhatupatha.py's
own generated `note` says seT/aniT was "left out entirely rather than risk a
second wrong guess" after a first pada-derivation mistake was caught.
ashtadhyayi-com/data (https://github.com/ashtadhyayi-com/data, README: "free
to use ... provided that appropriate credits are mentioned") ships exactly
this as explicit, human-curated fields (`settva`, `karma`) keyed by the same
baseindex ("01.0001" etc.) already used as this repo's own `id`, rather than
inferred from spelling -- so this merges those two fields plus Hindi/English
glosses, and nothing else from that source.

Usage:
    python3 tools/merge_dhatu_classification.py /path/to/ashtadhyayi-com/data
"""
import json
import sys
from pathlib import Path

SETTVA = {"S": "seṭ", "A": "aniṭ", "V": "veṭ"}
KARMA = {"S": "सकर्मक", "A": "अकर्मक", "D": "द्विकर्मक"}

def main():
    if len(sys.argv) != 2:
        sys.exit("usage: merge_dhatu_classification.py /path/to/ashtadhyayi-com/data")
    src_root = Path(sys.argv[1])
    src_file = src_root / "dhatu" / "data.txt"
    if not src_file.exists():
        sys.exit(f"not found: {src_file}")

    src = json.loads(src_file.read_text(encoding="utf-8"))
    by_index = {}
    for row in src["data"]:
        bi = row.get("baseindex")
        if bi:
            by_index[bi] = row

    dst_path = Path(__file__).resolve().parent.parent / "dge" / "data" / "vedanga" / "vyakarana" / "dhatupatha" / "data.json"
    dst = json.loads(dst_path.read_text(encoding="utf-8"))

    matched = set_matched = karma_matched = artha_matched = 0
    for it in dst["items"]:
        row = by_index.get(it["id"])
        if not row:
            continue
        matched += 1
        settva = row.get("settva")
        if settva in SETTVA:
            it["set"] = SETTVA[settva]
            set_matched += 1
        karma = row.get("karma")
        if karma in KARMA:
            it["karma"] = KARMA[karma]
            karma_matched += 1
        ah, ae = row.get("artha_hindi"), row.get("artha_english")
        if ah or ae:
            it["artha_extra"] = {k: v for k, v in (("hi", ah), ("en", ae)) if v}
            artha_matched += 1

    dst["note"] = (
        dst["note"].split(". seT/aniT intentionally left out")[0]
        + ". seṭ/aniṭ/veṭ (`set`) and sakarmaka/akarmaka/dvikarmaka (`karma`) merged from"
        " ashtadhyayi-com/data (github.com/ashtadhyayi-com/data, commit 24109f7,"
        " dhatu/data.txt `settva`/`karma` fields, matched by baseindex == this file's id);"
        " its README: \"free to use ... provided that appropriate credits are mentioned\"."
        " Hindi/English glosses (`artha_extra`) merged from the same source's"
        " `artha_hindi`/`artha_english` fields where present. आदिवर्ण/अन्त्यवर्ण/अनुबन्ध not"
        " merged -- not present as explicit fields in that source either; would need real"
        " SLP1 anubandha-stripping rules, not string slicing, and is deferred."
    )
    dst_path.write_text(json.dumps(dst, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"{len(dst['items'])} local roots, {len(by_index)} source rows")
    print(f"matched by baseindex: {matched}")
    print(f"  set (seṭ/aniṭ/veṭ): {set_matched}")
    print(f"  karma: {karma_matched}")
    print(f"  artha_extra (hi/en): {artha_matched}")

if __name__ == "__main__":
    main()
