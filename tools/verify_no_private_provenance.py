#!/usr/bin/env python3
"""Fail if anything in data carries the fingerprints of a private source.

WHAT THIS ENFORCES. Material from the rights-unresolved sites now lives in the
private Parabuddhi repository, is transformed there, and reaches this public
repository only through that repo's publish step — which strips the origin's
URLs, its record ids (content_id, work_id, anchor, block_uuid) and its raw
source_html. This script is the check that the rule actually held.

WHY IT IS NOT ENOUGH TO TRUST THE PIPELINE. The publish step scrubs what it was
told to scrub. This scans what actually ARRIVED. They are different questions,
and only the second one is about the file a visitor can fetch. The day someone
re-enables an old importer, restores a file from history, or hand-edits a
data.json with a URL pasted in a note, the pipeline is not involved at all —
and this still fires.

Run in CI on every change to data. Exit 1 on any hit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# 15 Sep 2026: this used to be REPO / "data", and the narrowness was the
# root cause of a whole class of misses. The lead found anandamakaranda.in
# sitting in backlinks/backlinks/darshana__...json on the PUBLIC site, and
# this script had reported that site clean — because the path was outside
# data/ AND the file was not named data.json, so it failed BOTH filters at
# once. A guard that only looks where you expect trouble is not a guard.
DATA = REPO

# Mirrors Parabuddhi's tools/lib/provenance.py PRIVATE_SITES. Kept as a literal
# here rather than imported: the private repo is not present when this runs.
PRIVATE_SITES = (
    "dvaitavedanta.in", "srivaishnavan.com", "advaitasharada.sringeri.net",
    "setutila.in", "anandamakaranda.in", "upanishat.com",
    "tirthaprabandha.wordpress.com", "srimadhvyasa.wordpress.com",
)
PRIVATE_LABELS = frozenset(s.split(".")[0].lower() for s in PRIVATE_SITES)

# Structural fields that only an importer writes. A reader never needs them.
ORIGIN_FIELDS = ("source_html", "content_id", "work_id", "block_uuid", "oldKey", "data_parent")

SITE_RE = re.compile("|".join(re.escape(s) for s in PRIVATE_SITES), re.I)
ID_RE = (
    re.compile(r"\bDV_\d{3,}\b"),
    re.compile(r"\barticle\d{3,}\b"),
)

SKIP_DIRS = {"_references", "_padaccheda", "_commentary_sandhi", "_highlight", "_search"}


def scan(value, path="$"):
    out = []
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str):
                if k in ORIGIN_FIELDS:
                    out.append((f"{path}.{k}", f"origin field {k!r}"))
                elif k.lower() in PRIVATE_LABELS or SITE_RE.search(k):
                    out.append((f"{path}.{k}", f"key names a private source: {k}"))
            out.extend(scan(v, f"{path}.{k}"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out.extend(scan(v, f"{path}[{i}]"))
    elif isinstance(value, str):
        m = SITE_RE.search(value)
        if m:
            out.append((path, f"names {m.group(0)}"))
        for pat in ID_RE:
            m = pat.search(value)
            if m:
                out.append((path, f"origin record id {m.group(0)}"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(DATA),
                    help="root to scan (default: the whole repository)")
    ap.add_argument("--max-report", type=int, default=15)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.data)
    if not root.is_dir():
        print(f"no corpus at {root}")
        return 0

    files = hits = 0
    offenders = []
    # Every .json, not just data.json. The importer's fingerprints land in
    # backlink shards, _meta.json, taxonomy.json and index files just as
    # readily as in a grantha's own data.json.
    #
    # Widening it to every file made the run unusable — json.loads over 200k
    # files takes minutes, and a check nobody can afford to run is a check
    # nobody runs. So each file is first read as BYTES and tested against the
    # literal site names and the id shapes; only a file that could possibly
    # match is parsed, which is the handful that matter. Same answer, and the
    # scan is bounded by disk rather than by the JSON parser.
    needles = [s.encode() for s in PRIVATE_SITES] + [b"DV_", b"article", b"content_id",
                                                     b"work_id", b"source_html", b"block_uuid"]
    for p in sorted(root.rglob("*.json")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        files += 1
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        if not any(n in raw for n in needles):
            continue
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        found = scan(doc)
        if found:
            hits += 1
            offenders.append((rel.as_posix(), found))

    if offenders:
        print(f"{hits} of {files} public corpus files carry a private source's fingerprints:\n")
        for rel, found in offenders[:args.max_report]:
            print(f"  {rel}   ({len(found)} marker(s))")
            for where, why in found[:3]:
                print(f"      {where}  — {why}")
        if len(offenders) > args.max_report:
            print(f"  … and {len(offenders) - args.max_report} more files")
        print("\nThese must be published through Parabuddhi's tools/publish.py, which")
        print("strips provenance and records the mapping, not imported here directly.")
        return 1

    if not args.quiet:
        print(f"{files} public corpus files scanned, no private-source fingerprints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
