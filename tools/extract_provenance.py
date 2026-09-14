#!/usr/bin/env python3
"""Lift every origin-site field out of ShriBuddhi and into Parabuddhi.

WHAT IS STILL THERE. 1,177 data.json carry the importer's `source` block —
241,978 of them — naming the site, its URL, its record numbers and the date we
fetched it:

    "source": {"site": "dvaitavedanta.in",
               "url": "https://dvaitavedanta.in/category-details/19202/945/...",
               "content_id": 19202, "work_id": 945,
               "anchor": "article19292", "fetched": "2026-09-01"}

The unit ids beside them already read SM9:3. The block is what is left of the
old identity, and the lead's rule is that it belongs in Parabuddhi and nowhere
else.

SAFE TO REMOVE, CHECKED RATHER THAN ASSUMED. Nothing in js/ reads it. The
`.source` hits in the reader are other shapes entirely — a note's own source in
actions.js, a vritti's in dhatu.js — and grantha-reader.js's `.layer` is a DOM
data attribute, not this field.

`layer` IS KEPT, promoted out of the block. "भावदीपः" is the commentary's own
name in the tradition; it is ours, and losing it would cost the reader a label
it has every right to show. Everything else goes.

Nothing is destroyed: the whole block is written to Parabuddhi keyed by file
path and unit id, so a question about where a reading came from is still
answerable by anyone entitled to ask it.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

# The importer's fingerprints. `layer` is deliberately absent -- see above.
DROP = ("site", "url", "content_id", "work_id", "anchor", "fetched",
        "source_url", "source_note", "licence", "license", "block_uuid", "origin")


def strip_item(item: dict, keep: dict) -> int:
    """Remove the source block from one unit, recording it. Returns 1 if it had one."""
    src = item.get("source")
    if not isinstance(src, dict):
        return 0
    layer = src.get("layer")
    kept = {k: v for k, v in src.items() if k in DROP or k == "layer"}
    if kept:
        keep[item.get("id") or f"#{id(item)}"] = kept
    item.pop("source", None)
    # The commentary's own name survives, as a plain field the reader can use.
    if layer and "layer" not in item:
        item["layer"] = layer
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map-out", default="/home/user/parabuddhi/provenance_map.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    out: dict[str, dict] = {}
    files = blocks = doc_level = 0
    for p in sorted(glob.glob("data/**/data.json", recursive=True)):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (ValueError, OSError):
            continue
        keep: dict = {}
        n = 0
        for key in ("items", "units"):
            for it in (d.get(key) or []):
                if isinstance(it, dict):
                    n += strip_item(it, keep)
        # A document-level source block, same treatment.
        if isinstance(d.get("source"), dict):
            keep["_doc"] = d.pop("source")
            doc_level += 1
        for k in ("source_url", "source_note", "licence", "license"):
            if k in d:
                keep.setdefault("_doc", {})[k] = d.pop(k)
        if not keep:
            continue
        files += 1
        blocks += n
        out[p] = keep
        if not a.dry_run:
            json.dump(d, open(p, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))

    print(f"{files:,} file(s); {blocks:,} unit source block(s); {doc_level:,} document-level")
    if not a.dry_run:
        json.dump({"_readme": "Origin provenance lifted out of the working repo. "
                              "Lives HERE and nowhere else: it is the only thing that "
                              "can say which site a reading came from. Keyed by the "
                              "file's path, then by unit id.",
                   "files": len(out), "map": out},
                  open(a.map_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"written to {a.map_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
