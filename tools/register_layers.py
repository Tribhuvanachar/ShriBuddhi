#!/usr/bin/env python3
"""Idempotently register every dge/data/**/data.json in library.json's granthas[].

The reader (core.js) only fetches content that has an entry in library.json, and
gen_library_status.py only counts taxonomy leaves that resolve to such an entry.
New importer output (a fresh layer folder like <kanda>/saartha, the bhagavad_gita
section, or darshana/vedanta/advaita/shankara_bhashya/**) therefore stays invisible until it is listed
here. This tool scans the data tree and appends any data.json that is missing,
with populated = (it has content). Safe to run repeatedly; run AFTER an importer.
"""
import json, os, glob, datetime

ROOT = 'dge' if os.path.isdir('dge/data') else '.'
DATA = os.path.join(ROOT, 'data')
LIB = os.path.join(DATA, 'library.json')

# data.json files that are real, but are internal lookup tables rather than
# browsable grantha content (not {items:[...]} shloka/verse text at all --
# kaumudi_order/data.json is a kaumudiIndex<->sutra id concordance
# ashtadhyayi.js reads directly). Registering one of these makes it a
# clickable Library entry that renders garbage in the generic reader, which
# only ever expects the shloka-corpus shape. Caught once by hand (20 Aug
# 2026) when this tool picked it up unprompted; listed here so it isn't
# re-flagged as "new" on every future run.
NOT_A_GRANTHA = {
    'dge/data/vedanga/vyakarana/ashtadhyayi/kaumudi_order/data.json',
}


def item_count(data):
    items = data.get('items', [])
    if items and isinstance(items[0], dict) and isinstance(items[0].get('shlokas'), list):
        return sum(len(it.get('shlokas', [])) for it in items)
    return len(items)


# View-By facet metadata (see dge/PENDING.md's 25 Aug Pancharatra pass) --
# kept in sync with tools/audit_library.py's own derive_facets(); copied into
# library.json so the reader can build facet groupings without downloading
# every leaf's full data.json just to read a handful of classification
# fields. None -> no 'facets' key at all.
FACET_KEYS = ('genre', 'guna_classification', 'ratnatraya', 'madhvacharya_relevance', 'text_status',
              'purana_class', 'traditional_lists')


def facets_of(data):
    facets = {k: data[k] for k in FACET_KEYS if k in data}
    return facets or None


# Lightweight provenance for the admin tracker's "sources" column -- kept in
# sync with tools/audit_library.py's own derive_source().
def source_of(data):
    source = {}
    for key in ('source', 'source_url', 'licence', 'license'):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            source['licence' if key == 'license' else key] = value.strip()
    return source or None


def main():
    lib = json.load(open(LIB, encoding='utf-8'))
    granthas = lib.setdefault('granthas', [])
    known = {g['path'] for g in granthas}
    added = 0
    # Stamped only on genuinely new entries below, never backfilled onto
    # existing ones -- this repo's git history is a shallow clone (a few
    # days deep) so there is no reliable way to know when an EXISTING
    # grantha was really added, and guessing "today" for all of them would
    # make the whole corpus look simultaneously brand-new the first time
    # this tool runs after this change. library.js's "New" badge (Category
    # 1) is correspondingly honest: entries with no addedAt just show no
    # badge rather than a wrong one.
    today = datetime.date.today().isoformat()
    for fp in sorted(glob.glob(os.path.join(DATA, '**', 'data.json'), recursive=True)):
        # catalog path convention is always "dge/data/.../data.json"
        rel = os.path.relpath(fp, DATA).replace(os.sep, '/')
        catalog = f"dge/data/{rel}"
        if catalog in known or catalog in NOT_A_GRANTHA:
            continue
        try:
            data = json.load(open(fp, encoding='utf-8'))
            n = item_count(data)
            facets = facets_of(data)
            source = source_of(data)
        except Exception:
            n = 0
            facets = None
            source = None
        entry = {"path": catalog, "populated": n > 0, "title": None, "addedAt": today}
        if facets:
            entry["facets"] = facets
        if source:
            entry["source"] = source
        granthas.append(entry)
        known.add(catalog)
        added += 1
        print(f"  + {catalog} (populated={n > 0})")
    if added:
        # library.json's own convention is 2-space indent -- writing with
        # anything else (the original indent=1 here) reformats every line
        # of the file for a one-entry addition, drowning the real change in
        # thousands of unrelated whitespace-only diff lines.
        json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        open(LIB, 'a', encoding='utf-8').write('\n')
    print(f"register_layers: added {added} new grantha entries")


if __name__ == '__main__':
    main()
