#!/usr/bin/env python3
"""Carry the द्वैतवेदान्तग्रन्थानुक्रमणी catalogue's findings back into the
rest of the project.

The catalogue (dge/data/catalogs/dvaita_grantha_anukramani.json) knows, for
740 distinct authors, every work the sheet attributes to them and how those
works nest. Guru Paramparā knows 696 ācāryas but lists works on only 53 of
them, as free English text. author_aliases.json declares 21 canonical
people and 11 spellings. This script joins the three.

TWO OUTPUTS, DELIBERATELY DIFFERENT IN KIND
-------------------------------------------
1. dge/data/catalogs/author_works_index.json -- GENERATED, always safe to
   rewrite. Keyed by the project's own person id (which is the parampara
   node id, per author_aliases.json's own convention), it lists that
   person's catalogued works so guru-data.js can show them on every Guru
   Paramparā view without either side duplicating the other's data.

2. Proposed additions to dge/data/author_aliases.json -- that file says of
   itself "Hand-maintained … leave it unmapped when it is not [certain]",
   so nothing is written without an explicit flag, and the two kinds of
   addition are separated because they are not equally safe:

     --apply             adds SPELLINGS to a person the file already
                         declares. Mechanical: the identity is the
                         project's own, this only teaches it another way
                         the corpus spells that name.
     --apply-new-persons adds a PERSON, for an author matched to an
                         existing parampara node. That is an identity
                         claim made by a fold-and-romanise match, so it
                         stays behind its own flag.

A match confirmed by a scholar in the catalogue page (recorded in
dvaita_grantha_anukramani.overrides.json under `links`) is always
preferred over a derived one, and is reported as confirmed.

Run:  python3 tools/sync_dvaita_crosslinks.py            # dry run, report only
      python3 tools/sync_dvaita_crosslinks.py --apply    # + write alias spellings
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timezone

CATALOGUE = "dge/data/catalogs/dvaita_grantha_anukramani.json"
OVERRIDES = "dge/data/catalogs/dvaita_grantha_anukramani.overrides.json"
ALIASES = "dge/data/author_aliases.json"
PARAMPARA = "dge/guru-parampara/data/parampara.json"
LIBRARY = "dge/data/library.json"
WORKS_INDEX = "dge/data/catalogs/author_works_index.json"


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def parampara_nodes(doc):
    """parampara.json's nodes are a list in the committed file, but the
    generated split files use a map -- accept either."""
    nodes = (doc or {}).get("nodes") or []
    if isinstance(nodes, dict):
        return nodes
    return {n.get("id"): n for n in nodes if n.get("id")}


def resolve_person_ids(cat, overrides):
    """author master id -> project person id, from three sources in order of
    authority: a scholar's confirmation, an author_aliases hit, a parampara
    node hit."""
    out = {}
    source = {}
    cross = cat.get("crossLinks", {})
    for p in cross.get("parampara", []):
        if p.get("kind") == "author" and p.get("authorId"):
            out[p["authorId"]] = p["nodeId"]
            source[p["authorId"]] = "parampara-node"
    for a in cross.get("authorAliases", []):
        out[a["authorId"]] = a["personId"]
        source[a["authorId"]] = "author-aliases"
    for key, val in (overrides.get("links") or {}).items():
        if key.startswith("kar-") and isinstance(val, str) and val:
            out[key] = val
            source[key] = "confirmed"
    return out, source


def build_works_index(cat, person_of, source):
    by_id = {it["id"]: it for it in cat["items"]}
    author_master = {a["id"]: a for a in cat["masters"]["authors"]}
    digitised = set()
    for m in cat.get("crossLinks", {}).get("library", []):
        digitised.add(m["id"])

    grouped = {}
    for it in cat["items"]:
        pid = person_of.get(it.get("kartaId"))
        if not pid or not it["grantha"]:
            continue
        parent = by_id.get(it.get("parentId") or "")
        grouped.setdefault(pid, {"authorIds": set(), "works": []})
        grouped[pid]["authorIds"].add(it["kartaId"])
        grouped[pid]["works"].append({
            "id": it["id"], "row": it["row"], "title": it["grantha"],
            "parent": parent["grantha"] if parent else None,
            "category": it["vishayaVibhaga"] or it["vibhaga"] or "",
            "digitised": it["id"] in digitised,
        })

    by_person = OrderedDict()
    for pid in sorted(grouped, key=lambda p: -len(grouped[p]["works"])):
        aids = sorted(grouped[pid]["authorIds"])
        # Several author-master entries can land on one person; the one the
        # sheet uses most often is the spelling worth showing.
        primary = max((author_master.get(a, {}) for a in aids),
                      key=lambda m: m.get("count", 0), default={})
        works = sorted(grouped[pid]["works"], key=lambda w: w["row"])
        by_person[pid] = {
            "authorIds": aids,
            "canonical": primary.get("canonical", ""),
            "iast": primary.get("iast", ""),
            "matchedVia": source.get(aids[0], "derived"),
            "count": len(works),
            "digitisedCount": sum(1 for w in works if w["digitised"]),
            "works": works,
        }
    return by_person


def propose_alias_changes(cat, aliases, para, person_of, source):
    """Spellings to teach author_aliases, and persons it does not yet know."""
    persons = aliases.get("persons") or {}
    known_spellings = set(aliases.get("aliases") or {})
    nodes = parampara_nodes(para)
    author_master = {a["id"]: a for a in cat["masters"]["authors"]}

    add_aliases, add_persons = OrderedDict(), OrderedDict()
    for author_id, pid in sorted(person_of.items()):
        m = author_master.get(author_id)
        if not m:
            continue
        for v in m["variants"]:
            if v["value"] not in known_spellings:
                add_aliases[v["value"]] = pid
        if pid not in persons:
            node = nodes.get(pid) or {}
            add_persons[pid] = {
                "parampara": True,
                "name_sa": m["canonical"],
                "name_en": node.get("name") or m["iast"],
                "_matchedVia": source.get(author_id, "derived"),
                "_catalogueCount": m["count"],
            }
    return add_aliases, add_persons


# Only these library paths get their author normalised. The project lead's
# instruction: "in library this should happen only for SarvamUlagrantha and
# vedanta/dvaita specific granthas. not other ones like vedas or sahitya" --
# this catalogue is a Dvaita bibliography and has no authority over how the
# Vedas, kavya or dasa sahitya spell their authors.
LIBRARY_AUTHOR_SCOPE = ("dge/data/darshana/vedanta/dvaita/",)


def canonical_author_map(aliases):
    """Every spelling the project knows -> that person's canonical Devanagari
    name. Devanagari is the target because the reader transliterates from it,
    so 'Sri Madhvacharya' becomes श्रीमदानन्दतीर्थभगवत्पादाचार्यः and not the
    other way round."""
    from import_dvaita_grantha_anukramani import iast as _iast, join_key as _jk
    out = {}
    persons = aliases.get("persons") or {}
    for spelling, pid in (aliases.get("aliases") or {}).items():
        name_sa = (persons.get(pid) or {}).get("name_sa")
        if name_sa:
            k = _jk(_iast(spelling))
            if k:
                out[k] = name_sa
    for pid, p in persons.items():
        if not p.get("name_sa"):
            continue
        for form in (p.get("name_sa"), p.get("name_en")):
            if form:
                k = _jk(_iast(form))
                if k:
                    out.setdefault(k, p["name_sa"])
    return out


def patch_default_author(path, new_value):
    """Rewrite just the default_author string in a data.json, leaving the rest
    of the file byte-for-byte alone. A json round-trip would reformat files up
    to 2.6 MB and bury a one-word change in a whole-file diff."""
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    pattern = re.compile(r'("default_author"\s*:\s*)"((?:[^"\\]|\\.)*)"')
    m = pattern.search(text)
    if not m or m.group(2) == new_value:
        return False
    escaped = json.dumps(new_value, ensure_ascii=False)
    patched = text[:m.start()] + m.group(1) + escaped + text[m.end():]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(patched)
    return True


def sync_library_authors(aliases, apply_it):
    library = load(LIBRARY, {}) or {}
    canon = canonical_author_map(aliases)
    from import_dvaita_grantha_anukramani import iast as _iast, join_key as _jk

    planned, unmapped, changed_files = [], {}, 0
    for g in library.get("granthas", []):
        path = g.get("path", "")
        if not path.startswith(LIBRARY_AUTHOR_SCOPE):
            continue
        cur = (g.get("facets") or {}).get("default_author") or ""
        if not cur:
            continue
        target = canon.get(_jk(_iast(cur)))
        if target is None:
            unmapped[cur] = unmapped.get(cur, 0) + 1
        elif target != cur:
            planned.append((path, cur, target))

    if apply_it and planned:
        by_path = {g["path"]: g for g in library.get("granthas", [])}
        for path, _cur, target in planned:
            by_path[path].setdefault("facets", {})["default_author"] = target
            if patch_default_author(path, target):
                changed_files += 1
        # indent=1 is what the committed file actually uses; writing it any
        # other way reformats all 17,919 lines and buries the real change.
        with open(LIBRARY, "w", encoding="utf-8") as fh:
            json.dump(library, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    return planned, unmapped, changed_files


DASA_INDEX = "dge/data/DvaitaVedanta/Itara/DasaSahitya/index.json"


def dasa_alias_proposals(cat, overrides, aliases, person_of):
    """Kannada composer names to teach author_aliases, for the dasa-sahitya
    joins a scholar has actually confirmed.

    Never for a merely proposed one. The join is made on a bare given name,
    and नरसिंहः / राघवेन्द्रः are among the commonest names in the tradition --
    a tikakara and a Kannada composer sharing one is no evidence at all that
    they are one person. Writing that automatically would be inventing an
    identity, so the confirmation in the overrides is the whole authority
    here; without one this returns nothing.
    """
    by_slug = {c["slug"]: c for c in (load(DASA_INDEX, {}) or {}).get("composers", [])}
    known = set(aliases.get("aliases") or {})
    proposals, unconfirmed = OrderedDict(), []
    for x in cat.get("crossLinks", {}).get("dasaSahitya", []):
        author_id = x.get("authorId")
        confirmed = (overrides.get("links") or {}).get("dasa:" + str(author_id))
        if not confirmed:
            unconfirmed.append(x)
            continue
        pid = person_of.get(author_id)
        if not pid:
            # Confirmed against a composer, but the catalogue author is not
            # tied to a person yet -- there is nothing to hang the spelling on.
            continue
        name = (by_slug.get(confirmed) or {}).get("composer") or x.get("composer")
        if name and name not in known:
            proposals[name] = pid
    return proposals, unconfirmed


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write new SPELLINGS into author_aliases.json for people it already declares")
    ap.add_argument("--apply-new-persons", action="store_true",
                    help="also add people matched to a parampara node (an identity claim)")
    ap.add_argument("--no-index", action="store_true", help="skip writing the works index")
    ap.add_argument("--apply-library-authors", action="store_true",
                    help="normalise facets.default_author in library.json and the matching "
                         "data.json files, for the Dvaita subtree only")
    args = ap.parse_args(argv)

    cat = load(CATALOGUE)
    if not cat:
        print(f"missing {CATALOGUE} — run tools/import_dvaita_grantha_anukramani.py first")
        return 1
    overrides = load(OVERRIDES, {}) or {}
    aliases = load(ALIASES, {}) or {}
    para = load(PARAMPARA, {}) or {}

    person_of, source = resolve_person_ids(cat, overrides)
    index = build_works_index(cat, person_of, source)
    add_aliases, add_persons = propose_alias_changes(cat, aliases, para, person_of, source)

    if not args.no_index:
        write_json(WORKS_INDEX, {
            "_readme": [
                "GENERATED by tools/sync_dvaita_crosslinks.py — do not hand-edit.",
                "Maps a project person id (the parampara.json node id) to the works the",
                "द्वैतवेदान्तग्रन्थानुक्रमणी catalogue attributes to that person, so every Guru",
                "Paramparā view can show them without duplicating the catalogue.",
                "matchedVia: confirmed (a scholar accepted it in the catalogue page) |",
                "author-aliases | parampara-node.",
            ],
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "byPerson": index,
        })

    total_works = sum(p["count"] for p in index.values())
    confirmed = sum(1 for p in index.values() if p["matchedVia"] == "confirmed")
    print(f"works index: {len(index)} people, {total_works} works "
          f"({confirmed} matched by a scholar's confirmation)")
    for pid, p in list(index.items())[:8]:
        print(f"    {pid:22s} {p['count']:4d} works ({p['digitisedCount']} digitised)  {p['canonical']}")

    print(f"\nauthor_aliases.json proposals:")
    print(f"  {len(add_aliases)} spellings for people it already declares")
    for s, pid in list(add_aliases.items())[:8]:
        print(f"    {s!r} -> {pid}")
    print(f"  {len(add_persons)} people it does not yet declare")
    for pid, p in list(add_persons.items())[:8]:
        print(f"    {pid:22s} {p['name_sa']}  ({p['_catalogueCount']} works, via {p['_matchedVia']})")

    planned, unmapped, changed_files = sync_library_authors(aliases, args.apply_library_authors)
    print(f"\nlibrary authors (Dvaita subtree only):")
    print(f"  {len(planned)} entries whose author spelling would be normalised")
    for path, cur, tgt in planned[:6]:
        print(f"    {cur!r} -> {tgt!r}")
    print(f"  {len(unmapped)} spellings the project does not yet map to a person")
    if args.apply_library_authors:
        print(f"  wrote library.json and {changed_files} data.json files")
    else:
        print("  (pass --apply-library-authors to write them)")

    dasa_add, dasa_pending = dasa_alias_proposals(cat, overrides, aliases, person_of)
    print(f"\ndasa sahitya:")
    print(f"  {len(dasa_add)} Kannada composer names to add, from confirmed joins")
    for name, pid in dasa_add.items():
        print(f"    {name!r} -> {pid}")
    print(f"  {len(dasa_pending)} joins still awaiting a scholar's confirmation")
    for x in dasa_pending:
        print(f"    {x['canonical']} ~ {x.get('composer') or x['slug']}  (unconfirmed, not written)")
    add_aliases.update(dasa_add)

    if not (args.apply or args.apply_new_persons):
        print("\ndry run — pass --apply to add the spellings, "
              "--apply-new-persons to also add the people")
        return 0

    aliases.setdefault("persons", {})
    aliases.setdefault("aliases", {})
    wrote = 0
    if args.apply:
        for spelling, pid in add_aliases.items():
            if pid in aliases["persons"] or args.apply_new_persons:
                aliases["aliases"][spelling] = pid
                wrote += 1
    added_people = 0
    if args.apply_new_persons:
        for pid, p in add_persons.items():
            entry = {k: v for k, v in p.items() if not k.startswith("_")}
            aliases["persons"][pid] = entry
            added_people += 1
    aliases["aliases"] = OrderedDict(sorted(aliases["aliases"].items()))
    write_json(ALIASES, aliases)
    print(f"\nwrote {ALIASES}: +{wrote} spellings, +{added_people} people")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
