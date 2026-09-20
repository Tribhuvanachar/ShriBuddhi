#!/usr/bin/env python3
"""
publish_opaque_rewrite.py -- swap breadcrumbs for ids as the site is staged.

THE PROBLEM THIS SOLVES. 1,713 published files name a structure-private tree.
Almost all of them are the dhatu and chandas attestation indexes, which cite
those works as sources of verb forms and metres, and they do it by SLUG:

    "darshana/vedanta/dvaita/DvaitaVedantaIn/dasha_prakarana_granthas/..."

That slug is dvaitavedanta.in's own shelf, reproduced. The text beside it is
fine to publish and useful to search; the shelf is the thing that must never
appear. So the slug is replaced by the work's opaque id and everything else
is left exactly as it was:

    "id:q7m4k2px"

WHY AT PUBLISH TIME AND NOT IN THE GENERATORS. Ten or more tools write these
indexes and each walks `data/` its own way. Teaching every one of them the
rule means ten chances to miss it and ten places for it to rot -- and it
would also strip the real paths out of ShriBuddhi, where the team needs them
to do any work at all. So the private repository keeps its readable paths
and the transform runs once, over the staged copy, on the way out.

That also makes the rule checkable in one place: after this runs, no
published file may contain any of those directory names, and
publish_clean_repo refuses the build if one does.

WHAT IT EMITS. `data/display.json`, the published half of the display layer:
an id, a title a reader may see, and the shelf it belongs on. Never a path.
The id-to-path map stays in admin/, which does not publish.

    python3 tools/publish_opaque_rewrite.py --staged /tmp/site --report
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opaque_ids import (MAP_PATH, STRUCTURE_PRIVATE, load as load_ids,  # noqa: E402
                        needs_id)

TEXT_SUFFIXES = (".json", ".xml", ".js", ".html", ".css", ".txt", ".md")
ID_PREFIX = "id:"


def slug_of(tree: str) -> str:
    return tree[len("data/"):] if tree.startswith("data/") else tree


def build_map(root: str) -> dict:
    """{slug -> id} for every work with an id, longest slug first.

    Longest first matters: a work and its parent shelf are both in the map,
    and replacing the parent first would leave the child's tail dangling
    behind an id -- `id:q7m4k2px/mula`, which still shows a shelf.
    """
    ids = load_ids(root)["by_path"]
    pairs = {slug_of(p): i for p, i in ids.items()}
    # The tree roots themselves, so a bare shelf reference is covered too.
    for t in STRUCTURE_PRIVATE:
        pairs.setdefault(slug_of(t), "tree" + str(abs(hash(t)) % 10 ** 6))
    return dict(sorted(pairs.items(), key=lambda kv: -len(kv[0])))


def prune_taxonomy(path: str) -> int:
    """taxonomy.json nests the shelf as OBJECT KEYS, not as a slug:

        "DvaitaVedantaIn": {"dasha_prakarana_granthas": {"karma_nirnaya": ...

    Replacing the key would leave the whole subtree under it standing, which
    is the shelf itself -- every level of it. There is nothing to rewrite
    here: these works have no browsable path, so they have no place in a
    taxonomy whose only job is to be browsed. The subtree is removed.
    """
    doc = json.load(open(path, encoding="utf-8"))
    names = {t.rsplit("/", 1)[-1] for t in STRUCTURE_PRIVATE}
    removed = 0

    def walk(node):
        nonlocal removed
        if not isinstance(node, dict):
            return
        for k in [k for k in node if k in names]:
            del node[k]
            removed += 1
        for v in node.values():
            walk(v)

    walk(doc)
    if removed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
    return removed


def rename_shards(staged: str, mapping: dict) -> int:
    """Search-index shards are NAMED after the slug, with `/` written `__`:

        units/darshana__vedanta__dvaita__Anandamakaranda__..__mula.json

    The filename is a URL the browser requests, so it is as public as any
    other and carries the whole shelf in it. Renaming the file is the only
    fix; rewriting the manifest that points at it without moving it would
    just 404 every one of them.
    """
    flat = {k.replace("/", "__"): v for k, v in mapping.items()}
    flat = dict(sorted(flat.items(), key=lambda kv: -len(kv[0])))
    moved = 0
    for dirpath, _, files in os.walk(staged):
        for name in files:
            new = name
            for slug, oid in flat.items():
                if slug in new:
                    new = new.replace(slug, ID_PREFIX.replace(":", "_") + oid)
                    break
            if new != name:
                os.rename(os.path.join(dirpath, name), os.path.join(dirpath, new))
                moved += 1
    return moved


def rewrite_text(text: str, mapping: dict) -> tuple[str, int]:
    n = 0
    for slug, oid in mapping.items():
        if slug in text:
            n += text.count(slug)
            text = text.replace(slug, ID_PREFIX + oid)
        # The same slug with `/` written `__`, which is how shard filenames
        # and sidecar keys spell it. Rewritten to match rename_shards, or the
        # manifest points at files that are no longer there.
        flat = slug.replace("/", "__")
        if flat != slug and flat in text:
            n += text.count(flat)
            text = text.replace(flat, ID_PREFIX.replace(":", "_") + oid)
    return text, n


def display_entry(slug: str, oid: str, titles: dict) -> dict:
    """What a reader may be told about a work with no public path.

    The title is the work's own, which names a text and not a website. The
    shelf is the last readable step of OUR taxonomy above the private tree --
    `dvaita`, `vishishtadvaita` -- so a result can be grouped sensibly
    without reproducing anything below it.
    """
    parts = slug.split("/")
    shelf = ""
    for t in STRUCTURE_PRIVATE:
        ts = slug_of(t)
        if slug == ts or slug.startswith(ts + "/"):
            shelf = ts.rsplit("/", 2)[-2] if ts.count("/") >= 2 else ts
            break
    return {"title": titles.get(slug) or parts[-1].replace("_", " "),
            "shelf": shelf, "public_path": None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--staged", required=True, help="the staged tree to rewrite in place")
    ap.add_argument("--root", default=".", help="the private checkout holding the id map")
    ap.add_argument("--report", action="store_true", help="count and stop, change nothing")
    args = ap.parse_args(argv)

    mapping = build_map(args.root)
    print("%d slug(s) map to an opaque id" % len(mapping))

    titles = {}
    lib = os.path.join(args.root, "data", "library.json")
    if os.path.exists(lib):
        for g in json.load(open(lib, encoding="utf-8")).get("granthas", []):
            p = str(g.get("path", ""))
            s = p[len("data/"):-len("/data.json")] if p.startswith("data/") and p.endswith("/data.json") else ""
            if s and g.get("title"):
                titles[s] = g["title"]

    if not args.report:
        tax = os.path.join(args.staged, "data", "taxonomy.json")
        if os.path.exists(tax):
            print("taxonomy.json: removed %d private subtree(s)" % prune_taxonomy(tax))
        print("renamed %d shard file(s) whose NAME carried a slug"
              % rename_shards(args.staged, mapping))

    touched = hits = 0
    for dirpath, _, files in os.walk(args.staged):
        for name in files:
            if not name.endswith(TEXT_SUFFIXES):
                continue
            full = os.path.join(dirpath, name)
            try:
                text = open(full, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            new, n = rewrite_text(text, mapping)
            if not n:
                continue
            hits += n
            touched += 1
            if not args.report:
                open(full, "w", encoding="utf-8").write(new)

    print("%d file(s) carried a private slug, %d occurrence(s)" % (touched, hits))

    if args.report:
        print("\nreport only -- nothing written.")
        return 0

    display = {"schema": "display/1",
               "_readme": ("Titles for works that have no public path. The id is "
                           "all a reader gets; the path it resolves to lives in "
                           "admin/config/opaque_ids.json, which does not publish."),
               "works": {}}
    for slug, oid in mapping.items():
        if oid.startswith("tree"):
            continue
        display["works"][ID_PREFIX + oid] = display_entry(slug, oid, titles)
    out = os.path.join(args.staged, "data", "display.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(display, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print("wrote data/display.json -- %d work(s) addressable by id"
          % len(display["works"]))

    # The map itself must not be anywhere in what ships, under any name.
    #
    # This is not hypothetical. The published site needs several files that
    # live in admin/config/ -- home.json, menu.json, seo.json and the rest --
    # and the obvious way to get them there is to copy admin/config/*.json to
    # the site's config/. That copies opaque_ids.json with them, and every id
    # on the site resolves to its real path for anybody who fetches it. The
    # allowlist for that copy is LEGACY_PUBLIC_CONFIG in js/admin-remote.js;
    # this is the backstop for the day someone does not use it.
    stray = []
    for dirpath, _, files in os.walk(args.staged):
        for name in files:
            if name == os.path.basename(MAP_PATH):
                stray.append(os.path.relpath(os.path.join(dirpath, name), args.staged))
            elif name.endswith(".json"):
                full = os.path.join(dirpath, name)
                try:
                    head = open(full, encoding="utf-8").read(4096)
                except (OSError, UnicodeDecodeError):
                    continue
                if '"by_id"' in head and '"by_path"' in head:
                    stray.append(os.path.relpath(full, args.staged) + " (looks like the id map)")
    if stray:
        print("\nSTOP. the id-to-path map is in the staged tree:")
        for f in stray[:10]:
            print("    %s" % f)
        print("  Every opaque id on the site resolves to its real path for anyone"
              "\n  who fetches this. Nothing else about the scheme matters if it ships.")
        return 1

    left = []
    names = [t.rsplit("/", 1)[-1] for t in STRUCTURE_PRIVATE]
    for dirpath, _, files in os.walk(args.staged):
        for name in files:
            if not name.endswith(TEXT_SUFFIXES):
                continue
            full = os.path.join(dirpath, name)
            try:
                text = open(full, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            if any(n in text for n in names):
                left.append(os.path.relpath(full, args.staged))
    if left:
        print("\nSTOP. %d file(s) still name a private tree after the rewrite:" % len(left))
        for f in left[:20]:
            print("    %s" % f)
        return 1
    print("no published file names a private tree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
