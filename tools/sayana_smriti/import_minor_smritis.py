#!/usr/bin/env python3
"""
import_minor_smritis.py — the last empty shelf in DGE's Dharmaśāstra section.

WHAT IS MISSING
    Fourteen smṛti folders and all seven dharmaśāstra nibandha folders contain
    zero items. Not thin — empty:

        aṅgiras · atri · dakṣa · hārīta · likhita · pracetas · saṃvarta
        śaṅkha · śātātapa · uśanas · yama · āpastamba · gautama · bṛhaspati
        mitākṣarā · dāyabhāga · dharmasindhu · nirṇayasindhu
        smṛticandrikā · kalpataru · caturvargacintāmaṇi

    The earlier source survey found no clean e-text for the eleven minor
    smṛtis anywhere — archive.org scans only, and Devanagari OCR from those is
    not good enough to ingest unreviewed.

THE ONE REMAINING LEAD, AND WHY THIS SCRIPT IS SHAPED THE WAY IT IS
    sa.wikisource.org. It is CC BY-SA, it has a clean API, and a category
    `वर्गः:स्मृतयः` ("Smṛtis") is confirmed to exist. What is NOT confirmed is
    which of these twenty-one works it actually holds — Wikimedia domains are
    cache-only from the authoring sandbox, so I could not look.

    So the script leads with `--probe-only`: a two-minute run that enumerates
    the category, probes each expected title and its spelling variants, runs a
    full-text search for the stragglers, and prints a table of what exists and
    how big it is. Nothing is written. Decide from that table whether a full
    run is worth it.

    This is deliberate. An importer that silently writes nothing when a source
    turns out to be empty is indistinguishable from one that is broken.

USAGE
    python import_minor_smritis.py --probe-only                    # look first
    python import_minor_smritis.py --dge-root ../bhumandala/dge    # then write
    python import_minor_smritis.py --dge-root ../bhumandala/dge --only yama_smriti

LICENCE
    sa.wikisource text is CC BY-SA 4.0. Attribution is written into each file's
    `commentary_sources` block, and the licence is recorded per grantha. This is
    share-alike, not public domain — DGE is non-commercial and attributes, which
    satisfies it, but the obligation is real and is recorded rather than assumed.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections import Counter
from pathlib import Path

from common import Fetcher, clean, load_json, save_json
from import_smriti import merge_into_existing
from parsers import wikisource as wk

LANG = "sa"
CATEGORY = "वर्गः:स्मृतयः"

# slug -> (English label, default author, [title variants to probe])
# Variants matter: Wikisource titling is inconsistent about visarga-compounds
# (अङ्गिरःस्मृतिः vs अङ्गिरस्स्मृतिः vs अङ्गिरसस्मृतिः) and about whether the
# work is filed under its own name or as a subpage of a collection.
TARGETS = {
    "angiras_smriti":   ("Aṅgiras Smṛti", "Aṅgiras",
                         ["अङ्गिरःस्मृतिः", "अङ्गिरस्स्मृतिः", "अङ्गिरसस्मृतिः", "आङ्गिरसस्मृतिः"]),
    "atri_smriti":      ("Atri Smṛti", "Atri",
                         ["अत्रिस्मृतिः", "आत्रेयस्मृतिः", "अत्रिसंहिता"]),
    "daksha_smriti":    ("Dakṣa Smṛti", "Dakṣa", ["दक्षस्मृतिः", "दाक्षस्मृतिः"]),
    "harita_smriti":    ("Hārīta Smṛti", "Hārīta", ["हारीतस्मृतिः", "हारितस्मृतिः"]),
    "likhita_smriti":   ("Likhita Smṛti", "Likhita", ["लिखितस्मृतिः"]),
    "pracetas_smriti":  ("Pracetas Smṛti", "Pracetas",
                         ["प्रचेतःस्मृतिः", "प्रचेतस्स्मृतिः", "प्राचेतसस्मृतिः"]),
    "samvarta_smriti":  ("Saṃvarta Smṛti", "Saṃvarta", ["संवर्तस्मृतिः", "सांवर्तस्मृतिः"]),
    "shankha_smriti":   ("Śaṅkha Smṛti", "Śaṅkha", ["शङ्खस्मृतिः", "शङ्खलिखितस्मृतिः"]),
    "shatatapa_smriti": ("Śātātapa Smṛti", "Śātātapa", ["शातातपस्मृतिः", "शतातपस्मृतिः"]),
    "ushanas_smriti":   ("Uśanas Smṛti", "Uśanas",
                         ["उशनःस्मृतिः", "उशनस्स्मृतिः", "औशनसस्मृतिः"]),
    "yama_smriti":      ("Yama Smṛti", "Yama", ["यमस्मृतिः", "याम्यस्मृतिः"]),
    # Larger smṛtis whose DGE folders are also empty
    "apastamba_smriti": ("Āpastamba Smṛti", "Āpastamba",
                         ["आपस्तम्बस्मृतिः", "आपस्तम्बधर्मसूत्रम्"]),
    "gautama_smriti":   ("Gautama Smṛti", "Gautama",
                         ["गौतमस्मृतिः", "गौतमधर्मसूत्रम्"]),
    "brihaspati_smriti": ("Bṛhaspati Smṛti", "Bṛhaspati", ["बृहस्पतिस्मृतिः"]),
}

# The nibandhas. Vīramitrodaya is on sa.wikisource — a search turned up
# 'वीरमित्रोदयः - श्राद्धप्रकाशः' — which is worth knowing, because the earlier
# survey had written the Sanskrit Vīramitrodaya off as scan-only.
NIBANDHAS = {
    "mitakshara":            ("Mitākṣarā", "Vijñāneśvara", ["मिताक्षरा", "मिताक्षरः"]),
    "dayabhaga":             ("Dāyabhāga", "Jīmūtavāhana", ["दायभागः", "दायभाग"]),
    "dharma_sindhu":         ("Dharmasindhu", "Kāśīnātha Upādhyāya", ["धर्मसिन्धुः"]),
    "nirnaya_sindhu":        ("Nirṇayasindhu", "Kamalākara Bhaṭṭa", ["निर्णयसिन्धुः"]),
    "smriti_chandrika":      ("Smṛticandrikā", "Devaṇabhaṭṭa", ["स्मृतिचन्द्रिका"]),
    "kalpataru":             ("Kṛtyakalpataru", "Lakṣmīdhara", ["कृत्यकल्पतरुः", "कल्पतरुः"]),
    "chaturvarga_chintamani": ("Caturvargacintāmaṇi", "Hemādri", ["चतुर्वर्गचिन्तामणिः"]),
    "viramitrodaya":         ("Vīramitrodaya", "Mitramiśra",
                              ["वीरमित्रोदयः", "वीरमित्रोदयः - श्राद्धप्रकाशः"]),
}

LICENCE = {
    "source": "sa.wikisource.org",
    "licence": "CC BY-SA 4.0 — share-alike. Attribution to Sanskrit Wikisource "
               "and its contributors must be kept visible, and any redistribution "
               "carries the same licence.",
    "language": "sa",
}

SMRITI_DIR = "data/smriti_dharma/smriti"
NIBANDHA_DIR = "data/smriti_dharma/dharmashastra"


def fetch_json(f: Fetcher, url: str):
    body = f.get(url, allow_missing=True)
    return body or ""


def enumerate_category(f: Fetcher) -> list:
    """Walk `वर्गः:स्मृतयः`, following subcategories one level deep."""
    seen, out, queue = set(), [], [CATEGORY]
    while queue:
        cat = queue.pop(0)
        if cat in seen:
            continue
        seen.add(cat)
        cont = ""
        while True:
            rows, cont = wk.category_members(
                fetch_json(f, wk.category_url(cat, lang=LANG, cmcontinue=cont)))
            for r in rows:
                if r["ns"] == 14:                       # a subcategory
                    if r["title"] not in seen:
                        queue.append(r["title"])
                else:
                    out.append(r["title"])
            if not cont:
                break
    return out


# Below this similarity a search hit is a coincidence, not the work we're
# looking for. Two distinct failure modes this guards against, both seen on
# real sa.wikisource results for these titles:
#  - a short shared prefix: "चतुर" ("catur-", four-) between
#    "चतुर्वर्गचिन्तामणिः" (Caturvargacintāmaṇi) and an unrelated dictionary
#    entry "चतुर्भाव" is not evidence they're the same text.
#  - an identically-named subsection of an unrelated work: "दायभागः"
#    ("division of inheritance") is both Jīmūtavāhana's independent nibandha
#    and the name of a traditional vyavahāra-pada, so it also appears as
#    "नारदस्मृतिः/व्यवहारपदानि/दायभागः" — a chapter *of Nārada Smṛti*, not the
#    nibandha. Comparing against the candidate's full title (not just its
#    last path segment) keeps that long, unrelated prefix in the score.
SEARCH_MATCH_THRESHOLD = 0.75


def _title_similarity(variant: str, candidate: str) -> float:
    return difflib.SequenceMatcher(None, variant, candidate).ratio()


def find_title(f: Fetcher, variants, category_titles, label) -> tuple:
    """-> (title, how_found) or (None, reason). Cheapest probe first."""
    norm = {t.replace("‍", "").strip(): t for t in category_titles}
    for v in variants:
        if v in norm:
            return norm[v], "category"
    for v in variants:
        if wk.html_from_parse(fetch_json(f, wk.parse_url(v, lang=LANG))):
            return v, "direct"
    # Last resort: full-text search on the first variant's stem, scored by
    # similarity to the full variant spelling rather than a short prefix —
    # a handful of Devanagari codepoints is not a distinctive enough prefix
    # to identify a work (many titles share a common first word).
    stem = variants[0].rstrip("ः").rstrip("्")
    best_ratio, best_title = 0.0, None
    for r in wk.search_results(fetch_json(f, wk.search_url(stem, lang=LANG))):
        ratio = max(_title_similarity(v, r["title"]) for v in variants)
        if ratio > best_ratio:
            best_ratio, best_title = ratio, r["title"]
    if best_ratio >= SEARCH_MATCH_THRESHOLD:
        return best_title, "search"
    return None, "not found"


def collect_pages(f: Fetcher, title: str) -> list:
    """A work may be one page or split into subpages ('यमस्मृतिः/अध्यायः १')."""
    pages = [title]
    subs = wk.all_pages(fetch_json(f, wk.prefix_url(title + "/", lang=LANG)))
    pages.extend(sorted(subs))
    return pages


def build_grantha(f: Fetcher, title: str, label: str, author: str, schema: str):
    """-> (data dict, stats)"""
    stats = Counter()
    items, chapter = [], 0
    for page in collect_pages(f, title):
        html = wk.html_from_parse(fetch_json(f, wk.parse_url(page, lang=LANG)))
        stats["pages"] += 1
        if not html:
            stats["pages_missing"] += 1
            continue
        verses = wk.parse_devanagari_verses(wk.page_body_text(html))
        if not verses:
            stats["pages_no_verses"] += 1
            continue
        chapter += 1
        items.append({
            "id": f"adhyaya_{chapter:02d}",
            "reference": f"{label}" + (f", {page.split('/', 1)[1]}" if "/" in page else ""),
            "shlokas": [{"number": v["number"], "sanskrit_text": v["text"]} for v in verses],
            "notes": f"Source: sa.wikisource.org/wiki/{page}",
        })
        stats["verses"] += len(verses)
    data = {
        "schema": schema,
        "default_author": author,
        "commentary_sources": {"sa_wikisource": dict(
            LICENCE, work=label, url=f"https://sa.wikisource.org/wiki/{title}")},
        "items": items,
    }
    return data, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dge-root", help="required unless --probe-only")
    ap.add_argument("--probe-only", action="store_true",
                    help="report what sa.wikisource actually has; write nothing")
    ap.add_argument("--only", action="append", help="slug filter (repeatable)")
    ap.add_argument("--include-nibandhas", action="store_true", default=True)
    ap.add_argument("--out-dir", default="dump")
    ap.add_argument("--cache-dir", default=".httpcache")
    ap.add_argument("--delay", type=float, default=0.8)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if not args.probe_only and not args.dge_root:
        print("!! --dge-root is required unless --probe-only", file=sys.stderr)
        return 2

    f = Fetcher(cache_dir=args.cache_dir, delay=args.delay, offline=args.offline)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Enumerating {CATEGORY} on {LANG}.wikisource.org …")
    cat_titles = enumerate_category(f)
    print(f"  {len(cat_titles)} pages in the category tree")

    plan = [(slug, *meta, SMRITI_DIR, "smriti_dharmashastra_text")
            for slug, meta in TARGETS.items()]
    if args.include_nibandhas:
        plan += [(slug, *meta, NIBANDHA_DIR, "generic")
                 for slug, meta in NIBANDHAS.items()]
    if args.only:
        plan = [p for p in plan if any(o in p[0] for o in args.only)]

    found, report = [], []
    print(f"\n{'slug':26} {'title on wikisource':34} {'how':9}")
    print("-" * 74)
    for slug, label, author, variants, folder, schema in plan:
        title, how = find_title(f, variants, cat_titles, label)
        report.append({"slug": slug, "label": label, "title": title, "how": how})
        print(f"{slug:26} {(title or '—'):34} {how:9}")
        if title:
            found.append((slug, label, author, title, folder, schema))

    print(f"\n{len(found)}/{len(plan)} works located on sa.wikisource.")
    if args.probe_only:
        save_json(out / "PROBE_minor_smritis.json",
                  {"category": CATEGORY, "category_pages": len(cat_titles),
                   "results": report}, indent=2)
        print(f"probe written to {out / 'PROBE_minor_smritis.json'} — nothing else touched.")
        return 0

    dge = Path(args.dge_root)
    totals = Counter()
    for slug, label, author, title, folder, schema in found:
        print(f"\n== {label}  ({title})")
        data, stats = build_grantha(f, title, label, author, schema)
        n = sum(len(i["shlokas"]) for i in data["items"])
        print(f"   {len(data['items'])} section(s), {n} verses "
              f"[{dict(stats)}]")
        totals["works"] += 1
        totals["verses"] += n
        save_json(out / f"minor__{slug}.json", data)
        if not n:
            print("   -- nothing parsed; not writing")
            continue

        target = dge / folder / slug / "data.json"
        existing = load_json(target) if target.exists() else None
        if existing is not None:
            merged, mstats = merge_into_existing(existing, data)
            before = sum(len(i.get("shlokas", [])) for i in existing.get("items", []))
            after = sum(len(i.get("shlokas", [])) for i in merged.get("items", []))
            if after < before:
                print(f"   !! refusing to write: {before} -> {after}", file=sys.stderr)
                continue
            if not args.dry_run:
                save_json(target, merged)
                print(f"   -> wrote {target} ({before} -> {after} verses)")
        elif not args.dry_run:
            save_json(target, data)
            print(f"   -> created {target}")

    save_json(out / "COUNTS_minor_smritis.json",
              {"located": report, "totals": dict(totals), "http": f.stats}, indent=2)
    print(f"\n{totals['works']} works, {totals['verses']:,} verses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
