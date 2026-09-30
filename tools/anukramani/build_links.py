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

SECOND PASS -- TITLES THAT ARE THE SAME WORK SPELT DIFFERENTLY. The sheet has
तैत्तिरीयोपनिशत् भाष्य (ष for ष, no द्, अनुस्वार for न्) where the library has
तैत्तिरीयोपनिषद्भाष्यम्. An exact match cannot see that. fold() reduces both
sides to a skeleton that ignores exactly those scribal differences -- hyphens
and joiners, ष/श, ी/ि, ू/ु, ण/न, व/ब, द्/त् at a word's end, parasavarṇa
(न्द्र = ंद्र), and a final ः / म् / ं -- and the pair is accepted at a
SequenceMatcher ratio of 0.90 or better AND the same author test as above. A
row is only ever linked this way if it has no exact link, and each such link
records by="title~+author" and its titleScore so it can be audited.

THIRD PASS -- THE SHEET'S SHORT NAME FOR A LONGER TITLE. The sheet says
अनुव्याख्यानम् and गीताभाष्यम्; the library titles the same works
ब्रह्मसूत्रानुव्याख्यानम् and भगवद्गीताभाष्यम्. The short title sits inside the long
one (with the initial अ merged by sandhi into the preceding आ). Accepted when
the folded short title is at least 7 letters, is contained in the folded library
title, makes up at least half of it, and the author test passes. Recorded as
by="title-in+author".

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
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data/catalogs/dvaita_grantha_anukramani.json"
LIBRARY = ROOT / "data/library.json"
MANIFEST = ROOT / "data/layer_manifest.json"
OVERRIDES = ROOT / "data/catalogs/anukramani_links.overrides.json"
OUT = ROOT / "data/catalogs/anukramani_links.json"
SCHOLAR = ROOT / "data/catalogs/dvaita_grantha_anukramani.overrides.json"

# Whitespace, punctuation and the zero-width joiners the scans leave behind --
# all of which differ between the sheet and the catalogue without the name
# differing at all.
DROP = re.compile(r"[\s।॥|.,\-–—'’\"()​-‍]+")

MIN_AUTHOR_OVERLAP = 8

# 1. Only the first 1,200 rows of the sheet are used for now (the lead,
#    30 Sep 2026): from row 1201 on, works and authors repeat heavily and need
#    cleaning first. library.html applies the same limit -- keep them equal.
MAX_SHEET_ROW = 1200

# 2. A catalogue entry may link ONLY into the Tattvavada folder, never anywhere
#    else in the library (the lead: "never, ever"). Enforced where the library
#    index is built, on manual overrides, and asserted again before writing.
ALLOWED_PREFIX = "Tattvavada/"
FUZZY_TITLE_RATIO = 0.90
# The fuzzy pass tolerates one letter fewer of shared author name (a scribal slip
# such as राघवेन्दतीर्थः). Rows a person has checked and rejected go here.
FUZZY_AUTHOR_OVERLAP = 7
FUZZY_DENY = {
    "r2766",  # a tippani by Maudgara, not by the layer's default author (Ānandatīrtha)
}

sys.path.insert(0, str(ROOT / "tools"))
from parasavarna import to_anusvara  # noqa: E402

_FOLD_MAP = str.maketrans({"ष": "श", "ी": "ि", "ू": "ु", "ॄ": "ृ", "ई": "इ", "ऊ": "उ", "ळ": "ल",
                           "ङ": "न", "ञ": "न", "ण": "न", "व": "ब", "ॉ": "ा", "द": "त", "ध": "थ"})


def fold(s: str) -> str:
    """Skeleton of a title/name that ignores scribal spelling differences."""
    s = to_anusvara(unicodedata.normalize("NFC", norm(s)))
    s = s.translate(_FOLD_MAP)
    s = re.sub(r"[ःंम्ँ]+$", "", s)
    return s.replace("्", "")


def _bigrams(s: str) -> set:
    return {s[i:i + 2] for i in range(len(s) - 1)}


