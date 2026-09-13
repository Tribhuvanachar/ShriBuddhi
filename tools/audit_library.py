#!/usr/bin/env python3
"""Reconcile dge/data/library.json AND taxonomy.json against what is on disk.

dge/js/core.js will not fetch a grantha that has no library.json entry, and it
short-circuits to "Not Yet Available" when `populated` is false. So a data.json
can be fully ingested and still be invisible. That has bitten this project
repeatedly; this makes it a check rather than a discovery.

Three faults are detected and repaired:
  orphan   data.json on disk with no library.json entry  -> add one
  missing  library.json entry whose file does not exist  -> drop it
  stale    populated flag disagreeing with the item count -> correct it

taxonomy.json is the other half of the same problem: dge/js/library.js builds the
browsable tree from it, so a text absent from the taxonomy is missing from the
tree even when library.json lists it. Folders holding a real data.json that the
taxonomy does not name are added, with the schema read from the file itself.

Titles for new entries come from the file's own title_devanagari / title, then
its folder's _meta.json description, then a transliterated folder name — never
null, which is the other half of the same bug.

Run:  python tools/audit_library.py --data dge/data            # report only
      python tools/audit_library.py --data dge/data --fix
"""

import argparse
import json
import os
import re


def load(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def item_count(payload):
    """Item counts live under different keys across the corpus's schema
    generations; the legacy shape uses a dict keyed by verse number."""
    if not isinstance(payload, dict):
        return 0
    for key in ("items", "shlokas", "compositions", "entries"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
    # vedanga_chandas_vrutta_database is a lookup table, not an items[] list.
    # gen_library_status.py already knows this; without the same case here the
    # two tools fight over the populated flag — audit flips the live Chandas
    # entry to false, gen flips it back — on every reconcile pass.
    if payload.get("schema") == "vedanga_chandas_vrutta_database":
        return sum(len(v) for v in payload.values() if isinstance(v, list))
    return 0


def derive_title(path, payload, data_root):
    for key in ("title_devanagari", "title"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for sub in ("devanagari", "sa", "iast", "en"):
                if value.get(sub):
                    return value[sub]

    folder = os.path.dirname(path)
    for candidate in (folder, os.path.dirname(folder)):
        meta = load(os.path.join(candidate, "_meta.json"), {}) or {}
        description = (meta.get("description") or "").strip()
        if description:
            head = re.split(r"\s+—\s+|\s+\(", description)[0].strip()
            if head and "structure file" not in head.lower():
                leaf = os.path.basename(folder)
                return head if candidate == folder else f"{head} — {leaf}"

    rel = os.path.relpath(folder, data_root).replace(os.sep, "/")
    return rel.split("/")[-1].replace("_", " ").title()


def taxonomy_has(taxonomy, rel):
    node = taxonomy
    for part in rel.split("/"):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def taxonomy_add(taxonomy, rel, schema, author):
    node = taxonomy
    parts = rel.split("/")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            return False
    leaf = node.setdefault(parts[-1], {})
    if isinstance(leaf, dict):
        if schema:
            leaf["_schema"] = schema
        if author:
            leaf["_default_author"] = author
        return True
    return False


def scan(data_root):
    found = {}
    for dirpath, dirnames, filenames in os.walk(data_root):
        dirnames[:] = [d for d in dirnames if not d.startswith(("_dump", ".git"))]
        if "data.json" not in filenames:
            continue
        full = os.path.join(dirpath, "data.json")
        rel = "dge/data/" + os.path.relpath(full, data_root).replace(os.sep, "/")
        payload = load(full, {})
        found[rel] = {"count": item_count(payload), "payload": payload, "full": full}
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="dge/data")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY", ""))
    args = parser.parse_args(argv)

    library_path = os.path.join(args.data, "library.json")
    library = load(library_path)
    if library is None:
        print(f"no library.json at {library_path}")
        return 2

    entries = library.get("granthas", [])
    by_path = {e["path"]: e for e in entries}
    on_disk = scan(args.data)

    taxonomy_path = os.path.join(args.data, "taxonomy.json")
    taxonomy = load(taxonomy_path, {})
    untracked = []
    for rel_path, record in sorted(on_disk.items()):
        folder = rel_path[len("dge/data/"):].rsplit("/data.json", 1)[0]
        if not taxonomy_has(taxonomy, folder):
            untracked.append((folder, record))

    orphans = sorted(set(on_disk) - set(by_path))
    missing = sorted(set(by_path) - set(on_disk))
    stale = [p for p in set(by_path) & set(on_disk)
             if bool(by_path[p].get("populated")) != (on_disk[p]["count"] > 0)]
    untitled = [p for p in set(by_path) & set(on_disk) if not by_path[p].get("title")]

    hidden_items = sum(on_disk[p]["count"] for p in orphans)
    hidden_bytes = sum(os.path.getsize(on_disk[p]["full"]) for p in orphans)

    lines = ["## library.json audit", ""]
    lines.append(f"- entries: {len(entries)} · data.json on disk: {len(on_disk)}")
    lines.append(f"- **orphans (invisible to the reader): {len(orphans)}** "
                 f"carrying **{hidden_items:,} items / {hidden_bytes / 1048576:.1f} MB**")
    lines.append(f"- missing (entry points at nothing): {len(missing)}")
    lines.append(f"- stale populated flags: {len(stale)}")
    lines.append(f"- entries with no title: {len(untitled)}")
    untracked_items = sum(r["count"] for _, r in untracked)
    lines.append(f"- **folders the taxonomy does not name: {len(untracked)}** "
                 f"holding **{untracked_items:,} items** (absent from the browse tree)")
    report = "\n".join(lines)
    print(report)

    if orphans:
        print("\nORPHANS")
        for path in orphans:
            print(f"  {on_disk[path]['count']:>7,} items  {path}")
    if missing:
        print("\nMISSING")
        for path in missing:
            print(f"          {path}")
    if stale:
        print("\nSTALE populated")
        for path in sorted(stale):
            print(f"  {by_path[path].get('populated')!s:>5} -> "
                  f"{on_disk[path]['count'] > 0!s:<5} {path}")

    if untracked:
        print("\nNOT IN TAXONOMY")
        for folder, record in sorted(untracked, key=lambda x: -x[1]["count"]):
            print(f"  {record['count']:>7,} items  {folder}")

    if args.summary_file:
        with open(args.summary_file, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")

    if not args.fix:
        if orphans or missing or stale or untitled:
            print("\nrun with --fix to repair")
        return 0

    for path in orphans:
        record = on_disk[path]
        entries.append({"path": path, "populated": record["count"] > 0,
                        "title": derive_title(record["full"], record["payload"], args.data)})
    for path in missing:
        entries.remove(by_path[path])
    for path in stale:
        by_path[path]["populated"] = on_disk[path]["count"] > 0
    for path in untitled:
        record = on_disk[path]
        by_path[path]["title"] = derive_title(record["full"], record["payload"], args.data)

    added_nodes = 0
    for folder, record in untracked:
        payload = record["payload"] if isinstance(record["payload"], dict) else {}
        if taxonomy_add(taxonomy, folder, payload.get("schema"),
                        payload.get("default_author")):
            added_nodes += 1
    if added_nodes:
        with open(taxonomy_path, "w", encoding="utf-8") as handle:
            json.dump(taxonomy, handle, ensure_ascii=False, indent=1)
            handle.write("\n")

    library["granthas"] = sorted(entries, key=lambda e: e["path"])
    with open(library_path, "w", encoding="utf-8") as handle:
        json.dump(library, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"\nfixed: library +{len(orphans)} added, -{len(missing)} removed, "
          f"{len(stale)} flags corrected, {len(untitled)} titles filled; "
          f"taxonomy +{added_nodes} nodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
