#!/usr/bin/env python3
"""Stamp the big catalogue files so the browser can finally cache them.

THE PROBLEM. js/core.js fetched data/library.json -- 521 KB and growing -- as
`?t=' + Date.now()` with cache:'no-store', and js/layer-stitch.js did the same
for the 80 KB layer_manifest.json. Both are therefore re-downloaded IN FULL on
every single page view, by every reader, forever. That is what "the library
says loading, loading, it is not as fast as it used to be" was: roughly 600 KB
of uncacheable traffic before the first verse appears, and it got worse each
time the corpus grew.

WHY THE CACHE-BUSTING WAS THERE, and it was a real problem, not paranoia: a
browser or a CDN will otherwise serve a catalogue from before the most recent
content push, and a newly added grantha is then silently invisible even though
its files are live.

WHY NOT JUST KEY ON THE SITE VERSION. The obvious fix is `?v=4.85.0`, the stamp
already on the script tags. It is wrong here: content lands far more often than
anyone bumps that number, so the first data-only push would pin every reader to
a stale catalogue -- exactly the failure the no-store was protecting against,
but now sticky.

WHAT THIS DOES INSTEAD. One tiny file, data/catalog-version.json (~150 bytes),
carries a content hash of each big file. The reader fetches THAT uncached, then
requests the big files at `?v=<hash>` with ordinary caching. A hash only moves
when the file's bytes move, so: content changes -> new URL -> fresh download;
nothing changes -> the browser serves it from disk and the network is untouched.
The cost is one ~150-byte round trip in place of 600 KB.

Re-run after anything that writes library.json or layer_manifest.json.
tests/test_catalog_version.py fails if the stamp has drifted, so a content push
that forgets this is caught before it reaches a reader rather than after.

Usage: python3 tools/stamp_catalog_version.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/catalog-version.json"
STAMPED = {"library": "data/library.json",
           "manifest": "data/layer_manifest.json"}


def digest(path: Path) -> str:
    """First 12 hex of the file's SHA-256 -- long enough that two different
    catalogues will not collide, short enough to keep the URL readable."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def build() -> str:
    stamps = {}
    for key, rel in STAMPED.items():
        path = ROOT / rel
        if not path.is_file():
            print(f"missing {rel}", file=sys.stderr)
            raise SystemExit(1)
        stamps[key] = digest(path)
    return json.dumps({
        "schema": "catalog_version_v1",
        "note": ("Content hashes of the big catalogue files. Fetched uncached so "
                 "the files themselves can be cached; see "
                 "tools/stamp_catalog_version.py."),
        **stamps,
    }, ensure_ascii=False, indent=1) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed stamp is stale; write nothing")
    args = ap.parse_args()
    want = build()
    have = OUT.read_text(encoding="utf-8") if OUT.is_file() else None
    for key, rel in STAMPED.items():
        print(f"   {rel:<30} {digest(ROOT / rel)}")
    if args.check:
        if have != want:
            print("catalog-version.json is stale -- run "
                  "tools/stamp_catalog_version.py", file=sys.stderr)
            return 1
        print("stamp is current")
        return 0
    OUT.write_text(want, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
