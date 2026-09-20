#!/usr/bin/env python3
"""make_fixture.py -- a miniature corpus with both kinds of work in it.

A full stage cannot be built beside a checkout: search_index alone is 2.7 GB.
This picks a handful of works -- some id-addressed, some not -- and writes a
library.json holding only those, which build_search_index.py then indexes in
about a minute.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opaque_ids import STRUCTURE_PRIVATE                      # noqa: E402

SUPPORT = ("schemas.json", "taxonomy.json", "_meta.json",
           "commentators.json", "author_aliases.json", "dge_entities.json")


def slug(p: str) -> str:
    return p[5:-10] if p.startswith("data/") and p.endswith("/data.json") else ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", required=True)
    ap.add_argument("--each", type=int, default=4, help="works of each kind")
    args = ap.parse_args(argv)

    lib = json.load(open(os.path.join(args.root, "data", "library.json"), encoding="utf-8"))
    priv, pub = [], []
    for g in lib["granthas"]:
        if not g.get("populated"):
            continue
        s = slug(str(g.get("path", "")))
        if not s or not os.path.exists(os.path.join(args.root, "data", s, "data.json")):
            continue
        if any(("data/" + s).startswith(t + "/") for t in STRUCTURE_PRIVATE):
            if len(priv) < args.each:
                priv.append((s, g))
        elif len(pub) < args.each:
            pub.append((s, g))
        if len(priv) >= args.each and len(pub) >= args.each:
            break

    out = {"libraryVersion": lib.get("libraryVersion", "5.0"),
           "appName": lib.get("appName", "DGE"), "granthas": []}
    for s, g in priv + pub:
        d = os.path.join(args.out, "data", s)
        os.makedirs(d, exist_ok=True)
        shutil.copy2(os.path.join(args.root, "data", s, "data.json"), os.path.join(d, "data.json"))
        out["granthas"].append(g)
    with open(os.path.join(args.out, "data", "library.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for f in SUPPORT:
        src = os.path.join(args.root, "data", f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(args.out, "data", f))

    print("%d id-addressed + %d public work(s) -> %s" % (len(priv), len(pub), args.out))
    for s, _ in priv + pub:
        print("    %s" % s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
