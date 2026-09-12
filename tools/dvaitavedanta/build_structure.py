#!/usr/bin/env python3
"""
build_structure.py — rebuild the Dvaita tree from the data already committed.

WHY NOT FROM THE CACHED PAGES
-----------------------------
The first attempt read the tree out of the crawled HTML, on the assumption
that a page's sidebar carries the whole navigation. It does not: the source
lazy-loads sub-menus, so every page ships the same partly-expanded menu and
the union over all 1,655 pages recovers the same 187 parent links that one
page gives. The rest was never in the HTML at all.

It did not need to be. import_dvaitavedanta.py already stores each item's
full ancestor path as `breadcrumb` — 9,779 of Nyāya Sudhā's 9,929 entries at
depth 7, e.g.

    श्रीमन्न्यायसुधा > सुधा > अनुव्याख्यानम् > मूलम् > तृतीयाध्याय: > प्रथमः पादः > <unit>

so the hierarchy was never lost, only stored as a path of titles instead of a
parent id. This turns those paths back into a tree, from data alone: no
cache, no network, and nothing that can expire.

WHAT IT GIVES A READER
----------------------
Per node: its parent, its children, and its depth. Per leaf: the item ids
sitting there and — because the importer keys mūla and its commentaries on the
same id — the set of layers that speak at that point. That last one answers
"which commentaries comment here", which is the question the folder-per-layer
shape makes hard to ask.

    python tools/dvaitavedanta/build_structure.py \\
        --data data/darshana/vedanta/dvaita/DvaitaVedantaIn --out data/darshana/vedanta/dvaita/DvaitaVedantaIn/_structure.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

SEP = " > "


def walk_items(data_root: Path):
    """Every item in the corpus, with the grantha and layer it came from."""
    for path in sorted(data_root.rglob("data.json")):
        rel = path.relative_to(data_root).parts
        if len(rel) < 2:
            continue
        layer = rel[-2]
        grantha = "/".join(rel[:-2])
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for item in payload.get("items", []):
            yield grantha, layer, item


def build(data_root: Path) -> dict:
    nodes: dict[str, dict] = {}
    skipped = 0

    for grantha, layer, item in walk_items(data_root):
        crumbs = [c for c in (item.get("breadcrumb") or []) if str(c).strip()]
        if not crumbs:
            # No path means nothing to hang the item on. Counted rather than
            # guessed at: a fabricated parent is worse than a known gap.
            skipped += 1
            continue

        for depth in range(1, len(crumbs) + 1):
            key = SEP.join(crumbs[:depth])
            node = nodes.get(key)
            if node is None:
                node = nodes[key] = {
                    "title": crumbs[depth - 1],
                    "depth": depth,
                    "parent": SEP.join(crumbs[: depth - 1]) or None,
                    "grantha": grantha,
                    "children": [],
                    "items": [],
                    "layers": {},
                }
            if depth == len(crumbs):
                if item["id"] not in node["items"]:
                    node["items"].append(item["id"])
                node["layers"][layer] = node["layers"].get(layer, 0) + 1

    for key, node in nodes.items():
        parent = node["parent"]
        if parent is not None and parent in nodes:
            nodes[parent]["children"].append(key)

    for node in nodes.values():
        node["children"].sort()

    return {"nodes": nodes, "skipped_without_breadcrumb": skipped}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/darshana/vedanta/dvaita/DvaitaVedantaIn")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    built = build(Path(args.data))
    nodes = built["nodes"]

    roots = [k for k, v in nodes.items() if v["parent"] is None]
    leaves = [k for k, v in nodes.items() if not v["children"]]
    depths = Counter(v["depth"] for v in nodes.values())
    multi = [k for k, v in nodes.items() if len(v["layers"]) > 1]
    per_grantha = Counter(v["grantha"] for v in nodes.values())

    out = Path(args.out)
    out.write_text(json.dumps({
        "generated_note": "The dvaitavedanta.in hierarchy, rebuilt from the "
                          "breadcrumb each item already carries, by "
                          "tools/dvaitavedanta/build_structure.py. Nodes are keyed "
                          "by their full title path; 'layers' on a leaf is every "
                          "layer that speaks at that point, which is how to ask "
                          "'which commentaries comment here'.",
        "nodes_total": len(nodes),
        "roots": sorted(roots),
        "leaves": len(leaves),
        "depth_histogram": {str(k): v for k, v in sorted(depths.items())},
        "leaves_with_more_than_one_layer": len(multi),
        "skipped_without_breadcrumb": built["skipped_without_breadcrumb"],
        "nodes": nodes,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"nodes {len(nodes)} | roots {len(roots)} | leaves {len(leaves)}")
    print("depths:", dict(sorted(depths.items())))
    print(f"leaves carrying more than one layer: {len(multi)}")
    print(f"items with no breadcrumb (skipped): {built['skipped_without_breadcrumb']}")
    print("granthas:", len(per_grantha))
    print(f"written to {out} ({out.stat().st_size/1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
