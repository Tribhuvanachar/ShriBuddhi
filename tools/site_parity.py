#!/usr/bin/env python3
"""
site_parity.py -- make a downstream repo able to actually serve the site.

Work flows ShriBuddhi -> BrahmaBuddhi -> Jagat, and the downstream repos
drift behind. This measures the gap and closes it.

Measured 22 Sep 2026 against each repo's origin/main:

    jagattest     99 files missing, 94 behind -- among them js/audio.js
                  with no dgeHasAudioConfig and js/core.js with no
                  legacy-slug guard
    brahmabuddhi  99 missing, 94 behind, much the same set

A correction worth recording, because it nearly went into the corpus as
fact: an earlier version of this file said BrahmaBuddhi had no root
.html, no js/, no css/ and no data/library.json, and so "could not serve
a single page". That was false. It described a stale local clone --
checked out at a 13 Sep commit and 83 commits behind origin, with no
merge base -- not the repository. BrahmaBuddhi's origin/main has had the
full front end all along. Always fetch before concluding a repo is
missing something.

What a running site needs is deliberately a curated list rather than
something scraped out of the HTML: the pages load almost everything
dynamically (parsing the root HTML for src/href finds 26 static
references, which is nowhere near the truth), so a scraped manifest would
be confidently wrong. The list below is the set of directories the site
is built from. What actually proves a target works is not this tool at
all: serve the target and drive a browser at it, which is how both
downstream repos were checked before their syncs were committed.

admin/config is excluded on purpose: 120 MB of OCR receipts, cost ledgers
and spend reports. It is an audit trail of this repo's own spending, not
something the site serves, and copying it downstream would add 120 MB to
every repo for nothing. admin/content (the About text, What's New, legal
pages, the walkthrough) IS copied -- the site reads it.

data/ is not blanket-copied either: it is 1.8 GB here, and each repo
carries the granthas it has. What IS copied is data/*.json -- the indexes,
library.json among them -- and library.json's `populated` flag is then
recomputed against what the target actually holds on disk, so a repo with
644 granthas says 644 rather than inheriting this repo's claim of 1,716.

  python3 tools/site_parity.py --check   ../brahmabuddhi
  python3 tools/site_parity.py --sync    ../brahmabuddhi
  (verification is by serving the target and driving a browser at it —
   see the commit that added this file)
"""
from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROOT_GLOBS = ["*.html", "sw.js", "favicon.ico", "robots.txt", "sitemap.xml",
              "firebase-hosting.json"]

# The directories the site is served from. Sizes are this repo's, 22 Sep.
SITE_DIRS = [
    "js",                          # 2.5M
    "css",                         # 336K
    "config",                      #  60K  menu, site config, overrides
    "content",                     #  60K  home.json, reader.json, tour.json
    "images",                      # 6.2M
    "vyakarana",                   # 600K  sub-site, linked from the root pages
    "kavya",                       #  12K
    "dvaita-grantha-anukramani",   #  16K
    "guru-parampara",              # 1.9M
    "dasa-sahitya",                # 148K
    "tirtha",                      # 204K
    "firebase",                    # 968K  rules and functions
]

# admin/, minus the ledgers. admin/content is what the reader's panels read.
ADMIN_INCLUDE = ["admin/css", "admin/js", "admin/content", "admin/tests"]

# admin/config is 120 MB of ledgers, but nine small runtime configs are
# buried in it that the site fetches at boot -- without them the reader
# 404s on its menu, its contextual actions and its overrides. This list is
# not guessed: it is every admin/config/*.json named in js/ or the root
# HTML, found with
#     grep -rho "admin/config/[a-zA-Z0-9_.-]*\.json" js/ *.html | sort -u
# and cross-checked against LEGACY_PUBLIC_CONFIG in js/admin-remote.js,
# which is the authoritative list -- several of these are fetched through
# the dgeAdminConfigUrl() helper, so a literal grep alone misses them
# (intellisense.json was found 404ing in a browser precisely that way).
ADMIN_CONFIG_FILES = [
    "admin/config/admin-menu.json",
    "admin/config/chandas-features.json",
    "admin/config/config-overrides.json",
    "admin/config/contextual-actions.json",
    "admin/config/home.json",
    "admin/config/intellisense.json",
    "admin/config/kosha-overrides.json",
    "admin/config/library-overrides.json",
    "admin/config/menu.json",
    "admin/config/opaque_ids.json",
    "admin/config/seo.json",
    "admin/config/site.config.json",
]
ADMIN_ROOT_GLOB = "admin/*.html"

