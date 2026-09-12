#!/usr/bin/env python3
"""Import the द्वैतवेदान्तग्रन्थानुक्रमणी bibliography (a scholar's Excel
catalogue of every known Dvaita Vedanta work, digitised or not) into the
committed JSON that dvaita-grantha-anukramani/ reads.

This is a BIBLIOGRAPHY, not the corpus itself: most rows have no digitised
text anywhere in data/ yet (many are marked अनुपलब्ध/manuscript-only).

WHAT THE SHEET ACTUALLY IS
--------------------------
Not a flat list. The "Link" column (D) names a row's parent work BY TITLE,
so a टीका/टिप्पणी/विवरणम् row points back at the मूलम् or टीका it comments
on. Sheet order is depth-first, which is the only thing that makes an
ambiguous title like "जयतीर्थीय-टीका" -- typed identically once per
prakarana, since Jayatirtha wrote one for each of the दशप्रकरण -- resolvable
at all: resolve_parents walks BACKWARD to the nearest earlier row with a
matching title, never just any row with that title.

WHAT THIS SCRIPT DERIVES ON TOP OF THE SHEET
--------------------------------------------
Everything below is a SUGGESTION for a scholar to accept or reject in the
page's review tabs. None of it silently rewrites the sheet's own data:

* masters -- one canonical entry per category / author / work-title, with
  every spelling variant found attached to it. The sheet spells one term
  several ways ('भाष्यम्' ×11 and 'भाष्यम' ×1; 'मूलम्' ×202 and 'मूल' ×2),
  and the three tag columns share ONE vocabulary space rather than three
  (मूलम् appears in both विभागः and विषयविभागः), so the category master is
  built across all three columns at once.
* suggestions.parentLinks -- ~2,180 rows carry no Link at all, yet many are
  plainly commentaries: 'प्रमाणपद्धतिटीका' ×18 sits at depth 0 while
  'प्रमाणपद्धतिः' is a row of its own. Where a parentless row's title is a
  known title plus a commentary word, that parent is suggested.
* crossLinks -- candidate joins to data/library.json (what is actually
  digitised), guru-parampara's own works lists, dāsa-sāhitya composers, and
  data/author_aliases.json's canonical person ids.

Duplicate detection stays split three ways on purpose (see detect_duplicates).

Run:  python3 tools/import_dvaita_grantha_anukramani.py <source.xlsx> \
        --out data/catalogs/dvaita_grantha_anukramani.json

Requires openpyxl and indic_transliteration (both local, no network).
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import unicodedata
from collections import defaultdict

import openpyxl
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

SHEET_NAME = "dwita.books.index."
# Spreadsheet column letter -> our field name. Columns with no header in
# row 1 (I, everything from M on) carry no data and are skipped.
COLUMNS = {
    "B": "status",          # 'publish' -- publication shorthand (vmp, s, no, ...)
    "C": "grantha",         # ग्रन्थनाम -- the work's title
    "D": "linkRaw",         # Link -- parent work's title as typed (ambiguous; resolved below)
    "E": "karta",           # ग्रन्थकर्तृ -- author
    "F": "vibhaga",         # विभागः -- broad division
    "G": "vishayaVibhaga",  # विषयविभागः -- finer division
    "H": "prasthana",       # द्वैत-वेदान्तग्रन्थानुक्रमणिका -- corpus/prasthana tag
    "J": "mention",         # free-text notes (manuscript codes, remarks)
    "K": "sourceLibrary",   # manuscript repository (baroda, saraswatimahal, ...)
    "L": "availability",    # हस्तप्रति / नोपलब्धम् / ...
}
TAG_FIELDS = ("vibhaga", "vishayaVibhaga", "prasthana")

# Words that mark a title as a commentary ON something else. Only the
# unambiguous ones: 'सङ्ग्रहः' and 'दीपिका' are deliberately absent because
# 'तारतम्यसङ्ग्रहः' is a work in its own right, not a commentary on
# 'तारतम्य', and suggesting otherwise would bury the real finds.
COMMENTARY_SUFFIXES = [
    "टिप्पणी", "टिप्पणि", "टीका", "व्याख्यानम्", "व्याख्या",
    "भाष्यम्", "भाष्य", "खण्डार्थः", "खण्डार्थ", "विवरणम्",
    "विवृतिः", "भावदीपः", "पदार्थदीपिका",
]
HONORIFICS = ("श्रीमद्", "श्रीमत्", "श्री")


def norm(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value)).strip())


def iast(deva):
    """Devanagari -> IAST. Left as-is when the string isn't Devanagari
    (a few cells hold latin codes like 'S.M.T')."""
    if not deva or not re.search(r"[ऀ-ॿ]", deva):
        return deva
    try:
        return transliterate(deva, sanscript.DEVANAGARI, sanscript.IAST)
    except Exception:
        return deva


def ascii_fold(s):
    """Lowercase, diacritic-free, alphanumeric-only."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def join_key(s):
    """The key both sides of a cross-corpus join reduce to before comparing.
    One side is IAST off the Devanagari ('jayatīrthaḥ'), the other bare
    English ('Jayatirtha'), so beyond dropping diacritics this also drops a
    final 'h' -- almost always the nominative visarga, which the English
    spellings in library.json and parampara.json simply don't write. Without
    it 'jayatirthah' and 'jayatirtha' never meet."""
    k = ascii_fold(s)
    return k[:-1] if k.endswith("h") else k


