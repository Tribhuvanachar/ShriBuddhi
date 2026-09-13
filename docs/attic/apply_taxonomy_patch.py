#!/usr/bin/env python3
"""Merge the Kavya genre tree into dge/data/taxonomy.json.

Non-destructive by construction:
  * the existing kavya_alankara node's own attributes are preserved;
  * the five work ids that were already flat children (raghuvamsha,
    kumarasambhava, kiratarjuniya, shishupalavadha, sumadhva_vijaya) are
    RE-PARENTED into the new tree, never recreated, so anything else that
    references them keeps working;
  * any child not mentioned by the patch is kept, parked under the closest
    matching genre or, failing that, left where it was.

  python3 patches/apply_taxonomy_patch.py --taxonomy dge/data/taxonomy.json
  python3 patches/apply_taxonomy_patch.py --taxonomy ... --dry-run
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, "..", "tools", "kavya", "config",
                     "taxonomy_patch.json")
WORKS = os.path.join(HERE, "..", "tools", "kavya", "config", "works.json")


def find_node(node, wanted, parent=None):
    if isinstance(node, dict):
        if node.get("id") == wanted:
            return node, parent
        for key in ("children", "nodes", "items"):
            for child in node.get(key, []) or []:
                hit = find_node(child, wanted, node)
                if hit[0]:
                    return hit
    elif isinstance(node, list):
        for child in node:
            hit = find_node(child, wanted, parent)
            if hit[0]:
                return hit
    return None, None


def walk(node):
    yield node
    for child in node.get("children", []) or []:
        for n in walk(child):
            yield n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    patch = json.load(open(PATCH, encoding="utf-8"))
    works = {w["id"]: w for w in
             json.load(open(WORKS, encoding="utf-8"))["works"]}
    tax = json.load(open(args.taxonomy, encoding="utf-8"))

    old, parent = find_node(tax, "kavya_alankara")
    if old is None:
        print("kavya_alankara not found in %s -- aborting" % args.taxonomy)
        return 1

    new = json.loads(json.dumps(patch["node"]))
    for k, v in old.items():
        if k not in ("children", "nodes", "items"):
            new.setdefault(k, v)

    by_id = {n["id"]: n for n in walk(new)}
    existing_children = old.get("children") or old.get("nodes") or []
    moved, orphaned = [], []
    for child in existing_children:
        cid = child.get("id")
        cfg = works.get(cid)
        target = None
        if cfg:
            for step in reversed(cfg.get("genre_path", [])):
                if step in by_id:
                    target = by_id[step]
                    break
        if target is None:
            orphaned.append(cid)
            target = by_id.get("shravya", new)
        target.setdefault("children", []).append(child)
        moved.append("%s -> %s" % (cid, target["id"]))

    # attach every configured work that is not yet present
    for wid, cfg in works.items():
        if wid in {c.get("id") for c in existing_children}:
            continue
        path = cfg.get("genre_path") or []
        target = None
        for step in reversed(path):
            if step in by_id:
                target = by_id[step]
                break
        if target is None:
            continue
        target.setdefault("children", []).append({
            "id": wid, "name_sa": cfg.get("name_sa", wid),
            "name_iast": cfg.get("name_iast", ""),
            "name_en": cfg.get("name_en", ""),
            "author": cfg.get("author", ""),
            "type": "grantha",
        })

    if parent is None:
        tax = new
    else:
        for key in ("children", "nodes", "items"):
            kids = parent.get(key)
            if kids and old in kids:
                kids[kids.index(old)] = new
                break

    print("re-parented %d existing children:" % len(moved))
    for m in moved:
        print("   " + m)
    if orphaned:
        print("NOT in works.json, parked under shravya -- check these: %s"
              % orphaned)
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    backup = args.taxonomy + ".bak"
    if not os.path.exists(backup):
        os.replace(args.taxonomy, backup)
        print("backed up -> " + backup)
    with open(args.taxonomy, "w", encoding="utf-8") as fh:
        json.dump(tax, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("wrote " + args.taxonomy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
