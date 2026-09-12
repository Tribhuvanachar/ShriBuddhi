#!/usr/bin/env python3
"""Stage source-derived corpus material into the private Parabuddhi repository.

WHY THIS EXISTS. data is public, and ~833 of its data.json files carry the
fingerprints of the site they were imported from: a top-level `source_url`, a
per-unit `source` dict holding the ORIGIN'S OWN database keys (content_id,
work_id, anchor, block_uuid), the origin's raw `source_html`, and its
navigation `breadcrumb`. Anyone can join the public repo back to its sources in
minutes — not by recognising the prose, but by reading those ids.

The plan is to hold that material privately, transform it into the project's
own edition, and publish only a cleaned copy. This script does the first step:
it COPIES (never moves, never deletes) the fingerprinted files into Parabuddhi,
grouped by origin site, with a manifest recording where each came from.

DELIBERATELY A COPY. Nothing leaves data here. Removing anything from the
public repository is a separate, deliberate act, taken after the private copy
is verified — a migration whose rollback needs a restore is not a migration.

WHAT IS AND IS NOT STAGED. Only sites whose rights position in
admin/config/sources.registry.json is unresolved or case-by-case. Openly
licensed and public-domain sources (GRETIL, sanskritdocuments.org, wikisource,
archive.org, the vishvasa GitHub repos) stay public: hiding them would cost
content and buy nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"

# Generated sidecars, not imported text — never staged.
SKIP_DIRS = {"_references", "_padaccheda", "_commentary_sandhi", "_highlight", "_search"}

# The sites whose material moves private, and why. The `rights` line is copied
# from admin/config/sources.registry.json so the manifest carries the reason
# next to the file rather than in a document nobody opens.
STAGED_SITES = {
    "dvaitavedanta.in": "No explicit licence. Absence of a licence is not permission.",
    "srivaishnavan.com": "Public site; case-by-case permission recorded 2 Sep 2026.",
    "advaitasharada.sringeri.net": "Case-by-case permission; licensed corpus — must not be indexed publicly.",
    "setutila.in": "Case-by-case permission recorded by the lead; all 47 leaves flagged restricted.",
    "anandamakaranda.in": "No licence statement; used under the lead's case-by-case authorisation.",
    "upanishat.com": "Case-by-case; grouped with the SarvaMula imports.",
    "tirthaprabandha.wordpress.com": "Case-by-case; grouped with the SarvaMula imports.",
    "srimadhvyasa.wordpress.com": "Case-by-case; grouped with the SarvaMula imports.",
}

# Everything else stays public. Listed explicitly rather than inferred, so a new
# importer whose site is in neither list fails loudly instead of defaulting.
PUBLIC_SITES = {
    "github.com", "gretil.sub.uni-goettingen.de", "sanskritdocuments.org",
    "archive.org", "sa.wikisource.org", "vedicreserve.miu.edu", "docs.google.com",
    "android_app_local_asset:dasa1", "https://madhwafestivals.com",
    "https://dasasahithyamahithi.com", "https://dasasahitya.net",
}


def origin_site(doc):
    """The site a data.json came from, or None if it carries no origin mark.

    Two places record it and they do not always agree in form: the top-level
    `source_url` is a URL, while the per-unit `source.site` is a bare hostname.
    The per-unit value is preferred — it is the one the importers write
    consistently, and the one that carries the origin's record ids beside it.
    """
    units = doc.get("items") or list((doc.get("shlokas") or {}).values())
    for u in units[:1]:
        if isinstance(u, dict) and isinstance(u.get("source"), dict):
            site = u["source"].get("site")
            if site:
                return str(site)
    su = doc.get("source_url")
    if isinstance(su, str) and su.startswith("http"):
        return su.split("/")[2]
    return None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(root: Path):
    """Every data.json under `root`, bucketed into staged / public / unknown."""
    staged, public, unknown = [], [], []
    for path in sorted(root.rglob("data.json")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        try:
            doc = json.load(path.open(encoding="utf-8"))
        except Exception as e:
            unknown.append((rel.as_posix(), f"unreadable: {e}"))
            continue
        site = origin_site(doc)
        if site is None:
            public.append((rel.as_posix(), None))       # no origin mark: our own work
        elif site in STAGED_SITES:
            staged.append((rel.as_posix(), site))
        elif site in PUBLIC_SITES:
            public.append((rel.as_posix(), site))
        else:
            unknown.append((rel.as_posix(), site))
    return staged, public, unknown


def stage(staged, dest: Path, root: Path = None, sites=None, apply=False, quiet=False):
    """Copy each staged file from `root` to dest/source/<site>/<its path>.

    `root` is passed in rather than read from the module global: --data has to
    mean the same thing to this function as it does to classify(), or a run
    against a second tree reports one set of files and copies another.

    Keyed by site first, then the original path. Grouping by origin makes the
    provenance visible in the filesystem and puts every file belonging to one
    rights holder in one place — which is the axis that matters the day a
    permission question is asked about a particular site.
    """
    src_root = Path(root) if root is not None else DATA
    rows, copied, total = [], 0, 0
    for rel, site in staged:
        if sites and site not in sites:
            continue
        src = src_root / rel
        size = src.stat().st_size
        row = {
            "site": site,
            "data_path": rel,
            "object": f"source/{site}/{rel}",
            "bytes": size,
            "rights": STAGED_SITES[site],
        }
        if apply:
            out = dest / "source" / site / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
            row["sha256"] = sha256(out)
            copied += 1
            if not quiet and copied % 50 == 0:
                print(f"  {copied} files, {total/1e6:.0f} MB", flush=True)
        rows.append(row)
        total += size
    return rows, total


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default="/home/user/parabuddhi", help="the Parabuddhi working copy")
    ap.add_argument("--data", default=str(DATA), help="corpus root (default data)")
    ap.add_argument("--site", action="append", help="stage only this site (repeatable)")
    ap.add_argument("--apply", action="store_true", help="actually copy (default: report only)")
    ap.add_argument("--manifest", action="store_true", help="write/merge source/_manifest.json")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.data)
    dest = Path(args.dest)
    staged, public, unknown = classify(root)

    if unknown:
        # A site in neither list is a judgement call, not a default. Refusing
        # here is what stops a future importer silently publishing material
        # nobody decided about.
        print(f"{len(unknown)} file(s) from a site in neither STAGED_SITES nor PUBLIC_SITES:")
        for rel, site in unknown[:20]:
            print(f"  {site!r}  {rel}")
        print("Add each site to one list in tools/parabuddhi_stage.py, then re-run.")
        return 2

    sites = set(args.site) if args.site else None
    rows, total = stage(staged, dest, root=root, sites=sites, apply=args.apply, quiet=args.quiet)

    if not args.quiet:
        by = {}
        for r in rows:
            b = by.setdefault(r["site"], [0, 0])
            b[0] += 1
            b[1] += r["bytes"]
        print(f"\n{'site':<34}{'files':>7}{'MB':>9}")
        for site, (n, b) in sorted(by.items(), key=lambda x: -x[1][1]):
            print(f"{site:<34}{n:>7}{b/1e6:>9.1f}")
        print(f"{'TOTAL':<34}{len(rows):>7}{total/1e6:>9.1f}")
        print(f"\nstaying public: {len(public)} files")
        if not args.apply:
            print("\nreport only — nothing copied. Re-run with --apply.")

    if args.apply and args.manifest:
        mp = dest / "source" / "_manifest.json"
        existing = {}
        if mp.exists():
            for r in json.loads(mp.read_text(encoding="utf-8")).get("files", []):
                existing[r["object"]] = r
        for r in rows:
            existing[r["object"]] = r
        merged = sorted(existing.values(), key=lambda r: r["object"])
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps({
            "_readme": "Every file staged from the public corpus into this repository, "
                       "with the origin site it came from, the data path it was copied "
                       "from, its digest, and the rights position recorded for that site. "
                       "Written by tools/parabuddhi_stage.py in the bhumandala repo.",
            "files": merged,
            "count": len(merged),
            "bytes": sum(r["bytes"] for r in merged),
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        if not args.quiet:
            print(f"manifest: {len(merged)} files -> {mp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
