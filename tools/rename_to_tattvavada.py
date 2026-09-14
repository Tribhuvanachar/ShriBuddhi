#!/usr/bin/env python3
"""
rename_to_tattvavada.py — data/DvaitaVedanta/ becomes data/Tattvavada/.

WHY THIS IS A SCRIPT AND NOT A sed ONE-LINER. Two different trees in this
corpus are called some form of "DvaitaVedanta", which is the confusion the
project lead asked (14 Sep 2026) to end:

    data/DvaitaVedanta/            SarvaMula + Itara -- the one being renamed
    data/darshana/vedanta/dvaita/DvaitaVedantaIn/   admin-only, NOT renamed

A blanket replace corrupts the second one, and not in a way that shows up
quickly. Three specific traps, all confirmed against the tree:

  1. `DvaitaVedanta` is a literal PREFIX of `DvaitaVedantaIn`, so any naive
     match hits 315 granthas that must not move.
  2. taxonomy.json keys the NESTED tree as plain "DvaitaVedanta" (at
     /darshana/vedanta/dvaita/DvaitaVedanta), even though its folder on disk
     is DvaitaVedantaIn. So the bare quoted string "DvaitaVedanta" belongs to
     the tree we are NOT renaming. Replacing it would silently repoint the
     admin-only taxonomy at nothing.
  3. search_index/manifest.json carries `category` separately from `slug`.
     The two trees are cleanly split there -- 249 granthas under category
     "DvaitaVedanta" vs 315 under "darshana" -- so category is fixed by
     looking at each grantha's slug, never by matching the string.

The rule that survives all three: replace `DvaitaVedanta` ONLY when the very
next character begins a path or a shard separator (`/` or `__`). After
`DvaitaVedanta` in `DvaitaVedantaIn` comes `I`, so that tree cannot match, and
the bare taxonomy key has nothing after it at all.

    python3 tools/rename_to_tattvavada.py --dry-run
    python3 tools/rename_to_tattvavada.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

OLD, NEW = "DvaitaVedanta", "Tattvavada"

# The whole safety argument, in one expression: a following '/' or '__' means
# this is a path or a shard name, which is exactly what moves.
PATTERN = re.compile(re.escape(OLD) + r"(?=/|__)")

TEXT_EXT = {".json", ".js", ".py", ".md", ".html", ".yml", ".yaml", ".txt",
            ".xml", ".css", ".csv", ".sh"}


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def candidate_files(repo: str) -> list[str]:
    """Tracked text files that mention the old name. `git grep -l` reads the
    index, which is the only way this finishes quickly on a 205k-file tree."""
    try:
        out = subprocess.run(["git", "-C", repo, "grep", "-lI", "--", OLD],
                             capture_output=True, text=True).stdout
    except OSError:
        return []
    return [f for f in out.splitlines()
            if os.path.splitext(f)[1].lower() in TEXT_EXT]


def rewrite(repo: str, files: list[str], dry: bool) -> tuple[int, int]:
    changed = hits = 0
    for rel in files:
        full = os.path.join(repo, rel)
        try:
            with open(full, encoding="utf-8") as fh:
                before = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        after, n = PATTERN.subn(NEW, before)
        if not n:
            continue
        hits += n
        changed += 1
        if not dry:
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(after)
    return changed, hits


def move_tree(repo: str, dry: bool) -> bool:
    src, dst = os.path.join(repo, "data", OLD), os.path.join(repo, "data", NEW)
    if not os.path.isdir(src):
        return False
    if dry:
        print(f"  would git mv data/{OLD} -> data/{NEW}")
        return True
    subprocess.run(["git", "-C", repo, "mv", f"data/{OLD}", f"data/{NEW}"], check=True)
    return True


def move_shards(repo: str, dry: bool) -> int:
    """search_index/units/<slug with / as __>.json -- the filename encodes the
    slug, so a renamed tree needs its shards renamed in step or the manifest
    points at files that are not there."""
    d = os.path.join(repo, "search_index", "units")
    if not os.path.isdir(d):
        return 0
    n = 0
    for name in sorted(os.listdir(d)):
        if not name.startswith(OLD + "__"):
            continue
        n += 1
        if not dry:
            subprocess.run(["git", "-C", repo, "mv",
                            f"search_index/units/{name}",
                            f"search_index/units/{NEW + name[len(OLD):]}"], check=True)
    return n


def fix_manifest(repo: str, dry: bool) -> int:
    """`category` is NOT derived from the slug at read time, so it has to be
    corrected explicitly -- and only for granthas whose slug actually moved."""
    p = os.path.join(repo, "search_index", "manifest.json")
    if not os.path.isfile(p):
        return 0
    with open(p, encoding="utf-8") as fh:
        m = json.load(fh)
    n = 0
    for g in m.get("granthas", []):
        if g.get("slug", "").startswith(NEW + "/") and g.get("category") == OLD:
            g["category"] = NEW
            n += 1
    if n and not dry:
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(m, fh, ensure_ascii=False, separators=(",", ":"))
    return n


def survivors(repo: str) -> list[str]:
    """What still says the old name after the pass. Never expected to be zero:
    the nested DvaitaVedantaIn tree and taxonomy.json's own key legitimately
    keep it, and seeing them listed is how we know they were left alone."""
    out = subprocess.run(["git", "-C", repo, "grep", "-lI", "--", OLD],
                         capture_output=True, text=True).stdout
    return out.splitlines()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    dry = a.dry_run

    print(f"{'DRY RUN on' if dry else 'renaming in'} {repo}")
    files = candidate_files(repo)
    print(f"  {len(files)} tracked text file(s) mention {OLD}")

    changed, hits = rewrite(repo, files, dry)
    print(f"  {hits} reference(s) rewritten across {changed} file(s)")
    print(f"  tree moved: {move_tree(repo, dry)}")
    print(f"  {move_shards(repo, dry)} index shard(s) renamed")
    print(f"  {fix_manifest(repo, dry)} manifest category value(s) corrected")

    if not dry:
        left = survivors(repo)
        print(f"\n  {len(left)} file(s) still mention {OLD} (expected: the "
              f"admin-only DvaitaVedantaIn tree and taxonomy.json's key):")
        for f in left[:10]:
            print(f"    {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
