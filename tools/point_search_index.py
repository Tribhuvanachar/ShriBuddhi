#!/usr/bin/env python3
"""
point_search_index.py -- point the site at a freshly published search index.

Run by reindex.yml inside the public repo's checkout, after the index has been
uploaded to Cloud Storage under a prefix named for the data commit.

What it replaces: a regex that rewrote a 40-character commit SHA inside a
jsDelivr URL, because the index was force-pushed to a branch and jsDelivr
caches per file for about 12 hours -- so a new manifest could meet stale
shards and, in js/config.js's own words, break search entirely for those
users. A pin was the fix, and bumping it by hand was the cost.

A prefix named for the build makes every path immutable, so there is nothing
to invalidate and nothing to pin. This just writes the new base URL.

It rewrites the VALUE of searchIndexBase (and global-search.js's CDN_INDEX
fallback) and nothing else -- kavyaDataBase, wordnetDataBase and koshaDataBase
keep whatever they hold.

    python3 tools/point_search_index.py --base https://... --prefix search_index/abc123 \
        --data-sha <sha>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time

# The value is a plain quoted string in both files.
ASSIGNMENT = re.compile(
    r"(searchIndexBase\s*:\s*|CDN_INDEX\s*=\s*)(['\"])(?P<value>(?:\\.|[^'\"\\])*)\2")

TARGETS = ("js/config.js", "js/global-search.js")
STATE = "admin/config/search-index.state.json"


def point(text: str, base: str) -> tuple[str, int]:
    changed = 0

    def swap(match: re.Match) -> str:
        nonlocal changed
        if match.group("value") == base:
            return match.group(0)
        changed += 1
        return match.group(1) + match.group(2) + base + match.group(2)

    return ASSIGNMENT.sub(swap, text), changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--base", required=True, help="the new base URL the client reads from")
    ap.add_argument("--prefix", required=True, help="the bucket prefix it was written to")
    ap.add_argument("--data-sha", required=True)
    ap.add_argument("--root", default=".", help="the checkout to write into")
    args = ap.parse_args(argv)

    total = 0
    for name in TARGETS:
        path = os.path.join(args.root, name)
        if not os.path.exists(path):
            print("  %s is not in this checkout -- skipped" % name)
            continue
        before = open(path, encoding="utf-8").read()
        after, changed = point(before, args.base)
        if changed:
            open(path, "w", encoding="utf-8").write(after)
            total += changed
        print("  %-24s %s" % (name, "pointed at the new prefix" if changed else "already current"))

    state = os.path.join(args.root, STATE)
    os.makedirs(os.path.dirname(state), exist_ok=True)
    with open(state, "w", encoding="utf-8") as handle:
        json.dump({
            "_readme": ("Written by reindex.yml: which data commit the published search index was "
                        "built from, and where it went. The prefix is immutable -- a rebuild writes "
                        "a new one rather than overwriting this one, so there is nothing to "
                        "invalidate and no pin to bump."),
            "data_sha": args.data_sha,
            "prefix": args.prefix,
            "base": args.base,
            "published_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }, handle, ensure_ascii=False, indent=1)
        handle.write("\n")

    print("%d assignment(s) rewritten" % total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
