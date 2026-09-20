#!/usr/bin/env python3
"""
opaque_ids.py -- publish the text, never the shelf it sits on.

THE REQUIREMENT, corrected. An earlier pass here excluded whole trees from
publication. That was the wrong reading and it cost coverage for no gain.
The lead's actual rule:

    The NAME is not the problem. A chunk of text is fine. What must never
    appear publicly is the breadcrumb -- the folder hierarchy that reproduces
    the structure those copyrighted sites maintain. `later_acharyas/...` in a
    URL or a search result IS that structure. Instead: an ID, which resolves
    to the real path only for an admin, dynamically.

So the text publishes and stays searchable. The PATH is what gets withheld,
and a public artifact carries an opaque id in its place.

WHY A RANDOM ID AND NOT A HASH OF THE PATH.

A hash looks like it does the job and does not. Anyone who wants to invert it
already has the input dictionary: the source websites publish their own
structure, so their paths are enumerable. Hash every one of them, compare,
and the map is reconstructed in seconds. That is true of SHA-256, of a
truncated digest, and of anything else derived from the path alone. The only
construction that survives someone holding the source site's sitemap is an id
with NO relationship to the path: minted at random once and recorded.

That recording is `admin/config/opaque_ids.json`, which lives under `admin/`
and therefore never publishes (publish_clean_repo.EXCLUDE_DIRS). The public
side gets ids; the map stays here. An admin with a token loads the map, turns
an id back into a path, and fetches the data.json from the private repository
-- via jsDelivr as js/admin-remote.js already does, or from localhost.

WHAT AN ID LOOKS LIKE.  `q7m4k2px` -- 8 characters of Crockford base32, drawn
from os.urandom. 32^8 is 2^40, which is not a keyspace anyone brute-forces
into a 600-entry map, and it stays short enough to sit in a URL.

WHICH TREES. Only those whose hierarchy is someone else's. A work that has
been prepared and moved into data/Tattvavada/ is ours; it keeps its readable
path, because that path is Sarvamula's own structure and names nobody.

    python3 tools/opaque_ids.py --mint        # give every work an id
    python3 tools/opaque_ids.py --resolve q7m4k2px
    python3 tools/opaque_ids.py --check       # ids cover every work, no dupes
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Crockford base32 minus the letters it excludes for being confusable: I, L,
# O, U. An id gets read off a screen and typed back in more often than anyone
# plans for.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ID_LEN = 8

MAP_PATH = os.path.join("admin", "config", "opaque_ids.json")

# Trees whose folder hierarchy reproduces a source website's own. The text
# under them publishes; these paths do not.
STRUCTURE_PRIVATE = (
    "data/darshana/vedanta/dvaita/DvaitaVedantaIn",
    "data/darshana/vedanta/dvaita/Anandamakaranda",
    "data/darshana/vedanta/vishishtadvaita/RamanujaMeghamala",
)


def needs_id(rel_path: str) -> bool:
    """True if this path must not appear in anything published."""
    p = str(rel_path).replace(os.sep, "/")
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    return any(p == t or p.startswith(t + "/") for t in STRUCTURE_PRIVATE)


def needs_id_slug(slug: str) -> bool:
    """The same question about a library slug -- the path with `data/` gone,
    which is the form library.json, the sitemap and the search index carry."""
    return needs_id("data/" + str(slug).lstrip("/"))


def mint(n: int = ID_LEN) -> str:
    raw = os.urandom(n)
    return "".join(ALPHABET[b % len(ALPHABET)] for b in raw).lower()


def load(root: str = ".") -> dict:
    p = os.path.join(root, MAP_PATH)
    if not os.path.exists(p):
        return {"schema": "opaque_ids/1", "by_path": {}, "by_id": {}}
    return json.load(open(p, encoding="utf-8"))


def save(m: dict, root: str = ".") -> None:
    p = os.path.join(root, MAP_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def works(root: str = ".") -> list[str]:
    """Every directory holding a data.json inside a structure-private tree."""
    out = []
    for t in STRUCTURE_PRIVATE:
        for dirpath, _, files in os.walk(os.path.join(root, t)):
            if "data.json" in files:
                out.append(os.path.relpath(dirpath, root).replace(os.sep, "/"))
    return sorted(out)


def do_mint(root: str = ".") -> dict:
    """Give an id to every work that lacks one. Existing ids are NEVER
    reissued: an id that has been published is a link someone may hold, and
    reminting turns it into a 404 for no reason."""
    m = load(root)
    by_path, by_id = m["by_path"], m["by_id"]
    taken = set(by_id)
    added = 0
    for w in works(root):
        if w in by_path:
            continue
        while True:
            i = mint()
            if i not in taken:
                break
        taken.add(i)
        by_path[w] = i
        by_id[i] = w
        added += 1
    m["by_path"], m["by_id"] = by_path, by_id
    save(m, root)
    return {"added": added, "total": len(by_path)}


def check(root: str = ".") -> list[str]:
    m = load(root)
    by_path, by_id = m.get("by_path", {}), m.get("by_id", {})
    problems = []
    for w in works(root):
        if w not in by_path:
            problems.append("no id: %s" % w)
    for p, i in by_path.items():
        if by_id.get(i) != p:
            problems.append("map disagrees with itself at %s / %s" % (p, i))
    if len(set(by_path.values())) != len(by_path):
        problems.append("two paths share an id")
    for p in by_path:
        if not needs_id(p):
            problems.append("id issued to a path that does not need one: %s" % p)
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--root", default=".")
    ap.add_argument("--mint", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--resolve", default="", help="an id, or a path, to look up")
    args = ap.parse_args(argv)

    if args.mint:
        r = do_mint(args.root)
        print("minted %d new id(s); %d work(s) now addressable by id" % (r["added"], r["total"]))
        print("map: %s  (under admin/, so it never publishes)" % MAP_PATH)
        return 0

    if args.resolve:
        m = load(args.root)
        key = args.resolve.strip()
        if key in m["by_id"]:
            print(m["by_id"][key])
        elif key in m["by_path"]:
            print(m["by_path"][key])
        else:
            print("not found: %s" % key, file=sys.stderr)
            return 1
        return 0

    problems = check(args.root)
    m = load(args.root)
    print("%d work(s) inside a structure-private tree, %d with an id"
          % (len(works(args.root)), len(m.get("by_path", {}))))
    for t in STRUCTURE_PRIVATE:
        print("    %s" % t)
    if problems:
        print("\n%d problem(s):" % len(problems))
        for p in problems[:20]:
            print("    %s" % p)
        return 1
    print("\nmap is consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