def fold_term(s):
    """Fold a category term to its identity: whitespace/punctuation out,
    trailing visarga/anusvara/virama-म variants normalised away. Merges
    'भाष्यम्'/'भाष्यम' and 'खण्डन-मण्डनग्रन्थः'/'खण्डनमण्डनग्रन्थः'."""
    s = re.sub(r"[\s\-\.।॥,()]+", "", unicodedata.normalize("NFC", s or "").strip())
    return re.sub(r"(म्|म|ः|ं|्)+$", "", s)


def fold_person(s):
    """Same idea for a person, plus the honorific prefix, so 'जयतीर्थः',
    'जयतीर्थ' and 'श्रीजयतीर्थः' fold together."""
    s = re.sub(r"[\s\-\.।॥,()]+", "", unicodedata.normalize("NFC", s or "").strip())
    for h in HONORIFICS:
        if s.startswith(h):
            s = s[len(h):]
            break
    return re.sub(r"(म्|ः|ं|्)+$", "", s)


def fold_title(s):
    s = re.sub(r"[\s\-\.।॥,()]+", "", unicodedata.normalize("NFC", s or "").strip())
    return re.sub(r"(ः|ं)+$", "", s)


def read_rows(path):
    from openpyxl.utils import column_index_from_string
    ws = openpyxl.load_workbook(path, data_only=True)[SHEET_NAME]
    col_idx = {f: column_index_from_string(L) for L, f in COLUMNS.items()}
    rows = []
    for r in range(2, ws.max_row + 1):
        rec = {f: norm(ws.cell(row=r, column=i).value) for f, i in col_idx.items()}
        if not rec["grantha"] and not rec["karta"]:
            continue  # a genuinely blank spreadsheet row
        rec["row"] = r
        rows.append(rec)
    return rows


def resolve_parents(rows):
    """Bind each row to the NEAREST EARLIER row whose title equals this row's
    linkRaw. Falls back to the nearest row in either direction when no
    earlier one matches (a few rows name a parent typed further down), and
    flags unresolvedLink when no row anywhere carries that title."""
    by_title = defaultdict(list)
    for i, rec in enumerate(rows):
        if rec["grantha"]:
            by_title[rec["grantha"]].append(i)

    for i, rec in enumerate(rows):
        rec["parentIdx"] = None
        rec["unresolvedLink"] = False
        link = rec["linkRaw"]
        if not link:
            continue
        candidates = by_title.get(link)
        if not candidates:
            rec["unresolvedLink"] = True
            continue
        pos = bisect.bisect_left(candidates, i) - 1
        rec["parentIdx"] = candidates[pos] if pos >= 0 else min(candidates, key=lambda j: j - i)


def build_paths(rows):
    """Ancestor chain, depth and breadcrumb per row. Capped at the row count
    so a malformed sheet producing a cycle cannot hang the build."""
    ids = [f"r{rec['row']}" for rec in rows]
    n = len(rows)
    for i, rec in enumerate(rows):
        chain, seen, cur, steps = [i], {i}, rec["parentIdx"], 0
        while cur is not None and steps < n:
            if cur in seen:
                break
            chain.append(cur)
            seen.add(cur)
            cur = rows[cur]["parentIdx"]
            steps += 1
        chain.reverse()
        rec["path"] = [ids[j] for j in chain]
        rec["depth"] = len(chain) - 1
        rec["breadcrumb"] = " › ".join(rows[j]["grantha"] or "?" for j in chain)


