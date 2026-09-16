#!/usr/bin/env python3
"""
mirror_changed_paths.py -- copy a working tree's changed files into a second
checkout, deletions included.

interlink.yml rebuilds index layers in this repo and then mirrors whatever
moved into a BrahmaBuddhi checkout to commit there. It used to do that with

    git status --porcelain | awk '{print $2}'   →   cp

which reads a DELETED path as something to copy and dies on `cp: cannot
stat`. That is not a rare case: a rebuild removes shards as well as writing
them -- a dhatu that lost its last prayoga has no file any more -- so the
workflow failed whenever the rebuild shrank anything. The awk also took the
wrong field for a rename and split any path containing a space.

Reading `git status --porcelain -z` instead: the status is two characters,
the path is the rest of the record, a rename or copy spends a second record
on its old path, and nothing is split on whitespace. A deletion is mirrored
AS a deletion, so the mirror does not keep files the source no longer has.

    git status --porcelain -z -- <paths> > changed.z
    python3 tools/mirror_changed_paths.py changed.z <destination-root>
"""
from __future__ import annotations

import os
import shutil
import sys

# Both columns of the porcelain status; either one showing D means the path
# is gone from the working tree (staged deletion, unstaged deletion, both).
DELETED = {" D", "D ", "DD", "AD", "RD", "CD", "MD", "UD", "DU"}


def records(blob: bytes) -> list[tuple[str, str, str | None]]:
    """(status, path, renamed_from) for each entry git reported."""
    fields = blob.split(b"\0")
    out: list[tuple[str, str, str | None]] = []
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        status = entry[:2].decode("utf-8")
        path = entry[3:].decode("utf-8")
        renamed_from = None
        if "R" in status or "C" in status:
            if i < len(fields):
                renamed_from = fields[i].decode("utf-8")
                i += 1
        out.append((status, path, renamed_from))
    return out


def mirror(entries, destination: str) -> tuple[int, int]:
    copied = removed = 0
    for status, path, renamed_from in entries:
        target = os.path.join(destination, path)
        if status in DELETED:
            if os.path.lexists(target):
                os.remove(target)
                removed += 1
            continue
        if renamed_from:
            stale = os.path.join(destination, renamed_from)
            if os.path.lexists(stale):
                os.remove(stale)
                removed += 1
        if not os.path.exists(path):
            # Staged and then removed again; there is nothing to carry over,
            # and inventing an empty file would be worse than skipping it.
            continue
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied, removed


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print(__doc__.strip().rsplit("\n\n", 1)[-1], file=sys.stderr)
        return 2
    status_file, destination = argv
    with open(status_file, "rb") as handle:
        entries = records(handle.read())
    copied, removed = mirror(entries, destination)
    print("mirrored %d file(s) into %s, removed %d" % (copied, destination, removed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
