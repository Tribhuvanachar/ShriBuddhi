#!/usr/bin/env python3
"""Rename every filesystem-hostile path onto tools/safe_paths.safe_component.

Physical renames rather than a rebuild: the index is a 330 MB artifact that
takes hours to regenerate, and the mapping is a pure function of the name, so
moving the files gives exactly what a rebuild would give for a fraction of the
cost. Three trees, all of them generated:

  search_index/postings/<trigram>/   34,711 directories
  search_index/words/<bucket>/        4,677 directories
  data/kosha/<lang>/<dict>/e/*.json   the entry files

manifest.json's wordBucketDeepen is keyed by bucket name, so it moves in the
same pass or the client asks for a depth that no longer exists.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from safe_paths import safe_component  # noqa: E402


def rename_dirs(root: str, dry: bool) -> int:
    if not os.path.isdir(root):
        return 0
    n = 0
    for name in sorted(os.listdir(root)):
        new = safe_component(name)
        if new == name:
            continue
        n += 1
        if not dry:
            os.rename(os.path.join(root, name), os.path.join(root, new))
    return n


def rename_entry_files(dry: bool) -> int:
    n = 0
    for dirpath, _d, files in os.walk(os.path.join("data", "kosha")):
        if os.path.basename(dirpath) != "e":
            continue
        for name in sorted(files):
            stem, ext = os.path.splitext(name)
            new = safe_component(stem) + ext
            if new == name:
                continue
            n += 1
            if not dry:
                os.rename(os.path.join(dirpath, name), os.path.join(dirpath, new))
    return n


def fix_manifest(dry: bool) -> int:
    p = os.path.join("search_index", "manifest.json")
    if not os.path.isfile(p):
        return 0
    with open(p, encoding="utf-8") as fh:
        m = json.load(fh)
    d = m.get("wordBucketDeepen")
    if not isinstance(d, dict):
        return 0
    new = {safe_component(k): v for k, v in d.items()}
    n = sum(1 for k in d if safe_component(k) != k)
    if n and not dry:
        m["wordBucketDeepen"] = new
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(m, fh, ensure_ascii=False, separators=(",", ":"))
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = a.dry_run
    print(f"postings dirs renamed : {rename_dirs(os.path.join('search_index','postings'), d):,}")
    print(f"word bucket dirs      : {rename_dirs(os.path.join('search_index','words'), d):,}")
    print(f"kosha entry files     : {rename_entry_files(d):,}")
    print(f"manifest deepen keys  : {fix_manifest(d):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