def overlap_folded(a: str, b: str) -> int:
    a, b = fold(a), fold(b)
    if not a or not b:
        return 0
    return SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b)).size


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
        if not g["path"][5:-10].startswith(ALLOWED_PREFIX):
            continue
        idx[title].append((g["path"][5:-10], author, bool(g.get("populated"))))
    if MANIFEST.is_file():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for slug, entry in (man.get("granthas") or {}).items():
            title = entry.get("title") or ""
            # "Mula" is the layer-title fallback, not a work's name.
            if not title or title == "Mula":
                continue
            spine = entry.get("spineSlug") or "mula"
            if not slug.startswith(ALLOWED_PREFIX):
                continue
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
    # Links a scholar confirmed on the catalogue page (data/... paths). Only
    # Tattvavada ones are taken; the hand-made file above wins on a clash.
    if SCHOLAR.is_file():
        for rid, path in (json.loads(SCHOLAR.read_text(encoding="utf-8")).get("links") or {}).items():
            slug = path[5:-10] if path.startswith("data/") and path.endswith("/data.json") else path
            if slug.startswith(ALLOWED_PREFIX) and rid not in manual:
                manual[rid] = {"slug": slug, "populated": True}

    links: dict[str, dict] = {}
    title_only = 0
    for item in catalog["items"]:
        rid = item["id"]
        if item["row"] > MAX_SHEET_ROW:
            continue
        if rid in manual:
            if not str(manual[rid].get("slug", "")).startswith(ALLOWED_PREFIX):
                sys.exit(f"override {rid} links outside {ALLOWED_PREFIX}: refused")
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

    # ---- second pass: same work, spelt differently --------------------------
    folded: dict[str, list] = collections.defaultdict(list)
    for k, v in idx.items():
        folded[fold(k)].extend(v)
    grams = {k: _bigrams(k) for k in folded}
    fuzzy = 0
    for item in catalog["items"]:
        rid = item["id"]
        if item["row"] > MAX_SHEET_ROW or rid in links or rid in FUZZY_DENY:
            continue
        fk = fold(item.get("grantha"))
        if not fk:
            continue
        fg = _bigrams(fk)
        best = None
        for k, kg in grams.items():
            if abs(len(k) - len(fk)) > 3 or len(fg & kg) / max(1, len(fg | kg)) < 0.5:
                continue
            ratio = SequenceMatcher(None, fk, k).ratio()
            if ratio < FUZZY_TITLE_RATIO:
                continue
            for slug, author, populated in folded[k]:
                score = overlap_folded(item.get("karta"), author)
                if score >= FUZZY_AUTHOR_OVERLAP and (best is None or (ratio, score) > best[:2]):
                    best = (ratio, score, slug, populated)
        if best:
            links[rid] = {"slug": best[2], "populated": best[3], "authorOverlap": best[1],
                          "titleScore": round(best[0], 3), "by": "title~+author"}
            fuzzy += 1

    # ---- third pass: short sheet title inside a longer library title ---------
    contained = 0
    for item in catalog["items"]:
        rid = item["id"]
        if item["row"] > MAX_SHEET_ROW or rid in links or rid in FUZZY_DENY:
            continue
        fk = fold(item.get("grantha"))
        core = fk[1:] if fk.startswith("अ") else fk   # अनुव्याख्यान after सूत्र → त्रानुव्याख्यान
        if len(core) < 6 or len(fk) < 7:
            continue
        best = None
        for k, entries in folded.items():
            if k == fk or core not in k:
                continue
            share = len(fk) / len(k)
            if share < 0.5:
                continue
            for slug, author, populated in entries:
                score = overlap_folded(item.get("karta"), author)
                if score >= FUZZY_AUTHOR_OVERLAP and (best is None or (share, score) > best[:2]):
                    best = (share, score, slug, populated)
        if best:
            links[rid] = {"slug": best[2], "populated": best[3], "authorOverlap": best[1],
                          "titleShare": round(best[0], 2), "by": "title-in+author"}
            contained += 1

    # ---- library-only: Tattvavada works no sheet row (1..1200) describes -----
    # "Link every Tattvavada work" (the lead). A held work with no row must still
    # be findable, so it is listed as its own entry, marked as not from the sheet.
    lib = json.loads(LIBRARY.read_text(encoding="utf-8"))
    linked_slugs = [v["slug"] for v in links.values()]
    works: dict[str, list] = collections.OrderedDict()
    for g in lib["granthas"]:
        slug = g["path"][5:-10]
        if not slug.startswith(ALLOWED_PREFIX) or not g.get("populated") or "DasaSahitya" in slug:
            continue
        parts = slug.split("/")
        depth = 4 if (parts[1] == "SarvaMula" or (parts[1] == "Itara" and len(parts) > 2 and parts[2] in ("Kavya", "Stotra"))) else 3
        works.setdefault("/".join(parts[:depth]), []).append(g)
    library_only = []
    for wd, gs in works.items():
        if any(x == wd or x.startswith(wd + "/") for x in linked_slugs):
            continue
        gs.sort(key=lambda g: (not g["path"].endswith("/mula/data.json"), g["path"]))
        first = gs[0]
        title = re.split(r"\s+(?:—|सर्गः)", first.get("title") or wd.split("/")[-1])[0].strip()
        karta = (first.get("facets") or {}).get("default_author") or ""
        # Attach to the catalogue's own author entry when the names share a long
        # run (Ānandatīrtha in either spelling), so the work lands under the
        # same person; the most-used spelling wins.
        cands = [(overlap_folded(karta, a["canonical"]), a["count"], a["id"], a["canonical"])
                 for a in catalog["masters"]["authors"] if karta]
        cands = [x for x in cands if x[0] >= MIN_AUTHOR_OVERLAP]
        kid, kname = (max(cands)[2:] if cands else ("", karta))
        library_only.append({"id": "L" + str(len(library_only) + 1), "grantha": title,
                             "karta": kname, "kartaId": kid,
                             "slug": first["path"][5:-10], "folder": wd[len(ALLOWED_PREFIX):]})

    assert all(v["slug"].startswith(ALLOWED_PREFIX) for v in links.values()), "link outside Tattvavada"
    payload = {
        "schema": "anukramani_links_v1",
        "note": ("Derived from the catalogue and the library by "
                 "tools/anukramani/build_links.py. Not hand-edited: put manual "
                 "links in anukramani_links.overrides.json, which wins."),
        "catalogRows": len(catalog["items"]),
        "maxSheetRow": MAX_SHEET_ROW,
        "allowedPrefix": ALLOWED_PREFIX,
        "linked": len(links),
        "libraryOnly": library_only,
        "links": dict(sorted(links.items(), key=lambda kv: int(kv[0][1:]))),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"

    print(f"{len(catalog['items'])} catalogue rows")
    print(f"   {len(links)} linked ({sum(1 for v in links.values() if v['by']=='manual')} by hand)")
    print(f"   {fuzzy} of those linked by the spelling-tolerant second pass")
    print(f"   {contained} more where the sheet's short title sits inside a longer library title")
    print(f"   {len(library_only)} held Tattvavada works have no sheet row (listed as library-only)")
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
