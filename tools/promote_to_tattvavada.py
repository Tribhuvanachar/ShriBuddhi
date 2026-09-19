#!/usr/bin/env python3
"""
promote_to_tattvavada.py -- the one sanctioned way a private work goes public.

THE RULE (the lead, 19 Sep 2026):

    DvaitaVedantaIn and Anandamakaranda sit only in ShriBuddhi. If a work has
    to go out, it goes as modified prepared content into data/Tattvavada/ --
    and nowhere else.

So publication is a MOVE, not a flag. There is no setting that makes a work
under those directories public where it stands, because the directory name
is the problem: a URL containing `DvaitaVedantaIn` names dvaitavedanta.in to
every reader and every crawler before the page even loads. Renaming it for
display does not help -- js/library.js already shows Anandamakaranda as
सर्वमूलग्रन्थाः while the URL underneath goes on saying Anandamakaranda.

WHAT MOVES WITH THE WORK.

  * the directory itself, git-mv'd so the history follows it
  * its library.json entry, repathed
  * its sidecars, which are keyed by grantha path with `/` written `__`
  * its layer_manifest.json entry, if it has one

WHAT DOES NOT MOVE. Nothing is stripped from the data.json, because there is
nothing in it to strip: these files carry no `source`, `source_url` or
`work_id` field (verify_no_private_provenance.py reads 194,706 files and
finds none). "Modified prepared content" means the text has been proofread
and the path no longer names anyone else's website. It does not mean a
scrubbing step this tool could perform -- if provenance fields ever do
appear, that checker fails the build and this comment is wrong.

WHAT IT DOES NOT DO. It does not decide that a work is ready. A work is
promoted when the lead says its proofreading is done, one at a time. This
refuses to run on a tree, only on a single work, for exactly that reason.

    python3 tools/promote_to_tattvavada.py \\
        --work data/darshana/vedanta/dvaita/Anandamakaranda/dvadasha_stotra \\
        --into Itara/Stotra --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unpublished_trees import PRIVATE_TREES, is_unpublished

DEST_ROOT = "data/Tattvavada"
SIDECAR_DIRS = ("admin/sidecars", "data/_morph", "data/_highlight", "data/_synonyms")


def slug(path: str) -> str:
    """The library slug for a work directory: the path with `data/` removed."""
    p = path.replace(os.sep, "/").strip("/")
    return p[len("data/"):] if p.startswith("data/") else p


def sidecar_key(s: str) -> str:
    return s.replace("/", "__")


def plan(work: str, into: str, root: str = ".") -> dict:
    """Everything the move touches, worked out before anything is written."""
    work = work.replace(os.sep, "/").strip("/")
    if not is_unpublished(work):
        raise SystemExit("%s is not inside a tree that stays private:\n  %s"
                         % (work, "\n  ".join(PRIVATE_TREES)))
    if not os.path.isdir(os.path.join(root, work)):
        raise SystemExit("no such directory: %s" % work)
    # A work has a data.json at or just under it. A whole shelf does not, and
    # promoting a shelf in one go is the thing this tool exists to prevent.
    depth = sum(1 for _, _, fs in os.walk(os.path.join(root, work)) if "data.json" in fs)
    if depth == 0:
        raise SystemExit("%s holds no data.json -- nothing to promote" % work)

    name = work.rsplit("/", 1)[-1]
    dest = "/".join([DEST_ROOT, into.strip("/"), name]) if into.strip("/") else \
           "/".join([DEST_ROOT, name])
    if os.path.exists(os.path.join(root, dest)):
        raise SystemExit("destination already exists: %s" % dest)

    old_slug, new_slug = slug(work), slug(dest)
    sidecars = []
    for d in SIDECAR_DIRS:
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        for f in sorted(os.listdir(full)):
            if f.startswith(sidecar_key(old_slug)):
                sidecars.append((os.path.join(d, f),
                                 os.path.join(d, sidecar_key(new_slug) +
                                              f[len(sidecar_key(old_slug)):])))

    lib_path = os.path.join(root, "data", "library.json")
    entries = []
    if os.path.exists(lib_path):
        lib = json.load(open(lib_path, encoding="utf-8"))
        for g in lib.get("granthas", []):
            gp = str(g.get("path", ""))
            if slug(gp) == old_slug or slug(gp).startswith(old_slug + "/"):
                entries.append(gp)

    return {"work": work, "dest": dest, "old_slug": old_slug, "new_slug": new_slug,
            "works": depth, "sidecars": sidecars, "library_entries": entries}


def apply(p: dict, root: str = ".") -> None:
    src, dst = os.path.join(root, p["work"]), os.path.join(root, p["dest"])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # git mv so the history follows the text. Falls back to a plain move when
    # the tree is not a checkout, which is only ever the case in tests.
    try:
        subprocess.run(["git", "mv", p["work"], p["dest"]], cwd=root,
                       check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        shutil.move(src, dst)

    for old, new in p["sidecars"]:
        os.makedirs(os.path.dirname(os.path.join(root, new)), exist_ok=True)
        shutil.move(os.path.join(root, old), os.path.join(root, new))

    lib_path = os.path.join(root, "data", "library.json")
    if p["library_entries"] and os.path.exists(lib_path):
        text = open(lib_path, encoding="utf-8").read()
        lib = json.loads(text)
        for g in lib.get("granthas", []):
            gp = str(g.get("path", ""))
            s = slug(gp)
            if s == p["old_slug"] or s.startswith(p["old_slug"] + "/"):
                g["path"] = gp.replace(p["old_slug"], p["new_slug"], 1)
        json.dump(lib, open(lib_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        open(lib_path, "a", encoding="utf-8").write("\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--work", required=True, help="the work directory to promote")
    ap.add_argument("--into", default="", help="shelf under data/Tattvavada, e.g. Itara/Stotra")
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    p = plan(args.work, args.into, args.root)
    print("promote   %s" % p["work"])
    print("      ->  %s" % p["dest"])
    print("          %d data.json, %d sidecar(s), %d library.json entr(ies)"
          % (p["works"], len(p["sidecars"]), len(p["library_entries"])))
    for old, new in p["sidecars"][:10]:
        print("          sidecar %s -> %s" % (old, new))
    if len(p["sidecars"]) > 10:
        print("          ... and %d more" % (len(p["sidecars"]) - 10))

    if args.dry_run:
        print("\ndry run -- nothing written.")
        return 0

    apply(p, args.root)
    print("\nmoved. Now regenerate what indexes it, or the indexes will go on"
          "\nnaming the old path:")
    print("    python3 tools/build_sitemap.py")
    print("    python3 tools/build_layer_manifest.py")
    print("    python3 tools/build_search_index.py --data data --out search_index")
    print("    python3 tools/publish_clean_repo.py --source . --scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
