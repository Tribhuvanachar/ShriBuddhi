#!/usr/bin/env python3
"""
check_sidecars.py -- find enrichment sidecars whose work has moved.

Every enrichment layer is stored beside the corpus, not inside it, in a file
named after the grantha's path: `data/_references/<path with / as __>.json`.
The reader resolves it at read time (`dgeGranthaSlug` in js/core.js). So when a
work is moved on disk, its sidecar keeps the OLD name, the fetch 404s, and the
feature turns itself off. Silently. No error anywhere: the page just renders
without citations, or without padaccheda, and looks fine.

That is how the project arrived at 0% live coverage for citation references and
commentary sandhi while holding thousands of units of perfectly good data --
two corpus restructures, and nothing that noticed.

    python3 tools/check_sidecars.py            # report, exit 1 if any orphan
    python3 tools/check_sidecars.py --fix      # rename, only where SAFE

SAFE means: exactly one live grantha matches, and every unit id in the sidecar
is also a unit id in that grantha. A rename that cannot prove it landed on the
same text is not performed -- the point of the check is to stop enrichment
drifting away from the text it describes, and a confident wrong rename does
that faster than the drift did.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

# Sidecar directories keyed by grantha slug, each holding <slug>.json, and how
# a stale one should be dealt with.
#
#   "authored"  -- expensive or hand-checked output that nothing regenerates.
#                  A stale one must be RENAMED or the work in it is lost.
#   "generated" -- an index a workflow rebuilds from the corpus. A stale one
#                  must be PRUNED, not renamed: the rebuild has already written
#                  the correct file under the new name, and the old one is a
#                  leftover, because the builders only ever add.
SIDECAR_DIRS = {
    "data/_references": "authored",
    "data/_commentary_sandhi": "authored",
    "data/_padaccheda": "authored",
    "data/vedanga/chandas/reports/granthas": "generated",
    "data/vedanga/vyakarana/dhatu_prayoga/by_grantha": "generated",
}
# Files in those directories that are not per-grantha sidecars.
NOT_SIDECARS = {"manifest", "index", "by_vrutta"}


def library_slugs(root="."):
    lib = json.load(open(os.path.join(root, "data/library.json")))
    out = {}
    for g in lib["granthas"]:
        p = g["path"]
        if p.startswith("data/") and p.endswith("/data.json"):
            out[p[len("data/"):-len("/data.json")].replace("/", "__")] = p
    return out


def unit_ids(path):
    """Unit ids of a grantha, across the shapes the corpus actually uses."""
    try:
        d = json.load(open(path))
    except Exception:  # noqa: BLE001
        return set()
    for key in ("items", "units", "data"):
        v = d.get(key)
        if isinstance(v, list):
            return {str(i.get("id")) for i in v if isinstance(i, dict)}
    sh = d.get("shlokas")
    if isinstance(sh, dict):
        return set(map(str, sh))
    if isinstance(sh, list):
        return {str(i.get("id") or i.get("number")) for i in sh if isinstance(i, dict)}
    return set()


def declared_slug(path):
    """The slug the sidecar says it is for, if it says.

    Worth more than anything guessed from the filename: the builders were
    updated to the new corpus paths and kept writing the right value inside
    the file while the filename stayed wrong. For the DvaitaVedanta split --
    where one old shelf became two, Anandamakaranda and DvaitaVedantaIn --
    this is the only thing that can tell which of the two a file belongs to.
    """
    try:
        s = json.load(open(path))
    except Exception:  # noqa: BLE001
        return None
    v = s.get("slug")
    return v.replace("/", "__") if isinstance(v, str) else None


def sidecar_units(path):
    try:
        s = json.load(open(path))
    except Exception:  # noqa: BLE001
        return set()
    u = s.get("units")
    if isinstance(u, dict):
        return set(u)
    if isinstance(u, list):
        return {str(x.get("id")) for x in u if isinstance(x, dict)}
    # dhatu_prayoga/by_grantha writes no wrapper at all: the whole object is
    # unit id -> list of occurrences. Recognise that by its shape rather than
    # by filename, so one more layout does not need one more special case.
    if isinstance(s, dict) and s and all(isinstance(v, list) for v in s.values()):
        return set(s)
    return set()


def norm(s):
    """Fold the spelling differences a restructure introduces.

    Works have been moved AND renamed in the same commit -- PrahladaKrutaNarasimha
    became prahlada_kruta_narasimha -- so comparing raw segments misses them.
    """
    return re.sub(r"[^a-z0-9]", "", s.lower())


def candidates(old_slug, slugs):
    """Live slugs whose trailing segments match this one's, most specific first."""
    parts = old_slug.split("__")
    for depth in (3, 2, 1):
        if len(parts) < depth:
            continue
        tail = norm("".join(parts[-depth:]))
        hits = [s for s in slugs if norm("".join(s.split("__")[-depth:])) == tail]
        if hits:
            return hits, depth
    return [], 0


