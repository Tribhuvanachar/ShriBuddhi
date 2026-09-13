#!/usr/bin/env python3
"""Check whether our ashtadhyayi-com/data-derived corpora have drifted from
the live upstream repository.

Why this exists: DGE_Vyakarana_Source_Acquisition_List.md excludes
ashtadhyayi.com as a source for *new* acquisitions, but several corpora we
already have were legitimately pulled from ashtadhyayi.com's own GitHub data
repo (free to use with credit, per its README -- a different thing from
scraping the live site). Four of them (phitsutra, ganapatha, linganushasana,
unadi) record the exact commit they were pulled at, via
tools/vyakarana/import_ashtadhyayi_corpora.py. Two (Mahabhashya, Vasu's
English translation) predate that convention and only cite a filename, with
no commit or accessed_date recorded at all -- so for those we cannot know
whether we are stale relative to any specific point in time; the best we can
do is diff current content against what we hold right now.

This script never re-imports anything by itself -- it only reports. A human
decides whether a reported diff is worth re-running the importer for.

Usage:
    python3 tools/vyakarana/check_ashtadhyayi_drift.py [--src DIR]
(--src defaults to a local clone of ashtadhyayi-com/data, same default as
the importer.)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def strip_markup(text):
    """Our importer strips the raw scraped text's <i>/<b> HTML tags on the way
    in (confirmed by inspecting 1.1.1: upstream has '<i>vriddhi</i>', ours has
    plain 'vriddhi') -- normalize both sides the same way before diffing, or
    every single entry falsely shows as changed."""
    return _HTML_TAG.sub("", text)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The four corpora with a recorded source_commit (see import_ashtadhyayi_corpora.py).
TRACKED = [
    ("fit", "phitsutra", "dge/data/vedanga/vyakarana/phitsutra/data.json"),
    ("ganapath", "ganapatha", "dge/data/vedanga/vyakarana/ganapatha/data.json"),
    ("linganushasanam", "linganushasana", "dge/data/vedanga/vyakarana/linganushasana/data.json"),
    ("unaadi", "unadi", "dge/data/vedanga/vyakarana/unadi/data.json"),
]

# The two direct-from-site citations with no recorded commit -- content-diffed
# by sutra reference instead of by commit.
UNTRACKED = [
    ("sutraani/bhashya.txt", "dge/data/vedanga/vyakarana/ashtadhyayi/mahabhashya_patanjali/data.json"),
    ("sutraani/vasu_english.txt", "dge/data/vedanga/vyakarana/ashtadhyayi/vasu/data.json"),
]


def upstream_key_to_reference(key):
    """'11001' -> '1.1.1', '84068' -> '8.4.68' (adhyaya[1] pada[1] sutra[3])."""
    adhyaya, pada, sutra = key[0], key[1], key[2:]
    return f"{adhyaya}.{pada}.{int(sutra)}"


def check_tracked(src, src_dir, slug, out_path):
    doc_path = os.path.join(src, src_dir, "data.txt")
    if not os.path.exists(doc_path):
        return {"slug": slug, "status": "ERROR", "detail": f"upstream path missing: {doc_path}"}
    if not os.path.exists(os.path.join(ROOT, out_path)):
        return {"slug": slug, "status": "ERROR", "detail": f"our file missing: {out_path}"}

    ours = json.load(open(os.path.join(ROOT, out_path), encoding="utf-8"))
    recorded_commit = ours.get("attribution", {}).get("source_commit", "unknown")
    current_commit = subprocess.check_output(
        ["git", "-C", src, "rev-parse", "HEAD"], text=True).strip()

    upstream_items = json.load(open(doc_path, encoding="utf-8")).get("data") or []
    ours_items = ours.get("items") or []

    same_content = json.dumps(upstream_items, sort_keys=True, ensure_ascii=False) == \
        json.dumps(ours_items, sort_keys=True, ensure_ascii=False)

    return {
        "slug": slug,
        "recorded_commit": recorded_commit,
        "current_commit": current_commit,
        "commit_changed": recorded_commit != current_commit,
        "content_identical": same_content,
        "our_count": len(ours_items),
        "upstream_count": len(upstream_items),
        "status": "OK" if same_content else "DRIFTED",
    }


def check_untracked(src, rel_path, out_path):
    up_path = os.path.join(src, rel_path)
    if not os.path.exists(up_path):
        return {"file": rel_path, "status": "ERROR", "detail": f"upstream path missing: {up_path}"}
    if not os.path.exists(os.path.join(ROOT, out_path)):
        return {"file": rel_path, "status": "ERROR", "detail": f"our file missing: {out_path}"}

    upstream_raw = json.load(open(up_path, encoding="utf-8"))
    upstream_by_ref = {
        upstream_key_to_reference(k): strip_markup(v) for k, v in upstream_raw.items() if v
    }

    ours = json.load(open(os.path.join(ROOT, out_path), encoding="utf-8"))
    our_items = ours.get("items") or []
    our_by_ref = {it["reference"]: strip_markup(it.get("sanskrit_text", "")) for it in our_items}

    only_upstream = sorted(set(upstream_by_ref) - set(our_by_ref))
    only_ours = sorted(set(our_by_ref) - set(upstream_by_ref))
    changed = sorted(
        ref for ref in (set(upstream_by_ref) & set(our_by_ref))
        if upstream_by_ref[ref].strip() != our_by_ref[ref].strip()
    )

    return {
        "file": rel_path,
        "no_recorded_baseline": True,
        "our_count": len(our_by_ref),
        "upstream_count_nonempty": len(upstream_by_ref),
        "only_in_upstream": only_upstream,
        "only_in_ours": only_ours,
        "content_changed": changed,
        "status": "OK" if not (only_upstream or only_ours or changed) else "DRIFTED",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/home/user/ashtadhyayi-com/data")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(args.src, ".git")):
        sys.exit(f"{args.src} is not a git checkout of ashtadhyayi-com/data -- "
                  f"clone it first (GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 "
                  f"https://github.com/ashtadhyayi-com/data {args.src})")

    report = {"tracked": [], "untracked_no_baseline": []}
    for src_dir, slug, out_path in TRACKED:
        report["tracked"].append(check_tracked(args.src, src_dir, slug, out_path))
    for rel_path, out_path in UNTRACKED:
        report["untracked_no_baseline"].append(check_untracked(args.src, rel_path, out_path))

    print(json.dumps(report, indent=2, ensure_ascii=False))

    any_drift = any(r["status"] != "OK" for r in report["tracked"] + report["untracked_no_baseline"])
    sys.exit(1 if any_drift else 0)


if __name__ == "__main__":
    main()