DATA_INDEX_GLOB = "data/*.json"

# Files that are legitimately the target's own, and must survive --overwrite.
#
#   sitemap.xml        the deployment's SEO sitemap. JagatTest's is LARGER
#                      than this repo's (4,979 lines against 3,012) because
#                      it is generated for the live URL set; overwriting it
#                      would shrink the public sitemap.
#
# data/library.json is deliberately NOT here. Protecting it looked right and
# was wrong: it froze the target's catalogue, so a grantha added upstream --
# Manimanjari's eight sargas among them -- never appeared downstream at all.
# BrahmaBuddhi sat at 1,696 entries against this repo's 1,716. The right
# order is copy THEN repopulate: the file comes down whole, and
# repopulate_library() immediately rewrites its `populated` flags against the
# target's own disk, which is what makes it repo-specific. Excluding it from
# the copy skipped the first half.
#   admin/js/keys.js   and the four admin pages beside it: BrahmaBuddhi
#   admin/*.html       rewrote them on 12 Sep for its BYOK loader, which
#                      renders admin pages through an iframe srcdoc where
#                      document.currentScript.src is empty. This repo's
#                      copies would break every admin tool there.
PER_REPO = {
    "sitemap.xml",
    "admin/js/keys.js",
    "admin/js/ocr-studio-core.js",
    "admin/library.html",
    "admin/ocr-review.html",
    "admin/ocr-studio.html",
}


def iter_source() -> list[Path]:
    """Every path this repo would hand downstream, relative to the root."""
    out: list[Path] = []
    for g in ROOT_GLOBS:
        out += [p.relative_to(ROOT) for p in ROOT.glob(g) if p.is_file()]
    for d in SITE_DIRS:
        base = ROOT / d
        if base.is_dir():
            out += [p.relative_to(ROOT) for p in base.rglob("*") if p.is_file()]
    out += [p.relative_to(ROOT) for p in ROOT.glob(ADMIN_ROOT_GLOB) if p.is_file()]
    for d in ADMIN_INCLUDE:
        base = ROOT / d
        if base.is_dir():
            out += [p.relative_to(ROOT) for p in base.rglob("*") if p.is_file()]
    out += [Path(f) for f in ADMIN_CONFIG_FILES if (ROOT / f).is_file()]
    out += [p.relative_to(ROOT) for p in ROOT.glob(DATA_INDEX_GLOB) if p.is_file()]
    return sorted(set(out))


def classify(target: Path, paths: list[Path]) -> dict[str, list[Path]]:
    missing, differs, same = [], [], []
    for rel in paths:
        dst = target / rel
        if not dst.exists():
            missing.append(rel)
        elif not filecmp.cmp(ROOT / rel, dst, shallow=False):
            differs.append(rel)
        else:
            same.append(rel)
    return {"missing": missing, "differs": differs, "same": same}


def has_units(path: Path) -> bool:
    """Does this data file actually carry text a reader could open?

    The three shapes in the corpus: `items` (a list), `shlokas` (a dict
    keyed by verse number), and a bare list. Any of them empty means the
    file exists and holds nothing.
    """
    if not path.is_file():
        return False
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError):
        return False
    if isinstance(doc, list):
        return bool(doc)
    for key in ("items", "shlokas", "units"):
        v = doc.get(key)
        if isinstance(v, (list, dict)):
            return bool(v)
    # THE SPLIT SHAPE. A layer too big for one file is written as an index --
    # {schema, work, layer, units_total, parts} -- with the text itself in
    # sibling part-NNN.json files keyed `units`. It carries none of the three
    # keys above, so this returned False for every one of them.
    #
    # Found 26 Sep 2026 on Nyaya Sudha, whose 8 layers hold 27,413 units
    # between them and were all marked populated:false in library.json. The
    # reader then answered "This text hasn't been added to the library". I had
    # made the identical misreading by hand an hour earlier, counting those
    # same layers as 0 units, which is a fair sign the shape needs handling
    # rather than remembering.
    if isinstance(doc.get("parts"), (list, dict)) and doc.get("parts"):
        total = doc.get("units_total")
        if isinstance(total, int):
            return total > 0
        # No declared total: trust the parts only if one really carries units.
        for part in (doc["parts"] if isinstance(doc["parts"], list) else doc["parts"].values()):
            name = part if isinstance(part, str) else (part or {}).get("file")
            if not name:
                continue
            try:
                sub = json.loads((path.parent / name).read_text())
            except (OSError, ValueError):
                continue
            if sub.get("units"):
                return True
        return False
    return False


