#!/usr/bin/env python3
"""Register the extracted dvaitavedanta tree in taxonomy.json and library.json.

Why this exists rather than reusing tools/register_layers.py: the layer folders
here are discovered at runtime (one per commentary found on the site), so the
taxonomy nodes cannot be authored ahead of time.

It also closes the two failure modes PROJECT_STATUS.md records as repeat bugs:
  * library.json entries written with "title": null
  * "populated": false left stale, which makes dge/js/core.js short-circuit to
    "Not Yet Available" even though the data is right there

Both are set explicitly here, from the data on disk.

Run:  python tools/dvaitavedanta/sync_catalog.py --data dge/data
"""

from __future__ import annotations

import argparse
import json
import os

ROOT_KEY = "dvaitavedanta"


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def scan(tree_root):
    """Yield (rel_slug, schema, default_author, item_count, title) per data.json."""
    for dirpath, _dirnames, filenames in os.walk(tree_root):
        if "data.json" not in filenames:
            continue
        payload = load_json(os.path.join(dirpath, "data.json"), {})
        rel = os.path.relpath(dirpath, os.path.dirname(tree_root)).replace(os.sep, "/")
        grantha_meta = load_json(os.path.join(os.path.dirname(dirpath), "_meta.json"), {}) or {}
        title = (grantha_meta.get("description") or "").split(" — ")[0].strip()
        # The layer's own Devanagari name (सत्तर्कदीपावली, तत्त्वप्रकाशिका …)
        # reads far better in the catalog than the ascii folder slug.
        items = payload.get("items") or []
        layer_title = ""
        if items:
            first = items[0]
            layer_title = (first.get("tika_title") or first.get("tippani_title")
                           or (first.get("source") or {}).get("layer") or "")
        yield (
            rel,
            payload.get("schema", "grantha_tika_text"),
            payload.get("default_author", ""),
            len(items),
            title or None,
            layer_title,
        )


def upsert_taxonomy(taxonomy, slug, schema, default_author):
    node = taxonomy
    parts = slug.split("/")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    leaf = node.setdefault(parts[-1], {})
    leaf["_schema"] = schema
    if default_author:
        leaf["_default_author"] = default_author


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="dge/data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    tree_root = os.path.join(args.data, ROOT_KEY)
    if not os.path.isdir(tree_root):
        print(f"nothing to sync: {tree_root} does not exist")
        return 0

    taxonomy_path = os.path.join(args.data, "taxonomy.json")
    library_path = os.path.join(args.data, "library.json")
    taxonomy = load_json(taxonomy_path, {})
    library = load_json(library_path, {"granthas": []})

    status = load_json(os.path.join(tree_root, "_extract_status.json"), {}) or {}
    titles = {key: entry.get("title") for key, entry in (status.get("granthas") or {}).items()}

    by_path = {entry["path"]: entry for entry in library.get("granthas", [])}
    added = updated = 0

    for slug, schema, default_author, count, meta_title, layer_title in sorted(scan(tree_root)):
        upsert_taxonomy(taxonomy, slug, schema, default_author)

        rel_parts = slug.split("/")            # dvaitavedanta/<section>/<grantha>/<layer>
        grantha_key = "/".join(rel_parts[1:3]) if len(rel_parts) >= 3 else ""
        layer = rel_parts[-1]
        base_title = titles.get(grantha_key) or meta_title or rel_parts[-2]
        suffix = layer_title or layer
        title = base_title if layer == "mula" else f"{base_title} — {suffix}"

        repo_path = f"dge/data/{slug}/data.json"
        entry = by_path.get(repo_path)
        if entry is None:
            entry = {"path": repo_path, "populated": count > 0, "title": title}
            library.setdefault("granthas", []).append(entry)
            by_path[repo_path] = entry
            added += 1
        else:
            changed = False
            if entry.get("populated") != (count > 0):
                entry["populated"] = count > 0
                changed = True
            if not entry.get("title"):
                entry["title"] = title
                changed = True
            updated += int(changed)

    print(f"taxonomy: synced {ROOT_KEY} subtree")
    print(f"library.json: +{added} new, {updated} corrected "
          f"(populated/title), {len(library.get('granthas', []))} total")

    if args.dry_run:
        return 0

    with open(taxonomy_path, "w", encoding="utf-8") as handle:
        json.dump(taxonomy, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    # library.json is indent=2 by convention — indent=1 here would drown the real
    # change in thousands of whitespace-only diff lines (see register_layers.py).
    with open(library_path, "w", encoding="utf-8") as handle:
        json.dump(library, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