def scan(root="."):
    slugs = library_slugs(root)
    orphans = []
    for d, kind in SIDECAR_DIRS.items():
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        for f in sorted(glob.glob(os.path.join(full, "*.json"))):
            slug = os.path.basename(f)[:-5]
            if slug in NOT_SIDECARS or slug in slugs:
                continue
            # The file's own declared slug beats any guess from its name.
            decl = declared_slug(f)
            if decl and decl in slugs:
                orphans.append({"dir": d, "kind": kind, "slug": slug, "file": f,
                                "target": decl,
                                "verdict": "safe: the file declares slug %s" % decl})
                continue
            cand, depth = candidates(slug, slugs)
            verdict, target = "no live grantha matches this name", None
            if len(cand) > 1:
                verdict = "%d live granthas match -- ambiguous" % len(cand)
            elif len(cand) == 1:
                target = cand[0]
                su, lu = sidecar_units(f), unit_ids(os.path.join(root, slugs[target]))
                if not su:
                    verdict = "safe (no unit ids to check)" if lu else "target has no units"
                elif su <= lu:
                    verdict = "safe: %d/%d units match" % (len(su), len(su))
                else:
                    verdict = "UNSAFE: only %d/%d units match" % (len(su & lu), len(su))
                    target = None
            if kind == "generated" and target is None:
                verdict = "stale generated index and unresolvable -- rebuild"
            orphans.append({"dir": d, "kind": kind, "slug": slug, "file": f,
                            "target": target, "verdict": verdict})
    return orphans


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--fix", action="store_true", help="rename the safe ones (git mv)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    orphans = scan(args.root)
    if not orphans:
        if not args.quiet:
            print("every enrichment sidecar names a live grantha.")
        return 0

    safe = [o for o in orphans if o["target"]]
    stale_generated = [o for o in orphans if o["kind"] == "generated"]
    stuck = [o for o in orphans if not o["target"] and o["kind"] == "authored"]
    by_dir = {}
    for o in orphans:
        by_dir.setdefault(o["dir"], []).append(o)

    print("%d orphaned sidecar(s): the work moved, the file did not." % len(orphans))
    for d, rows in sorted(by_dir.items()):
        print("  %-48s %d" % (d, len(rows)))
    if stale_generated:
        print("\n%d are stale GENERATED indexes. Do not rename them -- re-run the"
              % len(stale_generated))
        print("builder and delete what it no longer writes (the builders only add):")
        for d in sorted({o["dir"] for o in stale_generated}):
            print("  %s" % d)
    if stuck:
        print("\nneeding a human (%d authored sidecar(s)):" % len(stuck))
        for o in stuck:
            print("  %-56s %s" % (o["slug"][:56], o["verdict"]))

    if not args.fix:
        if safe:
            print("\n%d sidecar(s) can be renamed safely -- run with --fix." % len(safe))
        # Only an ORPHANED AUTHORED sidecar fails the build. It means work that
        # nothing regenerates has been cut loose from its text, which is the
        # regression this check exists to stop. A stale generated index is a
        # leftover: it costs coverage until the next rebuild, but no data is at
        # risk, and failing CI for it would only teach people to ignore a red
        # build -- which is how the authored ones went unnoticed for two
        # restructures.
        return 1 if (safe or stuck) and any(
            o["kind"] == "authored" for o in orphans) else 0

    for o in safe:
        dest = os.path.join(os.path.dirname(o["file"]), o["target"] + ".json")
        if os.path.exists(dest):
            print("  skip %s -- %s already exists" % (o["slug"], o["target"]))
            continue
        if subprocess.call(["git", "mv", o["file"], dest], cwd=args.root) != 0:
            os.rename(o["file"], dest)
        print("  %s\n    -> %s" % (o["slug"], o["target"]))
    print("\nrenamed %d; %d still need a human." % (len(safe), len(stuck)))
    return 1 if any(o["kind"] == "authored" for o in stuck) else 0


if __name__ == "__main__":
    raise SystemExit(main())
