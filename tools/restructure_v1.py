#!/usr/bin/env python3
"""The V1 library restructure: display path and disk path become the same thing.

WHAT THIS DOES. Until now the library tree a reader sees was produced by the
`moves` map in admin/config/library-overrides.json -- a display-only overlay on
top of wherever the files happened to land when they were imported. The lead
asked for that to stop: what the library manager shows IS the folder structure,
so a rename in one is a rename in the other.

    DvaitaVedanta/                  <- new, at the top of the library
      SarvaMula/                    <- was darshana/vedanta/dvaita/SetuTila
      Itara/                        <- everything that is not a mula grantha
        DasaSahitya/                <- was dasa_sahitya/
        Kavya/                      <- was kavya_alankara/{sumadhva,raghavendra,tirtha}
        Stotra/                     <- was stotra/PrahladaKrutaNarasimha

    darshana/vedanta/dvaita/
      Anandamakaranda/              <- stays; no longer promoted to the top
      DvaitaSahitya/                <- was DvaitaVedanta, renamed to free the name

WHY A TOOL AND NOT A FEW git mv's. It is ~900 files across eight moves, and
every one of them is referenced by path in library.json, the search backlinks,
the chandas and dhatu-prayoga reports, the catalogs and the config. Moving the
files without rewriting those references produces a library that looks right
and 404s on every link. Doing it as one reviewable script means the reference
rewrite cannot be forgotten, and --dry-run shows the whole blast radius before
anything moves.

SetuTila/_raw DOES NOT MOVE HERE. It is 26 MB of raw HTML chunks scraped from
setutila.in -- the origin's own markup, verbatim, in a public repository. It
belongs in Parabuddhi with the rest of that site's material, so this script
refuses to carry it into the new tree and reports it instead.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "dge" / "data"

# (source, destination) in data terms. Order matters: the DvaitaVedanta
# rename runs last, so the earlier entries can still name the old path.
MOVES = [
    ("darshana/vedanta/dvaita/SetuTila",            "DvaitaVedanta/SarvaMula"),
    ("dasa_sahitya",                                "DvaitaVedanta/Itara/DasaSahitya"),
    ("kavya_alankara/sumadhva_vijaya",              "DvaitaVedanta/Itara/Kavya/sumadhva_vijaya"),
    ("kavya_alankara/raghavendra_vijaya",           "DvaitaVedanta/Itara/Kavya/raghavendra_vijaya"),
    ("darshana/vedanta/dvaita/Anandamakaranda/kavya/tirtha_prabandha",
                                                    "DvaitaVedanta/Itara/Kavya/tirtha_prabandha"),
    ("stotra/PrahladaKrutaNarasimha",               "DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha"),
    # Last: frees the name DvaitaVedanta for the new top-level container.
    ("darshana/vedanta/dvaita/DvaitaVedanta",       "darshana/vedanta/dvaita/DvaitaVedantaIn"),
]

# Import leftovers that must never reach the new public tree. _raw holds the
# origin site's own HTML; _sync_state is the crawler's bookkeeping.
PRIVATE_LEFTOVERS = ["_raw", "_sync_state.json"]

# Where path strings are written. Scanned repo-wide rather than by a list of
# known files, because the last rename found 834 of them and a list would have
# missed most.
REWRITE_SUFFIXES = (".json", ".js", ".py", ".yml", ".yaml", ".md", ".html")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".puppeteer-cache"}


SELF = Path(__file__).resolve()


def rewrite_targets(root: Path):
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in REWRITE_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        # Never this file. On the first run it rewrote its own MOVES table,
        # replacing every source with its destination -- which leaves a tool
        # that does nothing and no record of what it did.
        if p.resolve() == SELF:
            continue
        yield p


def find_leftovers():
    """Import artefacts sitting inside something about to be published."""
    found = []
    for src, _ in MOVES:
        base = DATA / src
        for name in PRIVATE_LEFTOVERS:
            p = base / name
            if p.exists():
                n = sum(1 for x in p.rglob("*") if x.is_file()) if p.is_dir() else 1
                size = sum(x.stat().st_size for x in p.rglob("*") if x.is_file()) if p.is_dir() else p.stat().st_size
                found.append((f"{src}/{name}", n, size))
    return found


def do_moves(apply=False, quiet=False):
    moved = []
    for src, dst in MOVES:
        s, d = DATA / src, DATA / dst
        if not s.exists():
            if not quiet:
                print(f"  skip (absent): {src}")
            continue
        n = sum(1 for x in s.rglob("*") if x.is_file())
        if apply:
            d.parent.mkdir(parents=True, exist_ok=True)
            if d.exists():
                # Merge rather than clobber: the destination may already hold a
                # sibling moved by an earlier entry in this same run.
                for x in sorted(s.rglob("*")):
                    if not x.is_file():
                        continue
                    out = d / x.relative_to(s)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(x), str(out))
                shutil.rmtree(s, ignore_errors=True)
            else:
                shutil.move(str(s), str(d))
        moved.append((src, dst, n))
        if not quiet:
            print(f"  {n:>5} files  {src}  ->  {dst}")
    return moved


def rewrite_references(apply=False, quiet=False):
    """Rewrite every stored path string, longest source first.

    Longest first matters: kavya_alankara/sumadhva_vijaya must be rewritten
    before anything that would match the bare kavya_alankara prefix, or the
    specific rule never fires.

    AND IT MATCHES ON A PATH BOUNDARY, not as a substring. A plain replace of
    "dasa_sahitya" also rewrites "dasa_sahitya_local" -- a different directory
    this script does not move. That is not hypothetical: the first run here
    corrupted 61 references across 14 files exactly that way. The lookahead
    requires the next character to end the path.
    """
    pairs = [(re.compile(re.escape(src) + r"(?=[/\"'`\s,)\]}]|$)"), dst)
             for src, dst in sorted(MOVES, key=lambda m: -len(m[0]))]
    touched, total = 0, 0
    for p in rewrite_targets(REPO):
        try:
            s = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        orig = s
        hits = 0
        for pat, dst in pairs:
            s, n = pat.subn(dst, s)
            hits += n
        if hits and s != orig:
            total += hits
            touched += 1
            if apply:
                p.write_text(s, encoding="utf-8")
    if not quiet:
        print(f"  {total:,} path reference(s) in {touched} file(s)")
    return touched, total


def update_overrides(apply=False, quiet=False):
    """Empty the `moves` overlay: the paths are real now.

    Two entries survive, because they are genuine cross-placements rather than
    the old promote-to-top overlay -- a Vadiraja work that belongs in the
    DvaitaVedanta tree while living under Dasa Sahitya.
    """
    p = REPO / "admin" / "config" / "library-overrides.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    before = dict(d.get("moves") or {})

    # Apply the path rewrite here too rather than relying on rewrite_references
    # having already run over this file. Depending on step order would make the
    # dry run report something different from what --apply does, and a dry run
    # that lies about the outcome is worse than no dry run.
    def remap(x):
        for src, dst in sorted(MOVES, key=lambda m: -len(m[0])):
            x = x.replace(src, dst)
        return x

    kept = {remap(k): remap(v) for k, v in before.items()
            if remap(k).startswith("DvaitaVedanta/Itara/DasaSahitya/")}
    d["moves"] = kept
    d["shelf"]["allow"] = [
        "DvaitaVedanta/Itara/Kavya/sumadhva_vijaya",
        "DvaitaVedanta/Itara/Kavya/mani_manjari",
        "DvaitaVedanta/Itara/Kavya/raghavendra_vijaya",
        "DvaitaVedanta/Itara/Kavya/tirtha_prabandha",
    ]
    if not quiet:
        print(f"  moves: {len(before)} -> {len(kept)}; shelf re-pointed at DvaitaVedanta/Itara/Kavya")
    if apply:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return before, kept


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually move and rewrite")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    leftovers = find_leftovers()
    if leftovers:
        print("REFUSED — import leftovers sit inside folders about to be published:\n")
        for path, n, size in leftovers:
            print(f"  {path}   {n} file(s), {size/1e6:.1f} MB")
        print("\n_raw holds the origin site's own HTML, verbatim. Publishing it would put")
        print("back exactly what moving that material into Parabuddhi was meant to remove.")
        print("Stage it privately and delete it here, then re-run.")
        return 2

    print("MOVES")
    do_moves(apply=args.apply, quiet=args.quiet)
    print("\nREFERENCES")
    rewrite_references(apply=args.apply, quiet=args.quiet)
    print("\nCONFIG")
    update_overrides(apply=args.apply, quiet=args.quiet)

    if not args.apply:
        print("\ndry run — nothing changed. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
