#!/usr/bin/env python3
"""
unpublished_trees.py -- the corpus that stays in the private repository.

THE RULE, as the lead set it on 19 Sep 2026:

    Some works sit only in ShriBuddhi. If such a work is ever to go public
    it goes as modified, prepared content into data/Tattvavada/ -- and
    nowhere else. It is never published from where it sits now.

The reason is the folder name, not the text. `DvaitaVedantaIn` is
dvaitavedanta.in and `Anandamakaranda` is anandamakaranda.com. Publishing a
directory called DvaitaVedantaIn tells every reader, and every crawler,
which website the text was taken from -- from the URL alone, before anyone
opens the page. The Sanskrit inside is not the problem; the path is.

WHY A HARD EXCLUDE AND NOT `hidden`.

admin/config/library-overrides.json already has a `hidden` list, and it is
the obvious place to reach for. It is the wrong one. js/library.js says so
itself: "A NON-DESTRUCTIVE display layer only". Hiding a slug removes it
from the shelf and from search; the data.json still ships, the URL still
resolves, and anyone who guesses the path -- or reads an old sitemap, or
holds a copy of one -- fetches it. On top of that the overrides file lives
under admin/, which publish_clean_repo.py excludes, so the published site
never even receives the hide list. `hidden` is curation. This is exclusion.

WHAT THIS MODULE IS FOR.

One list, read by everything that writes a published artifact, so that the
site, the sitemap, library.json, the layer manifest and the search index
cannot disagree about what is public. When they disagree the result is the
worst of both: the files stop shipping and the sitemap goes on naming them,
which is a dead link that still leaks the source.

    from unpublished_trees import is_unpublished
    if is_unpublished(rel_path):    # "data/darshana/.../mula/data.json"
        continue

PROMOTING A WORK.

Publication is a MOVE, not a flag. When a work has been proofread and
prepared it is relocated into data/Tattvavada/, its unit ids and any
sidecars follow it, and it publishes from there under a path that names
Sarvamula and no one else. tools/promote_to_tattvavada.py does the move.
Nothing here flips a work public in place, because there is no path under
these directories that is safe to serve.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ONE list, and it lives in opaque_ids.py because that is where the ids are
# minted. Two lists that must agree is one list and a bug waiting.
#
# 20 Sep 2026: these trees changed meaning. They were "does not publish at
# all". They are now "publishes its TEXT, never its PATH" -- the lead's
# actual requirement, which an earlier pass here read too broadly. The files
# still do not ship, because a path is what a file needs to be fetched by and
# these works have no public path. What ships is the text, inside the search
# index and the attestation indexes, addressed by an opaque id.
from opaque_ids import STRUCTURE_PRIVATE as PRIVATE_TREES   # noqa: E402

# Nothing is undecided any more: RamanujaMeghamala was the open question and
# the ids answered it. Under an exclusion it would have meant retiring 175
# live URLs; under ids those works stay published and searchable and only
# their shelf changes.
UNDECIDED_TREES = ()


def _norm(rel_path: str) -> str:
    """A repo-relative POSIX path, with no leading ./ or /."""
    p = str(rel_path).replace(os.sep, "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def is_unpublished(rel_path: str, trees=PRIVATE_TREES) -> bool:
    """True if this repo-relative path is inside a tree that does not publish.

    Prefix matching is on whole path segments. "data/x/Foo" must not swallow
    "data/x/Foobar", which is a different work that has nothing to do with it.
    """
    p = _norm(rel_path)
    return any(p == t or p.startswith(t + "/") for t in trees)


def excludes_slug(slug: str, trees=PRIVATE_TREES) -> bool:
    """Same question asked about a library slug -- the path with `data/`
    already stripped, which is the form library.json, the sitemap and the
    search index all carry."""
    return is_unpublished("data/" + str(slug).lstrip("/"), trees)


def scan_tree(root: str = ".") -> dict:
    """What is on disk under each listed tree, for the report."""
    out = {}
    for label, trees in (("private", PRIVATE_TREES), ("undecided", UNDECIDED_TREES)):
        for t in trees:
            full = os.path.join(root, t)
            n = 0
            for _, _, files in os.walk(full):
                n += sum(1 for f in files if f == "data.json")
            out[t] = {"status": label, "exists": os.path.isdir(full), "works": n}
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="report the trees that do not publish")
    ap.add_argument("--root", default=".", help="repository root")
    args = ap.parse_args(argv)

    found = scan_tree(args.root)
    for t, info in found.items():
        print("%-10s %-58s %s" % (
            info["status"], t,
            "%d work(s)" % info["works"] if info["exists"] else "not on disk"))

    undecided = [t for t, i in found.items() if i["status"] == "undecided" and i["exists"]]
    if undecided:
        print("\n%d tree(s) are named after a source website but have not been"
              " classified.\nThey publish today. Decide each one:" % len(undecided))
        for t in undecided:
            print("    %s" % t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
