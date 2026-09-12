#!/usr/bin/env python3
"""Post-run QA for the Kavya corpus.  Exits non-zero on any FAIL.

Checks, in the order they matter:

  1. An attested layer (mula / tika / tippani) must NEVER carry the
     ai_generated flag.  This is the check that keeps a generated gloss from
     being mistaken for Mallinatha.
  2. Every commentary layer's unit ids must be a subset of its work's mula
     ids -- a commentary that references verses the mula does not have means
     the marker convention was misread.
  3. No layer may be empty, and no layer may have fewer filled entries than
     the previous run recorded (reads _index.json if present).
  4. _index.json must be in sync with what is on disk.
  5. Every layer must carry a source and a licence note.
"""
from __future__ import annotations

import argparse
import os
import sys

from .common import log, read_json
from .schema import ATTESTED_KINDS, validate_layer

CATEGORY = "kavya_alankara"


class Result:
    def __init__(self):
        self.failures = []
        self.warnings = []
        self.checked = 0

    def fail(self, msg):
        self.failures.append(msg)
        log("FAIL  " + msg)

    def warn(self, msg):
        self.warnings.append(msg)
        log("warn  " + msg)


def _ids(layer):
    out = set()
    for it in layer.get("items", []):
        for sh in it.get("shlokas", []):
            out.add(sh.get("id"))
    return out


def verify(data_root, strict_index=True):
    r = Result()
    root = os.path.join(data_root, CATEGORY)
    if not os.path.isdir(root):
        r.fail("no such directory: %s" % root)
        return r

    prev = read_json(os.path.join(root, "_index.json"), {}) or {}
    prev_counts = {}
    for w in prev.get("works", []):
        for l in w.get("layers", []):
            prev_counts[(w["id"], l["id"])] = (l.get("counts") or {}).get("filled", 0)

    for wid in sorted(os.listdir(root)):
        wdir = os.path.join(root, wid)
        if not os.path.isdir(wdir) or wid.startswith("_"):
            continue
        mula_ids = None
        layers = {}
        for lid in sorted(os.listdir(wdir)):
            layer = read_json(os.path.join(wdir, lid, "data.json"))
            if not layer:
                continue
            layers[lid] = layer
            if lid == "mula":
                mula_ids = _ids(layer)

        for lid, layer in layers.items():
            r.checked += 1
            g = layer.get("grantha") or {}
            for e in validate_layer(layer):
                r.fail("%s/%s: %s" % (wid, lid, e))

            # 1 -- AI flag on an attested layer
            if g.get("ai_generated") and g.get("layer_kind") in ATTESTED_KINDS:
                r.fail("%s/%s: attested layer (%s) flagged ai_generated"
                       % (wid, lid, g.get("layer_kind")))
            for _, sh in _iter(layer):
                for b in sh.get("bhashya", []):
                    if b.get("ai_generated"):
                        r.fail("%s/%s: bhashya entry on %s flagged ai_generated"
                               % (wid, lid, sh.get("id")))

            # 2 -- commentary alignment
            if g.get("layer_kind") in ("tika", "tippani") and mula_ids:
                orphan = _ids(layer) - mula_ids
                if orphan:
                    r.fail("%s/%s: %d unit ids absent from mula (e.g. %s) -- "
                           "marker convention likely misread"
                           % (wid, lid, len(orphan), sorted(orphan)[:5]))

            # 3 -- emptiness and regression
            counts = g.get("counts") or {}
            if not counts.get("shlokas"):
                r.fail("%s/%s: layer is empty" % (wid, lid))
            was = prev_counts.get((wid, lid))
            if was and counts.get("filled", 0) < was:
                r.fail("%s/%s: filled entries dropped %d -> %d"
                       % (wid, lid, was, counts.get("filled", 0)))

            # 5 -- provenance
            if not g.get("source"):
                r.warn("%s/%s: no source recorded" % (wid, lid))
            if not g.get("license"):
                r.warn("%s/%s: no licence note" % (wid, lid))

    # 4 -- index freshness
    if strict_index:
        from .build_kavya_index import build
        fresh = build(data_root)
        if fresh["totals"] != prev.get("totals"):
            r.fail("_index.json is stale (disk %s vs index %s) -- re-run "
                   "build_kavya_index" % (fresh["totals"], prev.get("totals")))
    return r


def _iter(layer):
    for it in layer.get("items", []):
        for sh in it.get("shlokas", []):
            yield it, sh


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", default="dge/data")
    p.add_argument("--no-index-check", action="store_true")
    args = p.parse_args(argv)
    r = verify(args.data_root, strict_index=not args.no_index_check)
    log("\nverify_kavya: %d layers checked, %d failures, %d warnings"
        % (r.checked, len(r.failures), len(r.warnings)))
    return 1 if r.failures else 0


if __name__ == "__main__":
    sys.exit(main())
