#!/usr/bin/env python3
"""
audit_names.py — are the names in step with each other?

The library, the guru-paramparā, the Dāsa Sāhitya corpus and the admin pages
each carry names — of granthas and of the people who wrote them — and until
now nothing checked that they agree. This does, read-only, and says exactly
where they do not:

  titles      library.json entries whose `title` has no Devanagari/Kannada at
              all (an English slug-humanisation like "Mula" or "Tika Jayatirtha",
              which the reader masks with DGE_PATH_LABELS but every other
              consumer sees verbatim), and titles with a garbage tail.
  authors     every distinct spelling of `default_author` / `author` /
              `composer` across the data.json files, which of them map to a
              person id in data/author_aliases.json, and which do not —
              grouped so the same person's spellings are visible side by side.
  taxonomy    `_default_author` values in taxonomy.json that are not names
              (the karmavijaya corruption: commentary body-text as author).
  parampara   `works[]` strings on parampara.json nodes that match no library
              title (they are free text today; the catalogue page needs ids).
  dasa        Dāsa Sāhitya composers whose name resolves to no person id,
              and the Kannada names the reader's fuzzy join cannot match.
  admin       the admin pages' own hardcoded name lists that duplicate a
              registry (ashtadhyayi.html's `who:` strings).

    python3 tools/audit_names.py            # report (markdown on stdout)
    python3 tools/audit_names.py --strict   # exit 1 on the checks marked HARD
    python3 tools/audit_names.py --json out.json

Nothing is written unless --json is given. The conventions this enforces are
in docs/NAMING_CONVENTIONS.md; when they change, change this in the same
commit. HARD checks (fail --strict): a taxonomy `_default_author` that is
plainly not a name (contains a daṇḍa, ends mid-word in "प्र", is URL-encoded);
a library title with a `— <ascii slug>` tail; an alias pointing at an
undeclared id; a Dāsa composer file whose `composer` differs from its index
entry.
Everything else is SOFT: reported, counted, not (yet) failing, because the
backlog is real and a red CI that everyone learns to ignore is worse than a
number that goes down every week.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LIBRARY = os.path.join(DATA, "library.json")
TAXONOMY = os.path.join(DATA, "taxonomy.json")
ALIASES = os.path.join(DATA, "author_aliases.json")
PARAMPARA = os.path.join(ROOT, "pages", "guru-parampara", "data", "parampara.json")
DASA_INDEX = os.path.join(DATA, "DvaitaVedanta/Itara/DasaSahitya", "index.json")
ADMIN_ASHTADHYAYI = os.path.join(ROOT, "admin", "ashtadhyayi.html")

DEVA = re.compile(r"[ऀ-ॿ]")
KANN = re.compile(r"[ಀ-೿]")
ASCII_JUNK_TAIL = re.compile(r"\s[—–-]\s[a-z0-9_]{25,}$")
DANDA = "।"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip()


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def indic(s: str) -> bool:
    return bool(DEVA.search(s or "") or KANN.search(s or ""))


# ---------------------------------------------------------------- checks
def check_titles(lib):
    english, junk, populated_english = [], [], 0
    for g in lib.get("granthas", []):
        t = norm(g.get("title", ""))
        if not indic(t):
            english.append((g["path"], t))
            if g.get("populated"):
                populated_english += 1
        elif ASCII_JUNK_TAIL.search(t):
            junk.append((g["path"], t))
    top = Counter(t for _, t in english).most_common(12)
    return {
        "entries": len(lib.get("granthas", [])),
        "english_only": len(english),
        "english_only_populated": populated_english,
        "top_english": top,
        "junk_tail": junk,
        "english_paths": english,
    }


def walk_data_json():
    """Yield (relpath, payload) for every data.json under data."""
    for dp, dns, fns in os.walk(DATA):
        dns[:] = [d for d in dns if not d.startswith(("_", "."))]
        if "data.json" in fns:
            p = os.path.join(dp, "data.json")
            try:
                yield os.path.relpath(p, ROOT), load(p)
            except (OSError, ValueError):
                continue


def check_authors(aliases):
    alias = {norm(k): v for k, v in aliases.get("aliases", {}).items()}
    persons = aliases.get("persons", {})
    spellings = Counter()
    per_field = defaultdict(Counter)
    empty = 0
    files = 0
    for rel, d in walk_data_json():
        files += 1
        found = False
        for field in ("default_author", "author", "composer"):
            v = d.get(field)
            if isinstance(v, str) and norm(v):
                spellings[norm(v)] += 1
                per_field[field][norm(v)] += 1
                found = True
        if not found:
            empty += 1
    mapped = {s: alias[s] for s in spellings if s in alias}
    unmapped = {s: n for s, n in spellings.items() if s not in alias}
    bad_ids = sorted({v for v in alias.values() if v not in persons})
    by_person = defaultdict(list)
    for s, pid in mapped.items():
        by_person[pid].append((s, spellings[s]))
    # Likely-same-person groups among the unmapped, by a crude Latin key, so a
    # human sees "Sri Vadiraja" / "Vadiraja Tirtha" / "श्रीवादिराजतीर्थः" together.
    def key(s):
        k = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
        k = re.sub(r"\b(sri|shri|shree|maharshi|swami|swamiji|tirtha|teertha|acharya|acarya|dasa|dasaru|bhagavatpada|guru)\b", " ", k)
        return re.sub(r"[^a-z]", "", k)
    groups = defaultdict(list)
    for s, n in unmapped.items():
        k = key(s)
        if k:
            groups[k].append((s, n))
    multi = {k: v for k, v in groups.items() if len(v) > 1}
    return {
        "files": files,
        "files_without_author": empty,
        "distinct_spellings": len(spellings),
        "mapped_spellings": len(mapped),
        "unmapped_spellings": len(unmapped),
        "unmapped_files": sum(unmapped.values()),
        "by_person": {k: sorted(v, key=lambda x: -x[1]) for k, v in by_person.items()},
        "unmapped_top": sorted(unmapped.items(), key=lambda x: -x[1])[:40],
        "likely_groups": sorted(multi.items(), key=lambda kv: -sum(n for _, n in kv[1]))[:25],
        "alias_ids_not_declared": bad_ids,
        "placeholder_spellings": {s: n for s, n in spellings.items() if s.lower() in ("unspecified", "unknown", "n/a", "none", "-", "—")},
    }


def check_taxonomy(tax):
    bad = []

    def walk(node, path):
        if not isinstance(node, dict):
            return
        da = node.get("_default_author")
        # A name never contains a daṇḍa, never ends mid-word in "प्र", and is
        # never URL-encoded. A long English explanation ("Apaurusheya
        # (traditionally unauthored …)") is unusual but is a value someone
        # meant, so length alone is not a fault.
        if isinstance(da, str) and (DANDA in da or "॥" in da or da.rstrip().endswith("प्र") or "%E0%B" in da.upper()):
            bad.append(("/".join(path), da[:90]))
        for k, v in node.items():
            if not k.startswith("_"):
                walk(v, path + [k])

    walk(tax, [])
    return {"corrupt_default_author": bad}


def check_parampara(par, lib):
    titles = {norm(g.get("title", "")).lower() for g in lib.get("granthas", [])}
    nodes = par.get("nodes", [])
    works_total = 0
    unlinked = []
    no_deva = 0
    for n in nodes:
        if not indic(n.get("name", "")):
            no_deva += 1
        for w in n.get("works") or []:
            works_total += 1
            if isinstance(w, str):
                if norm(w).lower() not in titles:
                    unlinked.append((n["id"], w))
    return {"nodes": len(nodes), "names_without_indic_script": no_deva,
            "works": works_total, "works_unlinked": len(unlinked), "unlinked_sample": unlinked[:15]}


def check_dasa(aliases):
    if not os.path.exists(DASA_INDEX):
        return {"skipped": "no DvaitaVedanta/Itara/DasaSahitya/index.json"}
    idx = load(DASA_INDEX)
    alias = {norm(k): v for k, v in aliases.get("aliases", {}).items()}
    comps = idx.get("composers", [])
    kannada = sum(1 for c in comps if KANN.search(c.get("composer", "")))
    unmapped = [c["composer"] for c in comps if norm(c.get("composer", "")) not in alias]
    mismatch = []
    for c in comps:
        f = os.path.join(DATA, "DvaitaVedanta/Itara/DasaSahitya", c.get("file", ""))
        if os.path.exists(f):
            try:
                d = load(f)
            except ValueError:
                mismatch.append((c["slug"], "unreadable file"))
                continue
            if norm(d.get("composer", "")) != norm(c.get("composer", "")):
                mismatch.append((c["slug"], f"index says {c.get('composer')!r}, file says {d.get('composer')!r}"))
        else:
            mismatch.append((c["slug"], "file missing: " + c.get("file", "")))
    return {"composers": len(comps), "kannada_named": kannada, "unmapped_to_person": len(unmapped),
            "unmapped_sample": unmapped[:10], "index_vs_file_mismatch": mismatch}


def check_admin():
    out = {}
    if os.path.exists(ADMIN_ASHTADHYAYI):
        html = open(ADMIN_ASHTADHYAYI, encoding="utf-8").read()
        whos = re.findall(r'who:\s*"([^"]+)"', html)
        out["ashtadhyayi_html_hardcoded_authors"] = whos
    return out


# ---------------------------------------------------------------- report
def report(res):
    L = ["## Names audit", ""]
    t = res["titles"]
    L += [f"**Titles** — {t['entries']} library entries; **{t['english_only']}** have no Devanagari/Kannada "
          f"({t['english_only_populated']} of them reader-visible); {len(t['junk_tail'])} carry a garbage tail.",
          "Most common English-only titles: " + ", ".join(f"`{x}` ×{n}" for x, n in t["top_english"]), ""]
    for p, x in t["junk_tail"][:8]:
        L.append(f"- HARD junk tail: `{p}` → {x[:80]}")
    a = res["authors"]
    L += ["", f"**Authors** — {a['files']} data.json files, {a['files_without_author']} with no author field; "
          f"{a['distinct_spellings']} distinct spellings, **{a['mapped_spellings']} mapped** to a person id, "
          f"**{a['unmapped_spellings']} not yet** (covering {a['unmapped_files']} files)."]
    if a["alias_ids_not_declared"]:
        L.append("- HARD: aliases point at undeclared ids: " + ", ".join(a["alias_ids_not_declared"]))
    for pid, sp in sorted(a["by_person"].items()):
        L.append(f"- `{pid}` ← " + " · ".join(f"{s} ×{n}" for s, n in sp))
    L.append("")
    L.append("Unmapped spellings that look like one person (add to author_aliases.json once certain):")
    for k, sp in a["likely_groups"][:12]:
        L.append(f"- {' · '.join(f'{s} ×{n}' for s, n in sorted(sp, key=lambda x: -x[1]))}")
    L.append("")
    L.append("Most frequent unmapped spellings: " + ", ".join(f"{s} ×{n}" for s, n in a["unmapped_top"][:15]))
    if a["placeholder_spellings"]:
        L.append("Placeholders counted as authors: " + ", ".join(f"`{s}` ×{n}" for s, n in a["placeholder_spellings"].items()))
    x = res["taxonomy"]
    L += ["", f"**Taxonomy** — {len(x['corrupt_default_author'])} `_default_author` values that are not names (HARD):"]
    for p, v in x["corrupt_default_author"]:
        L.append(f"- `{p}`: {v}…")
    p = res["parampara"]
    L += ["", f"**Guru paramparā** — {p['nodes']} nodes, {p['names_without_indic_script']} with a Latin-only name; "
          f"{p['works']} `works` strings, **{p['works_unlinked']} match no library title** (they are free text; the catalogue needs ids)."]
    d = res["dasa"]
    if "skipped" not in d:
        L += ["", f"**Dāsa Sāhitya** — {d['composers']} composers ({d['kannada_named']} named in Kannada); "
              f"**{d['unmapped_to_person']} not mapped** to a person id; {len(d['index_vs_file_mismatch'])} index/file mismatches (HARD)."]
        for s, why in d["index_vs_file_mismatch"][:10]:
            L.append(f"- `{s}`: {why}")
    ad = res["admin"]
    if ad.get("ashtadhyayi_html_hardcoded_authors"):
        L += ["", "**Admin pages** — admin/ashtadhyayi.html hardcodes its own author strings instead of reading a registry: "
              + ", ".join(f"`{w}`" for w in ad["ashtadhyayi_html_hardcoded_authors"])]
    L.append("")
    return "\n".join(L)


def hard_failures(res):
    fails = []
    fails += [f"junk title tail: {p}" for p, _ in res["titles"]["junk_tail"]]
    fails += [f"taxonomy _default_author is not a name: {p}" for p, _ in res["taxonomy"]["corrupt_default_author"]]
    fails += [f"alias → undeclared id: {i}" for i in res["authors"]["alias_ids_not_declared"]]
    fails += [f"dasa index/file mismatch: {s}" for s, _ in res["dasa"].get("index_vs_file_mismatch", [])]
    return fails


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit 1 on HARD findings")
    ap.add_argument("--json", help="also write the full result here")
    args = ap.parse_args()

    lib = load(LIBRARY)
    tax = load(TAXONOMY)
    aliases = load(ALIASES) if os.path.exists(ALIASES) else {"aliases": {}, "persons": {}}
    par = load(PARAMPARA) if os.path.exists(PARAMPARA) else {"nodes": []}
    res = {
        "titles": check_titles(lib),
        "authors": check_authors(aliases),
        "taxonomy": check_taxonomy(tax),
        "parampara": check_parampara(par, lib),
        "dasa": check_dasa(aliases),
        "admin": check_admin(),
    }
    print(report(res))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report(res) + "\n")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
    fails = hard_failures(res)
    if fails:
        print(f"{len(fails)} HARD finding(s):")
        for f in fails[:20]:
            print(" -", f)
    return 1 if (args.strict and fails) else 0


if __name__ == "__main__":
    sys.exit(main())