def repopulate_library(target: Path) -> tuple[int, int]:
    """Set each grantha's `populated` from what the TARGET actually holds.

    Without this a synced library.json carries this repo's answer, and the
    target's library claims texts it does not have -- every one of them a
    dead link that looks live.

    "Holds" means units, not a file. The first version of this tested
    `is_file()` and so marked 328 entries populated in each downstream repo
    that open to nothing: the Anandamakaranda shelf carries an empty
    tika_jayatirtha and an empty tippani beside every one of its ten
    upanisad books, and there are more elsewhere. A file with "items": []
    is exactly the dead link this function exists to prevent, so it has to
    be opened and counted.
    """
    lib = target / "data/library.json"
    if not lib.exists():
        return (0, 0)
    doc = json.loads(lib.read_text())
    on, off = 0, 0
    for g in doc.get("granthas", []):
        p = g.get("path")
        if not p:
            continue
        have = has_units(target / p)
        g["populated"] = have
        on += have
        off += not have
    lib.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return (on, off)


def sync(target: Path, paths: list[Path], report: dict, overwrite: bool) -> int:
    """Copies what the target LACKS. A file the target already has is left
    alone unless --overwrite is passed, because downstream divergence here
    is deliberate, not staleness: BrahmaBuddhi's admin/js/keys.js was
    rewritten on 12 Sep for its BYOK loader, which renders admin pages
    through an iframe srcdoc where document.currentScript.src is empty, so
    this repo's self-relative URL derivation cannot work there. Copying
    this repo's copy over it would break every admin tool in that repo.
    The same holds for the four admin pages beside it."""
    n = 0
    rows = report["missing"] + (
        [r for r in report["differs"] if str(r).replace("\\", "/") not in PER_REPO]
        if overwrite else [])
    for rel in rows:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--overwrite", action="store_true",
                    help="also replace files the target has but that differ; "
                         "off by default because downstream divergence is "
                         "usually deliberate")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    if not (target / ".git").is_dir():
        raise SystemExit(f"{target} is not a git repository")

    paths = iter_source()
    report = classify(target, paths)
    print(f"source : {ROOT.name}  ({len(paths)} site files)")
    print(f"target : {target.name}")
    print(f"  same     {len(report['same']):>5}")
    print(f"  differs  {len(report['differs']):>5}")
    print(f"  missing  {len(report['missing']):>5}")
    for label in ("missing", "differs"):
        rows = report[label]
        if not rows:
            continue
        by_top: dict[str, int] = {}
        for r in rows:
            by_top[r.parts[0]] = by_top.get(r.parts[0], 0) + 1
        print(f"  {label} by area: "
              + ", ".join(f"{k} {v}" for k, v in sorted(by_top.items(), key=lambda x: -x[1])))
        for r in rows[:args.limit]:
            print(f"      {r}")
        if len(rows) > args.limit:
            print(f"      ... and {len(rows) - args.limit} more")

    if args.sync:
        n = sync(target, paths, report, args.overwrite)
        on, off = repopulate_library(target)
        print(f"\ncopied {n} files")
        held = [r for r in report["differs"]
                if args.overwrite and str(r).replace("\\", "/") in PER_REPO]
        if held:
            print(f"kept {len(held)} target-owned files (PER_REPO):")
            for r in held:
                print(f"      {r}")
        if report["differs"] and not args.overwrite:
            print(f"left {len(report['differs'])} differing files alone "
                  f"(pass --overwrite to replace them):")
            for r in report["differs"]:
                print(f"      {r}")
        print(f"library.json repopulated for {target.name}: "
              f"{on} granthas present, {off} marked unpopulated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
