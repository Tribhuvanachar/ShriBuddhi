#!/usr/bin/env python3
"""Builds dge/data/kavya_alankara/_index.json -- the single file kavya.js
loads at start-up.  Every layer is listed with its counts and flags so the
reader can render the work picker and the layer chips without touching the
layer files; layers are fetched on demand, not sharded.

  python3 -m kavya.build_kavya_index --data-root dge/data
"""
from __future__ import annotations

import argparse
import os
import sys

from .common import log, read_json, write_json

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config")
CATEGORY = "kavya_alankara"

# Reading order in the UI: the attested text first (mula, then the
# traditional commentaries), and the analytic/derived layers after it.
REST_ORDER = ["padaccheda", "anvaya", "translation_en", "translation_hi",
              "saaramsha"]


def _order(layer):
    lid = layer["id"]
    kind = layer.get("layer_kind")
    if lid == "mula" or kind == "mula":
        return (0, 0, lid)
    if kind in ("tika", "tippani"):
        return (1, 0, lid)
    if lid in REST_ORDER:
        return (2, REST_ORDER.index(lid), lid)
    return (3, 0, lid)


def build(data_root):
    works_cfg = {w["id"]: w for w in
                 read_json(os.path.join(CONFIG, "works.json"),
                           {"works": []})["works"]}
    taxonomy = read_json(os.path.join(CONFIG, "taxonomy_patch.json"), {})
    root = os.path.join(data_root, CATEGORY)
    out_works = []
    totals = {"works": 0, "layers": 0, "entries": 0}

    for wid in sorted(os.listdir(root) if os.path.isdir(root) else []):
        wdir = os.path.join(root, wid)
        if not os.path.isdir(wdir) or wid.startswith("_"):
            continue
        cfg = works_cfg.get(wid, {})
        layers = []
        units = []
        for lid in sorted(os.listdir(wdir)):
            path = os.path.join(wdir, lid, "data.json")
            layer = read_json(path)
            if not layer or "grantha" not in layer:
                continue
            g = layer["grantha"]
            counts = g.get("counts") or {}
            layers.append({
                "id": lid,
                "name_sa": g.get("name_sa", ""),
                "name_iast": g.get("name_iast", ""),
                "name_en": g.get("name_en", ""),
                "commentator": g.get("commentator", ""),
                "layer_kind": g.get("layer_kind", ""),
                "language": g.get("language", "sa"),
                "ai_generated": bool(g.get("ai_generated")),
                "counts": counts,
                "path": "data/%s/%s/%s/data.json" % (CATEGORY, wid, lid),
                "source": g.get("source", {}),
                "license": g.get("license", ""),
            })
            totals["entries"] += counts.get("shlokas", 0)
            if not units and lid == "mula":
                units = [{"id": it.get("id"),
                          "name_sa": it.get("name_sa", ""),
                          "n": len(it.get("shlokas", []))}
                         for it in layer.get("items", [])]
        if not layers:
            continue
        layers.sort(key=_order)
        if not units:
            first = read_json(os.path.join(wdir, layers[0]["id"], "data.json"), {})
            units = [{"id": it.get("id"), "name_sa": it.get("name_sa", ""),
                      "n": len(it.get("shlokas", []))}
                     for it in first.get("items", [])]
        out_works.append({
            "id": wid,
            "name_sa": cfg.get("name_sa", wid),
            "name_iast": cfg.get("name_iast", ""),
            "name_en": cfg.get("name_en", ""),
            "author": cfg.get("author", ""),
            "genre_path": cfg.get("genre_path", []),
            "units": units,
            "layers": layers,
        })
        totals["works"] += 1
        totals["layers"] += len(layers)

    index = {
        "version": 2,
        "category": CATEGORY,
        "taxonomy": taxonomy.get("node", {}),
        "totals": totals,
        "works": out_works,
    }
    return index


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", default="dge/data")
    p.add_argument("--out")
    args = p.parse_args(argv)
    index = build(args.data_root)
    out = args.out or os.path.join(args.data_root, CATEGORY, "_index.json")
    write_json(out, index)
    t = index["totals"]
    log("wrote %s: %d works / %d layers / %d entries"
        % (out, t["works"], t["layers"], t["entries"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
