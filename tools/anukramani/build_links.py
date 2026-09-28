#!/usr/bin/env python3
"""Link the Dvaita Grantha Anukramaṇikā to the texts this library actually holds.

WHAT THE CATALOGUE IS. data/catalogs/dvaita_grantha_anukramani.json is the
2,456-row index of every known Dvaita work -- 740 canonical authors, 1,469
canonical titles -- built from the `dwita.books.index.` sheet. Most of those
works are not digitised anywhere, and that is the point of it: it is the map of
the territory, not of our holdings.

WHAT WAS MISSING. Not one of its 2,456 rows pointed at a text in this library,
so a reader browsing an author's works had no way to open the ones we have.
This writes that bridge as a DERIVED sidecar -- the catalogue file itself stays
a faithful copy of the sheet and is never edited to carry our slugs.

WHY A TITLE MATCH ALONE IS NOT ENOUGH, measured rather than assumed: matching
on the title only accepts 57 rows, and they are not all real. "विवरणम्" --
simply the word for an exposition -- matches yukti_mallika's vivaraṇe layer for
four different authors, and the Nyāyamañjarī of Candrakeśava matches Jayanta
Bhaṭṭa's entirely separate Nyāya classic. A commentary title is often a common
noun; the author is what makes the pair unique.

WHY THE AUTHOR IS COMPARED BY LONGEST COMMON SUBSTRING. The two sources spell
the same person differently at BOTH ends -- honorifics at the front
(श्रीवादिराजतीर्थः against श्रीमद्वादिराजतीर्थः) and titles at the back
(श्रीमदानन्दतीर्थः against श्रीमदानन्दतीर्थभगवत्पादाचार्यः). Comparing whole
strings finds nothing (measured: 0 of 2,456). Comparing prefixes fails on the
honorifics, because श्रीमद् + आनन्द welds by sandhi into श्रीमदानन्द and
stripping the honorific literally leaves a stranded vowel sign. The distinctive
part of a name -- वादिराज, आनन्दतीर्थ, व्यासतीर्थ -- survives in the middle
either way, so the longest run the two names share is the honest test.

The floor of 8 characters is chosen against the data, not picked: at 6 the
shared tail "तीर्थः" alone is enough to pair two unrelated Tīrthas, and at 10
real matches start falling out.

Anything this cannot decide is simply left unlinked. A catalogue entry with no
link reads exactly as it should -- a work we do not hold yet -- whereas a WRONG
link puts one ācārya's name on another's text. Hand-made links belong in
anukramani_links.overrides.json, which always wins.

Usage: python3 tools/anukramani/build_links.py [--check]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data/catalogs/dvaita_grantha_anukramani.json"
LIBRARY = ROOT / "data/library.json"
MANIFEST = ROOT / "data/layer_manifest.json"
OVERRIDES = ROOT / "data/catalogs/anukramani_links.overrides.json"
OUT = ROOT / "data/catalogs/anukramani_links.json"

# Whitespace, punctuation and the zero-width joiners the scans leave behind --
# all of which differ between the sheet and the catalogue without the name
# differing at all.
DROP = re.compile(r"[\s।॥|.,\-–—'’\"()​-‍]+")

MIN_AUTHOR_OVERLAP = 8


def norm(s: str) -> str:
    return DROP.sub("", s or "")


def overlap(a: str, b: str) -> int:
    """Length of the longest run the two names share."""
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0
    return SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b)).size


def library_index() -> dict[str, list[tuple[str, str, bool]]]:
    """normalised title -> [(slug, author, populated)].

    Indexes the flat library entries AND the layer manifest's family titles.
    The manifest is worth reading because a layered grantha's own entries are
    titled for the LAYER ("Mula", "Tika Satyapramoda") while the manifest
    carries the work's real name ("युक्तिमल्लिका") -- without it, every
    multi-layer work in the corpus would be invisible to this match.
    """
    idx: dict[str, list[tuple[str, str, bool]]] = collections.defaultdict(list)
    lib = json.loads(LIBRARY.read_text(encoding="utf-8"))
    for g in lib["granthas"]:
        title = norm(g.get("title"))
        if not title:
            continue
        author = (g.get("facets") or {}).get("default_author") or ""
        idx[title].append((g["path"][5:-10], author, bool(g.get("populated"))))
    if MANIFEST.is_file():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for slug, entry in (man.get("granthas") or {}).items():
            title = entry.get("title") or ""
            # "Mula" is the layer-title fallback, not a work's name.
            if not title or title == "Mula":
                continue
            spine = entry.get("spineSlug") or "mula"
            idx[norm(title)].append((f"{slug}/{spine}", entry.get("author") or "", True))
    return idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="compare against what is committed; write nothing")
    args = ap.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    idx = library_index()
    manual = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.is_file() else {}

    links: dict[str, dict] = {}
    title_only = 0
    for item in catalog["items"]:
        rid = item["id"]
        if rid in manual:
            links[rid] = dict(manual[rid], by="manual")
            continue
        key = norm(item.get("grantha"))
        if not key or key not in idx:
            continue
        best = None
        for slug, author, populated in idx[key]:
            score = overlap(item.get("karta"), author)
            if score >= MIN_AUTHOR_OVERLAP and (best is None or score > best[0]):
                best = (score, slug, populated)
        if best is None:
            title_only += 1
            continue
        links[rid] = {"slug": best[1], "populated": best[2],
                      "authorOverlap": best[0], "by": "title+author"}

    payload = {
        "schema": "anukramani_links_v1",
        "note": ("Derived from the catalogue and the library by "
                 "tools/anukramani/build_links.py. Not hand-edited: put manual "
                 "links in anukramani_links.overrides.json, which wins."),
        "catalogRows": len(catalog["items"]),
        "linked": len(links),
        "links": dict(sorted(links.items(), key=lambda kv: int(kv[0][1:]))),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"

    print(f"{len(catalog['items'])} catalogue rows")
    print(f"   {len(links)} linked ({sum(1 for v in links.values() if v['by']=='manual')} by hand)")
    print(f"   {title_only} matched a title but no author -- left unlinked on purpose")
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else None
        if current != text:
            print("links file is stale", file=sys.stderr)
            return 1
        print("links file matches")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