def detect_duplicates(rows):
    """Keyed on the RESOLVED parent, never on linkRaw's raw text -- linkRaw
    is deliberately ambiguous, so keying on it would lump together rows that
    merely share a commentary-title convention while sitting under entirely
    different mula works.

    Three tiers, kept separate because collapsing them would bury a few
    hundred real repeat-entry mistakes under normal structural repetition."""
    exact_key, npk_key, name_key = defaultdict(list), defaultdict(list), defaultdict(list)
    for i, rec in enumerate(rows):
        pm = rec["parentIdx"] if rec["parentIdx"] is not None else ("unresolved:" + rec["linkRaw"])
        full = (rec["status"], rec["grantha"], pm, rec["karta"], rec["vibhaga"],
                rec["vishayaVibhaga"], rec["prasthana"], rec["mention"],
                rec["sourceLibrary"], rec["availability"])
        exact_key[full].append(i)
        if rec["grantha"]:
            npk_key[(rec["grantha"], pm, rec["karta"])].append(i)
            name_key[rec["grantha"]].append(i)

    def gid(prefix, key):
        return prefix + hashlib.sha1("|".join(str(k) for k in key).encode("utf-8")).hexdigest()[:10]

    exact_groups, grouped = [], set()
    for key, idxs in exact_key.items():
        if len(idxs) > 1 and key[1]:
            g = gid("dup-", key)
            exact_groups.append({"id": g, "ids": [f"r{rows[i]['row']}" for i in idxs]})
            grouped.update(idxs)
            for i in idxs:
                rows[i]["exactDuplicateGroup"] = g

    npk_groups = []
    for key, idxs in npk_key.items():
        if len(idxs) > 1 and not all(i in grouped for i in idxs):
            g = gid("npk-", key)
            npk_groups.append({"id": g, "ids": [f"r{rows[i]['row']}" for i in idxs]})
            for i in idxs:
                if "exactDuplicateGroup" not in rows[i]:
                    rows[i]["nameParentKartaGroup"] = g

    collisions = []
    for key, idxs in name_key.items():
        if len(idxs) > 1 and (len({rows[i]["karta"] for i in idxs}) > 1
                              or len({rows[i]["linkRaw"] for i in idxs}) > 1):
            g = gid("coll-", (key,))
            collisions.append({"id": g, "name": key, "ids": [f"r{rows[i]['row']}" for i in idxs]})
            for i in idxs:
                rows[i].setdefault("nameCollisionGroup", g)

    return exact_groups, npk_groups, collisions


def drop_exact_duplicates(rows):
    """A row repeated with every column identical is a data-entry artifact,
    not a catalogue entry: 'ब्रह्मसूत्रभाष्यटीकाव्याख्या' by Rāghavendra fills
    26 consecutive rows. Keep the first, drop the rest.

    The one qualification, and it matters: sameness includes the RESOLVED
    parent, not just the typed columns. Sixteen groups have identical
    columns — same title, same author, same Link text — and yet belong in
    different places, because the Link text is itself ambiguous: Vyāsatīrtha's
    मन्दारमञ्जरी appears four times under 'जयतीर्थीय-टीका' because he wrote one
    on the ṭīkā of each of four prakaraṇas. Collapsing those would delete real
    works. They stay, and surface instead as name collisions.

    Returns (kept_rows, dropped_report)."""
    seen, kept, dropped = {}, [], []
    for rec in rows:
        pm = rec["parentIdx"] if rec["parentIdx"] is not None else ("unresolved:" + rec["linkRaw"])
        key = (rec["status"], rec["grantha"], pm, rec["karta"], rec["vibhaga"],
               rec["vishayaVibhaga"], rec["prasthana"], rec["mention"],
               rec["sourceLibrary"], rec["availability"])
        if not rec["grantha"]:
            kept.append(rec)
            continue
        if key in seen:
            seen[key].append(rec["row"])
            dropped.append({"row": rec["row"], "keptRow": seen[key][0], "grantha": rec["grantha"]})
        else:
            seen[key] = [rec["row"]]
            kept.append(rec)
    return kept, dropped


