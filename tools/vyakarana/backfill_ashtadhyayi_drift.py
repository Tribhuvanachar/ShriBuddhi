#!/usr/bin/env python3
"""Backfill sutras that check_ashtadhyayi_drift.py found missing from our
Mahabhashya / Vasu-English corpora relative to the live ashtadhyayi-com/data
repo.

Deliberately narrow: this only ADDS entries that are confirmed absent from
our corpus and present upstream. It never touches or overwrites an existing
entry -- check_ashtadhyayi_drift.py already confirmed zero content_changed
diffs on shared entries (after normalizing the <i>/<b> markup our importer
already strips), so there is nothing to reconcile there, only gaps to fill.

New entries get the same enrichment shape as their neighbours (tags, author,
tika_title, the comments_on cross-reference) -- these are constant/derived
per corpus, confirmed by inspecting existing entries, not guessed.

Usage:
    python3 tools/vyakarana/backfill_ashtadhyayi_drift.py [--src DIR] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def strip_markup(text):
    return _HTML_TAG.sub("", text)


def upstream_key_to_reference(key):
    adhyaya, pada, sutra = key[0], key[1], key[2:]
    return f"{adhyaya}.{pada}.{int(sutra)}"


def ref_tuple(ref):
    return tuple(int(x) for x in ref.split("."))


def backfill(src, rel_path, out_path, make_item):
    up_path = os.path.join(src, rel_path)
    out_full = os.path.join(ROOT, out_path)
    upstream_raw = json.load(open(up_path, encoding="utf-8"))
    ours = json.load(open(out_full, encoding="utf-8"))
    existing_refs = {it["reference"] for it in ours["items"]}

    added = []
    for key, text in upstream_raw.items():
        if not text:
            continue
        ref = upstream_key_to_reference(key)
        if ref in existing_refs:
            continue
        added.append(make_item(ref, strip_markup(text)))

    if not added:
        return ours, added

    ours["items"] = sorted(ours["items"] + added, key=lambda it: ref_tuple(it["reference"]))
    if "count" in ours:
        ours["count"] = len(ours["items"])
    return ours, added


def mahabhashya_item(ref, text):
    adhyaya = ref.split(".")[0]
    return {
        "id": ref,
        "reference": ref,
        "sanskrit_text": text,
        "references": [{"note": "comments_on",
                         "target": "vedanga/vyakarana/ashtadhyayi/sutrapatha",
                         "unit_id": ref}],
        "tags": ["ashtadhyayi", "mahabhashya", f"adhyaya_{adhyaya}"],
        "author": "Patañjali",
        "tika_title": "Mahābhāṣya",
    }


def vasu_item(ref, text):
    adhyaya = ref.split(".")[0]
    return {
        "id": ref,
        "reference": ref,
        "sanskrit_text": text,
        "references": [{"note": "comments_on",
                         "target": "vedanga/vyakarana/ashtadhyayi/sutrapatha",
                         "unit_id": ref}],
        "language": "en",
        "tags": ["ashtadhyayi", "vasu", "english", f"adhyaya_{adhyaya}"],
        "author": "Śrīśa Chandra Vasu",
        "tika_title": "Vasu — English translation",
    }


JOBS = [
    ("sutraani/bhashya.txt",
     "dge/data/vedanga/vyakarana/ashtadhyayi/mahabhashya_patanjali/data.json",
     mahabhashya_item),
    ("sutraani/vasu_english.txt",
     "dge/data/vedanga/vyakarana/ashtadhyayi/vasu/data.json",
     vasu_item),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/home/user/ashtadhyayi-com/data")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import subprocess
    commit = subprocess.check_output(
        ["git", "-C", args.src, "rev-parse", "HEAD"], text=True).strip()
    today = __import__("datetime").date.today().isoformat()

    for rel_path, out_path, make_item in JOBS:
        updated, added = backfill(args.src, rel_path, out_path, make_item)
        print(f"{out_path}: +{len(added)} entries -> {[a['reference'] for a in added]}")
        if not added:
            continue
        updated.setdefault("attribution_backfill", {})
        updated["attribution_backfill"] = {
            "note": f"{len(added)} entries backfilled from a gap the drift checker found; "
                    "pre-existing entries were left untouched (zero content diffs confirmed).",
            "source_commit": commit,
            "accessed_date": today,
        }
        if not args.dry_run:
            # Match the existing files' compact single-line format -- an
            # indented rewrite would turn an 11-entry addition into a
            # 30,000-line diff for no reason.
            with open(os.path.join(ROOT, out_path), "w", encoding="utf-8") as f:
                json.dump(updated, f, ensure_ascii=False, separators=(", ", ": "))


if __name__ == "__main__":
    main()
