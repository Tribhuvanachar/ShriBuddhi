#!/usr/bin/env python3
"""Merge per-shard _extract_status.json files into one.

The extract workflow fans out over sections as a matrix, so each shard produces
its own status file. This folds them into a single tracker and recomputes the
rollups, keeping the newest record for any grantha that appears twice.

Run:  python tools/dvaitavedanta/merge_status.py --inputs a.json b.json \
          --out data/darshana/vedanta/dvaita/DvaitaVedantaIn/_extract_status.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_dvaitavedanta import recompute_totals  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inputs", nargs="+", required=True,
                       help="status files or globs; the existing --out is merged too")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    paths = []
    for pattern in args.inputs:
        paths.extend(sorted(glob.glob(pattern)))
    if os.path.exists(args.out) and args.out not in paths:
        paths.insert(0, args.out)

    merged = None
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            print(f"  skip {path}: {exc}")
            continue
        if merged is None:
            merged = data
            merged.setdefault("granthas", {})
            merged.setdefault("unmapped_layers", {})
            merged.setdefault("failures", [])
            print(f"  base {path}: {len(merged['granthas'])} grantha(s)")
            continue
        for key, entry in (data.get("granthas") or {}).items():
            existing = merged["granthas"].get(key)
            if existing is None or (entry.get("last_run") or "") >= (existing.get("last_run") or ""):
                if existing and existing.get("first_run"):
                    entry.setdefault("first_run", existing["first_run"])
                merged["granthas"][key] = entry
        for title, count in (data.get("unmapped_layers") or {}).items():
            merged["unmapped_layers"][title] = merged["unmapped_layers"].get(title, 0) + count
        merged["failures"].extend(data.get("failures") or [])
        if (data.get("last_run") or "") > (merged.get("last_run") or ""):
            merged["last_run"] = data["last_run"]
        print(f"  merge {path}: {len(data.get('granthas') or {})} grantha(s)")

    if merged is None:
        print("no status files found")
        return 1

    # Dedupe failures on (url, error) while preserving order.
    seen, deduped = set(), []
    for failure in merged["failures"]:
        key = (failure.get("url"), failure.get("error"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(failure)
    merged["failures"] = deduped[-1000:]

    recompute_totals(merged)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, ensure_ascii=False, indent=1)
        handle.write("\n")

    totals = merged["totals"]
    print(f"→ {args.out}: {totals.get('granthas', 0)} granthas, "
          f"{totals.get('items', 0):,} items, {totals.get('failed', 0)} failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