def build_masters(rows):
    """One canonical entry per category / author / title, carrying every
    spelling variant that folds onto it. The canonical form is simply the
    commonest spelling -- a scholar can override it in the page, which is
    the point of shipping the variants rather than silently picking one."""
    def collect(fold_fn, values):
        buckets = defaultdict(lambda: defaultdict(int))
        for raw, where in values:
            buckets[fold_fn(raw)][raw] += 1
        out = []
        for key, spellings in buckets.items():
            ordered = sorted(spellings.items(), key=lambda kv: (-kv[1], kv[0]))
            canonical = ordered[0][0]
            out.append({
                "key": key,
                "canonical": canonical,
                "iast": iast(canonical),
                "count": sum(spellings.values()),
                "variants": [{"value": v, "count": c} for v, c in ordered],
            })
        return sorted(out, key=lambda e: (-e["count"], e["canonical"]))

    # Categories: ONE vocabulary shared by all three tag columns.
    cat_values, used_in = [], defaultdict(set)
    for rec in rows:
        for f in TAG_FIELDS:
            if rec[f]:
                cat_values.append((rec[f], f))
                used_in[fold_term(rec[f])].add(f)
    categories = collect(fold_term, cat_values)
    for c in categories:
        c["id"] = "cat-" + hashlib.sha1(c["key"].encode("utf-8")).hexdigest()[:8]
        c["usedIn"] = sorted(used_in[c["key"]])

    authors = collect(fold_person, [(r["karta"], "karta") for r in rows if r["karta"]])
    for a in authors:
        a["id"] = "kar-" + hashlib.sha1(a["key"].encode("utf-8")).hexdigest()[:8]

    titles = collect(fold_title, [(r["grantha"], "grantha") for r in rows if r["grantha"]])
    for t in titles:
        t["id"] = "ttl-" + hashlib.sha1(t["key"].encode("utf-8")).hexdigest()[:8]

    return {"categories": categories, "authors": authors, "titles": titles}


def attach_master_ids(rows, masters):
    cat_by_spelling, auth_by_spelling, title_by_spelling = {}, {}, {}
    for c in masters["categories"]:
        for v in c["variants"]:
            cat_by_spelling[v["value"]] = c["id"]
    for a in masters["authors"]:
        for v in a["variants"]:
            auth_by_spelling[v["value"]] = a["id"]
    for t in masters["titles"]:
        for v in t["variants"]:
            title_by_spelling[v["value"]] = t["id"]
    for rec in rows:
        for f in TAG_FIELDS:
            rec[f + "Id"] = cat_by_spelling.get(rec[f]) if rec[f] else None
        rec["kartaId"] = auth_by_spelling.get(rec["karta"]) if rec["karta"] else None
        rec["titleId"] = title_by_spelling.get(rec["grantha"]) if rec["grantha"] else None


