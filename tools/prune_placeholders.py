#!/usr/bin/env python3
"""Find data.json files the taxonomy no longer points at, and the placeholder
stubs still carrying scaffold dummy text.

The taxonomy restructure created canonical paths (purana/vishnu_purana/amsha_01,
itihasa/mahabharata/harivamsha_khila/…) beside the pre-restructure ones
(amsa_01, harivamsa/…). The old directories survived, still holding the original
scaffold placeholder — literal "Grantha Title" / "Sanskrit text goes here..." —
which renders as English dummy text the moment anything flips their populated
flag.

Classification, by taxonomy membership and content:
  orphan + placeholder  -> safe to delete (superseded scaffold)
  orphan + real data    -> NEVER deleted, reported loudly (data the taxonomy lost)
  canonical + placeholder -> rewritten as a proper empty stub
  canonical + real data -> untouched

Run:  python tools/prune_placeholders.py --data dge/data
      python tools/prune_placeholders.py --data dge/data --fix
"""

import argparse
import json
import os
import shutil

DUMMY_MARKERS = (
    "Grantha Title", "Sanskrit text goes here", "Author / Rishi",
    "Primary Commentary Name", "your_identifier", "Commentary text goes here",
)


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def taxonomy_paths(node, prefix=""):
    """Every path the taxonomy names, at any depth."""
    out = set()
    for key, value in node.items():
        if key.startswith("_"):
            continue
        path = f"{prefix}/{key}" if prefix else key
        out.add(path)
        if isinstance(value, dict):
            out |= taxonomy_paths(value, path)
    return out


def taxonomy_node(taxonomy, rel):
    """The taxonomy node at `rel`, or None if the path is not named."""
    node = taxonomy
    for part in rel.split("/"):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def is_canonical(taxonomy, canonical, data_root, rel):
    """Exact naming wins. Otherwise a folder is superseded when either
    the parent directory holds its own data.json (so the text lives there),
    or the parent's taxonomy node names siblings but not this one.

    Matching on any ancestor is too loose — it would bless
    purana/vishnu_purana/amsa_01 simply because `purana` exists."""
    if rel in canonical:
        return True
    parent, _, leaf = rel.rpartition("/")
    if not parent:
        return False
    if os.path.exists(os.path.join(data_root, parent, "data.json")):
        return False
    node = taxonomy_node(taxonomy, parent)
    if node is None:
        return False
    named = [k for k in node if not k.startswith("_")] if isinstance(node, dict) else []
    if named:
        return leaf in named
    # Parent is a taxonomy leaf with no data.json of its own: a single layer
    # folder beneath it is the intended home for the text.
    return True


def resolved_schema(taxonomy, rel):
    """Nearest ancestor's _schema / _default_author, the way the generator does."""
    node, schema, author = taxonomy, "generic", ""
    for part in rel.split("/"):
        if not isinstance(node, dict):
            break
        schema = node.get("_schema", schema)
        author = node.get("_default_author", author)
        node = node.get(part, {})
    if isinstance(node, dict):
        schema = node.get("_schema", schema)
        author = node.get("_default_author", author)
    return schema, author


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="dge/data")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--trash", default="",
                        help="move removals here instead of deleting")
    args = parser.parse_args(argv)

    taxonomy = load(os.path.join(args.data, "taxonomy.json"), {})
    canonical = taxonomy_paths(taxonomy)

    orphan_placeholder, orphan_real, canonical_placeholder = [], [], []
    for dirpath, dirnames, filenames in os.walk(args.data):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "_dump"))]
        if "data.json" not in filenames:
            continue
        full = os.path.join(dirpath, "data.json")
        rel = os.path.relpath(dirpath, args.data).replace(os.sep, "/")
        if rel == ".":
            continue
        payload = load(full, {})
        raw = json.dumps(payload, ensure_ascii=False)
        placeholder = any(marker in raw for marker in DUMMY_MARKERS)
        in_taxonomy = is_canonical(taxonomy, canonical, args.data, rel)
        items = payload.get("items")
        has_data = bool(items) if isinstance(items, list) else bool(
            payload.get("shlokas") and not placeholder)

        if not in_taxonomy and placeholder:
            orphan_placeholder.append(rel)
        elif not in_taxonomy and has_data:
            orphan_real.append((rel, len(items or [])))
        elif placeholder:
            canonical_placeholder.append(rel)

    print(f"taxonomy names {len(canonical)} paths\n")
    print(f"orphan + placeholder (safe to delete): {len(orphan_placeholder)}")
    for rel in sorted(orphan_placeholder):
        print(f"    {rel}")
    print(f"\ncanonical + placeholder (rewrite as empty stub): {len(canonical_placeholder)}")
    for rel in sorted(canonical_placeholder):
        print(f"    {rel}")
    print(f"\n!! orphan + REAL DATA (never deleted — taxonomy lost these): {len(orphan_real)}")
    for rel, count in sorted(orphan_real, key=lambda x: -x[1]):
        print(f"    {count:>7,} items  {rel}")

    if not args.fix:
        print("\nrun with --fix to apply")
        return 0

    for rel in orphan_placeholder:
        source = os.path.join(args.data, rel)
        if args.trash:
            destination = os.path.join(args.trash, rel)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.move(source, destination)
        else:
            shutil.rmtree(source)

    for rel in canonical_placeholder:
        schema, author = resolved_schema(taxonomy, rel)
        target = os.path.join(args.data, rel, "data.json")
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"schema": schema, "default_author": author, "items": []},
                      handle, ensure_ascii=False, indent=1)
            handle.write("\n")

    print(f"\nremoved {len(orphan_placeholder)} orphan placeholder folder(s); "
          f"rewrote {len(canonical_placeholder)} stub(s)")
    print("now run: python tools/audit_library.py --data dge/data --fix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
