#!/usr/bin/env python3
"""Replace an origin site's record ids with DGE-native ones, everywhere.

WHY. Unit ids like DV_14063 are dvaitavedanta.in's OWN record numbers,
carried in from the import and then used by us as if they were ours --
in data.json, in search_index/units ("u":"DV_14063"), and in 1,670
cross-reference files under data/vedanga that point AT those units. The
project lead's instruction (14 Sep 2026) is that no label or tag of an
external site may remain anywhere in our tree, public or private, so that
no one can say we copied their identifiers. They may stay in Parabuddhi,
which is where the mapping back to them belongs.

THE ONE DESIGN DECISION THAT MATTERS. The new id is derived from the OLD
ID ALONE -- sha256(old)[:12] -- and never from the file it happens to sit
in. A reference in data/vedanga/.../reports.json pointing at DV_14063
must land on exactly the same new id as the unit's own record in
data/darshana/..., and those two files know nothing about each other. Key
the hash on (slug, id) and every cross-reference in the corpus silently
breaks while each file still looks internally consistent.

Deterministic, so re-running gives the same answer, and a rebuilt index
agrees with data that was renumbered months earlier.

    python3 tools/renumber_origin_ids.py --dry-run
    python3 tools/renumber_origin_ids.py --map-out /home/user/parabuddhi/id_map.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

# Prefixes that are an external site's numbering, not our own semantics.
# 'adhyaya', 'sarga', 'section', 'verse', 'unit' are ours and stay.
ORIGIN = re.compile(r"\b(DV|KCM)_(\d+)\b")

TEXT_EXT = {".json", ".js", ".py", ".md", ".html", ".yml", ".yaml", ".txt", ".xml"}

# The detector has to NAME the format it hunts for, and its test has to hand
# it a string in that shape. Renumbering those is not a scrub, it is breaking
# the alarm -- the first run did exactly that and the suite caught it.
SKIP = {"tools/verify_no_private_provenance.py",
        "tests/test_verify_no_private_provenance.py",
        "tools/renumber_origin_ids.py",
        # The fold tools read an ordinal out of the origin site's id, so their
        # tests build ids with an f-string -- f"DV_{n}" -- which no textual
        # scrub can see. The first run rewrote the EXPECTED ids beside that
        # generator and left the generator alone, so the fixtures disagreed
        # with themselves and five tests failed behind a broken CI for days.
        "tools/dvaitavedanta/test_fold_tiny_layers.py",
        "tools/dvaitavedanta/test_import_offline.py",
        "tools/dvaitavedanta/test_fold_rare_headings.py"}


def new_id(old: str) -> str:
    return "dge_" + hashlib.sha256(old.encode("utf-8")).hexdigest()[:12]


def tracked_text_files(repo: str) -> list[str]:
    out = subprocess.run(["git", "-C", repo, "grep", "-lI", "-E", r"\b(DV|KCM)_[0-9]+\b"],
                         capture_output=True, text=True).stdout
    return [f for f in out.splitlines()
            if os.path.splitext(f)[1].lower() in TEXT_EXT and f not in SKIP]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--map-out", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)

    files = tracked_text_files(repo)
    print(f"{len(files)} tracked text file(s) carry an origin id")

    mapping: dict[str, str] = {}
    rewritten = hits = 0
    for rel in files:
        full = os.path.join(repo, rel)
        try:
            with open(full, encoding="utf-8") as fh:
                before = fh.read()
        except (OSError, UnicodeDecodeError):
            continue

        def sub(m: re.Match) -> str:
            old = m.group(0)
            n = mapping.get(old)
            if n is None:
                n = mapping[old] = new_id(old)
            return n

        after, n = ORIGIN.subn(sub, before)
        if not n:
            continue
        hits += n
        rewritten += 1
        if not a.dry_run:
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(after)

    # A collision would silently merge two different units into one.
    back: dict[str, str] = {}
    collisions = [(o, n) for o, n in mapping.items()
                  if back.setdefault(n, o) != o]
    print(f"{hits} occurrence(s) across {rewritten} file(s); "
          f"{len(mapping)} distinct id(s); {len(collisions)} collision(s)")
    if collisions:
        print("ABORT: hash collision -- widen the digest", file=sys.stderr)
        return 1

    if a.map_out and not a.dry_run:
        os.makedirs(os.path.dirname(a.map_out) or ".", exist_ok=True)
        with open(a.map_out, "w", encoding="utf-8") as fh:
            json.dump({
                "_readme": "origin record id -> DGE id. Lives HERE, in the private "
                           "repo, and nowhere else: it is the only thing that can "
                           "turn a DGE id back into the external site's own number. "
                           "Written by tools/renumber_origin_ids.py.",
                "algorithm": "dge_ + sha256(old_id)[:12]",
                "count": len(mapping),
                "map": dict(sorted(mapping.items())),
            }, fh, ensure_ascii=False, indent=1)
        print(f"mapping written to {a.map_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