def suggest_parents(rows, masters):
    """For a row with NO link whose title reads '<known title> + <commentary
    word>', suggest that known title's row as the parent. ~2,180 rows carry
    no link at all and a good share of them are plainly commentaries -- this
    is what makes them reviewable instead of invisible."""
    by_title_key = defaultdict(list)
    for i, rec in enumerate(rows):
        if rec["grantha"]:
            by_title_key[fold_title(rec["grantha"])].append(i)

    suggestions = []
    for i, rec in enumerate(rows):
        if rec["parentIdx"] is not None or not rec["grantha"] or rec["linkRaw"]:
            continue
        t = fold_title(rec["grantha"])
        for suf in COMMENTARY_SUFFIXES:
            sfold = fold_title(suf)
            if not t.endswith(sfold) or len(t) <= len(sfold) + 3:
                continue
            stem = t[: -len(sfold)]
            cands = [j for j in by_title_key.get(stem, []) if j != i and rows[j]["parentIdx"] is None]
            if not cands:
                cands = [j for j in by_title_key.get(stem, []) if j != i]
            if cands:
                suggestions.append({
                    "id": f"r{rec['row']}",
                    "candidates": [f"r{rows[j]['row']}" for j in cands[:5]],
                    "basis": "title-prefix",
                    "suffix": suf,
                    "confidence": "high" if len(cands) == 1 else "medium",
                })
            break
    return suggestions


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_cross_links(rows, masters, data_dir, repo_root):
    """Candidate joins to the rest of the project. Every match is a
    CANDIDATE for review -- the two sides spell names differently enough
    (one IAST, one bare English, one Kannada) that only an ascii-folded
    phonetic comparison gets them near each other, and that is exactly the
    kind of match a scholar has to confirm."""
    out = {"library": [], "parampara": [], "authorAliases": [], "dasaSahitya": []}

    # --- library.json: what is actually digitised -------------------------
    library = load_json(os.path.join(data_dir, "library.json"), {}) or {}
    lib_index = defaultdict(list)
    for g in library.get("granthas", []):
        title = g.get("title") or ""
        for key in {fold_title(title), join_key(title)}:
            if key:
                lib_index[key].append(g)
    for rec in rows:
        if not rec["grantha"]:
            continue
        keys = {fold_title(rec["grantha"]), join_key(iast(rec["grantha"]))}
        hits = []
        for k in keys:
            for g in lib_index.get(k, []):
                if g["path"] not in [h["path"] for h in hits]:
                    hits.append({"path": g["path"], "title": g.get("title", ""),
                                 "populated": bool(g.get("populated"))})
        if hits:
            out["library"].append({"id": f"r{rec['row']}", "matches": hits[:4]})

    # --- author_aliases.json: the project's canonical person ids ----------
    aliases = load_json(os.path.join(data_dir, "author_aliases.json"), {}) or {}
    person_index = {}

    def index_person(form, pid):
        # An empty key would match every junk author cell ('--', '0') at once.
        for k in (join_key(iast(form)), fold_person(form)):
            if k:
                person_index.setdefault(k, pid)

    for pid, p in (aliases.get("persons") or {}).items():
        for form in (p.get("name_sa"), p.get("name_en"), p.get("name_kn")):
            if form:
                index_person(form, pid)
    for spelling, pid in (aliases.get("aliases") or {}).items():
        index_person(spelling, pid)
    for a in masters["authors"]:
        keys = [k for k in (join_key(a["iast"]), a["key"]) if k]
        pid = next((person_index[k] for k in keys if k in person_index), None)
        if pid:
            out["authorAliases"].append({"authorId": a["id"], "canonical": a["canonical"],
                                          "personId": pid})

    # --- guru-parampara: node names, and the works those nodes list -------
    para = load_json(os.path.join(repo_root, "pages", "guru-parampara", "data", "parampara.json"), {}) or {}
    nodes = para.get("nodes") or {}
    if isinstance(nodes, dict):
        node_items = list(nodes.items())
    else:  # a list of node dicts
        node_items = [(n.get("id"), n) for n in nodes]
    node_by_name = {}
    works_index = defaultdict(list)
    for nid, n in node_items:
        if not nid:
            continue
        node_by_name.setdefault(join_key(n.get("name", "")), nid)
        for w in (n.get("works") or []):
            # 'Tattvapradipa (comm. on Brahmasutra Bhashya)' -> tattvapradipa
            head = re.split(r"[(–—,]", w)[0]
            key = join_key(head)
            if key:
                works_index[key].append({"nodeId": nid, "node": n.get("name", ""), "work": w})
    for a in masters["authors"]:
        nid = node_by_name.get(join_key(a["iast"]))
        if nid:
            out["parampara"].append({"kind": "author", "authorId": a["id"],
                                      "canonical": a["canonical"], "nodeId": nid})
    for t in masters["titles"]:
        hits = works_index.get(join_key(t["iast"]))
        if hits:
            out["parampara"].append({"kind": "work", "titleId": t["id"],
                                      "canonical": t["canonical"], "matches": hits[:3]})

    # --- dāsa sāhitya composers (Kannada) ---------------------------------
    dasa = load_json(os.path.join(data_dir, "DvaitaVedanta/Itara/DasaSahitya", "index.json"), {}) or {}
    dasa_index = {}
    for c in (dasa.get("composers") or []):
        dasa_index.setdefault(join_key(c.get("slug", "")), c)
    for a in masters["authors"]:
        c = dasa_index.get(join_key(a["iast"]))
        if c:
            out["dasaSahitya"].append({"authorId": a["id"], "canonical": a["canonical"],
                                        "slug": c.get("slug"), "composer": c.get("composer")})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="path to the .xlsx catalogue")
    parser.add_argument("--out", default="data/catalogs/dvaita_grantha_anukramani.json")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)

    rows = read_rows(args.source)
    resolve_parents(rows)
    # Drop the all-columns-identical repeats, then resolve again: parentIdx
    # is a position in the row list, so it has to be recomputed once rows
    # have gone, and the nearest-preceding parent of what remains is the
    # binding we actually want.
    rows, dropped_duplicates = drop_exact_duplicates(rows)
    resolve_parents(rows)
    build_paths(rows)
    exact_groups, npk_groups, collisions = detect_duplicates(rows)
    masters = build_masters(rows)
    attach_master_ids(rows, masters)
    parent_suggestions = suggest_parents(rows, masters)
    cross = build_cross_links(rows, masters, args.data_dir, args.repo_root)

    ids = [f"r{rec['row']}" for rec in rows]
    items = []
    for i, rec in enumerate(rows):
        p = rec["parentIdx"]
        items.append({
            "id": ids[i], "row": rec["row"],
            "grantha": rec["grantha"], "titleId": rec["titleId"],
            "karta": rec["karta"], "kartaId": rec["kartaId"],
            "vibhaga": rec["vibhaga"], "vibhagaId": rec["vibhagaId"],
            "vishayaVibhaga": rec["vishayaVibhaga"], "vishayaVibhagaId": rec["vishayaVibhagaId"],
            "prasthana": rec["prasthana"], "prasthanaId": rec["prasthanaId"],
            "status": rec["status"], "availability": rec["availability"],
            "mention": rec["mention"], "sourceLibrary": rec["sourceLibrary"],
            "linkRaw": rec["linkRaw"], "parentId": ids[p] if p is not None else None,
            "unresolvedLink": rec["unresolvedLink"],
            "depth": rec["depth"], "breadcrumb": rec["breadcrumb"],
            "flags": {
                "missingGrantha": not rec["grantha"],
                "missingKarta": not rec["karta"],
                "missingTags": not (rec["vibhaga"] or rec["vishayaVibhaga"] or rec["prasthana"]),
                "unresolvedLink": rec["unresolvedLink"],
                "noParent": p is None,
            },
            "exactDuplicateGroup": rec.get("exactDuplicateGroup"),
            "nameParentKartaGroup": rec.get("nameParentKartaGroup"),
            "nameCollisionGroup": rec.get("nameCollisionGroup"),
        })

    out = {
        "schema": "dvaita_grantha_anukramani",
        "version": 2,
        "title": "द्वैतवेदान्तग्रन्थानुक्रमणी",
        "sourceNote": "Imported from a scholar-compiled Excel bibliography of Dvaita "
                       "Vedanta works, digitised or not. Master lists, parent-link "
                       "suggestions and cross-links are DERIVED and meant for review, "
                       "not applied to the sheet's own data.",
        "sourceSheet": SHEET_NAME,
        "totalRows": len(rows),
        "droppedDuplicates": dropped_duplicates,
        "masters": masters,
        "items": items,
        "suggestions": {"parentLinks": parent_suggestions},
        "crossLinks": cross,
        "duplicates": {
            "exactRowDuplicates": exact_groups,
            "nameParentKartaDuplicates": npk_groups,
            "nameCollisions": collisions,
        },
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    print(f"{len(rows)} rows -> {args.out}  "
          f"({len(dropped_duplicates)} all-columns-identical repeats dropped)")
    print(f"  masters: {len(masters['categories'])} categories, "
          f"{len(masters['authors'])} authors, {len(masters['titles'])} titles")
    for name, key in (("categories", "categories"), ("authors", "authors"), ("titles", "titles")):
        multi = [m for m in masters[key] if len(m["variants"]) > 1]
        print(f"    {name}: {len(multi)} with >1 spelling "
              f"({sum(len(m['variants']) for m in multi)} spellings to review)")
    print(f"  parent-link suggestions: {len(parent_suggestions)}")
    print(f"  cross-links: library {len(cross['library'])}, parampara {len(cross['parampara'])}, "
          f"aliases {len(cross['authorAliases'])}, dasa {len(cross['dasaSahitya'])}")
    print(f"  duplicates: {len(exact_groups)} exact, {len(npk_groups)} name+parent+karta, "
          f"{len(collisions)} name collisions")
    print(f"  rows with no parent: {sum(1 for it in items if it['flags']['noParent'])}")
    print(f"  missing all tags: {sum(1 for it in items if it['flags']['missingTags'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
