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
    for key in ("items", "shlokas", "compositions", "entries", "units"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
    return 0


FACET_KEYS = ("genre", "guna_classification", "ratnatraya", "madhvacharya_relevance", "text_status",
              "purana_class", "traditional_lists", "default_author")


def derive_source(payload):
    """Lightweight provenance for the admin tracker's "sources" column --
    copied into library.json alongside facets, same reasoning: read once
    here rather than have the browser fetch every leaf's full data.json
    just to show where its text came from."""
    if not isinstance(payload, dict):
        return None
    source = {}
    for key in ("source", "source_url", "licence", "license"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            source["licence" if key == "license" else key] = value.strip()
    return source or None


def derive_facets(payload):
    """View-By facet metadata (see dge/PENDING.md's 25 Aug Pancharatra pass) --
    copied into library.json so the reader can build facet groupings from the
    already-fetched catalog instead of downloading every leaf's full data.json
    (some Pancharatra samhitas run tens of thousands of lines) just to read a
    handful of classification fields. None -> no 'facets' key at all, so a
    leaf that doesn't declare any of this stays exactly as small as before."""
    if not isinstance(payload, dict):
        return None
    facets = {k: payload[k] for k in FACET_KEYS if k in payload}
    return facets or None


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
        if isinstance(payload, dict) and payload.get("schema") == "grantha_layer_v2":
            # v2 architecture layers (grantha_data_architecture.md) are
            # deliberately outside library.json until the reader's v2 path
            # ships — never auto-registered by --fix, never counted orphans
            continue
        if isinstance(payload, dict) and payload.get("schema") == "vyakarana_corpus_v1":
            # sutra-corpora consumed by their own dge/vyakarana/*.html pages
            # (phitsutra/ganapatha/linganushasana/unadi), not by the reader —
            # same standing exclusion as grantha_layer_v2
            continue
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
    facet_diffs = [p for p in set(by_path) & set(on_disk)
                   if by_path[p].get("facets") != derive_facets(on_disk[p]["payload"])]
    source_diffs = [p for p in set(by_path) & set(on_disk)
                     if by_path[p].get("source") != derive_source(on_disk[p]["payload"])]

    hidden_items = sum(on_disk[p]["count"] for p in orphans)
    hidden_bytes = sum(os.path.getsize(on_disk[p]["full"]) for p in orphans)

    lines = ["## library.json audit", ""]
    lines.append(f"- entries: {len(entries)} · data.json on disk: {len(on_disk)}")
    lines.append(f"- **orphans (invisible to the reader): {len(orphans)}** "
                 f"carrying **{hidden_items:,} items / {hidden_bytes / 1048576:.1f} MB**")
    lines.append(f"- missing (entry points at nothing): {len(missing)}")
    lines.append(f"- stale populated flags: {len(stale)}")
    lines.append(f"- entries with no title: {len(untitled)}")
    lines.append(f"- facet metadata out of sync: {len(facet_diffs)}")
    lines.append(f"- source metadata out of sync: {len(source_diffs)}")
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

    if facet_diffs:
        print("\nFACET METADATA OUT OF SYNC")
        for path in sorted(facet_diffs):
            print(f"          {path}")
    if source_diffs:
        print(f"\nSOURCE METADATA OUT OF SYNC ({len(source_diffs)}, not listed individually)")
    if untracked:
        print("\nNOT IN TAXONOMY")
        for folder, record in sorted(untracked, key=lambda x: -x[1]["count"]):
            print(f"  {record['count']:>7,} items  {folder}")

    if args.summary_file:
        with open(args.summary_file, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")

    if not args.fix:
        if orphans or missing or stale or untitled or facet_diffs or source_diffs:
            print("\nrun with --fix to repair")
        return 0

    for path in orphans:
        record = on_disk[path]
        entry = {"path": path, "populated": record["count"] > 0,
                 "title": derive_title(record["full"], record["payload"], args.data)}
        facets = derive_facets(record["payload"])
        if facets:
            entry["facets"] = facets
        source = derive_source(record["payload"])
        if source:
            entry["source"] = source
        entries.append(entry)
    for path in missing:
        entries.remove(by_path[path])
    for path in stale:
        by_path[path]["populated"] = on_disk[path]["count"] > 0
    for path in untitled:
        record = on_disk[path]
        by_path[path]["title"] = derive_title(record["full"], record["payload"], args.data)
    for path in facet_diffs:
        facets = derive_facets(on_disk[path]["payload"])
        if facets:
            by_path[path]["facets"] = facets
        else:
            by_path[path].pop("facets", None)
    for path in source_diffs:
        source = derive_source(on_disk[path]["payload"])
        if source:
            by_path[path]["source"] = source
        else:
            by_path[path].pop("source", None)

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
          f"{len(stale)} flags corrected, {len(untitled)} titles filled, "
          f"{len(facet_diffs)} facets synced, {len(source_diffs)} sources synced; "
          f"taxonomy +{added_nodes} nodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
